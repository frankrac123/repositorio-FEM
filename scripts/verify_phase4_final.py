"""Stage D/F/G evidence: fair hybrids, authentic SAP and portable exports."""
from pathlib import Path
import json
from trusslab.core import benchmark
from trusslab.laboratory import CampaignConfig,run_campaign,validate_campaign,save_campaign
from trusslab.lab_report import export_report

root=Path(__file__).resolve().parents[1]/'data/phase4'
gate=json.loads((root/'abc_gate.json').read_text());assert gate['passed']
config=CampaignConfig(algorithms=['ASAM','DE','SLSQP','ASAM+SLSQP','DE+SLSQP'],budget=5000,sap_validation='none')
campaign=run_campaign(benchmark(),config,root/'final')
assert campaign['status']=='completed' and len(campaign['runs'])==25
for record in campaign['runs']:
    assert record['metrics']['evaluations']<=5000
    if '+' in record['algorithm']:
        assert record['result']['weight_lb']<=record['search']['global_weight_lb']
(root/'final_campaign.json').write_text(json.dumps({'directory':campaign['_directory']},indent=2),encoding='utf-8')
print('Final campaign completed',campaign['_directory'],flush=True)
validate_campaign(campaign,campaign['_directory'],'best_per_method',progress=lambda item:print(item,flush=True))
verified=[r for r in campaign['runs'] if r['sap_validation']['status']=='verified']
assert len(verified)==5, campaign.get('validation_error','SAP discrepancy')
report_dir=Path(campaign['_directory'])/'report'
paths=export_report(campaign,report_dir)
proof={'passed':True,'directory':campaign['_directory'],'statistics':campaign['statistics'],
    'verified_winners':[{'algorithm':r['algorithm'],'seed':r['seed'],'weight_lb':r['result']['weight_lb'],
        'project':r['sap_validation']['result_project'],'sdb':r['sap_validation']['sdb']} for r in verified],
    'validation_cost':campaign['validation_cost'],'reports':paths}
(root/'final_verification.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
print(json.dumps(proof,indent=2),flush=True)
