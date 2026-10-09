"""Original-release US company-operated peer margins; no production changes."""
from __future__ import annotations
import argparse
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from lxml import html

from .daily_capture import fetch
from .data import QuarterActual, RegionWeight, load_actuals, load_market, load_weights
from .geo import _predictions
from .model import NowcastEngine
from .peer_surprise import fit_correction, overlap_days, select_peer
from .pit_replay import now, save
from .prospective import sha
from .timing import _metrics

SPEC = Path('data/couchetard_peer_spec_v1.json')
ORDINALS = {'FIRST':1,'SECOND':2,'THIRD':3,'FOURTH':4}
DATE = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d{2})'


def clean(tree):
    for e in tree.xpath('//script|//style'):
        e.drop_tree()
    return ' '.join(tree.text_content().split())


def parse_release(raw, url):
    name = re.search(r'FOR-ITS-(FIRST|SECOND|THIRD|FOURTH)-QUARTER.*?(20\d{2})$',url,re.I)
    if not name:
        raise ValueError('unrecognized fiscal period in original release URL')
    quarter, year = ORDINALS[name[1].upper()], int(name[2])
    tree = html.fromstring(raw.decode('utf-8'))
    text = clean(tree)
    table = next((t for t in tree.xpath('//table') if
                  'Before deduction of expenses related to electronic payment modes' in ' '.join(t.text_content().split())),None)
    if table is None:
        raise ValueError('missing separately identified payment-fee margin table')
    values = {}
    for tr in table.xpath('.//tr'):
        cells = [s for c in tr.xpath('./td|./th') if (s:=' '.join(c.text_content().split()))]
        for prefix, key in [('Before deduction','before'),('Expenses related','fees'),('After deduction','after')]:
            if cells and prefix in cells[0] and key not in values:
                nums = [float(x) for x in cells[1:] if re.fullmatch(r'\d+\.\d+',x)]
                if len(nums) != 5:
                    raise ValueError('expected four fiscal quarters and weighted average')
                values[key] = nums[3]
    if set(values) != {'before','fees','after'} or abs(values['before']-values['fees']-values['after']) > .021:
        raise ValueError('payment-fee basis does not reconcile')
    # Original results table gives actual fiscal length, including 16-week Q2 and 53-week years.
    current = re.search(r'For its (?:first|second|third|fourth) quarter ended\s+'+DATE,text,re.I)
    if not current:
        raise ValueError('missing explicit current-quarter end')
    end = datetime.strptime(f'{current[1]} {current[2]} {current[3]}','%B %d %Y').date()
    matches = list(re.finditer(r'(\d{2})[\s\-–‑]+week periods? ended\s+'+DATE,text,re.I))
    eligible = [m for m in matches if int(m[1]) in (12,13,16,17) and
                datetime.strptime(f'{m[2]} {m[3]} {m[4]}','%B %d %Y').date()==end]
    if not eligible:
        raise ValueError('fiscal period dates/length not disclosed in parseable results table')
    match = eligible[0]
    weeks = int(match[1])
    end = datetime.strptime(f'{match[2]} {match[3]} {match[4]}','%B %d %Y').date()
    if weeks not in (12,13,16,17) or abs(end.year-year)>1:
        raise ValueError('invalid fiscal calendar')
    start = end-timedelta(days=weeks*7-1)
    paragraphs = [' '.join(p.text_content().split()) for p in tree.xpath('//p')]
    acquisitions = list(dict.fromkeys(p for p in paragraphs if re.search(r'acquisition|acquired|divestiture',p,re.I) and len(p)<4000))
    return {'quarter':f'F{year}Q{quarter}', 'start':start.isoformat(),'end':end.isoformat(),
      'weeks':weeks, 'retail_margin_cpg':values['before'], 'payment_fees_cpg':values['fees'],
      'after_payment_margin_cpg':values['after'], 'available_at':url.split('/')[-1][:10],
      'source_url':url, 'target_basis':'US_COMPANY_OPERATED_BEFORE_PAYMENT_FEES',
      'acquisition_context':acquisitions, 'acquisition_adjustment_applied':False}


