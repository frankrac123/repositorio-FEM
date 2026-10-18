"""Explicit reproducible audit. SAP is opt-in and owns only its test instances."""
import argparse,json,platform,sys,time,csv,hashlib,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from trusslab.core import load_project,save_project,Material
from trusslab.examples import triangle,spatial
from trusslab.analysis import solve_design,constraint_margins
from trusslab.fem import solve
from trusslab.validation import write_comparison_csv
from trusslab.laboratory import CampaignConfig,run_campaign
from trusslab.asam import ASAMOptions
from dataclasses import asdict

def main():
    p=argparse.ArgumentParser();p.add_argument('--sap',action='store_true');p.add_argument('--algorithms',action='store_true');p.add_argument('--output',default='data/audit/experiments');args=p.parse_args()
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True);started=time.perf_counter()
    report={'python':sys.version,'platform':platform.platform(),'sap_requested':args.sap,'models':[],'algorithm_checks':[]}
    a=load_project(Path(__file__).resolve().parents[1]/'examples/Caso_I_calculado.trusslab.json')[0]
    b=triangle();c=spatial()
    # Different from the archived modeler examples: geometry, density, material IDs and cases.
    b.node(2).xyz[0]=140.;b.node(3).xyz=[55.,0.,95.]
    b.materials.append(Material('legacy','Explicit identifier collision regression',18000.,.18))
    b.members[0].material_id=None;b.members[1].material_id='legacy'
    c.node(4).xyz=[37.,43.,112.];c.materials[1].density=.22
    for model in (b,c):model.optimization_config['load_cases']=['C1','C2','ULS']
    for label,m in [('A_case_i',a),('B_D_E_planar',b),('C_D_E_spatial',c)]:
        print('STRUCTURAL',label,flush=True);r=solve_design(m)
        save_project(root/(label+'.trusslab.json'),m,r)
        entry={'label':label,'model':m.to_dict(),'fem':r}
        if args.sap:
            from trusslab.sap import analyze
            external=analyze(m,root/label,progress=lambda text:print(text,flush=True))
            assert external['validation']['passed'],external['validation']
            entry['sap']=external
            save_project(root/(label+'_sap.trusslab.json'),m,external)
            for case,case_result in (external.get('case_results') or {external['analysis_case']:external}).items():
                comparison=case_result['validation']['comparison']
                write_comparison_csv(root/(label+'_'+case+'_comparison.csv'),comparison)
        report['models'].append(entry)
        (root/'verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    if args.algorithms:
        for label,m in [('planar',b),('spatial',c)]:
            config=CampaignConfig(algorithms=['ASAM','DE','SLSQP','ASAM+SLSQP','DE+SLSQP'],seeds=[42,17],budget=240,sap_validation='none')
            config.parameters['asam']=asdict(ASAMOptions(initial_points=20,proposals_per_temperature=10))
            print('ALGORITHMS',label,flush=True)
            first=run_campaign(m,config,root/label);again=run_campaign(m,config,root/label)
            assert [r.get('areas_in2') for r in first['runs']]==[r.get('areas_in2') for r in again['runs']]
            for run in first['runs']:
                assert run['metrics']['evaluations']<=config.budget
                assert run['status'] in ('feasible','infeasible'),run
                if run['status']=='feasible':
                    candidate=m.clone()
                    for bar,area in zip(candidate.members,run['areas_in2']):bar.area=area
                    actual=solve_design(candidate)
                    assert min(constraint_margins(candidate,actual))>=-1e-6
                    assert all(m.area_min<=area<=m.area_max for area in run['areas_in2'])
            report['algorithm_checks'].append({'model':label,'reproduced':True,'runs':[{'algorithm':r['algorithm'],'seed':r['seed'],'status':r['status'],'weight_lb':r.get('result',{}).get('weight_lb'),'strict_feasible':r.get('result',{}).get('strict_feasible'),'evaluations':r['metrics']['evaluations']} for r in first['runs']],'campaign':first['_directory'],'repeat':again['_directory']})
            if args.sap:
                from trusslab.sap import SapBatchSession
                best=min((r for r in first['runs'] if r['status']=='feasible'),key=lambda r:r['result']['weight_lb'])
                winner=m.clone()
                for bar,area in zip(winner.members,best['areas_in2']):bar.area=area
                print('REAL SAP BATCH INITIAL + WINNER',label,flush=True)
                with SapBatchSession(root/(label+'_batch')) as batch:
                    initial=batch.evaluate(m);verified=batch.evaluate(winner)
                    assert initial['validation']['passed'] and verified['validation']['passed'] and verified['feasible']
                    assert batch.evaluations==2 and set(verified['case_results'])=={'C1','C2','ULS'}
                    save_project(root/(label+'_winner_sap.trusslab.json'),winner,verified)
                    report['algorithm_checks'][-1]['sap_batch']={'evaluations':batch.evaluations,'winner_algorithm':best['algorithm'],'winner_seed':best['seed'],'result':verified}
    report.update(passed=True,elapsed_seconds=time.perf_counter()-started)
    (root/'verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print('AUDIT PASSED',report['elapsed_seconds'],flush=True)
if __name__=='__main__':main()
