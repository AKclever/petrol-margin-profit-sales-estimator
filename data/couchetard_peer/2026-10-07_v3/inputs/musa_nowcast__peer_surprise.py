"""Casey's period-matched surprise pilot. Research only; never production."""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from lxml import html

from .daily_capture import fetch
from .data import QuarterActual, load_actuals, load_market, load_weights
from .geo import _predictions
from .mathutils import RidgeModel
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .timing import _metrics

SPEC = Path('data/peer_surprise_spec_v1.json')


def eligible_training(rows, cutoff):
    return [r for r in rows if date.fromisoformat(r['available_at']) < cutoff]


def select_peer(rows, start, end):
    eligible = [r for r in rows if date.fromisoformat(r['available_at']) < end
                and date.fromisoformat(r['start']) <= end
                and date.fromisoformat(r['end']) >= start]
    return max(eligible, key=lambda r:r['end']) if eligible else None


def overlap_days(start, end, peer):
    return max(0, (min(end, date.fromisoformat(peer['end']))
                   - max(start, date.fromisoformat(peer['start']))).days+1)


def capture_dates(output, symbol, cik, periods):
    raw = fetch(f'https://data.sec.gov/submissions/CIK{cik:010d}.json')
    with (output/f'{symbol}_submissions.json').open('xb') as handle:
        handle.write(raw)
    recent = json.loads(raw)['filings']['recent']
    verified, checks = {}, []
    for index, form in enumerate(recent['form']):
        if form != '8-K' or '2.02' not in recent['items'][index]:
            continue
        filed = date.fromisoformat(recent['filingDate'][index])
        candidates = [a for a in periods if a.end < filed
                      and (filed-a.end).days <= 90 and a.quarter not in verified]
        if not candidates:
            continue
        accession = recent['accessionNumber'][index].replace('-', '')
        url = f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{recent["primaryDocument"][index]}'
        payload = fetch(url)
        path = output/f'{symbol}_{accession}.html'
        with path.open('xb') as handle:
            handle.write(payload)
        text = ' '.join(html.fromstring(payload).text_content().split())
        # Isolate Item 2.02, avoiding dates in other items and exhibit indexes.
        section = re.search(r'Item\s*2\.02\.?(.*?)(?=Item\s*\d\.\d\d|Signature|$)', text, re.I)
        evidence = section.group(1) if section else ''
        matched = []
        for actual in candidates:
            stamp = f'{actual.end:%B} {actual.end.day}, {actual.end.year}'
            if stamp in evidence and re.search(r'financial results|earnings|results of operations', evidence, re.I):
                verified[actual.quarter] = {'available_at':filed.isoformat(), 'url':url,
                    'sha256':sha(path), 'evidence':evidence, 'availability_basis':'SEC filingDate, conservative date only'}
                matched.append(actual.quarter)
        checks.append({'url':url, 'sha256':sha(path), 'matched_quarters':matched})
    save(output/f'{symbol}_source_checks.json', {'captured_at':now(), 'checks':checks,
         'verified':verified, 'unresolved':[a.quarter for a in periods if a.quarter not in verified]})
    return verified


def peer_predictions(market, weights, actuals, dates):
    result, excluded = [], []
    for actual in actuals:
        if actual.quarter not in dates:
            excluded.append({'quarter':actual.quarter, 'reason':'UNVERIFIED_PUBLICATION_DATE'})
            continue
        earlier = [a for a in actuals if a.end < actual.start and a.quarter in dates
                   and date.fromisoformat(dates[a.quarter]['available_at']) < actual.end]
        if len(earlier) < 8:
            excluded.append({'quarter':actual.quarter, 'reason':'INSUFFICIENT_EARLIER_PEER_TARGETS'})
            continue
        # Future weeks never enter this target's inputs. Original market vintage remains unverified.
        engine = NowcastEngine([m for m in market if m.week <= actual.end], weights, earlier+[actual])
        prediction = _predictions(engine)[-1]
        if prediction['quarter'] != actual.quarter:
            raise ValueError('peer held-out target mismatch')
        result.append(prediction | {'start':actual.start.isoformat(), 'end':actual.end.isoformat(),
          'available_at':dates[actual.quarter]['available_at'], 'source':dates[actual.quarter],
          'surprise_cpg':actual.retail_margin_cpg-prediction['prediction_cpg'],
          'training_quarters':[a.quarter for a in earlier], 'forecast_information_cutoff':actual.end.isoformat()})
    return result, excluded


def fit_correction(rows, cutoff):
    training = eligible_training(rows, cutoff)
    if len(training) < 8:
        raise ValueError('INSUFFICIENT_EIGHT_AVAILABLE_MUSA_RESIDUALS')
    model = RidgeModel(2).fit([[r['peer']['surprise_cpg']] for r in training],
                             [r['actual_cpg']-r['prediction_cpg'] for r in training])
    return model, training


