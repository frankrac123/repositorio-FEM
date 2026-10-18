import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from trusslab.examples import triangle,spatial
from trusslab.optimization import optimize
from trusslab.sap import SapBatchSession
from trusslab.analysis import solve_design,constraint_margins
from trusslab.core import save_project
root=Path('data/modeler/optimization');root.mkdir(parents=True,exist_ok=True)
checks=[]
for label,factory in [('triangle',triangle),('spatial',spatial)]:
    model=factory();model.optimization_config['load_cases']=['C1','C2','ULS']
    initial=model.weight();fingerprint=model.fingerprint()
    print('OPTIMIZE',label,flush=True)
    winner,result,history=optimize(model,method='SLSQP',iterations=200,max_evaluations=1800,output_dir=root/label)
    assert result['feasible'] and result['weight_lb']<initial and min(constraint_margins(winner,solve_design(winner)))>=-1e-6
    assert model.fingerprint()==fingerprint
    print('SAP INITIAL + UPDATE',label,flush=True)
    with SapBatchSession(root/(label+'_sap')) as batch:
        a=batch.evaluate(model);b=batch.evaluate(winner)
        assert a['validation']['passed'] and b['validation']['passed'] and b['feasible']
        assert set(b['case_results'])=={'C1','C2','ULS'}
        assert all(v['passed'] for v in b['validation']['cases'].values())
        assert batch.evaluations==2 and batch.last_fingerprint==winner.fingerprint()
        save_project(root/(label+'_optimized.trusslab.json'),winner,b,history)
        checks.append({'model':label,'initial_weight_lb':initial,'optimized_weight_lb':b['weight_lb'],
            'fingerprint':winner.fingerprint(),'evaluations':result['optimization']['evaluations'],
            'cases':list(b['case_results']),'sap_validation':b['validation'],'sdb':b['sap_model']})
(root/'verification.json').write_text(json.dumps({'passed':True,'checks':checks},indent=2),encoding='utf-8')
print('PASSED MULTI-CASE OPTIMIZATION + SAP UPDATE',flush=True)
