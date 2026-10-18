"""SAP2000 v26 OAPI adapter. Calls use the installed COM type library.

Each analysis owns a new SAP process and unique directory; no active user model
is cleared. COM objects stay on the creating thread; calls are serialized.
"""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import threading
import uuid
import queue
from concurrent.futures import Future
from .fem import solve, compare
from .core import save_project
from .sap_mapping import transfer_definition,pattern_forces,active_dof,material_key
from .units import lb_to_kip
from .analysis import design_cases,combine_cases
from .validation import validation_report, write_comparison_csv

_lock = threading.Lock()


class SapError(RuntimeError):
    pass


def find_installation():
    candidates = [os.environ.get('TRUSSLAB_SAP_EXE', ''), r'C:\SAAP2000\SAP2000.exe',
                  r'C:\Program Files\Computers and Structures\SAP2000 26\SAP2000.exe']
    return next((Path(p) for p in candidates if p and Path(p).is_file()), None)


def checked(result, name, log):
    code = result[-1] if isinstance(result, (list, tuple)) else result
    log.append({'method': name, 'return_code': int(code)})
    if code != 0:
        raise SapError(f'{name}: código de retorno {code}')
    return result


def diagnose():
    data = {'executable': str(find_installation() or ''), 'helper_registered': False,
            'running_instance': False, 'active_model_modified': False}
    try:
        import comtypes.client
        h = comtypes.client.CreateObject('SAP2000v1.Helper')
        from comtypes.gen import SAP2000v1
        h = h.QueryInterface(SAP2000v1.cHelper)
        data['helper_registered'] = True
        try:
            app = h.GetObject('CSI.SAP2000.API.SapObject')
            data['running_instance'] = bool(app)
            if app:
                data['version'] = list(app.SapModel.GetVersion())
        except Exception as e:
            data['instance_note'] = str(e)
    except Exception as e:
        data['error'] = str(e)
    return data


