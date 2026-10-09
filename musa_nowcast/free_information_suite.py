"""Coverage-aware free-information experiments; no production changes."""
import argparse
from datetime import date
import json
import math
from pathlib import Path
from statistics import mean

import xlrd

from .anchor_reliability import ROOT, tail_metrics
from .daily_capture import fetch
from .data import load_weights
from .history_floor_basis import bounds, regime
from .joint_all_features import market_from_json
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .evidence_intake import validate_panel

SPEC=Path('data/free_information_suite_spec_v1.json')
SERIES='EMA_EPMR_PRG_NUS_DPG'
URL=f'https://www.eia.gov/dnav/pet/hist_xls/{SERIES}m.xls'


def parse_rack(raw):
    book=xlrd.open_workbook(file_contents=raw);sheet=book.sheet_by_name('Data 1')
    if sheet.cell_value(1,1)!=SERIES:raise ValueError('rack series identifier mismatch')
    result={}
    for i in range(sheet.nrows):
        if sheet.cell_type(i,0)!=xlrd.XL_CELL_DATE or sheet.cell_type(i,1)!=xlrd.XL_CELL_NUMBER:continue
        source_day=xlrd.xldate_as_datetime(sheet.cell_value(i,0),book.datemode).date()
        # EIA labels monthly periods with the 15th, not a publication timestamp.
        day=source_day.replace(day=1)
        value=100*float(sheet.cell_value(i,1))
        if source_day.day not in (1,15) or day in result or not math.isfinite(value) or value<=0:
            raise ValueError('invalid monthly rack observation')
        result[day]=value
    if not result:raise ValueError('empty rack history')
    return result


def rack_adjustment(quarter, monthly, engine):
    start,end=bounds(quarter);old_start,old_end=bounds(f'{int(quarter[:4])-1}{quarter[4:]}')
    dates=[date(start.year,m,1) for m in range(start.month,start.month+3)]
    old_dates=[date(d.year-1,d.month,1) for d in dates]
    if any(d not in monthly for d in dates+old_dates):raise ValueError('MISSING_CURRENT_OR_PRIOR_RACK_MONTHS')
    current=engine._weekly_basket(start,end);prior=engine._weekly_basket(old_start,old_end)
    if engine.features(start,end).coverage!=1 or engine.features(old_start,old_end).coverage!=1:
        raise ValueError('MISSING_COMPLETE_SPOT_QUARTER')
    rack_delta=mean(monthly[d] for d in dates)-mean(monthly[d] for d in old_dates)
    spot_delta=mean(r[2] for r in current)-mean(r[2] for r in prior)
    basis_delta=rack_delta-spot_delta
    return {'rack_months':list(map(str,dates)),'prior_rack_months':list(map(str,old_dates)),
            'rack_yoy_change_cpg':rack_delta,'spot_yoy_change_cpg':spot_delta,
            'basis_yoy_change_cpg':basis_delta,'correction_cpg':-.5*basis_delta,
            'company_rack_cost_observed':False,'historical_available_at_verified':False}


def groups(baseline,shadow,quarters):
    large=[q for q in quarters if abs(baseline[q]['actual_cpg']-baseline[q]['prediction_cpg'])>=5]
    ordinary=[q for q in quarters if q not in large]
    return {'quarters':quarters,'metrics':tail_metrics(baseline,shadow,quarters),
            'original_large_quarters':large,'large_group':tail_metrics(baseline,shadow,large),
            'ordinary_group':tail_metrics(baseline,shadow,ordinary)}


def archived_mechanical_examples():
    paths=sorted(Path('data/historical_pit').glob('**/scoring/score.json'))
    rows=[]
    for path in paths:
        score=json.loads(path.read_text());forecast_path=path.parent.parent/'forecast.json'
        if not forecast_path.exists():continue
        forecast=json.loads(forecast_path.read_text())
        expected=score.get('frozen_forecast_sha256')
        if expected is None or sha(forecast_path)!=expected:raise ValueError('archived mechanical score link mismatch')
        share=forecast['observed_gallon_share'];remaining=forecast['remaining_margin_forecast']
        disclosure_source=forecast_path
        if 'disclosed_margin_cpg' in forecast:
            disclosed=forecast['disclosed_margin_cpg']
        else:
            disclosure_source=forecast_path.parent.parent/'capture.json'
            capture=json.loads(disclosure_source.read_text())
            if capture['case']['quarter']!=score['quarter']:raise ValueError('disclosure quarter mismatch')
            disclosed=capture['case']['disclosed_margin_cpg']
        point=share*disclosed+(1-share)*remaining
        if abs(point-score['shadow_forecast'])>1e-9:raise ValueError('mechanical arithmetic mismatch')
        rows.append({'quarter':score['quarter'],'forecast_path':str(forecast_path),'forecast_sha256':sha(forecast_path),
                     'score_path':str(path),'score_sha256':sha(path),'shadow_forecast_cpg':point,
                     'shadow_abs_error_cpg':score['shadow_abs_error'],'production_abs_error_cpg':score['production_abs_error'],
                     'gallon_share_evidence_type':forecast['gallon_share_evidence_type'],
                     'disclosed_margin_cpg':disclosed,'disclosure_precision':forecast.get('disclosure_precision','NUMERIC_COMPANY_DISCLOSURE'),
                     'disclosure_input_path':str(disclosure_source),'disclosure_input_sha256':sha(disclosure_source),
                     'role':'RETROSPECTIVE_MECHANICAL_REPLAY','new_validation':False})
    return rows


