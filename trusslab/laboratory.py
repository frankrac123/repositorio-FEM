"""Reproducible campaigns. Search budgets and external validation are separate."""
from contextlib import ExitStack
from dataclasses import dataclass,field,asdict
from pathlib import Path
from datetime import datetime,timezone
import copy,csv,json,os,platform,shutil,time,uuid,hashlib
import numpy as np
import scipy
from . import __version__
from .core import Model,save_project
from .asam import ASAMOptions
from .lab_evaluation import EvaluationSession
from .lab_search import METHODS,search
from .optimization import RunControl,Cancelled


@dataclass
class CampaignConfig:
    algorithms:list=field(default_factory=lambda:['ASAM','DE','SLSQP'])
    seeds:list=field(default_factory=lambda:[42,7,17,101,202])
    budget:int=2000
    engine:str='FEM'
    parameters:dict=field(default_factory=lambda:{'asam':asdict(ASAMOptions()),'iterations':10000,'slsqp_starts':5,
        'slsqp_ftol':1e-10,'de_mutation':[.5,1.],'de_recombination':.7,'de_tolerance':1e-6,
        'asam_constraint_policy':'feasible_first','penalty_coefficient':100.,'global_fraction':.7})
    sap_validation:str='best_per_method'
    active_ids:list|None=None
    groups:list|None=None

    def validate(self):
        if not self.algorithms or len(set(self.algorithms))!=len(self.algorithms) or not set(self.algorithms)<=set(METHODS):raise ValueError('Algoritmos de campaña inválidos.')
        if not self.seeds or len(set(self.seeds))!=len(self.seeds) or any(not isinstance(s,int) or not 0<=s<2**32 for s in self.seeds):raise ValueError('Las semillas deben ser enteras, distintas y no negativas.')
        if self.engine not in ('FEM','SAP','HYBRID') or self.sap_validation not in ('none','best_per_method','all_feasible'):raise ValueError('Motor o validación de campaña inválidos.')
        options=ASAMOptions(**self.parameters.get('asam',{}));options.validate()
        if options.initial_points<5:raise ValueError('Se necesitan al menos cinco candidatos comunes para DE.')
        cost=2 if self.engine=='SAP' else 1
        if self.budget<(options.initial_points+3)*cost:raise ValueError('El presupuesto debe superar la exploración común.')
        if self.parameters.get('iterations',10000)<1 or self.parameters.get('slsqp_starts',5)<1:raise ValueError('Conteos de búsqueda inválidos.')
        if not 0<self.parameters.get('global_fraction',.7)<1:raise ValueError('Fracción global inválida.')
        if any('+' in m for m in self.algorithms) and int((self.budget-1)*self.parameters.get('global_fraction',.7))<(options.initial_points+2)*cost:raise ValueError('El presupuesto global del híbrido es insuficiente.')


def statistics(runs,algorithms):
    out=[]
    for method in algorithms:
        records=[r for r in runs if r['algorithm']==method]
        complete=[r for r in records if r['status']!='cancelled']
        valid=[r for r in complete if r['status']=='feasible']
        values=[r['result']['weight_lb'] for r in valid]
        out.append({'algorithm':method,'n_observed':len(records),'n_completed':len(complete),'n_valid':len(valid),
            'n_failed_runs':sum(r['status']=='failed' for r in complete),'n_cancelled':len(records)-len(complete),
            'best_lb':min(values) if values else None,'worst_lb':max(values) if values else None,
            'mean_lb':float(np.mean(values)) if values else None,'median_lb':float(np.median(values)) if values else None,
            'sample_std_lb':float(np.std(values,ddof=1)) if len(values)>1 else None,
            'feasibility_rate':len(valid)/len(complete) if complete else None,
            'mean_seconds':float(np.mean([r['metrics']['elapsed_seconds'] for r in complete])) if complete else None,
            'mean_evaluations_to_best':float(np.mean([r['metrics']['best_evaluation'] for r in valid])) if valid else None,
            'failed_analyses':sum(r['metrics']['failed_analyses'] for r in complete),
            'limited_sample':len(valid)<20})
    return out