class FiscalEngine(NowcastEngine):
    def _prior_year_index(self,index):
        quarter=self.actuals[index].quarter
        wanted=f'F{int(quarter[1:5])-1}Q{quarter[-1]}'
        return next((i for i,a in enumerate(self.actuals[:index]) if a.quarter==wanted),None)


def fiscal_predictions(market,weights,targets,dates):
    results,excluded=[],[]
    for a in targets:
        earlier=[p for p in targets if p.end<a.start and date.fromisoformat(dates[p.quarter]['available_at'])<a.end]
        engine=FiscalEngine([m for m in market if m.week<=a.end],weights,earlier+[a])
        if len(earlier)<8 or engine._prior_year_index(len(earlier)) is None:
            excluded.append({'quarter':a.quarter,'reason':'INSUFFICIENT_HISTORY_OR_FISCAL_ANCHOR'})
            continue
        row=_predictions(engine)[-1]
        if row['quarter']!=a.quarter:raise ValueError('fiscal held-out mismatch')
        results.append(row|{'start':a.start.isoformat(),'end':a.end.isoformat(),
          'available_at':dates[a.quarter]['available_at'],'source':dates[a.quarter],
          'surprise_cpg':a.retail_margin_cpg-row['prediction_cpg'],
          'training_quarters':[p.quarter for p in earlier],'forecast_information_cutoff':a.end.isoformat()})
    return results,excluded


