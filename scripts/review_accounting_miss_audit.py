"""Append reviewed reconciliations to the frozen capture, without fitting models."""
import argparse
from datetime import date, timedelta
from pathlib import Path
import re

from lxml import html

from musa_nowcast.data import load_actuals,load_market,load_weights
from musa_nowcast.geo import _predictions
from musa_nowcast.model import NowcastEngine
from musa_nowcast.pit_replay import now,save
from musa_nowcast.prospective import sha

from capture_accounting_miss_audit import RELEASES,PEERS

PREFIXES = {
 'retail_contribution_million':['Total retail fuel contribution'],
 'supply_excluding_rins_million':['Total PS&W contribution','Total fuel supply contribution'],
 'rins_or_rins_and_other_million':['RINs'],
 'total_fuel_contribution_million':['Total fuel contribution ($'],
 'retail_gallons_million':['Retail fuel volume - chain'],
 'petroleum_sales_million':['Petroleum product sales'],
 'petroleum_cogs_million':['Petroleum product cost of goods sold'],
 'retail_margin_cpg':['Retail fuel margin (cpg)'],
 'all_in_cpg':['Total fuel contribution (including','Total fuel contribution (cpg)'],
 'excise_tax_million':['(a) Includes excise taxes','(a)Includes excise taxes']
}


def first_number(cells):
    text = ' '.join(cells)
    match = re.search(r'\(?\s*-?\d[\d,]*\.\d+',text)
    if not match:
        raise ValueError('no numeric value in checked source row')
    return float(match.group().replace(',','').replace('(','-').replace(' ',''))


def read_values(path):
    tree = html.fromstring(path.read_bytes().decode('utf-8'))
    values,evidence = {},{}
    for tr in tree.xpath('//tr'):
        cells = [' '.join(' '.join(c.itertext()).split()) for c in tr.xpath('./th|./td')]
        if not cells:
            continue
        for key,prefixes in PREFIXES.items():
            if key not in values and any(cells[0].startswith(p) for p in prefixes):
                values[key] = first_number(cells[1:])
                evidence[key] = cells
    if len(set(PREFIXES)-set(values)-{'excise_tax_million'}) > 0:
        raise ValueError(f'incomplete reconciliation at {path}')
    return values,evidence