def audit_model(s,model,points,frames,call):
    """Read back geometry, per-member properties, every pattern and case."""
    mapping,materials,patterns,cases=transfer_definition(model)
    issues=[]
    def require(ok,message):
        if not ok:issues.append(message)
    pn=call('PointObj.GetNameList',s.PointObj.GetNameList,0,[])
    fn=call('FrameObj.GetNameList',s.FrameObj.GetNameList,0,[])
    require(pn[0]==len(model.nodes) and set(pn[1])==set(points.values()),'Número/nombres de nodos.')
    require(fn[0]==len(model.members) and set(fn[1])==set(frames.values()),'Número/nombres de barras.')
    expected={p.id:pattern_forces(model,p.id) for p in patterns}
    nodes=[];members=[];material_rows=[];pattern_rows=[];case_rows=[]
    for n in model.nodes:
        xyz=call('PointObj.GetCoordCartesian',s.PointObj.GetCoordCartesian,points[n.id],0.,0.,0.)
        restraint=call('PointObj.GetRestraint',s.PointObj.GetRestraint,points[n.id],[])[0]
        require(all(abs(x-y)<1e-8 for x,y in zip(xyz[:3],n.xyz)),f'Coordenadas N{n.id}.')
        require(list(restraint)==model.restraints(n)+[True]*3,f'Apoyos N{n.id}.')
        r=call('PointObj.GetLoadForce',s.PointObj.GetLoadForce,points[n.id],0,*([[]]*10))
        loads={}
        for pattern in patterns:
            values=[0.]*6
            for i in range(r[0]):
                if r[2][i]==mapping['patterns'][pattern.id]:
                    require(str(r[4][i]).casefold()=='global',f'Sistema de cargas N{n.id}.')
                    for d in range(6):values[d]+=float(r[5+d][i])
            require(all(abs(a-b)<1e-9 for a,b in zip(values,expected[pattern.id][str(n.id)]+[0.]*3)),f'Cargas N{n.id}/{pattern.id}.')
            loads[pattern.id]=values
        nodes.append({'id':n.id,'sap_name':points[n.id],'xyz':list(xyz[:3]),'restraints':list(restraint),'loads_by_pattern':loads})
    for m in model.members:
        ends=call('FrameObj.GetPoints',s.FrameObj.GetPoints,frames[m.id],'','')
        sec=call('FrameObj.GetSection',s.FrameObj.GetSection,frames[m.id],'','')[0]
        rectangle=call('PropFrame.GetRectangle',s.PropFrame.GetRectangle,sec,'','',0.,0.,0,'','')
        area=call('PropFrame.GetSectProps',s.PropFrame.GetSectProps,sec,*([0.]*12))[0]
        releases=call('FrameObj.GetReleases',s.FrameObj.GetReleases,frames[m.id],[],[],[],[])
        mesh=call('FrameObj.GetAutoMesh',s.FrameObj.GetAutoMesh,frames[m.id],False,False,False,0,0.)
        require(list(ends[:2])==[points[m.start],points[m.end]],f'Conectividad B{m.id}.')
        require(abs(area-m.area)<1e-9*max(1,m.area),f'Área B{m.id}.')
        require(rectangle[1]==mapping['materials'][material_key(m)],f'Material B{m.id}.')
        require(list(releases[0])==[False,False,False,True,True,True] and list(releases[1])==[False,False,False,False,True,True],f'Articulaciones B{m.id}.')
        require(not mesh[0],f'Automallado B{m.id}.')
        members.append({'id':m.id,'sap_name':frames[m.id],'start':ends[0],'end':ends[1],'section':sec,'material':rectangle[1],'area_in2':float(area)})
    for id,mat in materials.items():
        material=call('PropMaterial.GetMPIsotropic',s.PropMaterial.GetMPIsotropic,mapping['materials'][id],0.,0.,0.,0.)
        weight=call('PropMaterial.GetWeightAndMass',s.PropMaterial.GetWeightAndMass,mapping['materials'][id],0.,0.)
        require(abs(material[0]-mat.elastic_modulus)<1e-8,'Módulo de elasticidad '+id)
        require(abs(weight[0]-lb_to_kip(mat.density))<1e-12,'Peso específico '+id)
        material_rows.append({'id':id,'E_ksi':float(material[0]),'density_kip_in3':float(weight[0])})
    for pattern in patterns:
        sw=call('LoadPatterns.GetSelfWTMultiplier',s.LoadPatterns.GetSelfWTMultiplier,mapping['patterns'][pattern.id],0.)[0]
        require(abs(sw)<1e-12,'Peso propio distribuido inesperado.')
        pattern_rows.append({'id':pattern.id,'requested_self_weight':pattern.self_weight,'sap_self_weight':float(sw),'policy':'lumped_nodal_axial_truss'})
    for id,case in cases.items():
        data=call('LoadCases.StaticLinear.GetLoads',s.LoadCases.StaticLinear.GetLoads,mapping['cases'][id],0,[],[],[])
        factors={mapping['patterns'][key]:value for key,value in case.factors.items()}
        require(data[0]==len(factors) and dict(zip(data[2],data[3]))==factors and all(t=='Load' for t in data[1]),'Factores del caso '+id)
        case_rows.append({'id':id,'factors':dict(zip(data[2],data[3]))})
    dof=list(call('Analyze.GetActiveDOF',s.Analyze.GetActiveDOF,[])[0]);require(dof==active_dof(model),'Grados de libertad globales.')
    return {'passed':not issues,'issues':issues,'node_count':pn[0],'member_count':fn[0],'nodes':nodes,'members':members,
            'materials':material_rows,'patterns':pattern_rows,'cases':case_rows,'active_dof':dof,'mapping':mapping}


