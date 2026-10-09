"""Append-only earnings evidence and deterministic multi-company replay."""
import argparse
from collections import defaultdict
from datetime import date, timedelta
import json
import math
import fcntl
from pathlib import Path

from .anchor_reliability import ROOT, tail_metrics
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .timing import _metrics

HISTORY=Path('data/historical_evidence_extension/2026-10-08_review_v3/reviewed_peer_history.json')
SPEC=Path('data/earnings_event_replay_spec_v1.json')
BASES={'MUSA':'MUSA_RETAIL','CASY':'CASEYS_REPORTED_FUEL_EXCLUDING_CARD_FEES_INCLUDES_RIN',
       'ATD':'US_COMPANY_OPERATED_BEFORE_PAYMENT_FEES'}


def era(row):
    return 'earlier' if row['start']<'2020-01-01' else 'transition' if row['start']<'2021-01-01' else 'modern'


def validate(row):
    if row['company'] not in BASES or row['target_basis']!=BASES[row['company']]:
        raise ValueError('UNSUPPORTED_COMPANY_OR_TARGET_BASIS')
    start,end=date.fromisoformat(row['start']),date.fromisoformat(row['end'])
    if start>end or row['forecast_information_cutoff']>row['end']:
        raise ValueError('INVALID_PERIOD_OR_FORECAST_CUTOFF')
    if row.get('available_at') and row['available_at']<=row['end']:
        raise ValueError('OUTCOME_PUBLICATION_NOT_AFTER_PERIOD')
    date.fromisoformat(row['forecast_information_cutoff'])
    if row.get('available_at'):date.fromisoformat(row['available_at'])
    for key in ['prediction_cpg','actual_cpg']:
        if row.get(key) is not None and not math.isfinite(float(row[key])):
            raise ValueError('NONFINITE_MARGIN')
    if row.get('actual_cpg') is not None and not row.get('available_at'):
        raise ValueError('ACTUAL_WITHOUT_PUBLICATION_DATE')
    if not row.get('source_sha256') or not row.get('source_url'):
        raise ValueError('MISSING_SOURCE_PROVENANCE')


def load_archive():
    history=json.loads(HISTORY.read_text());records=[]
    for company in ['CASY','ATD']:
        for row in history['peer_predictions'][company]:
            source=row['source']
            records.append(row | {'company':company,'target_basis':BASES[company],
                'source_url':source['url'],'source_sha256':source['sha256']})
    targets={r['quarter']:r for r in json.loads((ROOT/'historical_targets.json').read_text())['quarters']}
    for row in json.loads((ROOT/'results.json').read_text())['baseline_rows']:
        target=targets[row['quarter']]
        records.append(row | {'company':'MUSA','target_basis':BASES['MUSA'],'start':target['quarter_start'],
            'end':target['quarter_end'],'available_at':target['available_at'],
            'forecast_information_cutoff':target['quarter_end'],
            'source_url':target['source_url'],'source_sha256':target['source_sha256']})
    for r in records:validate(r)
    return sorted(records,key=lambda r:(r['end'],r['company']))


def overlap(target, donor):
    return max(0,(min(date.fromisoformat(target['end']),date.fromisoformat(donor['end']))-
                  max(date.fromisoformat(target['start']),date.fromisoformat(donor['start']))).days+1)


def select(target, donor_company, records, cutoff):
    rows=[r for r in records if r['company']==donor_company and r.get('actual_cpg') is not None
          and r['available_at']<cutoff and r['end']<cutoff and overlap(target,r)>0]
    return max(rows,key=lambda r:(r['available_at'],r['end'])) if rows else None


def donor_input(target, donor):
    days=overlap(target,donor)
    fraction=days/((date.fromisoformat(target['end'])-date.fromisoformat(target['start'])).days+1)
    return fraction*(donor['actual_cpg']-donor['prediction_cpg'])


def loading(target, donor_company, records, cutoff):
    pairs=[]
    for earlier in records:
        if (earlier['company']!=target['company'] or earlier['end']>=target['start'] or
                era(earlier)!=era(target) or earlier.get('actual_cpg') is None or earlier['available_at']>=cutoff):
            continue
        donor=select(earlier,donor_company,records,earlier['available_at'])
        if donor is None:continue
        pairs.append({'recipient_quarter':earlier['quarter'],'recipient_available_at':earlier['available_at'],
            'donor_quarter':donor['quarter'],'donor_available_at':donor['available_at'],
            'x':donor_input(earlier,donor),'y':earlier['actual_cpg']-earlier['prediction_cpg']})
    if len(pairs)<8:return None,pairs
    raw=sum(r['x']*r['y'] for r in pairs)/(10+sum(r['x']**2 for r in pairs))
    return min(1.,max(0.,raw)),pairs


