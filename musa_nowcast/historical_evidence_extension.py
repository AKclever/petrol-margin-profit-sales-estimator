"""Source/basis audits and one publication-filtered peer challenger."""
import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re

from lxml import html
import xlrd

from .anchor_reliability import ROOT, tail_metrics
from .couchetard_peer import clean, DATE, fiscal_predictions
from .data import QuarterActual, RegionWeight, load_actuals, load_weights
from .history_floor_basis import bounds, regime
from .joint_all_features import market_from_json
from .mathutils import RidgeModel
from .model import NowcastEngine
from .peer_surprise import overlap_days
from .pit_replay import now, save
from .prospective import sha
from .timing import _metrics

SPEC = Path('data/historical_evidence_extension_spec_v1.json')
OLDER = Path('data/older_peer_evidence/2026-10-08_v1')
REVIEW = Path('data/older_peer_evidence/2026-10-08_review_v4/review.json')


def atd_target(raw, url):
    tree = html.fromstring(raw, parser=html.HTMLParser(encoding='utf-8')); text = clean(tree)
    ordinal = re.search(r'(first|second|third|fourth)-quarter.*?(20\d{2})', url, re.I)
    if not ordinal: raise ValueError('missing fiscal identity')
    quarter = ['first','second','third','fourth'].index(ordinal[1].lower())+1
    year = int(ordinal[2])
    match = re.search(r'For its (?:first|second|third|fourth) quarter(?: of fiscal(?: year)? \d{4})? ended\s+'+DATE, text, re.I)
    if not match:
        match = re.search(r'(?:12|13|16|17)(?: and \d{2})?[\s\-–‑]+week periods? ended\s+'+DATE, text, re.I)
    if not match: raise ValueError('missing explicit current-period end')
    end = datetime.strptime(' '.join(match.groups()), '%B %d %Y').date()
    periods = [m for m in re.finditer(r'(\d{2})(?: and \d{2})?[\s\-–‑]+week periods? ended\s+'+DATE, text, re.I)
               if datetime.strptime(' '.join(m.groups()[1:]), '%B %d %Y').date() == end and int(m[1]) in (12,13,16,17)]
    if not periods: raise ValueError('missing explicit current-period length')
    weeks = int(periods[0][1]); values = {}; evidence = []
    table = next((t for t in tree.xpath('//table') if 'Before deduction of expenses related to electronic payment modes' in clean(t)), None)
    if table is None: raise ValueError('missing fee-separated US margin table')
    for tr in table.xpath('.//tr'):
        cells = [clean(c) for c in tr.xpath('./td|./th') if clean(c)]
        for prefix,key in [('Before deduction','before'),('Expenses related','fees'),('After deduction','after')]:
            if cells and prefix in cells[0] and key not in values:
                nums = [float(v) for v in cells[1:] if re.fullmatch(r'\d+\.\d+', v)]
                if len(nums) != 5: raise ValueError('unexpected fiscal margin columns')
                values[key] = nums[3]; evidence.append(cells)
    if set(values) != {'before','fees','after'} or abs(values['before']-values['fees']-values['after']) > .021:
        raise ValueError('fee bridge does not reconcile')
    # Independent narrative verification of geography, company-operated perimeter and number.
    if not re.search(r'fuel gross margin of our company[\s\-–‑]+operated stores in the United States', text):
        raise ValueError('US company-operated table basis not explicit')
    passage = next((clean(p) for p in tree.xpath('//p') if 'United States' in clean(p) and 'fuel gross margin' in clean(p)
                    and re.search(r'\b'+re.escape(f"{values['before']:.2f}")+r'\b', clean(p))), None)
    if not passage: raise ValueError('current US margin narrative not reconciled to fee table')
    context = [clean(p) for p in tree.xpath('//p') if re.search(r'acquisition|acquired|divest', clean(p), re.I) and len(clean(p)) < 4000]
    return {'quarter': f'F{year}Q{quarter}', 'start': str(end-timedelta(days=weeks*7-1)), 'end': str(end),
            'weeks': weeks, 'retail_margin_cpg': values['before'], 'payment_fees_cpg': values['fees'],
            'after_payment_margin_cpg': values['after'], 'available_at': url.split('/')[-1][:10],
            'source_url': url, 'target_basis': 'US_COMPANY_OPERATED_BEFORE_PAYMENT_FEES',
            'review_status': 'NARRATIVE_PERIOD_AND_FEE_BRIDGE_RECONCILED', 'evidence': evidence,
            'current_margin_passage': passage, 'period_evidence': periods[0][0],
            'acquisition_context': context, 'acquisition_adjustment_applied': False}


