"""Frozen, regime-separated historical expansion and measurement challengers.

Current market vintages: developmental research, never strict PIT validation.
No production inputs are modified by this module.
"""
import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import re
from statistics import mean

import xlrd

from .data import MarketWeek, QuarterActual, load_actuals, load_market, load_weights
from .geo import _predictions
from .mathutils import RidgeModel
from .model import NowcastEngine
from .pit_replay import save, now
from .prospective import sha
from .revenue_gap_audit import rows_from_html, reported_volume_and_margin, reported_sss, decimal_values
from .timing import _metrics

ROOT = Path('data/history_floor_basis')
OLD = ROOT/'2026-10-07_sec_v2'
PRICES = ROOT/'2026-10-07_capture_v1'
MODERN = Path('data/revenue_gap_all/2026-10-07_v2')
SPEC = Path('data/history_floor_basis_spec_v1.json')
REGIONS = {'East Coast': 1, 'Midwest': 2, 'Gulf Coast': 3}


def bounds(q):
    y, n = int(q[:4]), int(q[-1]); month = 3*n-2
    return date(y, month, 1), date(y+1, 1, 1)-timedelta(days=1) if n == 4 else date(y, month+3, 1)-timedelta(days=1)


def regime(q):
    return 'earlier_low_margin' if q < '2020Q1' else 'transition' if q < '2021Q1' else 'later_regime'


def previous(q):
    y, n = int(q[:4]), int(q[-1])
    return f'{y if n > 1 else y-1}Q{n-1 if n > 1 else 4}'


def extract_target(raw):
    tree, rows = rows_from_html(raw); text = ' '.join(tree.text_content().split())
    try:
        table = reported_volume_and_margin(raw)
        margin, gallons = table['retail_margin_cpg']['value'], table['gallons_million']['value']
        evidence = table
    except ValueError:
        # First before-card-fee sentence is quarterly, subsequent sentences are YTD.
        match = re.search(r'Retail fuel margins \(before credit card expenses\) (?:were ([\d.]+) (?:cents per gallon \(cpg\)|cpg)|(?:increased|decreased) [\d.]+ cents per gallon \(cpg\) to ([\d.]+) cpg)', text, re.I)
        if not match:
            raise ValueError('Missing directly reported quarterly retail margin')
        margin = float(match[1] or match[2]); gallons = None
        volume = re.search(r'(?:retail fuel volumes|retail fuel sales).{0,65}?(?:were|with|to) ([\d,.]+) (million|billion) gallons', text, re.I)
        if volume and volume[2].lower() == 'million':
            gallons = float(volume[1].replace(',', ''))
        evidence = {'margin_sentence': match[0], 'volume_sentence': volume[0] if volume else None}
    contribution = None; bridge = None
    for cells in rows:
        if cells and re.match(r'^(?:Total )?Retail fuel contribution.*\$(?:\s*Million|\s*M\b)', cells[0], re.I):
            values = decimal_values(cells[1:])
            if values:
                contribution = values[0]; bridge = cells; break
    implied = 100*contribution/gallons if contribution is not None and gallons else None
    if implied is not None and abs(implied-margin) > .11:
        raise ValueError('Contribution/gallons bridge outside rounding tolerance')
    return {'retail_margin_cpg': margin, 'gallons_million': gallons,
            'target_evidence': evidence, 'retail_contribution_million': contribution,
            'contribution_evidence': bridge, 'bridge_implied_margin_cpg': implied,
            'reconciliation_status': 'RECONCILED_WITHIN_ROUNDING' if implied is not None else 'DIRECT_MARGIN_ONLY_NO_EXACT_CONTRIBUTION_BRIDGE',
            'gallons_status': 'REPORTED_EXACT_DECIMAL' if gallons is not None else 'UNRESOLVED_EXACT_GALLONS',
            'report_status': 'PRELIMINARY_REPORTED' if re.search(r'(?:reports|announced) preliminary', text[:3000], re.I) else 'ORIGINAL_REPORTED'}


def floor_values(raw, quarter, gallons):
    _, rows = rows_from_html(raw)
    # Pre-2016 consolidated expense can include ethanol: do not silently pool it.
    expense = None; evidence = None
    if quarter >= '2016Q1':
        for cells in rows:
            if cells and re.match(r'^Total (?:station|store) and other operating expenses?', cells[0]):
                values = decimal_values(cells[1:])
                if values:
                    expense = values[0]; evidence = cells; break
    sss = reported_sss(raw)
    return {'station_expense_million': expense, 'station_expense_evidence': evidence,
            'station_cost_cpg': 100*expense/gallons if expense is not None and gallons else None,
            'direct_sss_percent': sss['value'], 'sss_evidence': sss,
            'expense_basis': 'CONSOLIDATED_STATION_OR_STORE_TOTAL_INCLUDES_PAYMENT_FEES_NOT_PURE_WAGES' if expense is not None else 'BLOCKED_UNVERIFIED_CONSISTENT_EXPENSE_BASIS',
            'acquisition_comparability': 'QUICKCHEK_INCLUDED_2021_ONWARD_COST_VOLUME_NOT_LIKE_FOR_LIKE' if quarter >= '2021Q1' else 'PRE_QUICKCHEK'}