def checkpoint(target, records, cutoff):
    if cutoff<=target['end']:
        raise ValueError('BASELINE_NOT_AVAILABLE_BEFORE_PERIOD_END')
    if target.get('available_at') and cutoff>target['available_at']:
        raise ValueError('RECIPIENT_ALREADY_REPORTED')
    transfers=[];blocked=[]
    for company in BASES:
        if company==target['company']:continue
        donor=select(target,company,records,cutoff)
        if donor is None:
            blocked.append({'donor':company,'reason':'NO_PUBLISHED_OVERLAPPING_PEER'});continue
        coefficient,pairs=loading(target,company,records,cutoff)
        if coefficient is None:
            blocked.append({'donor':company,'reason':'FEWER_THAN_EIGHT_EARLIER_SAME_REGIME_PAIRS','pairs':len(pairs)});continue
        x=donor_input(target,donor)
        transfers.append({'donor':company,'donor_quarter':donor['quarter'],'donor_available_at':donor['available_at'],
            'donor_source_url':donor['source_url'],'donor_source_sha256':donor['source_sha256'],
            'donor_target_basis':donor['target_basis'],'overlap_days':overlap(target,donor),
            'overlap_weighted_surprise_cpg':x,'loading':coefficient,'training_pairs':pairs,
            'transfer_cpg':coefficient*x})
    correction=.5*sum(t['transfer_cpg'] for t in transfers)/len(transfers) if transfers else 0.
    return {'company':target['company'],'quarter':target['quarter'],'information_cutoff':cutoff,
        'baseline_cpg':target['prediction_cpg'],'prediction_cpg':target['prediction_cpg']+correction,
        'correction_cpg':correction,'target_basis':target['target_basis'],'transfers':transfers,'blocked':blocked,
        'status':'SHADOW' if transfers else 'UNCHANGED_NO_ELIGIBLE_TRANSFER',
        'evaluation_role':'DEVELOPMENTAL_CURRENT_VINTAGE_PUBLICATION_FILTERED_NOT_STRICT_PIT'}


def replay(records):
    dates=sorted(set(r['available_at'] for r in records if r.get('actual_cpg') is not None))
    ledger=[];event_diagnostics=[]
    for target in records:
        checkpoints=[checkpoint(target,records,str(date.fromisoformat(target['end'])+timedelta(days=1)))]
        for published in dates:
            cutoff=str(date.fromisoformat(published)+timedelta(days=1))
            if cutoff<=checkpoints[0]['information_cutoff'] or (target.get('available_at') and cutoff>target['available_at']):continue
            events=[r for r in records if r['available_at']==published and r['company']!=target['company'] and overlap(target,r)>0]
            if not events:continue
            new=checkpoint(target,records,cutoff)
            new['trigger_events']=[{'company':r['company'],'quarter':r['quarter'],'available_at':published} for r in events]
            before=checkpoints[-1]['prediction_cpg'];checkpoints.append(new)
            if target.get('actual_cpg') is not None:
                event_diagnostics.append({'company':target['company'],'quarter':target['quarter'],'cutoff':cutoff,
                    'before_cpg':before,'after_cpg':new['prediction_cpg'],
                    'abs_error_improvement_cpg':abs(target['actual_cpg']-before)-abs(target['actual_cpg']-new['prediction_cpg'])})
        if target.get('available_at') and checkpoints[-1]['information_cutoff']<target['available_at']:
            checkpoints.append(checkpoint(target,records,target['available_at']))
        ledger.extend(checkpoints)
    return ledger,event_diagnostics


def evaluate(output, dataset=None):
    output.mkdir(parents=True,exist_ok=False)
    files=[SPEC,Path(__file__),HISTORY,ROOT/'results.json',ROOT/'historical_targets.json',Path('musa_nowcast/timing.py')]
    if dataset:files.append(dataset)
    save(output/'frozen_inputs.json',{'created_at':now(),'files':[{'path':str(p),'sha256':sha(p)} for p in files]})
    (output/'inputs').mkdir()
    for i,p in enumerate(files):
        with (output/'inputs'/f'{i}_{p.name}').open('xb') as h:h.write(p.read_bytes())
    records=json.loads(dataset.read_text())['records'] if dataset else load_archive()
    for r in records:validate(r)
    if len({(r['company'],r['quarter']) for r in records})!=len(records):raise ValueError('DUPLICATE_TARGET')
    save(output/'dataset.json',{'records':records})
    ledger,events=replay(records)
    save(output/'frozen_checkpoints.json',{'frozen_at':now(),'checkpoints':ledger})
    final={(r['company'],r['quarter']):r for r in ledger};groups={};rows=[]
    for company in BASES:
        baseline={r['quarter']:r for r in records if r['company']==company and r.get('actual_cpg') is not None}
        shadows={q:b|final[(company,q)]|{'original_prediction_cpg':b['prediction_cpg'],
            'direction_correct':NowcastEngine._direction(final[(company,q)]['prediction_cpg']-b['seasonal_cpg'])==
                                NowcastEngine._direction(b['actual_cpg']-b['seasonal_cpg'])} for q,b in baseline.items()}
        rows.extend(shadows.values())
        for modern in [False,True]:
            qs=sorted(q for q in baseline if not modern or era(baseline[q])=='modern')
            eligible=[q for q in qs if shadows[q]['transfers']]
            label=company+('_modern' if modern else '_all')
            groups[label]={'all_targets':len(qs),'eligible_transfers':len(eligible),
                'all_metrics':_metrics(baseline,shadows,qs) if qs else None,
                'eligible_metrics':_metrics(baseline,shadows,eligible) if eligible else None,
                'tails':tail_metrics(baseline,shadows,eligible),
                'eligible_quarters':eligible}
    result={'role':json.loads(SPEC.read_text())['role'],'groups':groups,'rows':rows,'event_diagnostics':events,
        'event_count':len(events),'production_changed':False,'automatic_promotion':False,'strict_market_pit_verified':False,
        'live_scheduling_deployed':False}
    save(output/'results.json',result)
    print(json.dumps(groups,indent=2))
    return result