def caseys_target(raw, period):
    text = clean(html.fromstring(raw, parser=html.HTMLParser(encoding='utf-8')))
    section = re.search(r'(?:Fuel|Gasoline)\s*[-–—]\s*(.*?)(?:Grocery and Other|Grocery & Other)', text, re.I)
    if not section: raise ValueError('no separately delimited fuel section')
    matches = [m for m in re.finditer(r'For the (?:first |second |third |fourth )?quarter.{0,160}?average (?:fuel )?margin (?:of|above goal at) ([\d.]+) cents per gallon', section[1], re.I)
               if not re.search(r'year.to.date|annual|guidance', m[0], re.I)]
    if len({m[1] for m in matches}) != 1: raise ValueError('no unique achieved quarterly margin')
    if 'excluding credit card fees' not in text.lower(): raise ValueError('payment-fee basis not supported')
    end = date.fromisoformat(period['end'])
    start = date(end.year-1,11,1) if end.month == 1 else date(end.year,end.month-2,1)
    return {'quarter': period['quarter'], 'start': str(start), 'end': str(end),
            'retail_margin_cpg': float(matches[0][1]), 'evidence': matches[0][0],
            'rin_context': section[1], 'payment_fee_basis': 'EXCLUDING_CREDIT_CARD_FEES',
            'target_basis': 'CASEYS_REPORTED_FUEL_MARGIN_INCLUDES_RIN_WHERE_DISCLOSED_NOT_MUSA_RETAIL',
            'review_status': 'ACHIEVED_QUARTER_AND_PAYMENT_BASIS_RECONCILED'}


def monthly_series(path, expected):
    book = xlrd.open_workbook(str(path)); sheet = book.sheet_by_name('Data 1')
    if expected.lower() not in str(sheet.cell_value(1,1)).lower(): raise ValueError('wrong series')
    rows = {}
    for i in range(3,sheet.nrows):
        if sheet.cell_type(i,0) != xlrd.XL_CELL_DATE or sheet.cell_type(i,1) != xlrd.XL_CELL_NUMBER: continue
        observed = xlrd.xldate_as_datetime(sheet.cell_value(i,0),book.datemode).date()
        month = observed.replace(day=1)
        if month in rows or sheet.cell_value(i,1) <= 0: raise ValueError('duplicate/nonpositive observation')
        rows[month] = 100*sheet.cell_value(i,1)
    return rows


def select_peer(rows, start, end, report_date):
    cutoff = min(str(end), report_date)
    eligible = [r for r in rows if r['available_at'] < cutoff and r['start'] <= str(end) and r['end'] >= str(start)]
    return max(eligible,key=lambda r:(r['available_at'],r['end'])) if eligible else None


def peer_corrections(rows):
    frozen = {}; blocked = []
    for r in rows:
        training = [t for t in rows if regime(t['quarter']) == regime(r['quarter']) and t['quarter'] < r['quarter']
                    and t['available_at'] < r['cutoff']]
        if len(training) < 8:
            blocked.append({'quarter': r['quarter'], 'reason': 'FEWER_THAN_EIGHT_SAME_REGIME_PUBLISHED_PEER_RESIDUALS'}); continue
        model = RidgeModel(10).fit([t['features'] for t in training], [t['actual_cpg']-t['prediction_cpg'] for t in training])
        correction = .5*model.predict_one(r['features']); point = r['prediction_cpg']+correction
        frozen[r['quarter']] = {'prediction_cpg': point, 'correction_cpg': correction,
             'training_quarters': [t['quarter'] for t in training], 'coefficients': model.coefficients,
             'direction_correct': NowcastEngine._direction(point-r['seasonal_cpg']) == NowcastEngine._direction(r['actual_cpg']-r['seasonal_cpg'])}
    return frozen, blocked


