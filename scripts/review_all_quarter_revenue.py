"""Review captured all-quarter evidence without changing production or fitting."""
import argparse
import json
from pathlib import Path
from statistics import mean

from musa_nowcast.data import load_actuals, load_market, load_weights
from musa_nowcast.geo import _predictions
from musa_nowcast.model import NowcastEngine
from musa_nowcast.pit_replay import now, save
from musa_nowcast.prospective import sha
from musa_nowcast.revenue_forward import decompose, revenue_pairs
from musa_nowcast.revenue_gap_audit import reported_sss, reported_volume_and_margin, summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); root = args.output
    root.mkdir(parents=True, exist_ok=False)
    paths = ['data/actuals.csv','data/market.csv','data/weights.csv',
             'data/revenue_gap_all_quarters_spec_v1.json','musa_nowcast/revenue_gap_audit.py',
             'musa_nowcast/revenue_forward.py', __file__]
    snapshots = root/'inputs'; snapshots.mkdir()
    for i,p in enumerate(paths):
        with (snapshots/f'{i}_{Path(p).name}').open('xb') as f: f.write(Path(p).read_bytes())
    checks = json.loads((args.capture/'source_checks.json').read_text())['checks']
    for check in checks:
        if 'sha256' in check and sha(args.capture/check['raw_file']) != check['sha256']:
            raise ValueError('Captured raw hash mismatch')
    save(root/'input_manifest.json', {'frozen_at': now(), 'hashes': {p: sha(Path(p)) for p in paths},
          'capture_source_checks_sha256': sha(args.capture/'source_checks.json')})
    source_map = {(c['quarter'],c['source_type']): c for c in checks if c.get('raw_file')}
    actuals = load_actuals(paths[0]); indexed = {a.quarter:a for a in actuals}
    engine = NowcastEngine(load_market(paths[1]),load_weights(paths[2]),actuals)
    predictions = {r['quarter']:r for r in _predictions(engine)}
    rows = []; revenues = {}
    for a in actuals:
        q = a.quarter; source = source_map.get((q,'10-K' if q.endswith('4') else '10-Q'))
        row = {'quarter': q, 'quarter_end': str(a.end), 'issues': [],
               'actual_margin_cpg': a.retail_margin_cpg, 'reported_gallons_million': a.gallons_million,
               'original_target_revision_audit_complete': False,
               'exact_tax_product_reconciliation': 'UNAVAILABLE'}
        pred = predictions.get(q)
        row['production_prediction_cpg'] = pred['prediction_cpg'] if pred else None
        row['actual_minus_production_cpg'] = a.retail_margin_cpg-pred['prediction_cpg'] if pred else None
        try:
            if not source: raise ValueError('Original period filing unavailable')
            pairs = revenue_pairs((args.capture/source['raw_file']).read_bytes(), annual=q.endswith('4'))
            current, comparative, evidence = pairs[0]
            revenue_sources = [source]
            if q.endswith('4'):
                ytd = source_map[(q[:4]+'Q3','10-Q')]
                ytd_pair = revenue_pairs((args.capture/ytd['raw_file']).read_bytes())[1]
                current -= ytd_pair[0]; comparative -= ytd_pair[1]
                evidence = {'annual': evidence,'nine_month': ytd_pair[2], 'method': 'ANNUAL_MINUS_NINE_MONTH_RETAIL_ONLY'}
                revenue_sources.append(ytd)
            if current <= 0: raise ValueError('Invalid retail-only revenue')
            revenues[q] = current
            row.update({'retail_revenue_million': current, 'reported_revenue_per_gallon_cpg': 100*current/a.gallons_million,
                        'prior_year_comparative_revenue_million': comparative,
                        'revenue_evidence': evidence, 'revenue_sources': revenue_sources})
        except Exception as exc:
            row['issues'].append({'state':'BLOCKED_RETAIL_REVENUE_EVIDENCE','reason':str(exc)})
        release = source_map.get((q,'SEC_EARNINGS_EXHIBIT'))
        try:
            if not release: raise ValueError('Original earnings exhibit unavailable')
            raw = (args.capture/release['raw_file']).read_bytes()
            values = reported_volume_and_margin(raw)
            if abs(values['gallons_million']['value']-a.gallons_million) > .11 or abs(values['retail_margin_cpg']['value']-a.retail_margin_cpg) > .051:
                raise ValueError('Earnings gallons/margin disagree with target inputs')
            sss = reported_sss(raw)
            row.update({'reported_same_store_gallon_growth_percent':sss['value'], 'sss_audit':sss,
                        'release_source':release, 'target_table_evidence':values})
        except Exception as exc:
            row['reported_same_store_gallon_growth_percent'] = None
            row['issues'].append({'state':'BLOCKED_SSS_OR_TARGET_RECONCILIATION','reason':str(exc)})
        rows.append(row)
    for row in rows:
        q = row['quarter']; prior_q = f'{int(q[:4])-1}{q[4:]}'
        if q not in revenues or prior_q not in revenues:
            row['issues'].append({'state':'BLOCKED_PRIOR_YEAR_REVENUE_OR_MARKET', 'reason':'First year or missing source; no inferred prior-year market'})
            continue
        a = indexed[q]; prior = indexed[prior_q]
        current_market = mean(w[1] for w in engine._weekly_basket(a.start,a.end))
        prior_market = mean(w[1] for w in engine._weekly_basket(prior.start,prior.end))
        if row['production_prediction_cpg'] is None:
            prior_price = 100*revenues[prior_q]/prior.gallons_million
            proxy = prior_price + current_market-prior_market
            result = {'prior_reported_revenue_per_gallon_cpg':prior_price,
                      'eia_yoy_retail_change_cpg':current_market-prior_market,
                      'revenue_proxy_cpg':proxy,
                      'revenue_proxy_error_cpg':row['reported_revenue_per_gallon_cpg']-proxy,
                      'implied_cost_residual_cpg':None, 'actual_minus_production_cpg':None,
                      'identity_reconciliation_cpg':None}
        else:
            result = decompose(revenues[q], revenues[prior_q], a.gallons_million, prior.gallons_million,
                               current_market-prior_market, a.retail_margin_cpg,
                               row['production_prediction_cpg'])
        row.update(result)
        row['prior_revenue_source_quarter'] = prior_q
        row['comparative_revenue_difference_million'] = row['prior_year_comparative_revenue_million']-revenues[prior_q]
        prior_row = next(r for r in rows if r['quarter'] == prior_q)
        row['revenue_gap_available_at'] = max(s['publication_date'] for s in row['revenue_sources']+prior_row['revenue_sources'])
    checks_ytd = []
    for year in sorted({a.start.year for a in actuals}):
        quarters = [f'{year}Q{i}' for i in range(1,5)]
        if all(q in revenues for q in quarters):
            annual_source = source_map[(f'{year}Q4','10-K')]
            annual = revenue_pairs((args.capture/annual_source['raw_file']).read_bytes(),annual=True)[0][0]
            diff = sum(revenues[q] for q in quarters)-annual
            if abs(diff) > .21: raise ValueError('Quarterly retail revenue does not reconcile to annual')
            checks_ytd.append({'year':year, 'quarter_sum_minus_annual_million':diff})
    save(root/'quarter_rows.json', {'created_at':now(), 'rows':rows,
         'role':'RETROSPECTIVE_ACCOUNTING_PROXY_DIAGNOSTIC_NOT_FORECAST_VALIDATION',
         'annual_revenue_reconciliations':checks_ytd, 'production_changed':False})
    summary = summarize(rows)
    save(root/'summary.json', summary)
    print(json.dumps(summary,indent=2))
    print('Unresolved',[(r['quarter'],r['issues']) for r in rows if r['issues']])


if __name__ == '__main__':
    main()