MANUAL_VIEWS = [
    'View → Set 2D View: plano X-Z, Y = 0; para una cercha espacial usa la vista 3D.',
    'View → Set Display Options: activar Joint Labels, Frame Labels y restricciones.',
    'Display → Show Object Assigns → Frame: consultar las secciones por barra del proyecto.',
    'Display → Show Load Assigns → Joint: el patrón del proyecto para las cargas.',
    'Display → Show Deformed Shape: el caso del proyecto para la deformada y desplazamientos.',
    'Display → Show Forces/Stresses → Frames/Cables/Tendons: Axial Force, caso del proyecto.',
    'Display → Show Forces/Stresses → Joints: reacciones; clic derecho en nodos/barras para valores.',
]


def recover_results(model,s,points,frames,call,metadata):
    result=dict(metadata)
    result.update(members=[],displacements={},reactions={})
    for n in model.nodes:
        r = call('Results.JointDispl', s.Results.JointDispl, points[n.id], 0, 0, *([[]]*11))
        if r[0] < 1:
            raise SapError(f'No hay desplazamientos para el nodo {n.id}')
        result['displacements'][str(n.id)] = [float(r[k][0]) for k in (6, 7, 8)]
        if any(model.restraints(n)):
            r = call('Results.JointReact', s.Results.JointReact, points[n.id], 0, 0, *([[]]*11))
            if r[0] < 1:
                raise SapError(f'No hay reacciones para el nodo {n.id}')
            result['reactions'][str(n.id)] = [float(r[k][0]) for k in (6, 7, 8)]
        else:
            result['reactions'][str(n.id)] = [0.,0.,0.]
    max_bending = 0.
    for m in model.members:
        r = call('Results.FrameForce', s.Results.FrameForce, frames[m.id], 0, 0, *([[]]*13))
        if r[0] < 1:
            raise SapError(f'No hay fuerza axial para la barra {m.id}')
        p = float(r[8][0])
        max_bending = max(max_bending, *[abs(float(v)) for k in (9,10,11,12,13) for v in r[k]])
        stress = p/m.area
        result['members'].append({'id': m.id, 'force': p, 'stress': stress, 'area': m.area,
                                  'ratio': abs(stress)/model.stress_limit, 'length': model.length(m)})
    result['stress_ratio'] = max(m['ratio'] for m in result['members'])
    result['displacement_ratio'] = max((abs(result['displacements'][str(n.id)][d])/model.displacement_limit
                                        for n in model.nodes for d in range(3) if not model.restraints(n)[d]),default=0.)
    result['feasible'] = result['stress_ratio'] <= 1+1e-6 and result['displacement_ratio'] <= 1+1e-6
    result['strict_feasible']=result['stress_ratio']<=1 and result['displacement_ratio']<=1
    result['feasibility_tolerance']=1e-6
    result['max_nonaxial_component'] = max_bending
    return result


def recover_cases(model,s,points,frames,call,metadata,mapping):
    results={}
    for case in design_cases(model):
        name=mapping['cases'][case]
        call('Results.Setup.DeselectAll',s.Results.Setup.DeselectAllCasesAndCombosForOutput)
        call('Results.Setup.SelectCase',s.Results.Setup.SetCaseSelectedForOutput,name)
        r=recover_results(model,s,points,frames,call,{**metadata,'analysis_case':case,'sap_analysis_case':name})
        r['validation']=validation_report(model,solve(model,case=case),r)
        r['comparison']=r['validation']['comparison'];results[case]=r
    result=combine_cases(model,results)
    if len(results)>1:
        result['validation']={**result['validation'],'cases':{c:r['validation'] for c,r in results.items()},
            'passed':all(r['validation']['passed'] for r in results.values()),
            'design_feasible':all(r['validation']['design_feasible'] for r in results.values())}
    return result


