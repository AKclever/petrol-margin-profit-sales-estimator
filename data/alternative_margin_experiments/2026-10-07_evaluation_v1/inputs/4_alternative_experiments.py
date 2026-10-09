"""Separate lagged-gap and regional-supply residual challengers. Research only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import json
from pathlib import Path
from statistics import mean

import xlrd

from .daily_capture import fetch
from .data import load_actuals, load_market, load_weights
from .geo import _predictions
from .mathutils import RidgeModel
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .timing import _metrics

SPEC = Path('data/alternative_margin_experiments_spec_v1.json')
REGIONS = {'East Coast':1,'Midwest':2,'Gulf Coast':3}
SERIES = {f'{kind}_PADD{p}': (f'WGTSTP{p}1' if kind=='stocks' else f'W_NA_YUP_R{p}0_PER')
          for kind in ['stocks','utilization'] for p in [1,2,3]}


def previous_quarter(q):
    year, quarter = int(q[:4]), int(q[-1])
    return f'{year if quarter>1 else year-1}Q{quarter-1 if quarter>1 else 4}'


def parse_series(raw, series):
    book = xlrd.open_workbook(file_contents=raw); sheet = book.sheet_by_name('Data 1')
    if series.lower() not in str(sheet.cell_value(1,1)).lower():
        raise ValueError('EIA workbook series identifier mismatch')
    result = {}
    for r in range(3,sheet.nrows):
        if sheet.cell_type(r,0) != xlrd.XL_CELL_DATE:
            continue
        if sheet.cell_type(r,1) != xlrd.XL_CELL_NUMBER:
            continue
        observed = xlrd.xldate_as_datetime(sheet.cell_value(r,0),book.datemode).date()
        value = float(sheet.cell_value(r,1))
        if observed in result or value <= 0:
            raise ValueError('Duplicate or invalid EIA supply observation')
        if 'YUP' in series and value > 120:
            raise ValueError('Invalid refinery utilization percentage')
        result[observed] = value
    if not result:
        raise ValueError('Empty EIA supply series')
    return result


def capture_supply(output):
    output.mkdir(parents=True,exist_ok=False)
    def one(item):
        name, series = item
        url = f'https://www.eia.gov/dnav/pet/hist_xls/{series}w.xls'
        raw = fetch(url); path = output/f'{name}.xls'
        with path.open('xb') as f: f.write(raw)
        rows = parse_series(raw,series)
        captured = now()
        save(output/f'{name}.json', {'rows': [{'observed_at':str(d),'value':v,
                    'available_at':captured,'captured_at':captured} for d,v in sorted(rows.items())],
                    'series_id':series,'availability_method':'FIRST_CAPTURE_NOT_ORIGINAL_HISTORICAL_RELEASE'})
        return {'name':name,'series_id':series,'source_url':url,'sha256':sha(path),
                'captured_at':captured,'available_at':captured,'count':len(rows),
                'units':'thousand_barrels' if name.startswith('stocks') else 'percent'}
    with ThreadPoolExecutor(max_workers=3) as pool:
        sources = list(pool.map(one,SERIES.items()))
    save(output/'manifest.json', {'sources':sources,'captured_at':now(),
         'role':'CURRENT_VINTAGE_ARCHIVE_NOT_HISTORICAL_PIT'})
    print([(s['name'],s['count']) for s in sources])


def quarter_supply(series, start, end, weights):
    first = start + timedelta(days=(4-start.weekday())%7)
    expected = []
    while first <= end-timedelta(days=7):
        expected.append(first); first += timedelta(days=7)
    if not expected or any(d not in rows for rows in series.values() for d in expected):
        raise ValueError('Missing exact weekly supply observations; no forward fill')
    return [sum(w.weight*mean(series[f'stocks_PADD{REGIONS[w.region]}'][d] for d in expected) for w in weights),
            sum(w.weight*mean(series[f'utilization_PADD{REGIONS[w.region]}'][d] for d in expected) for w in weights)], expected


def supply_feature(series, start, end, weights):
    current, dates = quarter_supply(series,start,end,weights)
    # Quarter boundaries here are regular calendar boundaries, including leap years.
    prior_start = date(start.year-1,start.month,1)
    prior_end = start-timedelta(days=1) if start.month==1 else None
    next_month = end.month+1
    prior_end = date(start.year if next_month==13 else start.year-1,
                     1 if next_month==13 else next_month,1)-timedelta(days=1)
    prior, prior_dates = quarter_supply(series,prior_start,prior_end,weights)
    return [100*(current[0]/prior[0]-1),current[1]-prior[1]], {
        'weighted_current_stocks_thousand_barrels':current[0],
        'weighted_prior_stocks_thousand_barrels':prior[0],
        'weighted_current_utilization_percent':current[1],
        'weighted_prior_utilization_percent':prior[1],
        'observation_dates':list(map(str,dates)),'prior_observation_dates':list(map(str,prior_dates)),
        'original_eia_release_availability_verified':False}


def fit_before(rows, cutoff):
    training = [r for r in rows if r['quarter_end'] < str(cutoff)
                and r['outcome_available_at'] < str(cutoff)]
    if len(training) < 8:
        raise ValueError('Insufficient eight earlier published OOF residuals')
    model = RidgeModel(2).fit([r['features'] for r in training],
              [r['actual_cpg']-r['prediction_cpg'] for r in training])
    return model, training


def evaluate_rows(rows):
    production = {r['quarter']:r for r in rows}; shadow = {}; excluded = []
    for row in rows:
        try:
            model, training = fit_before(rows,date.fromisoformat(row['quarter_end']))
        except ValueError as exc:
            excluded.append({'quarter':row['quarter'],'reason':str(exc)}); continue
        correction = .5*model.predict_one(row['features'])
        point = row['prediction_cpg']+correction
        shadow[row['quarter']] = row | {'prediction_cpg':point,
            'production_prediction_cpg':row['prediction_cpg'],'correction_cpg':correction,
            'direction_correct': (point>row['seasonal_cpg'])-(point<row['seasonal_cpg']) ==
                                 (row['actual_cpg']>row['seasonal_cpg'])-(row['actual_cpg']<row['seasonal_cpg']),
            'training_quarters':[r['quarter'] for r in training],
            'paired_abs_error_improvement_cpg':abs(row['actual_cpg']-row['prediction_cpg'])-abs(row['actual_cpg']-point)}
    common = sorted(shadow)
    metrics = _metrics(production,shadow,common) if common else {'status':'BLOCKED_INSUFFICIENT_MATCHED_ROWS'}
    sensitivity = None
    if len(common)>1:
        best = max(common,key=lambda q:shadow[q]['paired_abs_error_improvement_cpg'])
        sensitivity = {'omitted_quarter':best,'metrics':_metrics(production,shadow,[q for q in common if q!=best])}
    return {'metrics':metrics,'rows':[shadow[q] for q in common],'excluded':excluded,
            'remove_best_benefit_sensitivity':sensitivity}


def evaluate(output, supply_root, audit_root):
    output.mkdir(parents=True,exist_ok=False)
    paths = [Path(p) for p in ['data/market.csv','data/weights.csv','data/actuals.csv']]+[
         SPEC,Path(__file__),Path('musa_nowcast/model.py'),Path('musa_nowcast/mathutils.py'),
         Path('musa_nowcast/timing.py'),Path('musa_nowcast/geo.py'),audit_root/'quarter_rows.json',
         supply_root/'manifest.json',Path('data/revenue_gap_all/2026-10-07_v2/source_checks.json')]
    snapshots = output/'inputs'; snapshots.mkdir()
    for i,p in enumerate(paths):
        with (snapshots/f'{i}_{p.name}').open('xb') as f: f.write(p.read_bytes())
    save(output/'input_manifest.json',{'frozen_at':now(),'hashes':{str(p):sha(p) for p in paths}})
    spec = json.loads(SPEC.read_text())
    market, weights, actuals = load_market(paths[0]),load_weights(paths[1]),load_actuals(paths[2])
    engine = NowcastEngine(market,weights,actuals)
    production = _predictions(engine); indexed = {a.quarter:a for a in actuals}
    audit = {r['quarter']:r for r in json.loads((audit_root/'quarter_rows.json').read_text())['rows']}
    sources = json.loads(Path('data/revenue_gap_all/2026-10-07_v2/source_checks.json').read_text())['checks']
    dates = {c['quarter']:c['publication_date'] for c in sources if c['source_type']=='SEC_EARNINGS_EXHIBIT' and 'publication_date' in c}
    manifest = json.loads((supply_root/'manifest.json').read_text())
    series = {}
    for source in manifest['sources']:
        raw = supply_root/f"{source['name']}.xls"
        if sha(raw) != source['sha256']:
            raise ValueError('Supply raw hash mismatch')
        series[source['name']] = parse_series(raw.read_bytes(),source['series_id'])
    prepared = {'lagged_gap':[],'regional_supply':[]}; exclusions = []
    for r in production:
        a = indexed[r['quarter']]
        base = r | {'quarter_end':str(a.end),'outcome_available_at':dates[a.quarter]}
        prior = audit.get(previous_quarter(a.quarter))
        if prior and prior.get('revenue_proxy_error_cpg') is not None and prior.get('revenue_gap_available_at','9999') < str(a.end):
            prepared['lagged_gap'].append(base | {'features':[prior['revenue_proxy_error_cpg']],
                 'feature_details':{'prior_quarter':prior['quarter'],'company_gap_available_at':prior['revenue_gap_available_at'],
                                    'market_history_original_vintage_verified':False}})
        else:
            exclusions.append({'quarter':a.quarter,'experiment':'lagged_gap','reason':'Missing or unavailable immediate prior-quarter gap'})
        try:
            feature, detail = supply_feature(series,a.start,a.end,weights)
            prepared['regional_supply'].append(base | {'features':feature,'feature_details':detail})
        except ValueError as exc:
            exclusions.append({'quarter':a.quarter,'experiment':'regional_supply','reason':str(exc)})
    results = {name:evaluate_rows(rows) for name,rows in prepared.items()}
    current = {'quarter':'2026Q3','forecast_created_at':now(),
               'production_same_inputs_cpg':engine.forecast('2026Q3',date(2026,7,1),date(2026,9,30),date(2026,10,7)).retail_margin_cpg}
    for name, rows in prepared.items():
        try:
            model, training = fit_before(rows,date(2026,10,7))
            if name=='lagged_gap':
                prior = audit['2026Q2']
                if prior['revenue_gap_available_at'] >= '2026-10-07': raise ValueError('Current prior gap not available')
                feature = [prior['revenue_proxy_error_cpg']]
            else:
                feature, _ = supply_feature(series,date(2026,7,1),date(2026,9,30),weights)
            correction = .5*model.predict_one(feature)
            current[name] = {'shadow_cpg':current['production_same_inputs_cpg']+correction,
                 'correction_cpg':correction,'features':feature,
                 'training_quarters':[r['quarter'] for r in training],
                 'actual_cpg':None,'promotion_authorized':False}
        except ValueError as exc:
            current[name] = {'status':'BLOCKED','reason':str(exc)}
    result = {'created_at':now(),'specification':spec,'results':results,'feature_exclusions':exclusions,
              'current_shadows':current,'production_changed':False,
              'evaluated_history_already_used_in_research':True,'strict_pit_validated':False}
    save(output/'results.json',result)
    print(json.dumps({'metrics':{n:r['metrics'] for n,r in results.items()},'current':current,'exclusions':exclusions},indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['capture','evaluate'])
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--supply',type=Path)
    parser.add_argument('--audit',type=Path,default=Path('data/revenue_gap_all/2026-10-07_review_v2'))
    args = parser.parse_args()
    if args.action=='capture': capture_supply(args.output)
    else:
        if args.supply is None: parser.error('--supply required for evaluation')
        evaluate(args.output,args.supply,args.audit)


if __name__=='__main__': main()
