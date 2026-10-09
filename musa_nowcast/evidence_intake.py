"""Manual pump evidence, disclosure review queues and prospective selection.

No scraping, station inference, automatic numeric classification or scoring.
"""
import argparse
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import re

from .history_floor_basis import bounds
from .pit_replay import save, now
from .prospective import timestamp, sha
from .revenue_gap_audit import rows_from_html


def validate_panel(panel):
    if panel.get('collection_mode')!='MANUAL_ONLY':raise ValueError('Automated source permission not established')
    pairs=panel.get('pairs',[])
    if not pairs:raise ValueError('No verified fixed station pairs')
    ids=set()
    for pair in pairs:
        for key in ['pair_id','region','musa_station_id','competitor_station_id','musa_address','competitor_address','station_identity_source']:
            if not pair.get(key):raise ValueError('Incomplete fixed station identities')
        if pair['pair_id'] in ids:raise ValueError('Duplicate station pair')
        ids.add(pair['pair_id'])
    return ids


def capture_manual(panel_path, observation_path, output):
    panel=json.loads(panel_path.read_text());ids=validate_panel(panel)
    record=json.loads(observation_path.read_text())
    if record['pair_id'] not in ids:raise ValueError('Station pair outside frozen panel')
    if record.get('collection_mode')!='MANUAL_ONLY':raise ValueError('Non-manual observation not permitted')
    for key in ['grade','payment_basis','reward_basis','source_locator','observer_reference','observed_at','musa_observed_at','competitor_observed_at','available_at','raw_path','raw_sha256']:
        if not record.get(key):raise ValueError('Missing observation basis/evidence')
    observed,available=timestamp(record['observed_at']),timestamp(record['available_at'])
    if not observed<=available<=timestamp(now()):raise ValueError('Invalid observation timestamps')
    station_times=[timestamp(record[key]) for key in ['musa_observed_at','competitor_observed_at']]
    if max(station_times)!=observed:raise ValueError('Paired timestamp must be latest station observation')
    if (max(station_times)-min(station_times)).total_seconds()>900:raise ValueError('Station observations more than 15 minutes apart')
    for name in ['musa_price_usd_per_gallon','competitor_price_usd_per_gallon']:
        value=record.get(name)
        if not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:raise ValueError('Invalid pump price')
    raw=Path(record['raw_path'])
    if sha(raw)!=record['raw_sha256']:raise ValueError('Raw evidence hash mismatch')
    output.mkdir(parents=True,exist_ok=False)
    for name,path in [('panel.json',panel_path),('observation.json',observation_path),('raw_evidence',raw)]:
        with (output/name).open('xb') as f:f.write(path.read_bytes())
    save(output/'capture.json',{'captured_at':now(),'panel_sha256':sha(panel_path),'record':record,
        'paired_difference_cpg':100*(record['musa_price_usd_per_gallon']-record['competitor_price_usd_per_gallon']),
        'representative_musa_gallon_weighted_price':False})


def queue_disclosures(manifest_path, output):
    manifest=json.loads(manifest_path.read_text());records=[]
    for source in manifest['sources']:
        path=manifest_path.parent/source['raw_file']
        if sha(path)!=source['raw_sha256']:raise ValueError('Disclosure raw hash mismatch')
        tree,_=rows_from_html(path.read_bytes());text=' '.join(tree.text_content().split())
        matches=[text[max(0,m.start()-120):m.end()+180] for m in re.finditer(r'(?:retail|all.in|total fuel).{0,20}margin',text,re.I)]
        records.append({'source':source,'candidate_passages':matches[:20],
            'status':'PENDING_PERIOD_AND_TARGET_REVIEW' if matches else 'NO_MARGIN_PASSAGE_MATCH_IN_CHECKED_SOURCE',
            'negative_disclosure_conclusion_authorized':False,'numeric_assimilation_authorized':False,
            'required_for_assimilation':['verified retail target and numeric bounds','quarter/period dates','publication/availability timestamp',
                  'frozen PIT_MODELLED_GALLON_SHARE or observed share','same-cutoff remaining forecast for exact undisclosed period']})
    save(output,{'created_at':now(),'manifest_sha256':sha(manifest_path),'source_scope':manifest['source_scope'],'rows':records,
        'frozen_historical_taxonomy_changed':False,'automatic_numeric_classification':False})


