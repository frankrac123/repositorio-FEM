"""Real SAP v26 regression; owns only its newly created hidden instances."""
import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from trusslab.examples import triangle,spatial
from trusslab.core import benchmark,load_project,save_project
from trusslab.sap import analyze,SapBatchSession
from trusslab.fem import solve

root=Path('data/modeler');root.mkdir(exist_ok=True)
checks=[]
for label,model in [('triangle',triangle()),('spatial',spatial()),('benchmark',benchmark())]:
    print('REAL SAP',label,flush=True)
    r=analyze(model,root/label,progress=lambda message:print(message,flush=True))
    assert r['validation']['passed'] and r['analysis_case_status'][r['sap_analysis_case']]==4
    assert r['input_audit']['passed']
    checks.append({'model':label,'fingerprint':model.fingerprint(),'weight_lb':r['weight_lb'],'validation':r['validation'],'sdb':r['sap_model'],'case_status':r['analysis_case_status']})
    save_project(root/(label+'.trusslab.json'),model,r)
(root/'sap_verification.json').write_text(json.dumps({'passed':True,'checks':checks},indent=2),encoding='utf-8')
print('PASSED',len(checks),flush=True)
