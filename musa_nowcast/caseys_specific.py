"""Casey-specific RIN decomposition research, without production changes."""
import argparse
from datetime import date
import json
from pathlib import Path
import re

from lxml import html

from .anchor_reliability import tail_metrics
from .couchetard_peer import fiscal_predictions
from .data import QuarterActual, load_weights
from .historical_evidence_extension import ROOT
from .joint_all_features import market_from_json
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .timing import _metrics

SPEC = Path('data/caseys_specific_spec_v1.json')
HISTORY = Path('data/historical_evidence_extension/2026-10-08_review_v3/reviewed_peer_history.json')
SOURCE = Path('data/caseys_specific/2026-10-08_sources_v2')
POLICY = Path('data/caseys_specific/2026-10-08_policies_v1')


def extract(raw, expected):
    tree = html.fromstring(raw,parser=html.HTMLParser(encoding='utf-8'))
    text = ' '.join(tree.text_content().split())
    margin_rows = [t for t in tree.xpath('//tr') if 'Fuel margin (cents per gallon, excluding credit card fees)' in t.text_content()]
    gallon_rows = [t for t in tree.xpath('//tr') if 'Fuel gallons sold (in thousands)' in t.text_content()]
    if not margin_rows or not gallon_rows:
        raise ValueError('NO_EXPLICIT_QUARTERLY_MARGIN_AND_GALLON_TABLE')
    margin = float(re.search(r'\d+\.\d+',margin_rows[0].text_content())[0])
    if abs(margin-expected['retail_margin_cpg']) > .001:
        raise ValueError('CURRENT_MARGIN_DOES_NOT_MATCH_REVIEWED_TARGET')
    gallon_text = gallon_rows[0].text_content().split('(in thousands)',1)[1]
    gallons = float(re.search(r'\d[\d,]*',gallon_text)[0].replace(',','')) * 1000
    matches = list(re.finditer(r'Company (?:sold|generated) \$([\d.]+) million in renewable fuel credits(?:\s*\(RINs\))? in the (?:first |second |third |fourth )?quarter',text,re.I))
    zero = re.search(r'Company did not sell (?:any renewable fuel credits\s*\(RINs\)|RINs) (?:during|in) the (?:first |second |third |fourth )?quarter',text,re.I)
    if zero and matches:
        raise ValueError('CONFLICTING_CURRENT_RIN_EVIDENCE')
    if len(matches) == 1:
        dollars = float(matches[0][1])*1e6; evidence = matches[0][0]
    elif zero:
        dollars = 0.; evidence = zero[0]
    else:
        raise ValueError('MISSING_UNIQUE_CURRENT_QUARTER_RIN_PROCEEDS_NOT_ZERO')
    cpg = dollars/gallons*100
    if not 0 <= cpg <= margin:
        raise ValueError('RIN_COMPONENT_OUTSIDE_MARGIN_BOUNDS')
    return expected | {'rin_proceeds_dollars':dollars,'fuel_gallons':gallons,'rin_proceeds_cpg':cpg,
                       'ex_rin_proxy_cpg':margin-cpg,'rin_evidence':evidence,
                       'gallons_evidence':gallon_rows[0].text_content(),
                       'margin_evidence':margin_rows[0].text_content(),
                       'component_basis':'REPORTED_MARGIN_MINUS_DISCLOSED_RIN_PROCEEDS_PROXY_NOT_INVOICE_COST'}


def component_forecasts(records, market, weights):
    actuals = [QuarterActual(r['quarter'],date.fromisoformat(r['start']),date.fromisoformat(r['end']),r['ex_rin_proxy_cpg']) for r in records]
    dates = {r['quarter']:{'available_at':r['available_at'],'url':r['source_url'],'sha256':r['source_sha256']} for r in records}
    predictions, excluded = fiscal_predictions(market,weights,actuals,dates)
    output = {}
    for prediction in predictions:
        prior = sorted([r for r in records if r['quarter'] in prediction['training_quarters']],key=lambda r:r['end'])[-4:]
        if len(prior) < 4:
            excluded.append({'quarter':prediction['quarter'],'reason':'FEWER_THAN_FOUR_PUBLISHED_RIN_COMPONENTS'});continue
        rin = sum(r['rin_proceeds_cpg'] for r in prior)/4
        output[prediction['quarter']] = {'prediction_cpg':prediction['prediction_cpg']+rin,
             'ex_rin_forecast_cpg':prediction['prediction_cpg'],'rin_forecast_cpg':rin,
             'training_quarters':prediction['training_quarters'],'rin_training_quarters':[r['quarter'] for r in prior],
             'information_cutoff':prediction['forecast_information_cutoff']}
    return output, excluded