def primary_eligible(checkpoint):
    if checkpoint.get('evaluation_role')!='PROSPECTIVE_CAPTURE':return False
    _,end=bounds(checkpoint['quarter'])
    created=timestamp(checkpoint['forecast_created_at'])
    lower=datetime.combine(end+timedelta(days=3),datetime.min.time(),tzinfo=created.tzinfo)
    upper=datetime.combine(end+timedelta(days=8),datetime.min.time(),tzinfo=created.tzinfo)
    forecast=checkpoint.get('production_forecast') or {}
    return lower<=created<upper and forecast.get('coverage')==1 and checkpoint.get('regime_risk_state') is not None


def prospective_inventory(root, output):
    checkpoints=[]
    for path in root.rglob('checkpoint.json'):
        item=json.loads(path.read_text())
        if item.get('evaluation_role')!='PROSPECTIVE_CAPTURE':continue
        checkpoints.append({'path':str(path),'sha256':sha(path),'quarter':item['quarter'],
           'forecast_created_at':item['forecast_created_at'],'primary_eligible':primary_eligible(item),
           'production_present':item.get('production_forecast') is not None,
           'risk_present':item.get('regime_risk_state') is not None,
           'status':item.get('market_forecast_status','CAPTURED')})
    selected={}
    for item in sorted(checkpoints,key=lambda r:(r['forecast_created_at'],r['path'])):
        if item['primary_eligible']:selected.setdefault(item['quarter'],item)
    scores=[]
    for path in root.rglob('score.json'):
        score=json.loads(path.read_text())
        picked=selected.get(score.get('quarter'))
        if score.get('evaluation_role')!='PROSPECTIVE_SCORE' or not picked or score.get('checkpoint_sha256')!=picked['sha256']:continue
        cp=json.loads(Path(picked['path']).read_text())
        if timestamp(score['reported_at'])<=timestamp(cp['forecast_created_at']):raise ValueError('Score predates forecast')
        scores.append({'quarter':score['quarter'],'risk_level':cp['regime_risk_state']['overall_risk'],
                      'production_absolute_error_cpg':score['absolute_errors_cpg']['production'],
                      'shadow_absolute_error_cpg':score['absolute_errors_cpg']['shadow']})
    from statistics import mean
    grouped={level:{'n':len(group),'production_mae_cpg':mean(r['production_absolute_error_cpg'] for r in group) if group else None}
             for level in ['NORMAL','ELEVATED'] for group in [[r for r in scores if r['risk_level']==level]]}
    save(output,{'created_at':now(),'checkpoints':checkpoints,'primary_selection':selected,'primary_scores':scores,'risk_groups':grouped,
        'selection_code_sha256':sha(Path(__file__)),
        'selection_spec_sha256':sha(Path('data/miss_evidence_workstream_spec_v1.json')),
        'primary_rule':'First complete capture 3-7 UTC days after quarter end; score only with verified later earnings',
        'weekly_checkpoints_independent_trials':False,'risk_rules_changed':False,'risk_predictiveness_established':False,
        'automatic_scoring':False,'scheduler_deployed_by_this_run':False})


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    q=sub.add_parser('disclosures');q.add_argument('--manifest',type=Path,required=True);q.add_argument('--out',type=Path,required=True)
    q=sub.add_parser('prospective');q.add_argument('--root',type=Path,default=Path('data/prospective'));q.add_argument('--out',type=Path,required=True)
    q=sub.add_parser('manual-price');q.add_argument('--panel',type=Path,required=True);q.add_argument('--observation',type=Path,required=True);q.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.action=='disclosures':queue_disclosures(a.manifest,a.out)
    elif a.action=='prospective':prospective_inventory(a.root,a.out)
    else:capture_manual(a.panel,a.observation,a.out)