def parse_prices(path):
    book = xlrd.open_workbook(str(path)); sheet = book.sheet_by_name('Data 1'); result = {}
    check = json.loads(path.with_name(path.stem+'_source_check.json').read_text())
    expected = check['original_index_locator_or_series']
    if sha(path) != check['sha256']:
        raise ValueError('Market source hash changed')
    if expected.lower() not in str(sheet.cell_value(1, 1)).lower():
        raise ValueError('Wrong EIA series in workbook')
    for r in range(3, sheet.nrows):
        if sheet.cell_type(r, 0) != xlrd.XL_CELL_DATE or sheet.cell_type(r, 1) != xlrd.XL_CELL_NUMBER:
            continue
        observed = xlrd.xldate_as_datetime(sheet.cell_value(r, 0), book.datemode).date()
        week = observed-timedelta(days=observed.weekday()); value = 100*float(sheet.cell_value(r, 1))
        if week in result or value <= 0:
            raise ValueError('Duplicate/invalid weekly price')
        result[week] = value
    return result


def make_market(series, kind):
    result = []
    for region, p in REGIONS.items():
        retail = series[f'{kind}_PADD{p}']; wholesale = series['NYH' if p == 1 else 'USGC']
        for week in sorted(set(retail)&set(wholesale)):
            if week >= date(2012, 1, 1):
                result.append(MarketWeek(week, region, retail[week], wholesale[week]))
    return result


def floor_feature(q, targets):
    prior = targets.get(previous(q)); year_ago = targets.get(f'{int(previous(q)[:4])-1}{previous(q)[4:]}')
    cutoff = str(bounds(q)[1])
    if not prior or not year_ago or any(r['available_at'] >= cutoff for r in [prior, year_ago]):
        raise ValueError('Missing prior-quarter published cost/volume evidence')
    if any(r['station_cost_cpg'] is None for r in [prior, year_ago]) or prior['direct_sss_percent'] is None:
        raise ValueError('Missing consistent station cost or direct SSS disclosure')
    return [prior['station_cost_cpg']-year_ago['station_cost_cpg'], -prior['direct_sss_percent']], {
        'prior_quarter': prior['quarter'], 'prior_year_quarter': year_ago['quarter'],
        'input_available_at': [prior['available_at'], year_ago['available_at']]}


def diesel_feature(q, series, weights):
    def average(quarter):
        start, end = bounds(quarter)
        first = start+timedelta(days=(-start.weekday())%7)
        weeks = []; week = first
        while week+timedelta(days=4) <= end:
            weeks.append(week); week += timedelta(days=7)
        if any(w not in series[f'diesel_PADD{REGIONS[r.region]}'] for r in weights for w in weeks):
            raise ValueError('Missing exact diesel observation; no fill')
        return sum(r.weight*mean(series[f'diesel_PADD{REGIONS[r.region]}'][w] for w in weeks) for r in weights)
    prior_q = f'{int(q[:4])-1}{q[4:]}'
    return [average(q)-average(prior_q)], {'role': 'DIESEL_RETAIL_YOY_CONTEXT_NOT_MUSA_FUEL_MIX'}


def residual_shadow(rows):
    shadow = {}; blocked = []
    for row in rows:
        training = [r for r in rows if r['quarter_end'] < row['quarter_end']
                    and r['outcome_available_at'] < row['quarter_end']
                    and regime(r['quarter']) == regime(row['quarter'])]
        if len(training) < 8:
            blocked.append({'quarter': row['quarter'], 'reason': 'FEWER_THAN_EIGHT_PUBLISHED_SAME_REGIME_RESIDUALS'}); continue
        fitted = RidgeModel(2).fit([r['features'] for r in training], [r['actual_cpg']-r['prediction_cpg'] for r in training])
        correction = .5*fitted.predict_one(row['features']); prediction = row['prediction_cpg']+correction
        shadow[row['quarter']] = row | {'prediction_cpg': prediction,
            'production_prediction_cpg': row['prediction_cpg'], 'correction_cpg': correction,
            'training_quarters': [r['quarter'] for r in training],
            'direction_correct': NowcastEngine._direction(prediction-row['seasonal_cpg']) == NowcastEngine._direction(row['actual_cpg']-row['seasonal_cpg'])}
    return shadow, blocked