def analyze(model, output_root, visible=False, progress=None, *, _session=None, _batch=None):
    """Automatic mode closes only its own instance.

    Persistent mode is provided by VisibleSapSessions, never by a temporary Job.
    The private session holder is created and used on its dedicated COM thread.
    """
    if _session is not None:
        _session.assert_owner()
        visible=True
    holder=_session if _session is not None else _batch
    if holder is not None:holder.assert_owner()
    model.validate();solve(model)  # Reject instability before starting COM.
    mapping,materials,patterns,cases=transfer_definition(model)
    case_name=mapping['cases'][model.active_case]
    install = find_installation()
    if install is None:
        raise SapError('No se encontró SAP2000.exe. Configura TRUSSLAB_SAP_EXE con la ruta existente.')
    run_dir = Path(output_root).resolve() / ('sap_' + datetime.now().strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:6])
    run_dir.mkdir(parents=True, exist_ok=False)
    if holder is not None:holder.run_directory=run_dir
    log, app = [], None
    def stage(name):
        (run_dir/'operation.json').write_text(json.dumps({'operation':name,'timestamp':datetime.now(timezone.utc).isoformat()}),encoding='utf-8')
    def call(name, function, *args):
        stage(name)
        result=checked(function(*args), name, log)
        if name in ('Analyze.RunAnalysis','View.RefreshView','View.RefreshWindow','File.Save(results)'):
            status=checked(s.Analyze.GetCaseStatus(0,[],[]),'Analyze.GetCaseStatus(after '+name+')',log)
            log.append({'after':name,'model_locked':bool(s.GetModelIsLocked()),
                        'case_status':dict(zip(status[1],status[2]))})
        (run_dir/'api_calls.json').write_text(json.dumps(log,indent=2),encoding='utf-8')
        return result
    with _lock:
        import comtypes
        import comtypes.client
        comtypes.CoInitialize()
        try:
            if progress:
                progress('Iniciando instancia independiente de SAP2000…')
            stage('CreateObject(SAP2000v1.Helper)')
            helper = comtypes.client.CreateObject('SAP2000v1.Helper')
            from comtypes.gen import SAP2000v1
            helper = helper.QueryInterface(SAP2000v1.cHelper)
            stage('Helper.CreateObject(SAP2000.exe)')
            app = helper.CreateObject(str(install))
            if not app:
                raise SapError('OAPI no pudo crear una instancia de SAP2000.')
            if holder is not None:holder.refs={'helper':helper,'app':app}
            call('ApplicationStart', app.ApplicationStart, 3, visible, '')  # kip_in_F
            s = app.SapModel
            if holder is not None:
                holder.refs={'helper':helper,'app':app,'sap_model':s}
            version = list(call('GetVersion', s.GetVersion))
            call('InitializeNewModel', s.InitializeNewModel, 3)
            call('File.NewBlank', s.File.NewBlank)
            call('SetPresentUnits', s.SetPresentUnits, 3)
            call('Analyze.SetActiveDOF',s.Analyze.SetActiveDOF,active_dof(model))
            for id,material in materials.items():
                name=mapping['materials'][id]
                call('PropMaterial.SetMaterial',s.PropMaterial.SetMaterial,name,1)
                call('PropMaterial.SetMPIsotropic',s.PropMaterial.SetMPIsotropic,name,material.elastic_modulus,.3,0.)
                call('PropMaterial.SetWeightAndMass',s.PropMaterial.SetWeightAndMass,name,1,lb_to_kip(material.density))
            points, frames = {}, {}
            for n in model.nodes:
                r = call('PointObj.AddCartesian', s.PointObj.AddCartesian, *n.xyz, '', f'N{n.id}')
                points[n.id] = r[0]
                call('PointObj.SetRestraint', s.PointObj.SetRestraint, points[n.id], model.restraints(n)+[True, True, True])
            for m in model.members:
                sec = mapping['sections'][m.id]
                side = m.area**.5
                # Nonzero section inertia only defines valid section metadata. End
                # releases plus inactive joint rotations remove flexural action.
                call('PropFrame.SetRectangle', s.PropFrame.SetRectangle, sec, mapping['materials'][material_key(m)], side, side)
                r = call('FrameObj.AddByPoint', s.FrameObj.AddByPoint, points[m.start], points[m.end], '', sec, f'B{m.id}')
                frames[m.id] = r[0]
                # R1 release at one end, R2/R3 at both; avoids double torsion release.
                call('FrameObj.SetReleases', s.FrameObj.SetReleases, frames[m.id],
                     [False, False, False, True, True, True], [False, False, False, False, True, True], [0.]*6, [0.]*6)
                call('FrameObj.SetAutoMesh', s.FrameObj.SetAutoMesh, frames[m.id], False, False, False, 1, 0.)
            for pattern in patterns:
                pattern_name=mapping['patterns'][pattern.id]
                types={'Dead':1,'Live':3,'Wind':6,'Other':8}
                # Self weight is lumped at joints to keep the axial-only model;
                # distributed frame gravity would introduce shear and bending.
                call('LoadPatterns.Add',s.LoadPatterns.Add,pattern_name,types.get(pattern.load_type,8),0.,False)
                forces=pattern_forces(model,pattern.id)
                for node in model.nodes:
                    if any(forces[str(node.id)]):call('PointObj.SetLoadForce',s.PointObj.SetLoadForce,points[node.id],pattern_name,forces[str(node.id)]+[0.]*3,True)
            for id,case in cases.items():
                name=mapping['cases'][id]
                call('LoadCases.StaticLinear.SetCase',s.LoadCases.StaticLinear.SetCase,name)
                call('LoadCases.StaticLinear.SetLoads',s.LoadCases.StaticLinear.SetLoads,name,len(case.factors),['Load']*len(case.factors),[mapping['patterns'][k] for k in case.factors],list(case.factors.values()))
            call('Analyze.SetRunCaseFlag(all off)',s.Analyze.SetRunCaseFlag,'',False,True)
            for name in mapping['cases'].values():call('Analyze.SetRunCaseFlag(case)',s.Analyze.SetRunCaseFlag,name,True,False)
            call('Analyze.SetSolverOption_3', s.Analyze.SetSolverOption_3, 0, 1, 1, 0, 1, '')
            if _session is not None:
                # Rebuild display object arrays before analysis and reset zoom.
                if not app.Visible():call('Unhide',app.Unhide)
                call('View.RefreshView',s.View.RefreshView,0,False)
            path = run_dir / (mapping['project']+'.sdb')
            call('File.Save', s.File.Save, str(path))
            audit=audit_model(s,model,points,frames,call)
            (run_dir/'input_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
            if not audit['passed']:
                raise SapError('La lectura de SAP no coincide con el modelo: '+'; '.join(audit['issues']))
            if progress:
                progress('Modelo creado. Ejecutando análisis SAP2000…')
            call('Analyze.RunAnalysis', s.Analyze.RunAnalysis)
            call('Results.Setup.DeselectAll', s.Results.Setup.DeselectAllCasesAndCombosForOutput)
            call('Results.Setup.SelectCase',s.Results.Setup.SetCaseSelectedForOutput,case_name)
            result = {'engine': 'SAP2000 ' + str(version[0]), 'timestamp': datetime.now(timezone.utc).isoformat(),
                      'weight_lb': model.weight(), 'members': [], 'displacements': {}, 'reactions': {},
                      'sap_model': str(path), 'version': version, 'run_directory': str(run_dir)}
            result['input_audit']=audit
            result['sap_mapping']=mapping;result['analysis_case']=model.active_case;result['sap_analysis_case']=case_name;result['model_id']=model.project_id
            result['model_fingerprint']=model.fingerprint()
            result['mode']='visible_persistent' if _session is not None else ('optimization_batch' if _batch is not None else 'automatic')
            if _batch is not None:
                _batch.points=points;_batch.frames=frames;_batch.version=version;_batch.path=path;_batch.initial_audit=audit;_batch.mapping=mapping
                _batch.previous_forces={p.id:pattern_forces(model,p.id) for p in patterns}
            result=recover_cases(model,s,points,frames,call,result,mapping)
            if _session is not None:
                # v26 returns 1 for Unhide when it is already visible.
                if not app.Visible():call('Unhide',app.Unhide)
                call('View.RefreshWindow',s.View.RefreshWindow,0)
                result['session']={'id':_session.id,'previous_session_id':_session.previous_id,
                                   'visible':bool(app.Visible()),'persistent':True,
                                   'update_policy':'new_instance_and_file','manual_views':list(MANUAL_VIEWS),
                                   'view_api':'RefreshView(0, False) before analysis / RefreshWindow(0) after analysis'}
                if not result['session']['visible']:
                    raise SapError('SAP2000 no confirmó que la sesión sea visible.')
            # A filename invokes Save As in v26.3 and invalidates analysis even
            # when that filename is the same. Plain Save retains analysis results.
            call('File.Save(results)', s.File.Save)
            case_status=call('Analyze.GetCaseStatus(final)',s.Analyze.GetCaseStatus,0,[],[])
            result['analysis_case_status']={name:int(code) for name,code in zip(case_status[1],case_status[2])}
            if any(result['analysis_case_status'].get(mapping['cases'][case])!=4 for case in design_cases(model)):
                raise SapError('El el caso del proyecto no conserva sus resultados en SAP2000 después de guardar. Revisa el registro de operaciones.')
            (run_dir / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            (run_dir/'comparison.json').write_text(json.dumps(result['validation'],indent=2),encoding='utf-8')
            write_comparison_csv(run_dir/'comparison.csv',result['comparison'])
            save_project(run_dir/'transferred.trusslab.json',model,result)
            (run_dir/'VISTAS_EN_SAP2000.txt').write_text('\n'.join(MANUAL_VIEWS),encoding='utf-8')
            return result
        except Exception as e:
            (run_dir / 'error.txt').write_text(str(e), encoding='utf-8')
            raise
        finally:
            if app is not None and holder is None:
                try:
                    call('ApplicationExit', app.ApplicationExit, False)
                except Exception as e:
                    log.append({'cleanup_error': str(e)})
            (run_dir / 'api_calls.json').write_text(json.dumps(log, indent=2), encoding='utf-8')
            app=None
            helper=None
            s=None
            comtypes.CoUninitialize()


class _ManagedSession:
    """COM references never leave the creating worker thread."""
    def __init__(self,previous_id=None):
        self.id=uuid.uuid4().hex
        self.previous_id=previous_id
        self.owner=threading.get_ident()
        self.refs={}
        self.run_directory=None

    def assert_owner(self):
        if threading.get_ident()!=self.owner:
            raise RuntimeError('Una referencia COM se intentó usar desde otro hilo.')

    def detach(self):
        self.assert_owner()
        # No ApplicationExit and no save: SAP belongs to manual inspection now.
        self.refs.clear()


class SapBatchSession(_ManagedSession):
    """One owned, hidden SAP instance for a size-optimization run, on one thread."""
    def __init__(self, output_root):
        super().__init__()
        self.output_root=Path(output_root)
        self.evaluations=0
        self.signature=None
        self.initialized=False
        self.closed=False

    def __enter__(self):
        import comtypes
        comtypes.CoInitialize()
        self.initialized=True
        return self

    @staticmethod
    def geometry_signature(model):
        clone=model.clone()
        for member in clone.members:member.area=clone.area_min
        return clone.fingerprint()

    def evaluate(self,model):
        self.assert_owner()
        if self.closed or not self.initialized:raise SapError('La sesión de optimización no está abierta.')
        signature=self.geometry_signature(model)
        if self.signature is not None and signature!=self.signature:
            raise SapError('Una sesión de tamaño no puede cambiar geometría, material, cargas o restricciones.')
        try:
            if not self.refs:
                self.signature=signature
                result=analyze(model,self.output_root,_batch=self)
            else:
                with _lock:
                    s=self.refs['sap_model'];log=[]
                    def call(name,function,*args):
                        value=checked(function(*args),name,log)
                        with (self.run_directory/'batch_api_calls.jsonl').open('a',encoding='utf-8') as stream:
                            stream.write(json.dumps({'candidate':self.evaluations+1,**log[-1]})+'\n')
                        return value
                    call('SetModelIsLocked(False)',s.SetModelIsLocked,False)
                    for member in model.members:
                        side=member.area**.5;section=self.mapping['sections'][member.id]
                        call('PropFrame.SetRectangle',s.PropFrame.SetRectangle,section,self.mapping['materials'][material_key(member)],side,side)
                        area=call('PropFrame.GetSectProps',s.PropFrame.GetSectProps,section,*([0.]*12))[0]
                        if abs(area-member.area)>1e-9*max(1.,member.area):raise SapError('SAP no confirmó la nueva área.')
                    for pattern in transfer_definition(model)[2]:
                        forces=pattern_forces(model,pattern.id)
                        for node in model.nodes:
                            values=forces[str(node.id)]
                            if any(values):
                                call('PointObj.SetLoadForce',s.PointObj.SetLoadForce,self.points[node.id],self.mapping['patterns'][pattern.id],values+[0.]*3,True)
                            elif any(self.previous_forces[pattern.id][str(node.id)]):
                                call('PointObj.DeleteLoadForce',s.PointObj.DeleteLoadForce,self.points[node.id],self.mapping['patterns'][pattern.id])
                        self.previous_forces[pattern.id]=forces
                    call('File.Save',s.File.Save)
                    call('Analyze.RunAnalysis' ,s.Analyze.RunAnalysis)
                    call('Results.Setup.DeselectAll',s.Results.Setup.DeselectAllCasesAndCombosForOutput)
                    call('Results.Setup.SelectCase',s.Results.Setup.SetCaseSelectedForOutput,self.mapping['cases'][model.active_case])
                    result=recover_cases(model,s,self.points,self.frames,call,
                        {'engine':'SAP2000 '+str(self.version[0]),'weight_lb':model.weight(),
                         'model_fingerprint':model.fingerprint(),'mode':'optimization_batch','analysis_case':model.active_case,'sap_analysis_case':self.mapping['cases'][model.active_case],'sap_mapping':self.mapping,
                         'sap_model':str(self.path),'run_directory':str(self.run_directory),
                         'timestamp':datetime.now(timezone.utc).isoformat()},self.mapping)
                    call('File.Save(results)',s.File.Save)
                    status=call('Analyze.GetCaseStatus',s.Analyze.GetCaseStatus,0,[],[])
                    result['analysis_case_status']=dict(zip(status[1],status[2]))
                    if any(result['analysis_case_status'].get(self.mapping['cases'][case])!=4 for case in design_cases(model)):raise SapError('Un caso seleccionado no está analizado.')
            if not result['validation']['passed']:
                raise SapError('La evaluación SAP difiere del control independiente FEM o no satisface el equilibrio.')
            self.evaluations+=1
            self.last_fingerprint=model.fingerprint()
            result['batch_session_id']=self.id;result['batch_evaluation']=self.evaluations
            with (self.run_directory/'candidate_results.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(result)+'\n')
            return result
        except Exception as error:
            self.output_root.mkdir(parents=True,exist_ok=True)
            with (self.output_root/'batch_errors.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps({'session':self.id,'candidate':self.evaluations+1,'error':str(error)})+'\n')
            raise

    def __exit__(self,*exc):
        self.assert_owner()
        try:
            app=self.refs.get('app')
            if app is not None:
                code=app.ApplicationExit(False)
                if code!=0:raise SapError(f'ApplicationExit: código {code}')
        finally:
            app=None
            self.refs.clear();self.closed=True
            if self.initialized:
                import comtypes
                comtypes.CoUninitialize();self.initialized=False


def pump_sta_messages():
    """Dispatch this STA's messages without a CoWait RPC modal wait.

    A standard STA message loop services marshalled calls on the owner thread.
    This does not suppress native diagnostics raised inside SAP RunAnalysis.
    """
    from ctypes import byref
    from ctypes.wintypes import MSG
    from comtypes.messageloop import PeekMessage,TranslateMessage,DispatchMessage,PM_REMOVE
    message=MSG()
    while PeekMessage(byref(message),0,0,0,PM_REMOVE):
        TranslateMessage(byref(message));DispatchMessage(byref(message))

class VisibleSapSessions:
    """Serial command queue on a long-lived STA thread, with message pumping.

    Every open/update creates a new instance and SDB. Existing sessions (including
    manual changes) remain untouched. Futures contain only ordinary Python data.
    shutdown releases references on the owner thread without closing SAP.
    """
    def __init__(self):
        self._queue=queue.Queue()
        self._state_lock=threading.Lock()
        self._closed=False
        self._thread=None

    def open(self,model,output_root,progress=None,previous_id=None):
        snapshot=model.clone();snapshot.validate()
        future=Future()
        with self._state_lock:
            if self._closed:raise RuntimeError('El gestor SAP ya se cerró.')
            if self._thread is None:
                self._thread=threading.Thread(target=self._run,name='TrussLab-SAP-STA',daemon=True)
                self._thread.start()
            self._queue.put((future,snapshot,output_root,progress,previous_id))
        return future

    def inspect(self,session_id):
        """Read liveness on the owner thread without changing the open model."""
        future=Future()
        with self._state_lock:
            if self._closed or self._thread is None:
                raise RuntimeError('No hay un gestor SAP activo.')
            self._queue.put((future,None,None,None,session_id))
        return future

    def _run(self):
        try:
            import comtypes
            import comtypes.client
            comtypes.CoInitializeEx(comtypes.COINIT_APARTMENTTHREADED)
        except Exception as exc:
            with self._state_lock:
                self._closed=True
                while True:
                    try:command=self._queue.get_nowait()
                    except queue.Empty:break
                    if command is not None:command[0].set_exception(SapError('No se pudo iniciar COM: '+str(exc)))
            return
        sessions=[]
        try:
            while True:
                try:command=self._queue.get(timeout=.08)
                except queue.Empty:
                    pump_sta_messages()
                    continue
                if command is None:break
                future,model,root,progress,previous_id=command
                if not future.set_running_or_notify_cancel():continue
                if model is None:
                    try:
                        session=next(s for s in sessions if s.id==previous_id)
                        session.assert_owner()
                        status={'id':session.id,'visible':bool(session.refs['app'].Visible()),
                                'model_file':session.refs['sap_model'].GetModelFilename(True),
                                'analysis_locked':bool(session.refs['sap_model'].GetModelIsLocked())}
                        cases=checked(session.refs['sap_model'].Analyze.GetCaseStatus(0,[],[]),'Analyze.GetCaseStatus',[])
                        status['case_status']={name:int(code) for name,code in zip(cases[1],cases[2])}
                        (session.run_directory/'session_status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
                        future.set_result(status)
                    except Exception as exc:future.set_exception(SapError(str(exc)))
                    continue
                session=_ManagedSession(previous_id)
                sessions.append(session)  # Keep refs even if analysis fails: inspect in SAP.
                try:
                    result=analyze(model,root,visible=True,progress=progress,_session=session)
                    future.set_result(result)
                except Exception as exc:
                    directory=f'\nDiagnóstico: {session.run_directory}' if session.run_directory else ''
                    future.set_exception(SapError(str(exc)+directory))
        finally:
            for session in sessions:session.detach()
            sessions.clear()
            comtypes.CoUninitialize()

    def shutdown(self,timeout=2.):
        with self._state_lock:
            if not self._closed:
                self._closed=True
                if self._thread is not None:self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout)
            return not self._thread.is_alive()
        return True
