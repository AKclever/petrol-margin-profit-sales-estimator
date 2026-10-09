"""Separate reviewed older peer targets and expanding-window surprises."""
import argparse
from datetime import date
import json
from pathlib import Path

from musa_nowcast.couchetard_peer import fiscal_predictions
from musa_nowcast.data import QuarterActual, RegionWeight, load_weights, load_actuals
from musa_nowcast.joint_all_features import market_from_json
from musa_nowcast.peer_surprise import select_peer
from musa_nowcast.pit_replay import now,save
from musa_nowcast.prospective import sha
from scripts.expand_older_peer_evidence import caseys_target


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();root=args.out;root.mkdir(parents=True,exist_ok=False)
    raw_checks=json.loads((args.source/'source_checks.json').read_text())['checks']
    candidates={'CASY':{},'ATD':{}};checks=[]
    for source in raw_checks:
        if source['status']!='ORIGINAL_RELEASE_CAPTURED':continue
        path=args.source/source['raw_file']
        if sha(path)!=source['sha256']:raise ValueError('Raw source hash changed')
        target=caseys_target(path.read_bytes()) if source['peer']=='CASY' else source['target']
        usable=target['status']=='VERIFIED_DIRECT_QUARTERLY_REPORTED_BASIS' if source['peer']=='CASY' else target['status']=='PARSED_FEE_RECONCILED_PENDING_REVIEW'
        checks.append({'peer':source['peer'],'period':source['period'],'source_url':source['source_url'],'raw_sha256':sha(path),'review_status':target['status']})
        if not usable or not source['period']:continue
        q=source['period']['quarter'];end=date.fromisoformat(source['period']['end'])
        if source['peer']=='CASY':
            start=date(end.year-1,11,1) if end.month==1 else date(end.year,end.month-2,1)
            row={'quarter':q,'start':str(start),'end':str(end),'retail_margin_cpg':target['reported_margin_cpg'],
                 'target_basis':target['target_basis'],'evidence':target['evidence'],'rin_context':target['rin_context']}
        else:row=target.copy()
        row.update(available_at=source['available_at'],source_url=source['source_url'],source_sha256=sha(path))
        candidates[source['peer']].setdefault(q,[]).append(row)
    histories={};unresolved=[]
    for peer,by_q in candidates.items():
        rows=[]
        for q,group in sorted(by_q.items()):
            if len({r['retail_margin_cpg'] for r in group})>1:
                unresolved.append({'peer':peer,'quarter':q,'reason':'CONFLICTING_ORIGINAL_REPORTED_MARGINS'});continue
            rows.append(min(group,key=lambda r:r['available_at']))
        histories[peer]=rows
    # Merge into separate research histories; never edit production/peer CSVs.
    market_json=Path('data/history_floor_basis/2026-10-07_evaluation_v6/normalized_market.json')
    market=market_from_json(json.loads(market_json.read_text())['regular'])
    existing_atd=json.loads(Path('data/couchetard_peer/2026-10-07_v3/history.json').read_text())['rows']
    combined_atd={r['quarter']:r for r in existing_atd}|{r['quarter']:r for r in histories['ATD']}
    existing_casy=load_actuals('data/caseys/actuals.csv')
    casy_dates=json.loads(Path('data/peer_surprise/2026-10-07_v2/sources/CASY_source_checks.json').read_text())['verified']
    casy_targets={a.quarter:a for a in existing_casy if a.quarter in casy_dates}
    for r in histories['CASY']:
        casy_targets[r['quarter']]=QuarterActual(r['quarter'],date.fromisoformat(r['start']),date.fromisoformat(r['end']),r['retail_margin_cpg'])
        casy_dates[r['quarter']]={'available_at':r['available_at'],'url':r['source_url'],'sha256':r['source_sha256'],'target_basis':r['target_basis']}
    dates_atd={q:{'available_at':r['available_at'],'url':r['source_url'],'sha256':r['source_sha256']} for q,r in combined_atd.items()}
    atd_targets=[QuarterActual(r['quarter'],date.fromisoformat(r['start']),date.fromisoformat(r['end']),r['retail_margin_cpg']) for r in sorted(combined_atd.values(),key=lambda r:r['end'])]
    save(root/'frozen_inputs.json',{'created_at':now(),'market_sha256':sha(market_json),'source_checks_sha256':sha(args.source/'source_checks.json'),
           'code_sha256':sha(Path(__file__)),'parser_sha256':sha(Path('scripts/expand_older_peer_evidence.py')),
           'reviewed_histories':histories})
    # Skip targets without an earlier same fiscal-quarter anchor; gaps must
    # not turn the previous target's forecast into the current prediction.
    cp,ce=fiscal_predictions(market,load_weights('data/caseys/weights.csv'),sorted(casy_targets.values(),key=lambda a:a.end),casy_dates)
    ap,ae=fiscal_predictions(market,[RegionWeight(r,1/3) for r in ['East Coast','Midwest','Gulf Coast']],atd_targets,dates_atd)
    big=['2021Q2','2021Q4','2022Q1','2022Q3','2023Q3','2026Q2'];coverage=[]
    from musa_nowcast.history_floor_basis import bounds
    for q in big:
        start,end=bounds(q)
        coverage.append({'quarter':q,'caseys':select_peer(cp,start,end),'couchetard':select_peer(ap,start,end),
                         'margin_correction_fitted':False})
    original=json.loads(Path('data/history_floor_basis/2026-10-07_evaluation_v6/results.json').read_text())['baseline_rows']
    comparisons=[]
    for r in original:
        start,end=bounds(r['quarter']);cpeer,apeer=select_peer(cp,start,end),select_peer(ap,start,end)
        error=r['actual_cpg']-r['prediction_cpg']
        comparisons.append({'quarter':r['quarter'],'actual_minus_original_cpg':error,
            'original_six_large_miss':r['quarter'] in big,
            'caseys_surprise_cpg':cpeer['surprise_cpg'] if cpeer else None,
            'couchetard_surprise_cpg':apeer['surprise_cpg'] if apeer else None,
            'both_peer_directions_match_error':(cpeer['surprise_cpg']*error>0 and apeer['surprise_cpg']*error>0) if cpeer and apeer else None,
            'overlap_periods':{'caseys':cpeer,'couchetard':apeer},'evaluation':'DESCRIPTIVE_NOT_A_FITTED_FORECAST'})
    save(root/'review.json',{'created_at':now(),'older_targets':histories,'source_reviews':checks,'unresolved_conflicts':unresolved,
        'caseys_peer_predictions':cp,'couchetard_peer_predictions':ap,'peer_prediction_exclusions':ce+ae,
        'original_big_miss_peer_evidence':coverage,'all_quarter_peer_diagnostics':comparisons,'production_changed':False,
        'evaluation_role':'CURRENT_VINTAGE_PUBLICATION_FILTERED_PEER_EVIDENCE_NOT_STRICT_PIT',
        'limitation':'Caseys reported fuel margin includes RIN effects; not a direct MUSA retail-margin target. No cross-regime residual correction fitted.'})
    print('Older targets:',{k:len(v) for k,v in histories.items()},'Peer surprises:',len(cp),len(ap))


if __name__=='__main__':main()