def compare_by_regime(baseline, shadow):
    result = {}
    for era in ['earlier_low_margin', 'transition', 'later_regime']:
        quarters = sorted(q for q in baseline.keys()&shadow.keys() if regime(q) == era)
        result[era] = {'quarters': quarters, 'metrics': _metrics(baseline, shadow, quarters) if quarters else None}
    return result


def evaluate(output):
    output.mkdir(parents=True, exist_ok=False)
    modern = load_actuals('data/actuals.csv'); weights = load_weights('data/weights.csv')
    sources = [r for r in json.loads((OLD/'source_checks.json').read_text())['checks'] if r.get('source_type') == 'SEC_EARNINGS_EXHIBIT']
    modern_sources = [r for r in json.loads((MODERN/'source_checks.json').read_text())['checks'] if r['source_type'] == 'SEC_EARNINGS_EXHIBIT']
    targets = {}; old_actuals = []
    for source, directory in [(s, OLD) for s in sources]+[(s, MODERN) for s in modern_sources]:
        q = source['quarter']; path = directory/source['raw_file']; raw = path.read_bytes()
        if sha(path) != source['sha256']:
            raise ValueError('Historical source hash changed')
        target = extract_target(raw); start, end = bounds(q)
        targets[q] = {'quarter': q, 'quarter_start': str(start), 'quarter_end': str(end),
                      'regime': regime(q), 'available_at': source.get('available_at', source.get('publication_date')),
                      'source_url': source['source_url'], 'source_sha256': source['sha256'], **target,
                      **floor_values(raw, q, target['gallons_million'])}
        if q < '2019Q1':
            old_actuals.append(QuarterActual(q, start, end, target['retail_margin_cpg'], gallons_million=target['gallons_million']))
    for actual in modern:
        if targets[actual.quarter]['retail_margin_cpg'] != actual.retail_margin_cpg:
            raise ValueError('Original exhibit margin disagrees with existing actual')
    all_actuals = sorted(old_actuals+modern, key=lambda r: r.quarter)
    series = {p.stem: parse_prices(p) for p in PRICES.glob('*.xls')}
    regular = make_market(series, 'regular'); all_grade = make_market(series, 'all_grade')
    production_market = load_market('data/market.csv')
    # Do not allow a missing weekly source to silently create a partial-quarter test.
    coverage = []
    for basis, market in [('regular', regular), ('all_grade', all_grade)]:
        engine = NowcastEngine(market, weights, all_actuals)
        for actual in all_actuals:
            f = engine.features(actual.start, actual.end)
            if f.observed_weeks != f.expected_weeks:
                raise ValueError(f'Incomplete {basis} quarter {actual.quarter}')
            if any(targets[a.quarter]['available_at'] >= str(actual.end) for a in all_actuals if a.end < actual.start):
                raise ValueError('Earlier outcome unavailable at target quarter-end')
            coverage.append({'basis':basis,'quarter':actual.quarter,'complete_weeks':f.observed_weeks})
    # Freeze raw bytes, code and normalized research inputs before computing errors.
    inputs = [SPEC, Path('data/actuals.csv'), Path('data/market.csv'), Path('data/weights.csv'), Path(__file__),
              Path('musa_nowcast/model.py'), Path('musa_nowcast/mathutils.py'), Path('musa_nowcast/geo.py'),
              Path('musa_nowcast/timing.py')]+list(PRICES.glob('*.xls'))+[OLD/s['raw_file'] for s in sources]+[MODERN/s['raw_file'] for s in modern_sources]
    save(output/'frozen_inputs.json', {'frozen_at': now(), 'files': [{'path':str(p),'sha256':sha(p)} for p in inputs],
                                     'evaluation_role':'DEVELOPMENTAL_CURRENT_VINTAGE_RESEARCH_NOT_STRICT_PIT'})
    save(output/'historical_targets.json', {'quarters': [targets[q] for q in sorted(targets)],
        'production_actuals_modified': False, 'source_scope':'ORIGINAL_RELEASE_NOT_RESTATEMENT_RECONCILIATION'})
    save(output/'normalized_market.json', {'regular':[r.__dict__ | {'week':str(r.week)} for r in regular],
                                         'all_grade':[r.__dict__ | {'week':str(r.week)} for r in all_grade]})
    baseline_old = _predictions(NowcastEngine(regular, weights, all_actuals))
    grade_old = _predictions(NowcastEngine(all_grade, weights, all_actuals))
    baseline_modern = _predictions(NowcastEngine(production_market, weights, modern))
    # Preserve existing modern wholesale and each week's coverage; substitute retail only.
    lookup = {(r.week,r.region):r for r in all_grade}
    substitute = [MarketWeek(r.week,r.region,lookup[(r.week,r.region)].retail_cpg,r.wholesale_cpg) for r in production_market]
    grade_modern = _predictions(NowcastEngine(substitute, weights, modern))
    baseline = {r['quarter']:r for r in baseline_old if r['quarter'] < '2021Q1'} | {r['quarter']:r for r in baseline_modern}
    grade = {r['quarter']:r for r in grade_old if r['quarter'] < '2021Q1'} | {r['quarter']:r for r in grade_modern}
    experiment_results = {}
    for name, feature in [('floor', lambda q: floor_feature(q, targets)), ('diesel', lambda q: diesel_feature(q, series, weights))]:
        rows = []; excluded = []
        for q,r in sorted(baseline.items()):
            try:
                x,evidence = feature(q)
            except ValueError as exc:
                excluded.append({'quarter': q, 'reason': str(exc)}); continue
            rows.append(r | {'quarter_end': str(bounds(q)[1]), 'outcome_available_at':targets[q]['available_at'],
                             'features':x, 'feature_evidence':evidence})
        shadow, blocked = residual_shadow(rows)
        experiment_results[name] = {'by_regime':compare_by_regime(baseline,shadow), 'eligible_feature_rows':len(rows),
                                    'feature_rows':rows,'shadow_rows':list(shadow.values()),'blocked':excluded+blocked}
    regular_lookup = {(r.week,r.region):r for r in regular}
    differences = [{'week':str(r.week),'region':r.region,'retail_difference_cpg': regular_lookup[(r.week,r.region)].retail_cpg-r.retail_cpg,
        'wholesale_difference_cpg':regular_lookup[(r.week,r.region)].wholesale_cpg-r.wholesale_cpg} for r in production_market
        if (r.week,r.region) in regular_lookup and (abs(regular_lookup[(r.week,r.region)].retail_cpg-r.retail_cpg)>.001 or abs(regular_lookup[(r.week,r.region)].wholesale_cpg-r.wholesale_cpg)>.001)]
    # Fresh-regular control isolates substitution from changing market vintage.
    fresh_modern = {r['quarter']:r for r in _predictions(NowcastEngine(regular, weights, modern))}
    result = {'created_at':now(),'role':'DEVELOPMENTAL_CURRENT_VINTAGE_RESEARCH_NOT_STRICT_PIT','production_changed':False,
        'target_quarters':len(targets),'added_target_quarters':len(old_actuals),'expanded_oof_quarters':len(baseline),
        'baseline_rows':list(baseline.values()),'baseline_by_regime':compare_by_regime(baseline,baseline),
        'all_grade':{'by_regime':compare_by_regime(baseline,grade),'shadow_rows':list(grade.values())},
        'floor':experiment_results['floor'],'diesel':experiment_results['diesel'],
        'fresh_regular_vintage_control':compare_by_regime({r['quarter']:r for r in baseline_modern},fresh_modern),
        'market_differences_from_production': differences,
        'weekly_coverage_checks':coverage,
        'target_summary_by_regime':{era:{'n':len(group), 'mean_retail_margin_cpg':mean(v['retail_margin_cpg'] for v in group),
                'minimum_retail_margin_cpg':min(v['retail_margin_cpg'] for v in group),
                'maximum_retail_margin_cpg':max(v['retail_margin_cpg'] for v in group)}
            for era in ['earlier_low_margin','transition','later_regime']
            for group in [[v for v in targets.values() if v['regime']==era]]},
        'limitations':['Original preliminary outcomes retained and labelled; subsequent restatements not audited',
                       'Current-vintage historical market data, not historical availability proof',
                       'Geographic weights fixed today; not historically reconstructed store exposure',
                       'Cost proxy includes payment fees, acquisition and mix effects; not measured competitor wages',
                       'All-grade benchmark is not MUSA actual fuel mix; diesel is context only',
                       'Earlier model and later production train on separate footprints; no pooled score']}
    save(output/'results.json',result)
    print(json.dumps({k:result[k] for k in ['target_quarters','added_target_quarters','expanded_oof_quarters']},indent=2))
    for name in ['all_grade','floor','diesel']:
        print(name,[(era, v['metrics']) for era,v in result[name]['by_regime'].items()])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out',type=Path,required=True)
    evaluate(parser.parse_args().out)