def simple_baseline(q, records):
    current = records[q]
    earlier = [r for r in records.values() if r['end'] < current['start'] and r['available_at'] < current['end']]
    indexed = {r['quarter']:r for r in earlier}
    def anchor(label):return f'F{int(label[1:5])-1}Q{label[-1]}'
    if anchor(q) not in indexed:
        return None
    changes = [r['retail_margin_cpg']-indexed[anchor(r['quarter'])]['retail_margin_cpg']
               for r in sorted(earlier,key=lambda r:r['end']) if anchor(r['quarter']) in indexed][-4:]
    if len(changes) < 4:return None
    return indexed[anchor(q)]['retail_margin_cpg'] + .5*sum(changes)/4


def evaluate(output):
    output.mkdir(parents=True,exist_ok=False)
    inputs = [SPEC,Path(__file__),HISTORY,SOURCE/'source_checks.json',POLICY/'source_checks.json',
              ROOT/'normalized_market.json',Path('data/caseys/weights.csv'),
              Path('musa_nowcast/couchetard_peer.py'),Path('musa_nowcast/model.py'),Path('musa_nowcast/mathutils.py')]
    checks = json.loads((SOURCE/'source_checks.json').read_text())['checks']
    policies = json.loads((POLICY/'source_checks.json').read_text())['checks']
    for c in checks + policies:
        folder = SOURCE if 'quarter' in c else POLICY
        if c.get('raw_file'):
            p=folder/c['raw_file']
            if sha(p) != c['sha256']:raise ValueError('source changed')
            inputs.append(p)
    save(output/'frozen_inputs.json',{'created_at':now(),'files':[{'path':str(p),'sha256':sha(p)} for p in inputs]})
    (output/'inputs').mkdir()
    for i,p in enumerate(inputs):
        with (output/'inputs'/f'{i}_{p.name}').open('xb') as h:h.write(p.read_bytes())
    policy_text = ' '.join(html.fromstring((POLICY/'policy_2024.html').read_bytes()).text_content().split())
    if not re.search(r'RINs are recorded as a reduction in cost of goods sold',policy_text):
        raise ValueError('RIN accounting reduction basis unverified')
    records = {r['quarter']:r for r in json.loads(HISTORY.read_text())['histories']['CASY']}
    # Latest achieved margin is independently supported by the existing archived release.
    latest = next(c for c in checks if c['quarter']=='F2027Q1' and c['status']=='RAW_CAPTURED')
    latest_text = ' '.join(html.fromstring((SOURCE/latest['raw_file']).read_bytes()).text_content().split())
    if '47.8' not in latest_text:raise ValueError('latest achieved margin not supported')
    records['F2027Q1']={'quarter':'F2027Q1','start':'2026-05-01','end':'2026-07-31','retail_margin_cpg':47.8,
                         'available_at':latest['available_at'],'source_url':latest['source_url'],'source_sha256':latest['sha256']}
    components, reviews = [], []
    for c in checks:
        review = dict(c)
        try:
            if c['status']!='RAW_CAPTURED':raise ValueError(c.get('error','FETCH_FAILED'))
            if c['quarter']=='F2027Q1':raise ValueError('BLOCKED_RIN_ACCOUNTING_CHANGE_PROCEEDS_NOT_TOTAL_RECOGNIZED_INCOME')
            expected=records[c['quarter']] | {'available_at':c['available_at'],'source_url':c['source_url'],'source_sha256':c['sha256']}
            row=extract((SOURCE/c['raw_file']).read_bytes(),expected)
            components.append(row);review.update(review_status='COMPONENT_RECONCILED',evidence=row)
        except (ValueError,KeyError,TypeError) as exc:
            review.update(review_status='UNRESOLVED_NOT_NO_DISCLOSURE',reason=str(exc))
        reviews.append(review)
    components.sort(key=lambda r:r['end'])
    save(output/'components.json',{'records':components,'source_reviews':reviews,'policies':policies,
        'gross_proceeds_proxy_not_independently_observed_net_retail_cost':True,'historical_geography_reconstructed':False})
    market = market_from_json(json.loads((ROOT/'normalized_market.json').read_text())['regular'])
    weights = load_weights('data/caseys/weights.csv')
    targets=[QuarterActual(r['quarter'],date.fromisoformat(r['start']),date.fromisoformat(r['end']),r['retail_margin_cpg']) for r in sorted(records.values(),key=lambda r:r['end'])]
    dates={q:{'available_at':r['available_at'],'url':r['source_url'],'sha256':r['source_sha256']} for q,r in records.items()}
    comparator, baseline_excluded=fiscal_predictions(market,weights,targets,dates)
    baseline={r['quarter']:r for r in comparator}
    frozen,excluded=component_forecasts(components,market,weights)
    # Diagnostic control: identical component-supported training population, no RIN split.
    matched_targets=[QuarterActual(r['quarter'],date.fromisoformat(r['start']),date.fromisoformat(r['end']),r['retail_margin_cpg']) for r in components]
    matched_dates={r['quarter']:dates[r['quarter']] for r in components}
    matched_predictions,_=fiscal_predictions(market,weights,matched_targets,matched_dates)
    matched_history={r['quarter']:r for r in matched_predictions}
    recent={q:simple_baseline(q,records) for q in frozen}
    frozen={q:f for q,f in frozen.items() if q in baseline and recent[q] is not None}
    save(output/'frozen_forecasts.json',{'created_at':now(),'forecasts':frozen,'recent_level_baselines':recent,'excluded':excluded,
         'component_model_target':'EX_RIN_PROCEEDS_PROXY','baseline_excluded':baseline_excluded})
    rows={q:baseline[q]|f|{'original_prediction_cpg':baseline[q]['prediction_cpg'],
          'direction_correct':NowcastEngine._direction(f['prediction_cpg']-baseline[q]['seasonal_cpg']) ==
                              NowcastEngine._direction(baseline[q]['actual_cpg']-baseline[q]['seasonal_cpg']),
          'original_abs_error_cpg':abs(baseline[q]['actual_cpg']-baseline[q]['prediction_cpg']),
          'shadow_abs_error_cpg':abs(baseline[q]['actual_cpg']-f['prediction_cpg']),
          'recent_level_prediction_cpg':recent[q]} for q,f in frozen.items()}
    groups={}
    for label,qs in [('all',sorted(rows)),('2021_onward_start',[q for q in sorted(rows) if records[q]['start']>='2021-01-01'])]:
        big=[q for q in qs if abs(baseline[q]['actual_cpg']-baseline[q]['prediction_cpg'])>=5]
        level={q:baseline[q]|{'prediction_cpg':recent[q]} for q in qs}
        seasonal={q:baseline[q]|{'prediction_cpg':baseline[q]['seasonal_cpg']} for q in qs}
        groups[label]={'quarters':qs,'metrics':_metrics(baseline,rows,qs) if qs else None,
              'same_history_no_split_metrics':_metrics(matched_history,rows,qs) if qs else None,
              'tails':tail_metrics(baseline,rows,qs),'large_group':tail_metrics(baseline,rows,big),
              'ordinary_group':tail_metrics(baseline,rows,[q for q in qs if q not in big]),
              'recent_level_baseline':tail_metrics(level,level,qs),
              'seasonal_baseline':tail_metrics(seasonal,seasonal,qs)}
    result={'role':json.loads(SPEC.read_text())['role'],'groups':groups,'rows':list(rows.values()),
            'same_history_no_split_predictions':matched_predictions,
            'reconciled_component_quarters':len(components),'production_changed':False,'automatic_promotion':False,
            'strict_market_pit_verified':False,'live_forecast_generated':False}
    save(output/'results.json',result)
    print(json.dumps({'component_quarters':len(components),'groups':groups},indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True,type=Path)
    evaluate(parser.parse_args().out)
