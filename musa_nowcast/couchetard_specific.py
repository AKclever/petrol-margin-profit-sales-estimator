"""Fixed recent-level seasonal anchor for the own-basis Couche-Tard model."""
import argparse
from datetime import date
import json
from pathlib import Path
import re

from lxml import html

from .anchor_reliability import tail_metrics
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .timing import _metrics

SPEC=Path('data/couchetard_specific_spec_v1.json')
HISTORY=Path('data/historical_evidence_extension/2026-10-08_review_v3/reviewed_peer_history.json')
CONTEXT=Path('data/couchetard_specific/2026-10-08_sources_v1')
NAMES=['CST','Holiday','MAPCO','GetGo','Kroger','TotalEnergies']


def prior_label(q):
    return f'F{int(q[1:5])-1}Q{q[-1]}'


def anchor_forecast(target, records, baseline):
    earlier={q:r for q,r in records.items() if r['end']<target['start'] and r['available_at']<target['end']}
    if prior_label(target['quarter']) not in earlier:
        return None,'MISSING_PUBLISHED_FISCAL_ANCHOR'
    pairs=[{'quarter':r['quarter'],'prior_year_quarter':prior_label(r['quarter']),
            'current_available_at':r['available_at'],
            'prior_available_at':earlier[prior_label(r['quarter'])]['available_at'],
            'change_cpg':r['retail_margin_cpg']-earlier[prior_label(r['quarter'])]['retail_margin_cpg']}
           for r in sorted(earlier.values(),key=lambda r:r['end']) if prior_label(r['quarter']) in earlier][-4:]
    if len(pairs)<4:return None,'FEWER_THAN_FOUR_PUBLISHED_FISCAL_YOY_CHANGES'
    offset=.5*sum(p['change_cpg'] for p in pairs)/4
    return {'quarter':target['quarter'],'information_cutoff':target['end'],
            'prediction_cpg':baseline['prediction_cpg']+offset,'anchor_offset_cpg':offset,
            'recent_level_seasonal_cpg':baseline['seasonal_cpg']+offset,
            'market_adjustment_cpg':baseline['prediction_cpg']-baseline['seasonal_cpg'],
            'change_pairs':pairs,'target_start':target['start'],'target_end':target['end'],
            'training_quarters':baseline['training_quarters']},None


