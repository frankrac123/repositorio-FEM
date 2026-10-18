"""Explicit real integration; never attaches to an existing user SAP instance."""
import json
from pathlib import Path
from trusslab.core import benchmark
from trusslab.sap import SapBatchSession
from trusslab.optimization import optimize

root=Path(__file__).resolve().parents[1]/'data'/'phase3_verification'
root.mkdir(parents=True,exist_ok=True)
model=benchmark();results=[]
with SapBatchSession(root/'persistent') as session:
    for area in (35.,30.,25.):
        candidate=model.clone()
        for member in candidate.members:member.area=area
        result=session.evaluate(candidate)
        assert result['validation']['passed'],result['validation']
        assert result['analysis_case_status']['CASE_I']==4
        results.append({'area':area,'session_id':result['batch_session_id'],'evaluation':result['batch_evaluation'],
            'weight_lb':result['weight_lb'],'passed':result['validation']['passed'],
            'fingerprint':result['model_fingerprint'],'sap_model':result['sap_model']})
assert session.closed and len({r['session_id'] for r in results})==1
_,sap,h=optimize(model,iterations=1,engine='SAP',max_evaluations=4,output_dir=root)
assert 3<=sap['optimization']['sap_evaluations']<=4 and sap['optimization']['fem_evaluations']==0
_,hybrid,j=optimize(model,iterations=2,engine='HYBRID',max_evaluations=60,hybrid_validations=2,output_dir=root)
assert hybrid['external_validation']=='verified' and 2<=hybrid['optimization']['sap_evaluations']<=3
assert hybrid['validation']['passed']
for result in [sap,hybrid]:
    directory=Path(result['optimization']['run_directory'])
    ledger=next(directory.rglob('candidate_results.jsonl'))
    last=json.loads(ledger.read_text().splitlines()[-1])
    assert last['model_fingerprint']==result['model_fingerprint']
evidence={'persistent_candidates':results,'closed_owned_session':session.closed,
    'sap_optimization':sap['optimization'],'hybrid_optimization':hybrid['optimization']}
(root/'verification.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
print(json.dumps(evidence,indent=2))
