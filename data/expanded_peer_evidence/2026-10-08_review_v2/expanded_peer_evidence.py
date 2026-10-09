"""Immutable public-release capture for additional peers; never updates forecasts."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import urllib.request

from lxml import html


def capture(source):
    request = urllib.request.Request(source['url'], headers={'User-Agent': 'Mozilla/5.0 (public earnings research)'})
    with urllib.request.urlopen(request, timeout=35) as response:
        raw = response.read()
        final_url = response.url
    tree = html.fromstring(raw)
    for node in tree.xpath('//script|//style'):
        node.drop_tree()
    clean = lambda node: ' '.join(node.text_content().split())
    tables = [[clean(row) for row in table.xpath('.//tr')] for table in tree.xpath('//table')]
    return raw, {'id': source['id'], 'company': source['company'], 'source_url': source['url'],
        'resolved_url': final_url, 'captured_at': datetime.now(timezone.utc).isoformat(),
        'sha256': hashlib.sha256(raw).hexdigest(), 'status': 'RAW_CAPTURED',
        'text': clean(tree), 'tables': tables,
        'historical_snapshot_captured_at_publication': False}


def run(spec, output):
    output.mkdir(parents=True, exist_ok=False)
    (output/'raw').mkdir()
    sources = json.loads(spec.read_text())['sources']
    (output/'spec.json').write_bytes(spec.read_bytes())
    checks = []
    def one(source):
        try:
            raw, row = capture(source)
            relative = 'raw/'+source['id']+'.html'
            with (output/relative).open('xb') as handle:
                handle.write(raw)
            return row | {'raw_file': relative}
        except Exception as exc:
            return source | {'status': 'CAPTURE_FAILED', 'error': str(exc)}
    with ThreadPoolExecutor(max_workers=3) as pool:
        checks = list(pool.map(one, sources))
    (output/'source_checks.json').write_text(json.dumps({'checks': checks}, indent=2)+'\n')
    print(json.dumps([{k:r.get(k) for k in ['id','status','error']} for r in checks], indent=2))


def usable_before(publication_date, cutoff):
    """Date-only evidence cannot resolve same-day ordering."""
    if not publication_date:
        return False
    return date.fromisoformat(publication_date) < date.fromisoformat(cutoff)


def normalize(check):
    """Fail closed unless the reviewed quarterly target is identifiable."""
    if check['status'] != 'RAW_CAPTURED':
        raise ValueError('SOURCE_NOT_CAPTURED')
    text = check['text']
    rows = [r for table in check['tables'] for r in table]
    company = check['company']
    if company == 'ARKO':
        candidates = [r for r in rows if re.match(r'Fuel margin, cents per gallon\s*3\s', r)]
        if len(candidates) != 1:
            raise ValueError('AMBIGUOUS_RETAIL_TARGET')
        values = re.findall(r'\d+\.\d+', candidates[0])
        if len(values) not in [2, 4]:
            raise ValueError('UNEXPECTED_MARGIN_COLUMNS')
        current, prior = map(float, values[:2])
        definition = re.search(r'Calculated as fuel revenue less fuel costs; excludes.{0,150}?cost of fuel\.', text)
        if not definition:
            raise ValueError('UNVERIFIED_FUEL_FEE_BASIS')
        return {'actual_cpg': current, 'prior_year_comparison_cpg': prior,
                'target_basis': 'ARKO_RETAIL_FUEL_CONTRIBUTION_EXCLUDES_GPMP_FIXED_MARGIN_OR_FEE',
                'margin_evidence': candidates[0], 'definition_evidence': definition[0]}
    if company == 'CAPL':
        candidates = [r for r in rows if re.match(r'Margin per gallon, before deducting credit card fees\s+\$', r)]
        if len(candidates) != 1 or 'Company operated site statistics:' not in rows:
            raise ValueError('AMBIGUOUS_COMPANY_OPERATED_TARGET')
        values = re.findall(r'\$\s*(\d+\.\d+)', candidates[0])
        if len(values) not in [2, 4]:
            raise ValueError('UNEXPECTED_MARGIN_COLUMNS')
        combined = next(r for r in rows if r.startswith('Margin per gallon, before deducting credit card fees and commissions'))
        wholesale = next(r for r in rows if re.match(r'Margin per gallon\s+\$', r))
        return {'actual_cpg': 100*float(values[0]), 'prior_year_comparison_cpg': 100*float(values[1]),
                'target_basis': 'CAPL_COMPANY_OPERATED_BEFORE_CREDIT_CARD_FEES',
                'margin_evidence': candidates[0],
                'combined_retail_segment_cpg': 100*float(re.findall(r'\$\s*(\d+\.\d+)', combined)[0]),
                'wholesale_cpg': 100*float(re.findall(r'\$\s*(\d+\.\d+)', wholesale)[0])}
    raise ValueError('NOT_A_DIRECT_RETAIL_TARGET')


def review(output):
    """Review archived captures, preserving failed attempts and date-only ordering."""
    output.mkdir(parents=True, exist_ok=False)
    frozen = []
    for path in [Path(__file__), Path('data/expanded_peer_company_policy_v1.json'),
                 Path('data/history_floor_basis/2026-10-07_evaluation_v6/historical_targets.json')]:
        frozen.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        (output/path.name).write_bytes(path.read_bytes())
    checks = []
    manifests = []
    for run in ['2026-10-08_v1', '2026-10-08_fallback_v1']:
        root = Path('data/expanded_peer_evidence')/run
        path = root/'source_checks.json'
        manifests.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        for check in json.loads(path.read_text())['checks']:
            if check['status'] == 'RAW_CAPTURED':
                if hashlib.sha256((root/check['raw_file']).read_bytes()).hexdigest() != check['sha256']:
                    raise ValueError('RAW_HASH_MISMATCH')
            checks.append(check | {'capture_run': str(root)})
    dates = {'ARKO_2025Q1':'2025-05-08', 'ARKO_2025Q2':'2025-08-06',
             'ARKO_2025Q3':'2025-11-05', 'ARKO_2025Q4':'2026-02-25',
             'ARKO_2026Q1':'2026-05-07', 'ARKO_2026Q2':'2026-08-07',
             'CAPL_2025Q2':'2025-08-06', 'CAPL_2025Q4':'2026-02-25',
             'CAPL_2026Q1':'2026-05-06', 'CAPL_2026Q2':'2026-08-05'}
    months = {'01':('Jan.', 'January'), '02':('Feb.', 'February'), '05':('May',),
              '08':('Aug.', 'August'), '11':('Nov.', 'November')}
    musa = {r['quarter']:r['available_at'] for r in json.loads(Path(
        'data/history_floor_basis/2026-10-07_evaluation_v6/historical_targets.json').read_text())['quarters']}
    targets = []
    for check in checks:
        if check['status'] != 'RAW_CAPTURED' or check['id'] not in dates:
            continue
        stamp = dates[check['id']]
        y,m,d = stamp.split('-')
        if not any(f'{month} {int(d):02d}, {y}' in check['text'] or
                   f'{month} {int(d)}, {y}' in check['text'] for month in months[m]):
            raise ValueError('PUBLICATION_DATE_NOT_IN_SOURCE')
        q = check['id'].split('_')[1]
        year, quarter = int(q[:4]), int(q[-1])
        start = f'{year}-{(quarter-1)*3+1:02d}-01'
        end = f'{year}-{quarter*3:02d}-{30 if quarter in [2,3] else 31:02d}'
        targets.append(normalize(check) | {'company':check['company'], 'quarter':q,
            'start':start, 'end':end, 'available_at':stamp, 'availability_precision':'DATE_ONLY',
            'captured_at':check['captured_at'], 'source_url':check['source_url'], 'sha256':check['sha256'],
            'same_quarter_musa_report_date':musa.get(q),
            'usable_before_same_quarter_musa_report':usable_before(stamp,musa[q]) if q in musa else None,
            'historical_vintage_verified':False})
    guidance = []
    for q,nextq in [('2025Q1','2025Q2'),('2025Q2','2025Q3'),('2025Q3','2025Q4')]:
        source = next(c for c in checks if c['id']=='ARKO_'+q and c['status']=='RAW_CAPTURED')
        passage = re.search(r'The Company currently expects (?:second|third|fourth) quarter 2025 Adjusted EBITDA.{0,260}?cents per gallon\.',source['text'])
        if not passage or '42.5 to 44.5' not in passage[0]:
            raise ValueError('UNVERIFIED_QUARTERLY_GUIDANCE')
        actual = next(r['actual_cpg'] for r in targets if r['company']=='ARKO' and r['quarter']==nextq)
        guidance.append({'company':'ARKO', 'target_quarter':nextq, 'available_at':dates['ARKO_'+q],
            'low_cpg':42.5, 'high_cpg':44.5, 'midpoint_cpg':43.5, 'eventual_actual_cpg':actual,
            'midpoint_abs_error_cpg':abs(actual-43.5), 'within_range':42.5<=actual<=44.5,
            'usable_before_musa_report':usable_before(dates['ARKO_'+q],musa[nextq]),
            'evidence':passage[0], 'source_url':source['source_url'], 'sha256':source['sha256'],
            'interpretation':'OWN_COMPANY_EBITDA_ASSUMPTION_NOT_MUSA_GUIDANCE'})
    result = {'role':'RESEARCH_EVIDENCE_ONLY_NOT_FORECAST_VALIDATION', 'targets':targets,
              'guidance_checks':guidance, 'source_manifests':manifests, 'frozen_inputs':frozen,
              'capture_failures':[{'id':c['id'],'error':c['error']} for c in checks if c['status']!='RAW_CAPTURED'],
              'production_changed':False, 'own_margin_backtest_status':'BLOCKED_INSUFFICIENT_REVIEWED_HISTORY',
              'cross_company_transfer_status':'NOT_FITTED_NOT_AUTHORIZED_BY_EVIDENCE'}
    (output/'reviewed_evidence.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'targets':len(targets),'guidance_checks':guidance},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--spec', type=Path)
    parser.add_argument('--review', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.review:
        review(args.out)
    elif args.spec:
        run(args.spec, args.out)
    else:
        parser.error('--spec is required for capture')
