"""Daily price evidence capture and exact-date diagnostics, not a margin estimator."""
from __future__ import annotations
import argparse
import json
import re
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import xlrd
from lxml import html

from .daily_capture import fetch
from .data import load_actuals
from .pit_replay import now, save
from .prospective import sha

SPEC=Path('data/daily_prices_spec_v1.json')
WHOLESALE={'NYH':'EER_EPMRU_PF4_Y35NY_DPG','USGC':'EER_EPMRU_PF4_RGC_DPG'}


def parse_wholesale(raw, series):
    workbook=xlrd.open_workbook(file_contents=raw)
    sheet=workbook.sheet_by_name('Data 1')
    if series not in WHOLESALE or sheet.cell_value(1,1)!=WHOLESALE[series]:
        raise ValueError('daily wholesale source-series mismatch')
    rows=[]
    for i in range(sheet.nrows):
        cells=sheet.row_values(i)
        if len(cells)<2 or sheet.cell_type(i,0)!=xlrd.XL_CELL_DATE:
            continue
        observed=xlrd.xldate_as_datetime(cells[0],workbook.datemode).date()
        if not isinstance(cells[1],(float,int)):
            continue
        value=float(cells[1])*100
        if not 0 < value < 2000:
            raise ValueError('invalid wholesale value')
        rows.append({'observed_at':observed.isoformat(),'series':series,'wholesale_cpg':value})
    if not rows or len({r['observed_at'] for r in rows})!=len(rows):
        raise ValueError('missing or duplicate daily wholesale observations')
    return rows


def parse_aaa(raw):
    tree=html.fromstring(raw.decode('utf-8'))
    visible=html.fromstring(raw.decode('utf-8'))
    for e in visible.xpath('//script|//style'):e.drop_tree()
    text=' '.join(visible.text_content().split())
    match=re.search(r'Price as of\s+(\d{1,2}/\d{1,2}/\d{2,4})',text)
    if not match:raise ValueError('AAA snapshot has no explicit observation date')
    fmt='%m/%d/%y' if len(match[1].split('/')[-1])==2 else '%m/%d/%Y'
    observed=datetime.strptime(match[1],fmt).date().isoformat()
    # Homepage's public regular-price map; no hidden API or challenge bypass.
    scripts=' '.join(s.text or '' for s in tree.xpath('//script'))
    values=re.findall(r'([A-Z]{2}),([^,;]+),\$([0-9]+\.[0-9]+),https://gasprices\.aaa\.com\?state=\1',scripts)
    unique={}
    for state,name,value in values:
        cpg=float(value)*100
        if not 0 < cpg < 2000:raise ValueError('invalid retail price')
        if state in unique and unique[state]['retail_cpg']!=cpg:raise ValueError('conflicting state prices')
        unique[state]={'observed_at':observed,'state':state,'state_name':name,'retail_cpg':cpg,
                       'fuel_grade':'REGULAR','basis':'AAA_STATE_AVERAGE_NOT_MUSA'}
    if len(unique)!=51:raise ValueError('AAA state map incomplete; expected 50 states plus DC')
    return list(unique.values())


def exact_pairs(retail, wholesale):
    costs={(r['observed_at'],r['series']):r for r in wholesale}
    rows=[]
    for r in retail:
        # Mapping must be supplied explicitly; never imply a state is NYH or USGC.
        key=(r['observed_at'],r.get('wholesale_series'))
        if key not in costs:continue
        w=costs[key]
        if not r.get('available_at') or not w.get('available_at'):
            raise ValueError('matched observations require separate availability timestamps')
        available=max(datetime.fromisoformat(r['available_at']),datetime.fromisoformat(w['available_at'])).isoformat()
        rows.append(r|{'wholesale_cpg':w['wholesale_cpg'],'spread_cpg':r['retail_cpg']-w['wholesale_cpg'],
                       'join_method':'EXACT_DATE_NO_FILL','available_at':available,
                       'retail_available_at':r['available_at'],'wholesale_available_at':w['available_at'],
                       'wholesale_raw_sha256':w.get('raw_sha256')})
    return rows


def daily_diagnostics(rows,start,end):
    selected=[r for r in rows if start<=date.fromisoformat(r['observed_at'])<=end]
    by_week=defaultdict(list)
    for r in selected:
        d=date.fromisoformat(r['observed_at']);week=d-timedelta(days=d.weekday())
        by_week[week].append(r['wholesale_cpg'])
    ranges=[max(v)-min(v) for v in by_week.values() if len(v)>=2]
    ordered=sorted(selected,key=lambda r:r['observed_at'])
    moves=[b['wholesale_cpg']-a['wholesale_cpg'] for a,b in zip(ordered,ordered[1:])
           if (date.fromisoformat(b['observed_at'])-date.fromisoformat(a['observed_at'])).days<=3]
    return {'daily_observations':len(selected),'weeks_with_at_least_two_observations':len(ranges),
      'mean_within_week_range_cpg':statistics.mean(ranges) if ranges else None,
      'maximum_within_week_range_cpg':max(ranges) if ranges else None,
      'positive_daily_move_total_cpg':sum(max(x,0) for x in moves),
      'negative_daily_move_magnitude_total_cpg':sum(max(-x,0) for x in moves),
      'interpretation':'WHOLESALE_PATH_DIAGNOSTIC_NOT_REALIZED_MUSA_MARGIN'}


