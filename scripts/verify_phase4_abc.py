"""Real FEM campaigns and ASAM sensitivity, with immutable configurations."""
from pathlib import Path
from dataclasses import asdict
import copy,json,time
import numpy as np
from trusslab.core import benchmark
from trusslab.fem import solve
from trusslab.prepared_fem import PreparedTruss
from trusslab.asam import ASAMOptions
from trusslab.laboratory import CampaignConfig,run_campaign

root=Path(__file__).resolve().parents[1]/'data/phase4';root.mkdir(parents=True,exist_ok=True)
model=benchmark();rng=np.random.default_rng(9);vectors=rng.uniform(.1,35,(400,10))
prepared=PreparedTruss(model);timings={}
for engine in ['reference','prepared']:
    started=time.perf_counter()
    for areas in vectors:
        if engine=='prepared':result=prepared.solve(areas)
        else:
            candidate=model.clone()
            for b,a in zip(candidate.members,areas):b.area=float(a)
            result=solve(candidate)
    timings[engine+'_seconds']=time.perf_counter()-started
report={'performance':timings,'campaigns':[],'sensitivity':[]}
for budget in [2000,5000]:
    config=CampaignConfig(budget=budget,sap_validation='none')
    c=run_campaign(model,config,root)
    assert c['status']=='completed' and all(r['metrics']['evaluations']<=budget for r in c['runs'])
    report['campaigns'].append({'budget':budget,'directory':c['_directory'],'statistics':c['statistics']})
    print('Campaign',budget,c['_directory'],[(s['algorithm'],s['best_lb'],s['n_valid']) for s in c['statistics']],flush=True)
# One-factor-at-a-time probes, paired seeds and same budget; no claim of a
# globally best setting and no reuse of the archived 5060.856 lb design.
variants=[('baseline',{}),('temperature_initial',{'temperature_initial':.01}),
    ('temperature_final',{'temperature_final':1e-4}),('cooling',{'cooling':.99}),
    ('initial_points',{'initial_points':200}),('radius_initial',{'radius_initial':5.}),
    ('radius_reduction',{'radius_reduction':.99}),('proposals',{'proposals_per_temperature':20}),
    ('stagnation',{'convergence_tolerance':1e-6,'convergence_patience':10}),('penalty',{})]
for name,changes in variants:
    config=CampaignConfig(algorithms=['ASAM'],seeds=[42,7,17],budget=2000,sap_validation='none')
    config.parameters['asam'].update(changes)
    if name=='penalty':config.parameters['asam_constraint_policy']='penalty'
    c=run_campaign(model,config,root/'sensitivity')
    assert c['status']=='completed'
    report['sensitivity'].append({'variant':name,'changes':changes,'directory':c['_directory'],'statistics':c['statistics']})
    print('Sensitivity',name,c['statistics'][0]['best_lb'],flush=True)
(root/'abc_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('A/B/C evidence complete',flush=True)