def save_campaign(campaign,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    data={k:v for k,v in campaign.items() if not k.startswith('_')}
    temporary=directory/'campaign.json.tmp';temporary.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    os.replace(temporary,directory/'campaign.json')
    if campaign['runs']:
        columns=['algorithm','seed','status','weight_lb','evaluations','cache_hits','requests','elapsed_seconds','best_evaluation','external_validation']
        with (directory/'runs.csv').open('w',newline='',encoding='utf-8-sig') as stream:
            writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
            for r in campaign['runs']:
                writer.writerow({'algorithm':r['algorithm'],'seed':r['seed'],'status':r['status'],
                    'weight_lb':r.get('result',{}).get('weight_lb'),**{k:r['metrics'].get(k) for k in columns if k in r['metrics']},
                    'external_validation':r.get('sap_validation',{}).get('status','pending')})
        rows=campaign['statistics']
        with (directory/'statistics.csv').open('w',newline='',encoding='utf-8-sig') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def load_campaign(path):
    path=Path(path);path=path/'campaign.json' if path.is_dir() else path
    c=json.loads(path.read_text(encoding='utf-8-sig'))
    if c.get('schema')!='trusslab.campaign/1':raise ValueError('Esquema de campaña desconocido.')
    model=Model.from_dict(c['model'])
    if model.fingerprint()!=c['model_fingerprint']:raise ValueError('La huella del modelo no corresponde a la campaña.')
    if c.get('configuration_sha256') and hashlib.sha256(json.dumps(c['configuration'],sort_keys=True,allow_nan=False).encode()).hexdigest()!=c['configuration_sha256']:
        raise ValueError('La configuración guardada fue modificada después de ejecutar la campaña.')
    CampaignConfig(**c['configuration']).validate();c['_directory']=str(path.parent.resolve())
    return c


def run_campaign(model,config,output_root,*,control=None,progress=None,batch_factory=None):
    config=copy.deepcopy(config);config.validate();model=model.clone();model.validate();control=control or RunControl()
    root=Path(output_root)/('campaign_'+datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:6]);root.mkdir(parents=True)
    campaign={'schema':'trusslab.campaign/1','created_utc':datetime.now(timezone.utc).isoformat(),'model':model.to_dict(),
        'model_fingerprint':model.fingerprint(),'configuration':asdict(config),'software':{'trusslab':__version__,
            'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'platform':platform.platform()},
        'runs':[],'statistics':[],'status':'running','validation_cost':{'sap_analyses':0,'independent_fem_audits':0},'_directory':str(root.resolve())}
    campaign['configuration_sha256']=hashlib.sha256(json.dumps(campaign['configuration'],sort_keys=True,allow_nan=False).encode()).hexdigest()
    source=hashlib.sha256()
    for file in sorted(Path(__file__).parent.glob('*.py')):source.update(file.name.encode());source.update(file.read_bytes().replace(b'\r\n',b'\n'))
    campaign['software']['source_sha256']=source.hexdigest()
    save_campaign(campaign,root);started=time.perf_counter()
    with ExitStack() as stack:
        session=None
        if config.engine=='SAP':
            from .sap import SapBatchSession
            session=stack.enter_context((batch_factory or SapBatchSession)(root/'sap_search'))
        try:
            for seed in config.seeds:
                for method in config.algorithms:
                    control.checkpoint();run_id=f'{len(campaign["runs"]):03d}_{method.replace("+","_")}_seed{seed}'
                    folder=root/'runs'/run_id
                    def notify(item):
                        if progress:progress({'algorithm':method,'seed':seed,'run_id':run_id,'completed_runs':len(campaign['runs']),
                            'total_runs':len(config.seeds)*len(config.algorithms),'campaign_directory':str(root.resolve()),'type':'evaluation',**item})
                    ev=EvaluationSession(model,config.budget,folder/'evaluations.jsonl.gz',control,notify,session,config.active_ids,config.groups)
                    record={'id':run_id,'algorithm':method,'seed':seed,'trace':str((folder/'evaluations.jsonl.gz').relative_to(root)).replace('\\','/'),
                            'sap_validation':{'status':'pending'}}
                    try:
                        info=search(ev,method,seed,config.parameters)
                        record['search']=info
                        record['status']='cancelled' if info['message']=='cancelled' else ('feasible' if ev.best else ('failed' if ev.failures==len(ev.history) else 'infeasible'))
                        if ev.best:
                            x,result=ev.best;winner=ev.space.expand(x);result=copy.deepcopy(result)
                            result['model_fingerprint']=winner.fingerprint()
                            result['optimization']={'method':method,'seed':seed,'initial_weight_lb':model.weight(),
                                'global_optimum_proven':False,**info,**ev.metrics()}
                            record.update(variables_in2=x.tolist(),areas_in2=[m.area for m in winner.members],result=result,
                                max_abs_stress_ksi=max(abs(m['stress']) for case_result in (result.get('case_results') or {'active':result}).values() for m in case_result['members']),
                                max_displacement_components_in=np.max(np.abs([u for case_result in (result.get('case_results') or {'active':result}).values() for u in case_result['displacements'].values()]),axis=0).tolist())
                            active=[]
                            for b in winner.members:
                                if abs(b.area-winner.area_min)/winner.area_min<=1e-4:active.append(f'Área mínima B{b.id}')
                                if abs(b.area-winner.area_max)/winner.area_max<=1e-4:active.append(f'Área máxima B{b.id}')
                            for case,case_result in (result.get('case_results') or {result.get('analysis_case',winner.active_case):result}).items():
                                for v in case_result['members']:
                                    if v['ratio']>=1-1e-4:active.append(f'Esfuerzo B{v["id"]} · {case}')
                                for n in winner.nodes:
                                    for d,axis in enumerate('XYZ'):
                                        if not winner.restraints(n)[d] and abs(case_result['displacements'][str(n.id)][d])/winner.displacement_limit>=1-1e-4:active.append(f'Desplazamiento N{n.id} {axis} · {case}')
                            record['active_constraints']=active;record['active_constraint_relative_tolerance']=1e-4
                            save_project(folder/'best.trusslab.json',winner,result)
                            record['best_project']=(folder/'best.trusslab.json').relative_to(root).as_posix()
                    except Cancelled:record.update(status='cancelled',search={'message':'cancelled'})
                    except Exception as exc:record.update(status='failed',error=str(exc),search={'message':'analysis_or_algorithm_error'})
                    finally:ev.close();record['metrics']=ev.metrics()
                    campaign['runs'].append(record);campaign['statistics']=statistics(campaign['runs'],config.algorithms)
                    save_campaign(campaign,root)
                    if progress:progress({'type':'run_completed','run':record,'completed_runs':len(campaign['runs']),'total_runs':len(config.seeds)*len(config.algorithms)})
                    if record['status']=='cancelled':raise Cancelled()
                    if record['status']=='failed' and config.engine=='SAP':raise RuntimeError(record['error'])
            campaign['status']='completed'
        except Cancelled:campaign['status']='cancelled'
        except Exception as exc:campaign.update(status='failed',error=str(exc))
    campaign['elapsed_seconds']=time.perf_counter()-started;save_campaign(campaign,root)
    mode=config.sap_validation if config.engine!='HYBRID' or config.sap_validation!='none' else 'best_per_method'
    if campaign['status']=='completed' and mode!='none':validate_campaign(campaign,root,mode,control=control,progress=progress,batch_factory=batch_factory)
    return campaign


def winner_model(campaign,record):
    model=Model.from_dict(campaign['model'])
    for m,a in zip(model.members,record['areas_in2']):m.area=a
    model.validate();return model


def validate_campaign(campaign,directory,mode='best_per_method',*,control=None,progress=None,batch_factory=None):
    from .sap import SapBatchSession
    control=control or RunControl();directory=Path(directory)
    candidates=[r for r in campaign['runs'] if r['status']=='feasible']
    if mode=='best_per_method':
        candidates=[min([r for r in candidates if r['algorithm']==method],key=lambda r:r['result']['weight_lb'])
                    for method in campaign['configuration']['algorithms'] if any(r['algorithm']==method for r in candidates)]
    if mode not in ('best_per_method','all_feasible'):raise ValueError('Modo de validación externo inválido.')
    if not candidates:return campaign
    try:
        with (batch_factory or SapBatchSession)(directory/'sap_validation') as batch:
            for record in candidates:
                control.checkpoint()
                if progress:progress({'type':'sap_validation','message':'SAP2000: '+record['id']})
                model=winner_model(campaign,record);result=batch.evaluate(model)
                if not result.get('engine','').startswith('SAP2000') or result.get('model_fingerprint')!=model.fingerprint() or result.get('analysis_case_status',{}).get(result.get('sap_analysis_case',next(iter(result.get('analysis_case_status',{})),'')))!=4:
                    raise RuntimeError('El validador no devolvió un análisis SAP terminado para el candidato seleccionado.')
                campaign['validation_cost']['sap_analyses']+=1;campaign['validation_cost']['independent_fem_audits']+=1
                target=directory/'validated'/record['id'];target.mkdir(parents=True,exist_ok=True)
                source=Path(result['sap_model']);shutil.copy2(source,target/'design.sdb')
                result['source_sap_model']=result['sap_model'];result['sap_model']=str(target/'design.sdb')
                save_project(target/'validated.trusslab.json',model,result)
                accepted=bool(result['validation']['passed'] and result['validation']['design_feasible'] and result['feasible'])
                record['sap_validation']={'status':'verified' if accepted else 'discrepancy',
                    'result_project':(target/'validated.trusslab.json').relative_to(directory).as_posix(),
                    'sdb':(target/'design.sdb').relative_to(directory).as_posix(),'comparison':result['validation']['comparison'],
                    'constraints':result['validation']['constraints'],'model_fingerprint':model.fingerprint()}
                save_campaign(campaign,directory)
    except Cancelled:campaign['validation_interrupted']=True
    except Exception as exc:
        campaign['validation_error']=str(exc)
        for record in candidates:
            if record['sap_validation']['status']=='pending':record['sap_validation']['error']=str(exc)
    save_campaign(campaign,directory);return campaign