def evaluate(output):
    output.mkdir(parents=True,exist_ok=False)
    checks=json.loads((CONTEXT/'source_checks.json').read_text())['checks']
    inputs=[SPEC,Path(__file__),HISTORY,CONTEXT/'source_checks.json',
            Path('musa_nowcast/timing.py'),Path('musa_nowcast/model.py')]
    for c in checks:
        if c['status']=='RAW_CAPTURED':
            p=CONTEXT/c['raw_file']
            if sha(p)!=c['sha256']:raise ValueError('context changed')
            inputs.append(p)
    save(output/'frozen_inputs.json',{'created_at':now(),'files':[{'path':str(p),'sha256':sha(p)} for p in inputs]})
    (output/'inputs').mkdir()
    for i,p in enumerate(inputs):
        with (output/'inputs'/f'{i}_{p.name}').open('xb') as h:h.write(p.read_bytes())
    data=json.loads(HISTORY.read_text());records={r['quarter']:r for r in data['histories']['ATD']}
    baseline={r['quarter']:r for r in data['peer_predictions']['ATD']}
    footprint=next(c for c in checks if c['id']=='footprint')
    if footprint['status']=='RAW_CAPTURED':
        text=' '.join(html.fromstring((CONTEXT/footprint['raw_file']).read_bytes()).text_content().split())
        match=re.search(r'Store count in each business unit.{0,220}includes corporate stores, CODO and DODO and affiliated stores',text,re.I)
        evidence=match[0] if match else 'MIXED_PERIMETER_NOT_RECONCILED'
    else:evidence='UNRESOLVED_FETCH_FAILED'
    perimeter=[]
    for q,r in sorted(records.items()):
        anchor=records.get(prior_label(q),{})
        passages=r.get('acquisition_context',[])
        anchor_passages=anchor.get('acquisition_context',[])
        named=[name for name in NAMES if any(re.search(r'\b'+name+r'\b',p,re.I) for p in passages)]
        prior_named=[name for name in NAMES if any(re.search(r'\b'+name+r'\b',p,re.I) for p in anchor_passages)]
        perimeter.append({'quarter':q,'source_url':r['source_url'],'sha256':r['source_sha256'],
             'available_at':r['available_at'],'current_named_transaction_mentions':named,
             'anchor_named_transaction_mentions':prior_named,'acquisition_context':passages,
             'new_named_mentions':sorted(set(named)-set(prior_named)),
             'interpretation':'RETROSPECTIVE_RELEASE_MENTIONS_NOT_EXHAUSTIVE_TRANSACTION_OR_COMPARABILITY_CLASSIFICATION',
             'margin_adjustment_cpg':None,'like_for_like_proven':False})
    save(output/'evidence_audit.json',{'geography_status':'BLOCKED_NO_DATED_TARGET_MATCHED_REGIONAL_WEIGHTS_VERIFIED',
         'footprint_evidence':evidence,'source_checks':checks,'quarters':perimeter,
         'geographic_weights_changed':False,'raw_release_audit_inherited_from':str(HISTORY),
         'provisional_model_weights':{'East Coast':1/3,'Midwest':1/3,'Gulf Coast':1/3},
         'western_exposure_omitted_from_proxy':True,'all_acquisitions_audited':False})
    frozen,excluded={},[]
    for q,b in sorted(baseline.items()):
        f,reason=anchor_forecast(records[q],records,b)
        if f:frozen[q]=f
        else:excluded.append({'quarter':q,'reason':reason})
    save(output/'frozen_forecasts.json',{'created_at':now(),'forecasts':frozen,'exclusions':excluded})
    rows={q:baseline[q]|f|{'original_prediction_cpg':baseline[q]['prediction_cpg'],
         'original_abs_error_cpg':abs(baseline[q]['actual_cpg']-baseline[q]['prediction_cpg']),
         'shadow_abs_error_cpg':abs(baseline[q]['actual_cpg']-f['prediction_cpg']),
         'direction_correct':NowcastEngine._direction(f['prediction_cpg']-baseline[q]['seasonal_cpg']) ==
                             NowcastEngine._direction(baseline[q]['actual_cpg']-baseline[q]['seasonal_cpg'])}
         for q,f in frozen.items()}
    groups={}
    for name,qs in [('all',sorted(rows)),('2021_onward_start',[q for q in sorted(rows) if records[q]['start']>='2021-01-01']),
                    ('earlier',[q for q in sorted(rows) if records[q]['start']<'2020-01-01']),
                    ('2020_transition',[q for q in sorted(rows) if '2020-01-01'<=records[q]['start']<'2021-01-01'])]:
        big=[q for q in qs if abs(baseline[q]['actual_cpg']-baseline[q]['prediction_cpg'])>=5]
        seasonal={q:baseline[q]|{'prediction_cpg':baseline[q]['seasonal_cpg']} for q in qs}
        recent={q:baseline[q]|{'prediction_cpg':rows[q]['recent_level_seasonal_cpg']} for q in qs}
        groups[name]={'quarters':qs,'metrics':_metrics(baseline,rows,qs) if qs else None,
            'tails':tail_metrics(baseline,rows,qs),'large_group':tail_metrics(baseline,rows,big),
            'ordinary_group':tail_metrics(baseline,rows,[q for q in qs if q not in big]),
            'seasonal_baseline':tail_metrics(seasonal,seasonal,qs),
            'recent_level_seasonal_baseline':tail_metrics(recent,recent,qs)}
    result={'role':json.loads(SPEC.read_text())['role'],'groups':groups,'rows':list(rows.values()),
            'production_changed':False,'automatic_promotion':False,'strict_market_pit_verified':False,
            'live_forecast_generated':False,'geographic_reweighting_supported':False}
    save(output/'results.json',result)
    print(json.dumps({k:v['metrics'] for k,v in groups.items()},indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path)
    evaluate(p.parse_args().out)