def capture(output, aaa_snapshot=None, permission=None, fetcher=fetch, source_archive=None):
    output.mkdir(parents=True,exist_ok=False)
    wholesale=[];sources=[];retail=[]
    processed=now()
    original=json.loads((source_archive/'manifest.json').read_text()) if source_archive else None
    captured=original['captured_at'] if original else processed
    for region,key in WHOLESALE.items():
        url=f'https://www.eia.gov/dnav/pet/hist_xls/{key}d.xls'
        raw=(source_archive/f'{region}.xls').read_bytes() if source_archive else fetcher(url)
        path=output/f'{region}.xls'
        with path.open('xb') as f:f.write(raw)
        rows=parse_wholesale(raw,region)
        wholesale.extend(r|{'available_at':captured,'captured_at':captured,'raw_sha256':sha(path),
          'availability_method':'FIRST_CAPTURE_CURRENT_VINTAGE_NOT_HISTORICAL_PIT'} for r in rows)
        sources.append({'url':url,'raw_file':path.name,'sha256':sha(path),'captured_at':captured})
    if permission:
        policy=json.loads(permission.read_text())
        if policy.get('source')!='https://gasprices.aaa.com/' or policy.get('automated_capture_authorized') is not True:
            raise ValueError('AAA automated capture permission not established')
        raw=fetcher('https://gasprices.aaa.com/')
    elif aaa_snapshot:
        raw=aaa_snapshot.read_bytes()
    else:raw=None
    if raw:
        path=output/'aaa_snapshot.html'
        with path.open('xb') as f:f.write(raw)
        retail=[r|{'available_at':captured,'captured_at':captured,'raw_sha256':sha(path),
                    'availability_method':'FIRST_CAPTURE_CONSERVATIVE'} for r in parse_aaa(raw)]
        sources.append({'url':'https://gasprices.aaa.com/','raw_file':path.name,'sha256':sha(path),
                         'capture_mode':'AUTHORIZED_AUTOMATION' if permission else 'LOCAL_FEASIBILITY_SNAPSHOT'})
    save(output/'wholesale.json',{'rows':wholesale})
    save(output/'retail.json',{'rows':retail})
    actuals=load_actuals('data/actuals.csv')
    diagnostics=[]
    for a in actuals:
        diagnostics.append({'quarter':a.quarter,'regions':{region:daily_diagnostics(
            [r for r in wholesale if r['series']==region],a.start,a.end) for region in WHOLESALE}})
    result={'captured_at':captured,'processed_at':processed,
      'acquisition_mode':'REPROCESS_EXISTING_RAW_CAPTURE' if source_archive else 'NETWORK_CAPTURE',
      'source_archive_manifest_sha256':sha(source_archive/'manifest.json') if source_archive else None,
      'sources':sources,'retail_observations':len(retail),
      'wholesale_observations':len(wholesale),'specification':json.loads(SPEC.read_text()),
      'daily_retail_historical_dates':sorted({r['observed_at'] for r in retail}),
      'backtest_status':'BLOCKED_DAILY_RETAIL_HISTORY','daily_margin_forecast':None,
      'aaa_automation_status':'ENABLED_WITH_PERMISSION_ARTIFACT' if permission else 'DISABLED_PENDING_PERMISSION_REVIEW',
      'quarterly_wholesale_path_diagnostics':diagnostics,'production_changed':False,
      'input_hashes':{str(p):sha(p) for p in [SPEC,Path(__file__),Path('data/actuals.csv')]}}
    save(output/'manifest.json',result)
    (output/'inputs').mkdir()
    for name in result['input_hashes']:
        with (output/'inputs'/name.replace('/','__')).open('xb') as handle:handle.write(Path(name).read_bytes())
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--aaa-snapshot',type=Path)
    parser.add_argument('--aaa-permission',type=Path)
    parser.add_argument('--source-archive',type=Path,help='reprocess an existing raw archive, not a new network observation')
    args=parser.parse_args();r=capture(args.output,args.aaa_snapshot,args.aaa_permission,source_archive=args.source_archive)
    print(json.dumps({k:r[k] for k in ['retail_observations','wholesale_observations','backtest_status','aaa_automation_status']},indent=2))


if __name__=='__main__':main()