def evaluate(output):
    output.mkdir(parents=True, exist_ok=False)
    sources = output/'sources'
    sources.mkdir()
    inputs = list(map(Path, ['data/market.csv','data/weights.csv','data/actuals.csv',
                            'data/caseys/weights.csv','data/caseys/actuals.csv']))
    market, weights, actuals = load_market(inputs[0]), load_weights(inputs[1]), load_actuals(inputs[2])
    peers = load_actuals(inputs[4])
    # Latest original earnings release archived by the prior accounting capture.
    latest_source = Path('data/accounting_miss_audit/2026-10-07_v1/caseys_f2027q1.html')
    latest_text = ' '.join(html.fromstring(latest_source.read_bytes()).text_content().split())
    if not re.search(r'47\.8', latest_text):
        raise ValueError('latest peer actual not supported by archived release')
    peers.append(QuarterActual('F2027Q1', date(2026,5,1), date(2026,7,31), 47.8))
    peer_dates = capture_dates(sources, 'CASY', 726958, peers)
    musa_dates = capture_dates(sources, 'MUSA', 1573516, actuals)
    peer_rows, peer_excluded = peer_predictions(market, load_weights(inputs[3]), peers, peer_dates)
    engine = NowcastEngine(market, weights, actuals)
    by_quarter = {a.quarter:a for a in actuals}
    residuals, excluded = [], []
    for row in _predictions(engine):
        actual = by_quarter[row['quarter']]
        peer = select_peer(peer_rows, actual.start, actual.end)
        if peer is None or actual.quarter not in musa_dates:
            excluded.append({'quarter':actual.quarter, 'reason':'NO_ELIGIBLE_PEER_OR_UNVERIFIED_MUSA_PUBLICATION'})
            continue
        residuals.append(row | {'peer':peer, 'available_at':musa_dates[actual.quarter]['available_at'],
                               'cutoff':actual.end.isoformat(), 'calendar_overlap_days':overlap_days(actual.start,actual.end,peer)})
    challenger = {}
    for row in residuals:
        cutoff = date.fromisoformat(row['cutoff'])
        try:
            model, training = fit_correction(residuals, cutoff)
        except ValueError as exc:
            excluded.append({'quarter':row['quarter'], 'reason':str(exc)})
            continue
        correction = .5*model.predict_one([row['peer']['surprise_cpg']])
        point = row['prediction_cpg']+correction
        challenger[row['quarter']] = row | {'prediction_cpg':point, 'production_prediction_cpg':row['prediction_cpg'],
          'correction_cpg':correction, 'training_quarters':[r['quarter'] for r in training],
          'direction_correct':engine._direction(point-row['seasonal_cpg']) == engine._direction(row['actual_cpg']-row['seasonal_cpg']),
          'production_abs_error_cpg':abs(row['actual_cpg']-row['prediction_cpg']),
          'challenger_abs_error_cpg':abs(row['actual_cpg']-point)}
    metrics = _metrics({r['quarter']:r for r in residuals}, challenger, sorted(challenger)) if challenger else None
    start, end = date(2026,7,1), date(2026,9,30)
    peer = select_peer(peer_rows, start, end)
    production = engine.forecast('2026Q3',start,end,date(2026,10,7)).retail_margin_cpg
    forecast = {'status':'BLOCKED_NO_ELIGIBLE_PEER', 'production_same_inputs_cpg':production}
    if peer:
        model, training = fit_correction(residuals, end)
        correction = .5*model.predict_one([peer['surprise_cpg']])
        forecast = {'status':'RESEARCH_ONLY', 'quarter':'2026Q3', 'information_cutoff':end.isoformat(),
          'production_same_inputs_cpg':production, 'retail_margin_cpg':production+correction,
          'correction_cpg':correction, 'peer':peer, 'calendar_overlap_days':overlap_days(start,end,peer),
          'training_quarters':[r['quarter'] for r in training], 'eventual_actual_margin_cpg':None,
          'coefficients':model.coefficients, 'feature_means':model.means, 'feature_scales':model.scales}
    snapshots = inputs+[SPEC, Path(__file__), latest_source, Path('musa_nowcast/model.py'),
                        Path('musa_nowcast/mathutils.py'), Path('musa_nowcast/geo.py'), Path('musa_nowcast/timing.py')]
    result = {'created_at':now(), 'specification':json.loads(SPEC.read_text()), 'metrics':metrics,
      'forecast':forecast, 'backtest_rows':[challenger[q] for q in sorted(challenger)],
      'excluded':excluded, 'peer_predictions':peer_rows, 'peer_excluded':peer_excluded,
      'production_changed':False, 'input_hashes':{str(p):sha(p) for p in snapshots}}
    save(output/'result.json',result)
    (output/'inputs').mkdir()
    for path in snapshots:
        with (output/'inputs'/str(path).replace('/', '__')).open('xb') as handle:
            handle.write(path.read_bytes())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    result = evaluate(parser.parse_args().output)
    print(json.dumps({'metrics':result['metrics'], 'forecast':result['forecast']},indent=2))


if __name__ == '__main__':
    main()