def ingest(ledger, event_file):
    """Append supplied evidence once; never fetch, change a forecast or rewrite history."""
    event=json.loads(event_file.read_text());validate(event)
    if event.get('actual_cpg') is None:raise ValueError('EARNINGS_EVENT_REQUIRES_REPORTED_ACTUAL')
    raw=Path(event['raw_source_path'])
    if sha(raw)!=event['source_sha256']:raise ValueError('RAW_SOURCE_HASH_MISMATCH')
    if event['captured_at'][:10]<event['available_at']:raise ValueError('CAPTURE_BEFORE_RELEASE')
    ledger.parent.mkdir(parents=True,exist_ok=True)
    with ledger.open('a+') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        handle.seek(0);old=[json.loads(line) for line in handle.read().splitlines()]
        matching=[r for r in old if (r['company'],r['quarter'])==(event['company'],event['quarter'])]
        if matching:
            if matching[0]!=event:raise ValueError('CONFLICTING_EXISTING_EVENT')
            return 'ALREADY_ARCHIVED'
        handle.write(json.dumps(event,sort_keys=True)+'\n');handle.flush()
    return 'APPENDED'


def update(dataset, ledger, cutoff, output):
    """Create a new immutable checkpoint from supplied forecasts and archived events."""
    date.fromisoformat(cutoff)
    records=json.loads(dataset.read_text())['records']
    indexed={(r['company'],r['quarter']):r for r in records}
    if len(indexed)!=len(records):raise ValueError('DUPLICATE_TARGET')
    for line in ledger.read_text().splitlines():
        event=json.loads(line);validate(event)
        if sha(Path(event['raw_source_path']))!=event['source_sha256']:raise ValueError('RAW_SOURCE_HASH_MISMATCH')
        if event['available_at']>=cutoff:continue
        key=(event['company'],event['quarter'])
        if key in indexed:
            existing=indexed[key]
            if any(existing[k]!=event[k] for k in ['prediction_cpg','start','end','target_basis']):
                raise ValueError('EVENT_BASELINE_OR_PERIOD_CONFLICT')
            if existing.get('actual_cpg') is not None and existing['actual_cpg']!=event['actual_cpg']:
                raise ValueError('CONFLICTING_REPORTED_ACTUAL')
        indexed[key]=event
    for r in indexed.values():validate(r)
    records=list(indexed.values())
    checkpoints=[checkpoint(r,records,cutoff) for r in records if r['end']<cutoff and
                 (not r.get('available_at') or r['available_at']>=cutoff)]
    output.mkdir(parents=True,exist_ok=False)
    save(output/'checkpoint.json',{'created_at':now(),'information_cutoff':cutoff,'checkpoints':checkpoints,
        'input_hashes':{str(p):sha(p) for p in [dataset,ledger,SPEC,Path(__file__)]},
        'production_changed':False,'strict_market_pit_verified':False,'status':'RESEARCH_SHADOW_ONLY'})
    return checkpoints


if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True)
    r=s.add_parser('replay');r.add_argument('--out',required=True,type=Path);r.add_argument('--dataset',type=Path)
    i=s.add_parser('ingest');i.add_argument('--ledger',required=True,type=Path);i.add_argument('--event',required=True,type=Path)
    u=s.add_parser('update');u.add_argument('--dataset',required=True,type=Path);u.add_argument('--ledger',required=True,type=Path)
    u.add_argument('--as-of',required=True);u.add_argument('--out',required=True,type=Path)
    args=p.parse_args()
    if args.command=='replay':evaluate(args.out,args.dataset)
    elif args.command=='ingest':print(ingest(args.ledger,args.event))
    else:print(json.dumps(update(args.dataset,args.ledger,args.as_of,args.out),indent=2))
