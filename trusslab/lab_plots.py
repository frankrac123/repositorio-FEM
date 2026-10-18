"""Plots use completed structural evaluations; never extrapolate a run."""
from pathlib import Path
import gzip,json
import numpy as np

COLORS={'ASAM':'#247ff3','DE':'#df8c26','SLSQP':'#17a478','ASAM+SLSQP':'#8d63c5','DE+SLSQP':'#df557c'}
PLOT_TYPES={'convergence':'Convergencia','boxplot':'Pesos factibles','time':'Tiempo de ejecución',
            'evaluations':'Evaluaciones consumidas','histogram':'Histograma de pesos','areas':'Áreas ganadoras','feasibility':'Evolución de factibilidad'}


def read_trace(directory,record):
    with gzip.open(Path(directory)/record['trace'],'rt',encoding='utf-8') as stream:return [json.loads(line) for line in stream]


def draw_plot(figure,campaign,kind='convergence',*,histories=None,seed=None):
    figure.clear();ax=figure.add_subplot(111);ax.grid(alpha=.17);ax.set_axisbelow(True)
    if not campaign or not campaign.get('runs'):
        ax.text(.5,.5,'Inicia o abre una campaña reproducible',ha='center',va='center',transform=ax.transAxes);ax.set_axis_off();return ax
    methods=campaign['configuration']['algorithms'];runs=campaign['runs']
    if seed is not None:runs=[r for r in runs if r['seed']==seed]
    valid=[r for r in runs if r['status']=='feasible'];histories=histories if histories is not None else {}
    if kind in ('convergence','feasibility'):
        for r in runs:
            if r['id'] not in histories:
                try:histories[r['id']]=read_trace(campaign['_directory'],r)
                except (OSError,EOFError):continue
            history=histories[r['id']];x=[h['evaluations'] for h in history];color=COLORS[r['algorithm']]
            if kind=='convergence':
                samples=[h for h in history if h['best_feasible_lb'] is not None]
                ax.plot([h['evaluations'] for h in samples],[h['best_feasible_lb'] for h in samples],color=color,alpha=.7,lw=1.2,label=f'{r["algorithm"]} · {r["seed"]}')
                bad=[h for h in history[::max(1,len(history)//100)] if not h['feasible']]
                ax.scatter([h['evaluations'] for h in bad],[h['weight_lb'] for h in bad],marker='x',s=6,color=color,alpha=.15)
            else:
                ax.plot(x,100*np.cumsum([h['feasible'] for h in history])/np.arange(1,len(history)+1),color=color,alpha=.7,label=f'{r["algorithm"]} · {r["seed"]}')
        ax.set_xlabel('Evaluaciones estructurales nuevas (incluye auditorías SAP)')
        ax.set_ylabel('Mejor peso factible acumulado (lb)' if kind=='convergence' else 'Candidatos factibles acumulados (%)')
        ax.set_ylim(bottom=0)
        if kind=='feasibility':ax.set_ylim(0,100)
        else:ax.set_title('Cruces: candidatos infactibles; líneas: mejor factible',fontsize=9)
    elif kind=='boxplot':
        selected=[m for m in methods if any(r['algorithm']==m for r in valid)]
        values=[[r['result']['weight_lb'] for r in valid if r['algorithm']==m] for m in selected]
        if values:
            boxes=ax.boxplot(values,tick_labels=[f'{m}\nn={len(v)}' for m,v in zip(selected,values)],patch_artist=True)
            for box,m in zip(boxes['boxes'],selected):box.set_facecolor(COLORS[m]);box.set_alpha(.4)
        ax.set_ylabel('Peso factible final (lb)');ax.set_ylim(bottom=0)
    elif kind in ('time','evaluations'):
        field='elapsed_seconds' if kind=='time' else 'evaluations'
        observed=[m for m in methods if any(r['algorithm']==m for r in runs)]
        values=[float(np.mean([r['metrics'][field] for r in runs if r['algorithm']==m])) for m in observed]
        ax.bar(observed,values,color=[COLORS[m] for m in observed],alpha=.8);ax.set_ylim(bottom=0)
        ax.set_ylabel('Tiempo medio (s; incluye pausas)' if kind=='time' else 'Evaluaciones nuevas medias (n)')
    elif kind=='histogram':
        for m in methods:
            values=[r['result']['weight_lb'] for r in valid if r['algorithm']==m]
            if values:ax.hist(values,bins=max(1,min(10,len(values))),alpha=.35,color=COLORS[m],label=f'{m} (n={len(values)})',histtype='stepfilled')
        ax.set_xlabel('Peso factible final (lb)');ax.set_ylabel('Corridas (n)');ax.set_ylim(bottom=0)
    elif kind=='areas':
        ids=[b['id'] for b in campaign['model']['members']]
        for m in methods:
            candidates=[r for r in valid if r['algorithm']==m]
            if candidates:
                winner=min(candidates,key=lambda r:r['result']['weight_lb']);ax.plot(ids,winner['areas_in2'],'o-',ms=3,color=COLORS[m],label=m)
        ax.set_xlabel('ID de barra');ax.set_ylabel('Área del mejor diseño factible (in²)');ax.set_ylim(bottom=0)
    handles,labels=ax.get_legend_handles_labels()
    if handles:ax.legend(fontsize=7,ncol=2)
    if kind not in ('convergence',):ax.set_title(PLOT_TYPES.get(kind,kind))
    figure.tight_layout();return ax