def evaluate(output, regional):
    output.mkdir(parents=True,exist_ok=False);(output/'inputs').mkdir()
    paths=[SPEC,Path(__file__),ROOT/'results.json',ROOT/'normalized_market.json',Path('data/weights.csv'),
           regional/'results.json',Path('data/daily_prices/2026-10-07_v4/manifest.json'),
           Path('data/pump_price_panel_plan_v1.json'),Path('data/partial_quarter_disclosure_audit.csv'),
           Path('data/deep_miss_diagnosis/2026-10-08_v1/new_disclosure_candidates.json'),
           Path('data/combined_challengers/2026-10-08_v2/results.json')]
    for i,p in enumerate(paths):
        with (output/'inputs'/f'{i}_{p.name}').open('xb') as handle:handle.write(p.read_bytes())
    save(output/'frozen_inputs.json',{'frozen_at':now(),'files':[{'path':str(p),'sha256':sha(p)} for p in paths]})
    raw=fetch(URL);rack_path=output/'rack.xls'
    with rack_path.open('xb') as handle:handle.write(raw)
    monthly=parse_rack(raw)
    save(output/'rack_capture.json',{'source_url':URL,'captured_at':now(),'sha256':sha(rack_path),
          'series_id':SERIES,'units':'cents_per_gallon_excluding_taxes',
          'vintage_status':'CURRENT_DOWNLOAD_NOT_HISTORICAL_PIT','available_at_method':'CAPTURE_ONLY',
          'date_normalization':'EIA monthly period labels on day15 mapped to month start, never publication dates',
          'first_observed_month':str(min(monthly)),'last_observed_month':str(max(monthly)),
          'rows':[{'observed_month':str(d),'rack_cpg':v} for d,v in sorted(monthly.items())]})
    history=json.loads((ROOT/'results.json').read_text());baseline={r['quarter']:r for r in history['baseline_rows']}
    engine=NowcastEngine(market_from_json(json.loads((ROOT/'normalized_market.json').read_text())['regular']),load_weights('data/weights.csv'),[])
    features={};blocked=[]
    for q in baseline:
        try:features[q]=rack_adjustment(q,monthly,engine)
        except ValueError as exc:blocked.append({'quarter':q,'reason':str(exc)})
    save(output/'frozen_rack_adjustments.json',{'features':features,'blocked':blocked})
    shadow={q:baseline[q]|{'prediction_cpg':baseline[q]['prediction_cpg']+r['correction_cpg'],
                         'production_prediction_cpg':baseline[q]['prediction_cpg'],'rack_evidence':r} for q,r in features.items()}
    rack_results={era:groups(baseline,shadow,sorted(q for q in shadow if regime(q)==era))
                  for era in ['earlier_low_margin','transition','later_regime']}
    regional_result=json.loads((regional/'results.json').read_text())
    context={}
    for name,r in regional_result['results'].items():
        challenger={x['quarter']:x for x in r['rows']};base={q:x|{'prediction_cpg':x['production_prediction_cpg']} for q,x in challenger.items()}
        context[name]=groups(base,challenger,sorted(challenger))|{'existing_metrics':r['metrics'],'new_test':True}
    for name in ['all_grade','diesel','floor']:
        challenger={r['quarter']:r for r in history[name]['shadow_rows'] if r['quarter']>='2021Q1'}
        context[name]=groups(baseline,challenger,sorted(challenger))|{'new_test':False,'source':str(ROOT/'results.json')}
    context['diesel']['validity_status']='QUARANTINED_SURVEY_BREAK_CROSSING_TRAINING_NOT_EVIDENCE_OF_IMPROVEMENT'
    context['clean_diesel_reference']=json.loads(paths[10].read_text())['results']['clean_diesel']|{'new_test':False,'source':str(paths[10])}
    daily=json.loads(paths[6].read_text());panel=json.loads(paths[7].read_text())
    try:
        validate_panel(panel);panel_readiness='READY_FOR_MANUAL_INPUT_ONLY'
    except ValueError as exc:
        panel_readiness='BLOCKED: '+str(exc)
    result={'created_at':now(),'role':'DEVELOPMENTAL_CURRENT_VINTAGE_NOT_PIT_VALIDATION','production_changed':False,
            'rack':{'by_regime':rack_results,'rows':list(shadow.values()),'blocked':blocked,
                    'strict_pit_test_status':'BLOCKED_ORIGINAL_MONTHLY_RELEASE_VINTAGES_UNVERIFIED',
                    'live_test_status':'BLOCKED_RACK_HISTORY_ENDS_2022Q1','automatic_promotion':False},
            'regional_context':context,'disclosures':{'verified_archived_mechanical_examples':archived_mechanical_examples(),
                    'audit_status':'ORIGINAL_19_PENDING_UNCHANGED_NEW_CANDIDATE_REQUIRES_REVIEW',
                    'live_anchoring_status':'BLOCKED_MISSING_REGISTERED_LIVE_SHARE_AND_REMAINDER'},
            'daily_price':{'backtest_status':daily['backtest_status'],'aaa_automation_status':daily['aaa_automation_status']},
            'pump_panel':{'status':panel['status'],'registered_pairs':len(panel['pairs']),
                    'readiness_validation':panel_readiness,
                    'historical_test_status':'BLOCKED_NO_VERIFIED_PAIRED_PRICE_HISTORY','collection_mode':panel['collection_mode']},
            'commercial_rack':{'status':'NOT_ACQUIRED_NO_PAID_DATA_OR_TRIAL_ENROLLED'}}
    save(output/'results.json',result)
    print(json.dumps({'rack':rack_results,'disclosures':result['disclosures'],'other_channels':{k:result[k] for k in ['daily_price','pump_panel','commercial_rack']}},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=Path);p.add_argument('--regional',required=True,type=Path)
    args=p.parse_args();evaluate(args.out,args.regional)
