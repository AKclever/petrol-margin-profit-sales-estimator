"""Focused Q3 2026 snapshot; frozen methods only, no production mutation."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import io
import json
from pathlib import Path
import urllib.request

from .data import load_actuals, load_market, load_weights
from .eia import DEFAULT_SERIES, _xls_url, download_market, fetch_series_xls
from .earnings_event_replay import donor_input, select
from .model import NowcastEngine
from .prospective import sha
from .risk import assess
from .timing import CANDIDATES, transform_market

Q2_URL='https://www.sec.gov/Archives/edgar/data/1573516/000157351626000164/exh991_06302026er.htm'
PEERS=Path('data/earnings_event_replay/2026-10-08_v3/dataset.json')
LATEST_PEER=Path('data/peer_surprise/2026-10-07_v2/result.json')
Q2_ARCHIVE=Path('data/accounting_miss_audit/2026-10-07_v1/2026Q2.html')
CHAMPION=Path('data/shadow/checkpoints/2026Q3_2026-09-28_20260927T211754Z.json')
START,END,ASOF=date(2026,7,1),date(2026,9,30),date(2026,10,8)


def fixed_peer_shadow(base, records):
    target={'start':START.isoformat(),'end':END.isoformat()}
    donor=select(target,'CASY',records,ASOF.isoformat())
    if donor is None:
        return {'status':'BLOCKED_NO_ELIGIBLE_REPORT'}
    x=donor_input(target,donor)
    return {'status':'RESEARCH_SHADOW_NOT_PROMOTED','retail_margin_cpg':base+.5*x,
        'correction_cpg':.5*x,'donor_quarter':donor['quarter'],
        'donor_available_at':donor['available_at'],'donor_actual_cpg':donor['actual_cpg'],
        'donor_baseline_cpg':donor['prediction_cpg'],'overlap_weighted_surprise_cpg':x,
        'source_url':donor['source_url'],'source_sha256':donor['source_sha256'],
        'weight_rule':'0.5 times calendar-overlap-weighted own-company surprise; not gallon share'}


def run(output, source_snapshot=None):
    output.mkdir(parents=True,exist_ok=False)
    (output/'raw').mkdir()
    ids=sorted({s for region in DEFAULT_SERIES for s in [region.retail,region.wholesale]})
    def capture(series):
        if source_snapshot is not None:
            raw=(source_snapshot/'raw'/(series+'.xls')).read_bytes()
        else:
            request=urllib.request.Request(_xls_url(series),headers={'User-Agent':'musa-margin-nowcast/0.1'})
            with urllib.request.urlopen(request,timeout=35) as response:
                raw=response.read()
        path=output/'raw'/(series+'.xls')
        path.write_bytes(raw)
        return series,raw
    with ThreadPoolExecutor(max_workers=3) as pool:
        snapshots=dict(pool.map(capture,ids))
    def fetcher(series,key,start,end):
        return fetch_series_xls(series,key,start,end,opener=lambda *args,**kwargs:io.BytesIO(snapshots[series]))
    download_market(output/'market.csv',output/'market.provenance.json','',date(2019,1,1),ASOF,
        fetcher=fetcher,source='official_xls_immutable_raw_capture')
    (output/'raw'/'musa_q2_2026.html').write_bytes(Q2_ARCHIVE.read_bytes())
    from lxml import html
    text=' '.join(html.fromstring((output/'raw'/'musa_q2_2026.html').read_bytes()).text_content().split())
    if 'second half all-in fuel margins average 35 cents per gallon' not in text:
        raise ValueError('MANAGEMENT_SCOPE_NOT_VERIFIED')
    inputs=[Path('data/weights.csv'),Path('data/actuals.csv'),PEERS,CHAMPION,Path(__file__),LATEST_PEER,Q2_ARCHIVE,
        Path('musa_nowcast/model.py'),Path('musa_nowcast/timing.py'),Path('musa_nowcast/risk.py')]
    (output/'inputs').mkdir()
    manifest=[]
    for i,p in enumerate(inputs):
        manifest.append({'path':str(p),'sha256':sha(p)})
        (output/'inputs'/f'{i}_{p.name}').write_bytes(p.read_bytes())
    market=load_market(output/'market.csv');weights=load_weights(inputs[0]);actuals=load_actuals(inputs[1])
    if any(a.quarter=='2026Q3' for a in actuals):
        raise ValueError('TARGET_ALREADY_REPORTED')
    engine=NowcastEngine(market,weights,actuals)
    current=engine.forecast('2026Q3',START,END,ASOF).as_dict()
    timing={name:NowcastEngine(transform_market(market,name),weights,actuals)
        .forecast('2026Q3',START,END,ASOF).as_dict() for name in CANDIDATES}
    basket=engine._weekly_basket(START,END,ASOF)
    weekly=[]
    for i,(week,retail,cost) in enumerate(basket):
        dr=retail-basket[i-1][1] if i else None
        dc=cost-basket[i-1][2] if i else None
        weekly.append({'week':str(week),'retail_proxy_cpg':retail,'wholesale_proxy_cpg':cost,
            'spread_proxy_cpg':retail-cost,'retail_change_cpg':dr,'wholesale_change_cpg':dc,
            'falling_capture_impulse_cpg':max(dr-dc,0) if dc is not None and dc<0 else 0,
            'rising_squeeze_impulse_cpg':max(dc-dr,0) if dc is not None and dc>0 else 0})
    spreads=[r['spread_proxy_cpg'] for r in weekly]
    # Explicit proxy weighting sensitivities, not alternative calibrated forecasts.
    months={m:[r['spread_proxy_cpg'] for r in weekly if int(r['week'][5:7])==m] for m in [7,8,9]}
    monthly={str(m):sum(v)/len(v) for m,v in months.items()}
    sensitivity={'equal_week_spread_proxy_cpg':sum(spreads)/len(spreads),
        'equal_month_spread_proxy_cpg':sum(monthly.values())/3,
        'monthly_spread_proxies_cpg':monthly,
        'minimum_week_spread_proxy_cpg':min(spreads),'maximum_week_spread_proxy_cpg':max(spreads),
        'interpretation':'Market proxy only, includes retail taxes; not MUSA margin or observed gallon weights'}
    records=json.loads(PEERS.read_text())['records']
    latest=json.loads(LATEST_PEER.read_text())['peer_predictions'][-1]
    records.append(latest | {'company':'CASY','source_url':latest['source']['url'],
        'source_sha256':latest['source']['sha256']})
    peer=fixed_peer_shadow(current['retail_margin_cpg'],records)
    peer['donor_baseline_provenance']='Existing Casey pilot expanding forecast; latest quarter absent from older event replay dataset'
    official=json.loads(CHAMPION.read_text())['forecasts']['PRODUCTION']
    result={'quarter':'2026Q3','information_cutoff':str(ASOF),'production_changed':False,
        'raw_market_capture_origin':str(source_snapshot) if source_snapshot else 'CURRENT_RUN',
        'frozen_official_forecast':official,'refreshed_frozen_method_forecast':current,
        'timing_shadows':timing,'caseys_fixed_shadow':peer,'risk':assess(engine,START,END,ASOF),
        'weekly_path':weekly,'weight_sensitivity':sensitivity,
        'management_evidence':{'available_at':'2026-08-05','source_url':Q2_URL,
            'source_sha256':sha(output/'raw'/'musa_q2_2026.html'),'margin_cpg':35,
            'period':'SECOND_HALF_2026','basis':'ALL_IN','role':'CONDITIONAL_EARNINGS_ASSUMPTION',
            'usable_retail_anchor':False},
        'coverage_note':'12 model-complete weeks, July 6–September 21. Quarter-edge days are not directly modelled. September 28 spot week crosses into October and is excluded by frozen complete-week rule.',
        'scenario_note':'Timing spread and model error bands are diagnostics, not calibrated tail probabilities. Supply/RIN is the frozen historical component, not an independent Q3 supply forecast.'}
    manifest.extend({'path':str(p),'sha256':sha(p)} for p in sorted((output/'raw').iterdir()))
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'refreshed':current,'peer':peer,'timing':{k:v['retail_margin_cpg'] for k,v in timing.items()},'risk':result['risk']},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--source-snapshot',type=Path)
    args=parser.parse_args();run(args.out,args.source_snapshot)
