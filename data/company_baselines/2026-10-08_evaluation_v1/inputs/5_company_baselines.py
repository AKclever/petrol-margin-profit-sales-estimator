"""Own-company simple benchmarks and a five-company evidence ledger."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re

from .company_evidence_ledger import append_event, eligible_events, read_ledger
from .expanded_peer_evidence import normalize
from .prospective import sha

SPEC = Path('data/company_baseline_spec_v1.json')
SEED = Path('data/expanded_peer_evidence/2026-10-08_review_v2/reviewed_evidence.json')
OLDER = Path('data/company_baselines/2026-10-08_capture_v1')
GAPS = Path('data/company_baselines/2026-10-08_gap_capture_v1')
EXISTING = Path('data/earnings_event_replay/2026-10-08_v3/dataset.json')


def older_target(check):
    company, quarter = check['company'], check['id'].split('_')[1]
    text = check['text']
    publication = re.search(r'(?:RICHMOND,?\s+Va\.?,?|Allentown,?\s+PA)\s+([A-Za-z.]+)\s+(\d{1,2}),?\s+(20\d{2})', text, re.I)
    if not publication:
        raise ValueError('MISSING_PUBLICATION_DATE')
    stamp = ' '.join(publication.groups()).replace('.', '')
    try:
        available = datetime.strptime(stamp, '%b %d %Y').date().isoformat()
    except ValueError:
        available = datetime.strptime(stamp, '%B %d %Y').date().isoformat()
    if company=='ARKO':
        # Earlier releases used footnote 2 for the same retail definition.
        rows = [r for t in check['tables'] for r in t
                if re.match(r'Fuel margin, cents per gallon\s*[23]\s+\d', r)]
        if len(rows)!=1:
            raise ValueError('AMBIGUOUS_RETAIL_ROW')
        values = re.findall(r'\d+\.\d+', rows[0])
        if len(values) not in [2,4]:
            raise ValueError('INVALID_QUARTERLY_COLUMNS')
        definition = re.search(r'Calculated as fuel revenue less fuel costs.{0,240}?excludes.{0,160}?cost of fuel\.', text)
        if not definition:
            raise ValueError('UNVERIFIED_FUEL_FEE_BASIS')
        normalized = {'actual_cpg':float(values[0]), 'prior_year_comparison_cpg':float(values[1]),
            'target_basis':'ARKO_RETAIL_FUEL_CONTRIBUTION_EXCLUDES_GPMP_FIXED_MARGIN_OR_FEE',
            'margin_evidence':rows[0], 'definition_evidence':definition[0]}
    else:
        # Older CAPL combined rows sometimes omit a dollar sign; retain the
        # company-operated target separately, never borrow the combined value.
        copied = check | {'tables':[[re.sub(r'^(Margin per gallon, before deducting credit card fees and commissions)\s+(0\.)',r'\1 $ \2',r) for r in t] for t in check['tables']]}
        normalized = normalize(copied)
    year, q = int(quarter[:4]), int(quarter[-1])
    start = f'{year}-{(q-1)*3+1:02d}-01'
    end = f'{year}-{q*3:02d}-{30 if q in [2,3] else 31:02d}'
    period = datetime.strptime(end, '%Y-%m-%d')
    if not re.search(rf'{period:%B}\s+{period.day},?\s+{year}', text):
        raise ValueError('PERIOD_NOT_SUPPORTED_BY_SOURCE')
    context = re.findall(r'[^.]{0,150}(?:converted|acquisition|divest|dealerization)[^.]{0,250}\.', text, re.I)
    return normalized | {'company':company, 'quarter':quarter, 'start':start,'end':end,
        'available_at':available,'captured_at':check['captured_at'],'source_url':check['source_url'],
        'sha256':check['sha256'],'historical_vintage_verified':False,
        'perimeter_context':list(dict.fromkeys(context))[:5], 'acquisition_adjustment_applied':False}


def forecast(target, events):
    cutoff = target['end']
    training = sorted([e for e in eligible_events(events,cutoff,target['company'])
        if e['kind']=='ACTUAL_MARGIN' and e['target_basis']==target['target_basis'] and e['end']<target['start']],key=lambda e:e['end'])
    wanted = str(int(target['quarter'][:4])-1)+target['quarter'][4:]
    prior = next((r for r in training if r['quarter']==wanted),None)
    if len(training)<8 or prior is None:
        return None
    recent = sum(e['actual_cpg'] for e in training[-4:])/4
    return {'company':target['company'],'quarter':target['quarter'],'information_cutoff':cutoff,
        'target_basis':target['target_basis'],'seasonal_cpg':prior['actual_cpg'], 'recent_cpg':recent,
        'blend_cpg':.5*prior['actual_cpg']+.5*recent,
        'training_quarters':[e['quarter'] for e in training],
        'training_available_at':[e['available_at'] for e in training],
        'training_source_hashes':[e['source_sha256'] for e in training]}


def metrics(rows, model):
    if not rows:
        return {'n':0}
    errors = [abs(r[model+'_cpg']-r['actual_cpg']) for r in rows]
    gains = [abs(r['seasonal_cpg']-r['actual_cpg'])-error for r,error in zip(rows,errors)]
    ordinary = [g for r,g in zip(rows,gains) if abs(r['seasonal_cpg']-r['actual_cpg'])<5]
    loo = [(sum(gains)-g)/(len(rows)-1) for g in gains] if len(rows)>1 else []
    return {'n':len(rows),'mae_cpg':sum(errors)/len(rows),
        'rmse_cpg':math.sqrt(sum(e*e for e in errors)/len(rows)),
        'errors_ge5':sum(e>=5 for e in errors),'mean_improvement_vs_seasonal_cpg':sum(gains)/len(rows),
        'ordinary_mean_improvement_cpg':sum(ordinary)/len(ordinary) if ordinary else None,
        'worst_leave_one_out_improvement_cpg':min(loo) if loo else None,
        'automatic_promotion':False}


def build(output):
    output.mkdir(parents=True,exist_ok=False)
    (output/'inputs').mkdir()
    paths = [SPEC,SEED,EXISTING,OLDER/'source_checks.json',GAPS/'source_checks.json',
             Path(__file__),Path('musa_nowcast/company_evidence_ledger.py')]
    manifest = []
    for i,p in enumerate(paths):
        manifest.append({'path':str(p),'sha256':sha(p)})
        (output/'inputs'/f'{i}_{p.name}').write_bytes(p.read_bytes())
    targets = json.loads(SEED.read_text())['targets']
    unresolved = []
    for root in [OLDER,GAPS]:
        for check in json.loads((root/'source_checks.json').read_text())['checks']:
            try:
                if check['status']!='RAW_CAPTURED' or sha(root/check['raw_file'])!=check['sha256']:
                    raise ValueError('MISSING_OR_CHANGED_SOURCE')
                targets.append(older_target(check))
            except (ValueError,StopIteration,KeyError) as exc:
                unresolved.append({'id':check['id'],'reason':str(exc)})
    ledger = output/'events.jsonl'
    captured = datetime.now(timezone.utc).isoformat()
    for r in json.loads(EXISTING.read_text())['records']:
        append_event(ledger, {'company':r['company'],'kind':'ACTUAL_MARGIN','quarter':r['quarter'],
            'target_basis':r['target_basis'],'actual_cpg':r['actual_cpg'],'start':r['start'],'end':r['end'],
            'available_at':r['available_at'],'captured_at':captured,'source_url':r['source_url'],
            'source_sha256':r['source_sha256'],'historical_vintage_verified':False,
            'capture_note':'Imported existing source-linked historical archive; not original publication capture'})
    for r in targets:
        append_event(ledger,{'company':r['company'],'kind':'ACTUAL_MARGIN','quarter':r['quarter'],
            'target_basis':r['target_basis'],'actual_cpg':r['actual_cpg'],'start':r['start'],'end':r['end'],
            'available_at':r['available_at'],'captured_at':r['captured_at'],'source_url':r['source_url'],
            'source_sha256':r['sha256'],'historical_vintage_verified':False})
        if r.get('perimeter_context'):
            append_event(ledger,{'company':r['company'],'kind':'PERIMETER_CONTEXT','quarter':r['quarter'],
                'target_basis':r['target_basis'],'available_at':r['available_at'],'captured_at':r['captured_at'],
                'source_url':r['source_url'],'source_sha256':r['sha256'],'passages':r['perimeter_context'],
                'numeric_adjustment_authorized':False})
    for r in json.loads(SEED.read_text())['guidance_checks']:
        append_event(ledger,{'company':r['company'],'kind':'GUIDANCE','quarter':r['target_quarter'],
            'target_basis':targets[0]['target_basis'],'available_at':r['available_at'],'captured_at':captured,
            'low_cpg':r['low_cpg'],'high_cpg':r['high_cpg'],'source_url':r['source_url'],
            'source_sha256':r['sha256'],'interpretation':r['interpretation'],
            'historical_vintage_verified':False})
    events = read_ledger(ledger)
    forecasts = []
    blocked = []
    for r in sorted(targets,key=lambda e:(e['end'],e['company'])):
        prediction = forecast(r,events)
        if prediction is None:
            blocked.append({'company':r['company'],'quarter':r['quarter'],'reason':'INSUFFICIENT_PUBLISHED_HISTORY_OR_SEASONAL_ANCHOR'})
        else:
            forecasts.append(prediction)
    def save(name,value):
        (output/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    save('frozen_inputs.json',manifest)
    save('reviewed_targets.json',{'targets':targets,'unresolved':unresolved})
    save('frozen_predictions.json',{'role':json.loads(SPEC.read_text())['role'],'forecasts':forecasts})
    actual = {(r['company'],r['quarter']):r['actual_cpg'] for r in targets}
    scored = [r | {'actual_cpg':actual[(r['company'],r['quarter'])]} for r in forecasts]
    result = {'production_changed':False,'strict_historical_vintage_verified':False,
        'groups':{c:{m:metrics([r for r in scored if r['company']==c],m) for m in ['seasonal','recent','blend']} for c in ['ARKO','CAPL']},
        'scored_rows':scored,'blocked':blocked,'unresolved_sources':unresolved,
        'ledger_events':len(events),'automatic_promotion':False}
    save('results.json',result)
    print(json.dumps(result['groups'],indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True,type=Path)
    build(parser.parse_args().out)