def evaluate(output,source_archive=None):
    output.mkdir(parents=True,exist_ok=False)
    source_dir = output/'sources'
    source_dir.mkdir()
    urls = []
    for offset in (0,100):
        url = f'https://corporate.couche-tard.com/financial-releases?l=100&o={offset}'
        raw = (source_archive/f'index_{offset}.html').read_bytes() if source_archive else fetch(url)
        with (source_dir/f'index_{offset}.html').open('xb') as f:f.write(raw)
        for a in html.fromstring(raw).xpath('//a'):
            link = a.get('href') or ''
            if re.search(r'announces.*results.*quarter.*20\d{2}$',link,re.I) and link not in urls and link.split('/')[-1][:10] >= '2018-01-01':
                urls.append(link)
    rows, checks = [], []
    for url in sorted(urls):
        filename = source_dir/(url.split('/')[-1]+'.html')
        try:
            raw = (source_archive/filename.name).read_bytes() if source_archive else fetch(url)
            with filename.open('xb') as f:f.write(raw)
            row = parse_release(raw,url)
            row['source_sha256'] = sha(filename)
            rows.append(row)
            checks.append({'url':url,'sha256':sha(filename),'status':'PARSED_RECONCILED','quarter':row['quarter']})
        except Exception as exc:
            checks.append({'url':url,'status':'UNRESOLVED_NOT_NO_DISCLOSURE','error':str(exc)})
    rows.sort(key=lambda r:r['end'])
    save(output/'history.json',{'rows':rows,'source_checks':checks,'captured_at':now()})
    inputs = list(map(Path,['data/market.csv','data/weights.csv','data/actuals.csv',
      'data/peer_surprise/2026-10-07_v2/sources/MUSA_source_checks.json']))
    market, actuals = load_market(inputs[0]),load_actuals(inputs[2])
    earliest = min(m.week for m in market)
    supported = [r for r in rows if date.fromisoformat(r['start']) >= earliest]
    targets = [QuarterActual(r['quarter'],date.fromisoformat(r['start']),date.fromisoformat(r['end']),r['retail_margin_cpg']) for r in supported]
    dates = {r['quarter']:{'available_at':r['available_at'],'url':r['source_url'],
                         'sha256':r['source_sha256']} for r in supported}
    # These equal weights are an explicit provisional proxy, not asserted company gallon shares.
    weights = [RegionWeight(r,1/3) for r in ('East Coast','Midwest','Gulf Coast')]
    peers, peer_excluded = fiscal_predictions(market,weights,targets,dates)
    engine = NowcastEngine(market,load_weights(inputs[1]),actuals)
    musa_dates = json.loads(inputs[3].read_text())['verified']
    indexed = {a.quarter:a for a in actuals}
    residuals, excluded = [], []
    for row in _predictions(engine):
        a = indexed[row['quarter']]
        peer = select_peer(peers,a.start,a.end)
        if peer is None or a.quarter not in musa_dates:
            excluded.append({'quarter':a.quarter,'reason':'NO_VERIFIED_ELIGIBLE_PEER_OR_MUSA_DATE'})
            continue
        residuals.append(row|{'peer':peer,'available_at':musa_dates[a.quarter]['available_at'],
          'cutoff':a.end.isoformat(),'calendar_overlap_days':overlap_days(a.start,a.end,peer)})
    challenger = {}
    for row in residuals:
        try:model, training = fit_correction(residuals,date.fromisoformat(row['cutoff']))
        except ValueError as exc:
            excluded.append({'quarter':row['quarter'],'reason':str(exc)})
            continue
        correction = .5*model.predict_one([row['peer']['surprise_cpg']])
        point = row['prediction_cpg']+correction
        challenger[row['quarter']] = row|{'prediction_cpg':point,'production_prediction_cpg':row['prediction_cpg'],
          'correction_cpg':correction,'training_quarters':[r['quarter'] for r in training],
          'direction_correct':engine._direction(point-row['seasonal_cpg'])==engine._direction(row['actual_cpg']-row['seasonal_cpg']),
          'production_abs_error_cpg':abs(row['actual_cpg']-row['prediction_cpg']),
          'challenger_abs_error_cpg':abs(row['actual_cpg']-point)}
    metrics = _metrics({r['quarter']:r for r in residuals},challenger,sorted(challenger)) if challenger else None
    start,end = date(2026,7,1),date(2026,9,30)
    peer = select_peer(peers,start,end)
    production = engine.forecast('2026Q3',start,end,date(2026,10,7)).retail_margin_cpg
    forecast = {'status':'BLOCKED_NO_ELIGIBLE_PEER','production_same_inputs_cpg':production}
    if peer:
        try:
            model,training = fit_correction(residuals,end)
            correction = .5*model.predict_one([peer['surprise_cpg']])
            forecast = {'status':'RESEARCH_ONLY','production_same_inputs_cpg':production,
              'retail_margin_cpg':production+correction,'correction_cpg':correction,'peer':peer,
              'calendar_overlap_days':overlap_days(start,end,peer),'eventual_actual_margin_cpg':None,
              'training_quarters':[r['quarter'] for r in training]}
        except ValueError as exc:forecast['status']=str(exc)
    result = {'specification':json.loads(SPEC.read_text()),'created_at':now(),'metrics':metrics,
      'forecast':forecast,'backtest_rows':[challenger[q] for q in sorted(challenger)],
      'excluded':excluded,'peer_predictions':peers,'peer_excluded':peer_excluded,
      'historical_market_pit_verified':False,'original_release_byte_identity_verified':False,
      'provisional_geography':True,'production_changed':False,
      'input_hashes':{str(p):sha(p) for p in inputs+[SPEC,Path(__file__),Path('musa_nowcast/peer_surprise.py'),
        Path('musa_nowcast/model.py'),Path('musa_nowcast/mathutils.py'),Path('musa_nowcast/geo.py'),Path('musa_nowcast/timing.py')]}}
    save(output/'result.json',result)
    (output/'inputs').mkdir()
    for name in result['input_hashes']:
        with (output/'inputs'/name.replace('/','__')).open('xb') as handle:
            handle.write(Path(name).read_bytes())
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--source-archive',type=Path)
    args=parser.parse_args()
    r=evaluate(args.output,args.source_archive)
    print(json.dumps({'metrics':r['metrics'],'forecast':r['forecast']},indent=2))


if __name__=='__main__':main()