MECHANISMS = {
 '2021Q2':{'issuer_retail_explanation':'rising fuel prices; difficult prior-year record comparison',
           'issuer_supply_explanation':'higher RIN prices offset negative spot-to-rack margins; supply timing impacts',
           'model_inference':'rising-price regime and exceptional 2020 seasonal anchor; QuickChek acquisition also changes exposure'},
 '2021Q4':{'issuer_retail_explanation':'higher retail margins despite dynamic fuel pricing',
           'issuer_supply_explanation':'less contribution from timing and inventory pricing adjustments',
           'model_inference':'late wholesale reversal is consistent with capture; not a quantified causal attribution'},
 '2022Q1':{'issuer_retail_explanation':'higher retail margins despite rising commodity prices',
           'issuer_supply_explanation':'inventory timing and pricing boosted supply/RIN contribution',
           'model_inference':'model overstates retail gain; supply tailwind must not be mistaken for retail benefit'},
 '2022Q3':{'issuer_retail_explanation':'declining commodity prices strengthened retail margins',
           'issuer_supply_explanation':'falling-market timing/pricing hurt supply, partly offset by spot-to-rack and RIN sales',
           'model_inference':'strong retail expansion and negative supply contribution coexist; actual retail miss cannot be repaired by adding supply gains'},
 '2023Q3':{'issuer_retail_explanation':'comparison against prior-year falling-price benefit; margin fell 27%',
           'issuer_supply_explanation':'inventory pricing adjustments improved supply, with weaker spot-to-rack spreads',
           'model_inference':'exceptional 2022 seasonal anchor is consistent with production overestimate; not proof of causal decomposition'},
 '2026Q2':{'issuer_retail_explanation':'persistent volatility supported retail margins',
           'issuer_supply_explanation':'market-driven pricing and timing of inventory activity',
           'model_inference':'violent squeeze/capture reversal, plus distinct supply tailwind; no disclosed weekly retail costs to identify the mapping'}
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    args = parser.parse_args()
    root = args.root
    if (root/'reviewed_audit.json').exists():
        raise ValueError('refusing overwrite of reviewed audit')
    actuals = load_actuals('data/actuals.csv')
    engine = NowcastEngine(load_market('data/market.csv'),load_weights('data/weights.csv'),actuals)
    predictions = {r['quarter']:r for r in _predictions(engine)}
    indexed = {a.quarter:a for a in actuals}
    reviewed = []
    for q,(published,_) in RELEASES.items():
        path = root/f'{q}.html'
        values,evidence = read_values(path)
        a = indexed[q]
        retail = values['retail_contribution_million']
        supply = values['supply_excluding_rins_million']
        rins = values['rins_or_rins_and_other_million']
        total = values['total_fuel_contribution_million']
        gallons = values['retail_gallons_million']
        bridge = retail+supply+rins-total
        if abs(bridge) > .21 or abs(100*retail/gallons-values['retail_margin_cpg']) > .06:
            raise ValueError(f'reconciliation failed: {q}')
        if values['retail_margin_cpg'] != a.retail_margin_cpg or gallons != a.gallons_million:
            raise ValueError('issuer target disagrees with model input')
        other = total-(values['petroleum_sales_million']-values['petroleum_cogs_million'])-rins
        features = engine.features(a.start,a.end)
        reviewed.append({'quarter':q,'available_at_date':published,'date_precision':'DATE_ONLY',
          'source_sha256':sha(path),'evidence_rows':evidence,'reported':values,
          'production_prediction_cpg':predictions[q]['prediction_cpg'],
          'actual_minus_production_cpg':a.retail_margin_cpg-predictions[q]['prediction_cpg'],
          'mean_absolute_weekly_wholesale_move_cpg':features.price_volatility,
          'retail_supply_rins_bridge_difference_million':bridge,
          'retail_margin_recomputed_cpg':100*retail/gallons,
          'other_fuel_revenue_required_by_sales_cogs_bridge_million':other,
          'other_fuel_revenue_required_cpg':100*other/gallons,
          'other_revenue_exact_quarter_composition':'NOT_ISOLATED; annual filings identify collection allowances and miscellaneous items, not proof of this quarterly allocation',
          'information_cutoff_reference':str(a.end),
          'cutoff_reference_role':'quarter-end reference, not an archived historical forecast timestamp',
          'results_explanation_usable_at_reference_cutoff':False,
          'retail_acquisition_cost_recovered':False,'numeric_retail_inventory_adjustment_identified':False,
          'review_scope':'earnings tables/commentary plus annual accounting policies; not exhaustive quarter-specific 10Q/call audit',
          'interpretation':MECHANISMS[q]})
    peers = [
      {'company':'Caseys','ticker':'CASY','source_id':'caseys_f2027q1','publication_date':'2026-09-08',
       'period_start':'2026-05-01','period_end':'2026-07-31','metric':'retail fuel margin excluding credit-card fees and wholesale/terminal activity',
       'margin_cpg':47.8,'prior_year_cpg':41.0,'musa_q3_calendar_overlap_days':31,
       'forecast_priority':'FIRST_IMPLEMENTATION_CANDIDATE_BUT_EXISTING_MODEL_FAILED_GATE'},
      {'company':'Alimentation Couche-Tard','ticker':'ATD','source_id':'couchetard_f2027q1','publication_date':'2026-09-01',
       'period_start':'2026-04-27','period_end':'2026-07-19','period_start_method':'12-week period ending July19; derived start',
       'metric':'US company-operated fuel gross margin BEFORE electronic-payment fees',
       'margin_cpg':53.87,'prior_year_cpg':44.81,'musa_q3_calendar_overlap_days':19,
       'broader_us_road_fuel_metric_cpg':52.61,'broader_us_prior_year_cpg':44.00,
       'forecast_priority':'SECOND_IMPLEMENTATION_CANDIDATE_SEPARATE_US_TARGET_REQUIRED'},
      {'company':'ARKO','ticker':'ARKO','source_id':'arko_2026q2','publication_date':'2026-08-07',
       'period_start':'2026-04-01','period_end':'2026-06-30','metric':'same-store retail fuel margin',
       'margin_cpg':48.7,'prior_year_cpg':45.7,'musa_q3_calendar_overlap_days':0,
       'forecast_priority':'LOWER_PRIORITY_DEALERIZATION_AND_SEGMENT_SEPARATION',
       'earlier_than_musa_same_calendar_q2_results':False}]
    for peer in peers:
        _,url = PEERS[peer['source_id']]
        peer['source_url'] = url
        peer['source_sha256'] = sha(root/f"{peer['source_id']}.html")
        peer['available_by_2026_10_07'] = True
        peer['overlap_is_gallon_share'] = False
        peer['usable_role'] = 'period-matched peer context, not a direct MUSA margin anchor'
    save(root/'reviewed_audit.json',{'reviewed_at':now(),'audit_role':'RETROSPECTIVE_ACCOUNTING_DIAGNOSTIC_NOT_FORECAST_VALIDATION',
       'quarter_rows':reviewed,'peer_rows':peers,'production_changed':False,
       'original_22_quarter_disclosure_audit_changed':False,
       'source_check_corrections':[{'source_id':'2022Q1','correct_publication_date':'2022-05-03','reason':'verified issuer page; acquisition manifest guessed date is superseded here'},
                                   {'source_id':'arko_2026q2','correct_publication_date':'2026-08-07','reason':'verified issuer release date, formerly pending'}],
       'inventory_policy_note':'2021/2022 filings distinguish Murphy LIFO from QuickChek weighted-average costing; 2023/2025 filings state general LIFO policy. No effect size attributed to a retail-model error.',
       'input_hashes':{p:sha(Path(p)) for p in ['data/market.csv','data/weights.csv','data/actuals.csv','data/caseys/backtest.json',__file__]}})
    print([(r['quarter'],round(r['retail_margin_recomputed_cpg'],3),round(r['other_fuel_revenue_required_cpg'],3)) for r in reviewed])


if __name__ == '__main__':
    main()