def evaluate(source, output, additional_source=None):
    output.mkdir(parents=True,exist_ok=False)
    inputs = [SPEC, Path(__file__), REVIEW, ROOT/'historical_targets.json', ROOT/'results.json',
              ROOT/'normalized_market.json', source/'source_checks.json', OLDER/'source_checks.json',
              Path('data/caseys/actuals.csv'), Path('data/caseys/weights.csv'), Path('musa_nowcast/couchetard_peer.py'),
              Path('musa_nowcast/mathutils.py'), Path('musa_nowcast/model.py'), Path('musa_nowcast/timing.py'),
              Path('data/couchetard_peer/2026-10-07_v3/history.json'),
              Path('data/peer_surprise/2026-10-07_v2/sources/CASY_source_checks.json'),
              Path('data/miss_evidence/2026-10-08_v1/quarter_diagnostics.json')]
    if additional_source: inputs.append(additional_source/'source_checks.json')
    save(output/'frozen_inputs.json', {'created_at': now(), 'files': [{'path': str(p), 'sha256': sha(p)} for p in inputs]})
    (output/'inputs').mkdir()
    for i,p in enumerate(inputs):
        with (output/'inputs'/f'{i}_{p.name}').open('xb') as handle: handle.write(p.read_bytes())
    checks = json.loads((source/'source_checks.json').read_text())['checks']
    if additional_source:
        checks.extend(r | {'raw_file':str((additional_source/r['raw_file']).resolve())} for r in
                      json.loads((additional_source/'source_checks.json').read_text())['checks'])
    for r in checks:
        if r['status'] == 'RAW_CAPTURED' and sha(source/r['raw_file']) != r['sha256']: raise ValueError('source bytes changed')
    baseline = {r['quarter']: r for r in json.loads((ROOT/'results.json').read_text())['baseline_rows']}
    targets = {r['quarter']: r for r in json.loads((ROOT/'historical_targets.json').read_text())['quarters']}
    large = [q for q,r in baseline.items() if q >= '2021Q1' and abs(r['actual_cpg']-r['prediction_cpg']) >= 5]
    wholesale = []
    for check in checks:
        if not check['id'].startswith('EMA_') or check['status'] != 'RAW_CAPTURED': continue
        values = monthly_series(source/check['raw_file'], check['id']); covered = []
        for q in large:
            start,_ = bounds(q); months = [date(start.year,start.month+i,1) for i in range(3)]
            if all(m in values for m in months): covered.append(q)
        wholesale.append(check | {'first_month': str(min(values)), 'last_month': str(max(values)),
            'observations': len(values), 'basis': 'ALL_SELLER_RACK' if '_PRA_' in check['id'] else 'REFINER_RESALE_NOT_RACK',
            'covered_large_miss_quarters': covered, 'local_terminal_prices': False, 'historical_pit_verified': False,
            'normalized_monthly_cpg':{str(k):v for k,v in values.items()}})
    save(output/'wholesale_coverage.json', {'series': wholesale, 'local_rack_status': 'BLOCKED_NO_FREE_MATCHED_TERMINAL_HISTORY_VERIFIED',
         'regional_resale_is_separate_context': True, 'price_correction_fitted': False,
         'nonseries_checks': [r for r in checks if not r['id'].startswith('EMA_')]})
    reviewed = {'CASY': {}, 'ATD': {}}; reviews = []
    raw_checks = json.loads((OLDER/'source_checks.json').read_text())['checks']
    for extra in checks:
        if extra['id'].startswith('atd_f') and extra['status'] == 'RAW_CAPTURED':
            raw_checks.append(extra | {'peer':'ATD','status':'ORIGINAL_RELEASE_CAPTURED','new_source':True})
    for check in raw_checks:
        if check.get('status') != 'ORIGINAL_RELEASE_CAPTURED': continue
        path = (source if check.get('new_source') else OLDER)/check['raw_file']
        if sha(path) != check['sha256']: raise ValueError('older source hash changed')
        review = {'peer': check['peer'], 'source_url': check['source_url'], 'raw_path': str(path), 'sha256': sha(path), 'available_at': check.get('available_at')}
        try:
            row = caseys_target(path.read_bytes(),check['period']) if check['peer'] == 'CASY' else atd_target(path.read_bytes(),check['source_url'])
            row.update(available_at=check.get('available_at',row.get('available_at')),source_url=check['source_url'],source_sha256=sha(path))
            q = row['quarter']; old = reviewed[check['peer']].get(q)
            if old and old['retail_margin_cpg'] != row['retail_margin_cpg']: raise ValueError('conflicting current-period values')
            if not old or row['available_at'] < old['available_at']: reviewed[check['peer']][q] = row
            review.update(status=row['review_status'], quarter=q, evidence=row)
        except (ValueError,TypeError,KeyError) as exc: review.update(status='UNRESOLVED_NOT_NO_DISCLOSURE',reason=str(exc))
        reviews.append(review)
    # Existing recent histories stay on their reviewed reported bases. Newly reconciled old rows replace provisional old rows.
    existing_atd = json.loads(Path('data/couchetard_peer/2026-10-07_v3/history.json').read_text())['rows']
    atd = {r['quarter']: r for r in existing_atd} | reviewed['ATD']
    casy_dates = json.loads(Path('data/peer_surprise/2026-10-07_v2/sources/CASY_source_checks.json').read_text())['verified']
    casy = {a.quarter: {'quarter':a.quarter,'start':str(a.start),'end':str(a.end),'retail_margin_cpg':a.retail_margin_cpg,
               'available_at':casy_dates[a.quarter]['available_at'],'source_url':casy_dates[a.quarter]['url'],
               'source_sha256':casy_dates[a.quarter]['sha256'],'target_basis':'CASEYS_REPORTED_FUEL_MARGIN_INCLUDES_RIN_WHERE_DISCLOSED_NOT_MUSA_RETAIL'}
            for a in load_actuals('data/caseys/actuals.csv') if a.quarter in casy_dates} | reviewed['CASY']
    market = market_from_json(json.loads((ROOT/'normalized_market.json').read_text())['regular'])
    predictions = {}; excluded = {}
    for peer, history, weights in [('CASY',casy,load_weights('data/caseys/weights.csv')),
                                  ('ATD',atd,[RegionWeight(r,1/3) for r in ['East Coast','Midwest','Gulf Coast']])]:
        records = sorted(history.values(),key=lambda r:r['end'])
        actuals = [QuarterActual(r['quarter'],date.fromisoformat(r['start']),date.fromisoformat(r['end']),r['retail_margin_cpg']) for r in records]
        dates = {r['quarter']: {'available_at':r['available_at'],'url':r['source_url'],'sha256':r['source_sha256'],'target_basis':r['target_basis']} for r in records}
        predictions[peer],excluded[peer] = fiscal_predictions(market,weights,actuals,dates)
    save(output/'reviewed_peer_history.json', {'new_source_reviews':reviews,'histories':{'CASY':list(casy.values()),'ATD':list(atd.values())},
        'older_reconciled_counts':{p:len(r) for p,r in reviewed.items()}, 'peer_predictions':predictions,'peer_exclusions':excluded,
        'target_basis_not_equal_to_musa':True,'strict_market_pit_verified':False})
    matched = []; absent = []
    for q,b in sorted(baseline.items()):
        start,end = bounds(q); report_date = targets[q]['available_at']
        cp,ap = [select_peer(predictions[p],start,end,report_date) for p in ['CASY','ATD']]
        if not cp or not ap:
            absent.append({'quarter':q,'reason':'NO_RECONCILED_PUBLISHED_OVERLAPPING_PEER_PAIR'}); continue
        matched.append(b | {'available_at':report_date,'cutoff':str(end),'features':[cp['surprise_cpg'],ap['surprise_cpg']],
             'peers':{'CASY':cp,'ATD':ap},'overlap_days':{'CASY':overlap_days(start,end,cp),'ATD':overlap_days(start,end,ap)}})
    frozen, blocked = peer_corrections(matched)
    save(output/'frozen_peer_forecasts.json', {'frozen_at':now(),'forecasts':frozen,'matched_inputs':matched,'blocked':blocked+absent})
    shadows = {r['quarter']:r|frozen[r['quarter']]|{'production_prediction_cpg':r['prediction_cpg']} for r in matched if r['quarter'] in frozen}
    results = {}
    for era in ['earlier_low_margin','transition','later_regime']:
        qs = sorted(q for q in shadows if regime(q) == era)
        big = [q for q in qs if abs(baseline[q]['actual_cpg']-baseline[q]['prediction_cpg'])>=5]
        results[era] = {'quarters':qs,'metrics':_metrics(baseline,shadows,qs) if qs else None,
            'tail_metrics':tail_metrics(baseline,shadows,qs),'large_group':tail_metrics(baseline,shadows,big),
            'ordinary_group':tail_metrics(baseline,shadows,[q for q in qs if q not in big])}
    save(output/'peer_results.json', {'role':'DEVELOPMENTAL_CURRENT_VINTAGE_PUBLICATION_FILTERED_NOT_STRICT_PIT','by_regime':results,
         'rows':list(shadows.values()),'blocked':blocked+absent,'production_changed':False,'automatic_promotion':False,
         'large_miss_coverage':[{'quarter':q,'published_pair_present':any(r['quarter']==q for r in matched),'scored':q in shadows} for q in large]})
    inventory = json.loads(Path('data/miss_evidence/2026-10-08_v1/quarter_diagnostics.json').read_text())['rows']
    perimeter = []
    for r in inventory:
        q = r['quarter']; path = Path(r['raw_file'])
        if sha(path) != r['source_sha256']: raise ValueError('MUSA release changed')
        tree = html.fromstring(path.read_bytes(),parser=html.HTMLParser(encoding='utf-8')); text = clean(tree)
        passages = list(dict.fromkeys(text[max(0,m.start()-100):m.end()+220] for m in re.finditer(r'QuickChek|Quick Chek|same.store|SSS|raze.and.rebuild|opened|closed',text,re.I)))
        status = 'PRE_QUICKCHEK' if q < '2021Q1' else ('PARTIAL_ACQUISITION_QUARTER_NOT_LIKE_FOR_LIKE' if q == '2021Q1' else
                  'ANCHOR_EXCLUDES_QUICKCHEK' if q < '2022Q1' else 'ANCHOR_HAS_PARTIAL_QUICKCHEK_PERIOD' if q == '2022Q1' else 'BOTH_PERIODS_INCLUDE_QUICKCHEK_ORGANIC_MIX_STILL_CHANGES')
        definitions = [text[max(0,m.start()-80):m.end()+650] for m in re.finditer(r'Average per store|same store sales \(?"?SSS|SSS\)? metric',text,re.I)]
        perimeter.append({'quarter':q,'source_url':r['source_url'],'raw_path':str(path),'sha256':sha(path),'available_at':r['source_available_at'],
            'quickchek_comparability':status,'evidence_passages':passages,'denominator_warning': 'SSS/APSM population may exclude acquired or rebuilt sites; do not divide consolidated cost by SSS gallons',
            'reported_population_definitions':definitions,
            'retail_margin_adjustment_cpg':None,'organic_mix_stable_proven':False,'audit_scope':'ORIGINAL_EARNINGS_RELEASE_PLUS_TARGETED_ACQUISITION_FILINGS_NOT_EXHAUSTIVE'})
    save(output/'perimeter_audit.json', {'quarters':perimeter,'closing_date':'2021-01-29','targeted_filing_checks':[r for r in checks if r['id'] in ['quickchek_close','musa_2022q2_filing','caseys_buchanan_filing']],
         'store_count_difference_retained':{'closing_announcement':157,'subsequent_filing_and_earnings_release':156,'reconciliation':'UNRESOLVED_NOT_FUEL_SITE_OR_GALLON_WEIGHTS'},
         'basis_findings':[
             'Consolidated MUSA results include QuickChek from Jan29 2021, not from Jan1',
             '2021 YoY retail margin comparisons cross the acquisition boundary; Q1 2022 compares full with partial ownership periods',
             'From Q2 2022 both periods include full QuickChek quarters; this removes this particular ownership-date discontinuity, not all mix/integration differences',
             'Original release APSM definition includes acquired sites from acquisition date; SSS uses stores open throughout comparison periods and calendar-year eligibility. Do not apply a presentation-specific exclusion to every period',
             'Casey Buchanan acquisition May13 2021 added retail stores and a dealer wholesale network; do not treat consolidated wholesale contributions as like-for-like pump economics'],
         'retail_margin_rebased':False,'production_changed':False})
    print(json.dumps({'older_reviewed':{p:len(r) for p,r in reviewed.items()},'peer_prediction_counts':{p:len(r) for p,r in predictions.items()},
       'metrics':results,'coverage':[{k:v for k,v in r.items() if k!='normalized_monthly_cpg'} for r in wholesale]},indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--additional-source',type=Path);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();evaluate(args.source,args.out,args.additional_source)
