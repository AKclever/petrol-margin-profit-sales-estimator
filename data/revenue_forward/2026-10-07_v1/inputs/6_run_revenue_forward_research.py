"""Archive six-miss revenue diagnostics and two-quarter forward benchmarks."""
import argparse
import json
import re
from pathlib import Path
from statistics import mean

from lxml import html

from musa_nowcast.data import load_actuals, load_market, load_weights
from musa_nowcast.daily_capture import fetch
from musa_nowcast.geo import _predictions
from musa_nowcast.model import NowcastEngine
from musa_nowcast.pit_replay import now, save
from musa_nowcast.prospective import sha
from musa_nowcast.revenue_forward import decompose, forward_rows, metrics, revenue_pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    root = parser.parse_args().output
    root.mkdir(parents=True, exist_ok=False)
    paths = ['data/actuals.csv', 'data/market.csv', 'data/weights.csv',
             'data/revenue_forward_research_spec_v1.json',
             'data/peer_surprise/2026-10-07_v2/sources/MUSA_source_checks.json',
             'musa_nowcast/revenue_forward.py', __file__]
    # Freeze spec and input bytes before computing results; no input mutation.
    snapshots = root / 'inputs'; snapshots.mkdir()
    for i, p in enumerate(paths):
        with (snapshots / f'{i}_{Path(p).name}').open('xb') as f:
            f.write(Path(p).read_bytes())
    save(root/'input_manifest.json', {'frozen_at': now(), 'hashes': {p: sha(Path(p)) for p in paths}})
    actuals = load_actuals(paths[0]); indexed = {a.quarter: a for a in actuals}
    engine = NowcastEngine(load_market(paths[1]), load_weights(paths[2]), actuals)
    predictions = {r['quarter']: r for r in _predictions(engine)}
    verified = json.loads(Path(paths[4]).read_text())['verified']
    rows = forward_rows(actuals, verified)
    keys = json.loads(Path(paths[3]).read_text())['forward_benchmarks']
    for row in rows:
        row['production_realized_market_nowcast'] = predictions[row['quarter']]['prediction_cpg']
    forward = {'evaluation_role': 'RETROSPECTIVE_PUBLICATION_FILTERED_BASELINE_NOT_STRICT_PIT_VALIDATION',
               'rows': rows, 'benchmarks': {k: metrics(rows, k) for k in keys},
               'recent_eight': {k: metrics(rows[-8:], k) for k in keys},
               'matched_realized_market_nowcast': metrics(rows, 'production_realized_market_nowcast'),
               'production_two_quarter_forward_accuracy': 'NOT_VALIDATED',
               'unresolved_publication_dates_excluded': ['2022Q2'],
               'current_vintage_target_revision_audit_complete': False}
    save(root/'forward_benchmarks.json', forward)
    base = Path('data/accounting_miss_audit/2026-10-07_deeper_v2')
    q3url = 'https://www.sec.gov/Archives/edgar/data/1573516/000157351621000055/musa-20210930.htm'
    q3path = root/'2021Q3_filing.html'
    try:
        with q3path.open('xb') as f: f.write(fetch(q3url))
        q4revenues = revenue_pairs((base/'2021Q4_filing.html').read_bytes(), annual=True)[0]
        q3revenues = revenue_pairs(q3path.read_bytes())[1]
        q4pair = (q4revenues[0]-q3revenues[0], q4revenues[1]-q3revenues[1])
        q4error = None
    except Exception as exc:
        q4pair = None; q4error = str(exc)
    diagnostics = []
    checks = json.loads((base/'source_checks.json').read_text())
    # Preserve source checks in their existing structure, not reinterpret taxonomy.
    save(root/'existing_source_checks.json', checks)
    for q in ['2021Q2', '2021Q4', '2022Q1', '2022Q3', '2023Q3', '2026Q2']:
        a = indexed[q]; prior = indexed[f'{int(q[:4])-1}{q[4:]}']
        source = base/f'{q}_filing.html'
        if q == '2021Q4' and q4pair is None:
            diagnostics.append({'quarter': q, 'status': 'BLOCKED_RETAIL_REVENUE_SOURCE', 'reason': q4error})
            continue
        if q == '2021Q4':
            revenues = q4pair
            evidence = {'annual': q4revenues[2], 'nine_month': q3revenues[2],
                        'derivation': 'Annual minus nine-month retail-only revenues, separately for each year',
                        'additional_source_url': q3url, 'additional_source_sha256': sha(q3path)}
        else:
            pair = revenue_pairs(source.read_bytes())[0]; revenues = pair[:2]
            evidence = {'quarterly_retail_revenue_row': pair[2]}
        current_market = mean(r[1] for r in engine._weekly_basket(a.start, a.end))
        prior_market = mean(r[1] for r in engine._weekly_basket(prior.start, prior.end))
        result = decompose(*revenues, a.gallons_million, prior.gallons_million,
                           current_market-prior_market, a.retail_margin_cpg,
                           predictions[q]['prediction_cpg'])
        release = Path('data/accounting_miss_audit/2026-10-07_v1')/f'{q}.html'
        text = ' '.join(html.fromstring(release.read_bytes()).text_content().split())
        match = re.search(r'volumes on a same store sales.*?basis (increased|declined|decreased) ([\d.]+)%', text)
        growth = float(match[2]) * (1 if match[1] == 'increased' else -1) if match else None
        diagnostics.append({'quarter': q, 'status': 'ACCOUNTING_PROXY_DIAGNOSTIC_COMPLETE',
                            **result, 'reported_same_store_gallon_growth_percent': growth,
                            'same_store_evidence': match[0] if match else None,
                            'revenue_source_sha256': sha(source), 'release_sha256': sha(release),
                            'evidence': evidence, 'independent_acquisition_cost_recovered': False,
                            'exact_tax_product_reconciliation': 'UNAVAILABLE'})
    save(root/'revenue_diagnostics.json', {'created_at': now(), 'rows': diagnostics,
         'role': 'RETROSPECTIVE_ACCOUNTING_PROXY_DIAGNOSTIC_NOT_FORECAST',
         'sample_selected_on_largest_errors': True, 'production_changed': False,
         'causal_attribution_authorized': False, 'six_rows_not_sufficient_for_discount_volume_regression': True})
    print(json.dumps({'forward': forward['benchmarks'], 'recent_eight': forward['recent_eight'],
                      'matched_nowcast': forward['matched_realized_market_nowcast'],
                      'revenue_rows': diagnostics}, indent=2))


if __name__ == '__main__':
    main()
