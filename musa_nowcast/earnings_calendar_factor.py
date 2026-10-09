"""Two frozen publication-filtered research shadows; production is untouched."""
import argparse
from datetime import date, timedelta
import json
from pathlib import Path

from .anchor_reliability import ROOT, tail_metrics
from .historical_evidence_extension import peer_corrections
from .history_floor_basis import bounds, regime
from .mathutils import solve
from .model import NowcastEngine
from .pit_replay import now, save
from .prospective import sha
from .timing import _metrics

ARCHIVE = Path('data/historical_evidence_extension/2026-10-08_review_v3')
SPEC = Path('data/earnings_calendar_factor_spec_v1.json')
COMPANIES = ['CASY', 'ATD', 'MUSA']


def select_peer(rows, start, end, cutoff):
    eligible = [r for r in rows if r['available_at'] < cutoff
                and r['end'] < cutoff and r['start'] <= str(end) and r['end'] >= str(start)]
    return max(eligible, key=lambda r: (r['available_at'], r['end'])) if eligible else None


def calendar_inputs(baseline, targets, peers, final):
    matched, blocked = [], []
    for q, row in sorted(baseline.items()):
        start, end = bounds(q)
        cutoff = targets[q]['available_at'] if final else str(end)
        selected = {p: select_peer(peers[p], start, end, cutoff) for p in ['CASY', 'ATD']}
        if not all(selected.values()):
            blocked.append({'quarter': q, 'reason': 'MISSING_PUBLISHED_OVERLAPPING_PEER_PAIR'})
            continue
        overlaps = {p: (min(end, date.fromisoformat(r['end'])) -
                       max(start, date.fromisoformat(r['start']))).days + 1 for p, r in selected.items()}
        matched.append(row | {'available_at': targets[q]['available_at'], 'cutoff': cutoff,
                       'features': [selected[p]['surprise_cpg'] for p in ['CASY', 'ATD']],
                       'peers': selected, 'overlap_days': overlaps})
    return matched, blocked


def shift_month(month, offset):
    index = month.year * 12 + month.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def period_weights(start, end, months):
    if start > end or start < months[0] or end >= shift_month(months[-1], 1):
        raise ValueError('period outside factor window')
    length = (end - start).days + 1
    return [max(0, (min(end, shift_month(m, 1) - timedelta(days=1)) - max(start, m)).days + 1) / length
            for m in months]


def latent_fit(observations, months):
    """Unit-loading interval factor with separate penalized company offsets."""
    width = len(months) + len(COMPANIES)
    gram = [[0.0] * width for _ in range(width)]
    rhs = [0.0] * width
    for obs in observations:
        weights = period_weights(date.fromisoformat(obs['start']), date.fromisoformat(obs['end']), months)
        design = weights + [float(obs['company'] == c) for c in COMPANIES]
        for i in range(width):
            rhs[i] += design[i] * obs['surprise_cpg']
            for j in range(width):
                gram[i][j] += design[i] * design[j]
    for i in range(width):
        gram[i][i] += 2.0
    for i in range(len(months) - 1):
        gram[i][i] += 2.0
        gram[i+1][i+1] += 2.0
        gram[i][i+1] -= 2.0
        gram[i+1][i] -= 2.0
    coefficients = solve(gram, rhs)
    return {'monthly_factor_cpg': dict(zip(map(str, months), coefficients[:len(months)])),
            'company_offsets_cpg': dict(zip(COMPANIES, coefficients[len(months):])),
            'coefficients': coefficients}


def factor_forecast(q, baseline, targets, peers, cutoff):
    start, end = bounds(q)
    months = [shift_month(date.fromisoformat(cutoff).replace(day=1), i) for i in range(-23, 1)]
    if start < months[0]:
        return None, 'TARGET_OUTSIDE_FACTOR_WINDOW'
    era = regime(q)
    era_start = date(2021,1,1) if era == 'later_regime' else date(2020,1,1) if era == 'transition' else date.min
    earlier = [p for p in baseline if p < q and regime(p) == era and targets[p]['available_at'] < cutoff]
    if len(earlier) < 8:
        return None, 'FEWER_THAN_EIGHT_SAME_REGIME_PUBLISHED_MUSA_RESIDUALS'
    observations = []
    for company in ['CASY', 'ATD']:
        for row in peers[company]:
            if (row['available_at'] < cutoff and row['end'] < cutoff
                    and row['start'] >= str(max(months[0], era_start))
                    and row['end'] < str(shift_month(months[-1],1))):
                observations.append(row | {'company': company})
        if sum(o['company'] == company for o in observations) < 4:
            return None, 'FEWER_THAN_FOUR_WINDOW_OBSERVATIONS_' + company
    if not any(o['start'] <= str(end) and o['end'] >= str(start) for o in observations):
        return None, 'NO_PUBLISHED_TARGET_OVERLAPPING_PEER'
    for p in sorted(earlier):
        ps, pe = bounds(p)
        if ps < max(months[0], era_start):
            continue
        observations.append({'company': 'MUSA', 'quarter': p, 'start': str(ps), 'end': str(pe),
                             'available_at': targets[p]['available_at'],
                             'surprise_cpg': baseline[p]['actual_cpg'] - baseline[p]['prediction_cpg'],
                             'source_url': targets[p].get('source_url'),
                             'source_sha256': targets[p].get('source_sha256')})
    fit = latent_fit(observations, months)
    weights = period_weights(start, end, months)
    factor = sum(w * v for w, v in zip(weights, fit['coefficients']))
    offset = fit['company_offsets_cpg']['MUSA']
    correction = 0.5 * (factor + offset)
    return {'quarter': q, 'cutoff': cutoff, 'prediction_cpg': baseline[q]['prediction_cpg'] + correction,
            'correction_cpg': correction, 'quarter_shared_factor_cpg': factor,
            'musa_offset_cpg': offset, 'fit': fit, 'observations': observations,
            'training_quarters': [o['quarter'] for o in observations if o['company'] == 'MUSA'],
            'interval_weights_are_gallon_shares': False}, None


def score(baseline, forecasts):
    shadows = {}
    for q, f in forecasts.items():
        b = baseline[q]
        shadows[q] = b | f | {'production_prediction_cpg': b['prediction_cpg'],
            'production_abs_error_cpg': abs(b['actual_cpg'] - b['prediction_cpg']),
            'shadow_abs_error_cpg': abs(b['actual_cpg'] - f['prediction_cpg']),
            'direction_correct': NowcastEngine._direction(f['prediction_cpg'] - b['seasonal_cpg']) ==
                                 NowcastEngine._direction(b['actual_cpg'] - b['seasonal_cpg'])}
    by_era = {}
    for era in ['earlier_low_margin', 'transition', 'later_regime']:
        qs = sorted(q for q in forecasts if regime(q) == era)
        big = [q for q in qs if abs(baseline[q]['actual_cpg'] - baseline[q]['prediction_cpg']) >= 5]
        by_era[era] = {'quarters': qs, 'metrics': _metrics(baseline, shadows, qs) if qs else None,
                       'tails': tail_metrics(baseline, shadows, qs),
                       'large_group': tail_metrics(baseline, shadows, big),
                       'ordinary_group': tail_metrics(baseline, shadows, [q for q in qs if q not in big])}
    return {'by_regime': by_era, 'rows': list(shadows.values())}


def evaluate(output):
    output.mkdir(parents=True, exist_ok=False)
    files = [SPEC, Path(__file__), ARCHIVE/'reviewed_peer_history.json', ROOT/'results.json',
             ROOT/'historical_targets.json', Path('musa_nowcast/historical_evidence_extension.py'),
             Path('musa_nowcast/mathutils.py'), Path('musa_nowcast/timing.py'),
             ARCHIVE/'frozen_inputs.json', ARCHIVE/'perimeter_audit.json']
    save(output/'frozen_inputs.json', {'created_at': now(), 'files': [{'path':str(p),'sha256':sha(p)} for p in files]})
    (output/'inputs').mkdir()
    for i, p in enumerate(files):
        with (output/'inputs'/f'{i}_{p.name}').open('xb') as handle:
            handle.write(p.read_bytes())
    peers = json.loads((ARCHIVE/'reviewed_peer_history.json').read_text())['peer_predictions']
    baseline = {r['quarter']: r for r in json.loads((ROOT/'results.json').read_text())['baseline_rows']}
    targets = {r['quarter']: r for r in json.loads((ROOT/'historical_targets.json').read_text())['quarters']}
    all_forecasts, exclusions, matched = {}, {}, {}
    for name, final in [('calendar_quarter_end', False), ('calendar_pre_report', True)]:
        matched[name], missing = calendar_inputs(baseline, targets, peers, final)
        all_forecasts[name], blocked = peer_corrections(matched[name])
        exclusions[name] = missing + blocked
    for name, final in [('factor_quarter_end', False), ('factor_pre_report', True)]:
        all_forecasts[name], exclusions[name] = {}, []
        for q in sorted(baseline):
            cutoff = targets[q]['available_at'] if final else str(bounds(q)[1])
            forecast, reason = factor_forecast(q, baseline, targets, peers, cutoff)
            if forecast:
                all_forecasts[name][q] = forecast
            else:
                exclusions[name].append({'quarter':q,'reason':reason})
    save(output/'frozen_forecasts.json', {'frozen_at': now(), 'forecasts': all_forecasts,
         'calendar_inputs': matched, 'exclusions': exclusions})
    results = {name: score(baseline, f) for name, f in all_forecasts.items()}
    comparisons = {}
    for prefix in ['calendar', 'factor']:
        first, last = [all_forecasts[prefix+'_'+suffix] for suffix in ['quarter_end', 'pre_report']]
        qs = sorted(set(first) & set(last))
        comparisons[prefix] = [{'quarter':q, 'quarter_end_prediction_cpg':first[q]['prediction_cpg'],
                               'pre_report_prediction_cpg':last[q]['prediction_cpg'],
                               'incremental_abs_error_improvement_cpg':
                                   abs(baseline[q]['actual_cpg']-first[q]['prediction_cpg']) -
                                   abs(baseline[q]['actual_cpg']-last[q]['prediction_cpg'])} for q in qs]
    sign_rows = []
    for r in matched['calendar_pre_report']:
        q = r['quarter']
        start, end = bounds(q)
        first_peers = {p:select_peer(peers[p],start,end,str(end)) for p in ['CASY','ATD']}
        added = [p for p in ['CASY','ATD'] if first_peers[p] is None or
                 r['peers'][p]['quarter'] != first_peers[p]['quarter']]
        for p in added:
            sign_rows.append({'quarter':q,'peer':p,'available_at':r['peers'][p]['available_at'],
                'surprise_cpg':r['peers'][p]['surprise_cpg'],
                'production_error_actual_minus_forecast_cpg':baseline[q]['actual_cpg']-baseline[q]['prediction_cpg'],
                'sign_matched': NowcastEngine._direction(r['peers'][p]['surprise_cpg']) ==
                                NowcastEngine._direction(baseline[q]['actual_cpg']-baseline[q]['prediction_cpg'])})
    large = [q for q in baseline if q >= '2021Q1' and abs(baseline[q]['actual_cpg']-baseline[q]['prediction_cpg']) >= 5]
    payload = {'role':json.loads(SPEC.read_text())['role'], 'models':results,'checkpoint_comparisons':comparisons,
        'newly_selected_peer_sign_diagnostic':sign_rows,
        'large_miss_coverage':[{ 'quarter':q, 'models':{n:q in f for n,f in all_forecasts.items()}} for q in large],
        'strict_market_pit_verified':False,'production_changed':False,'automatic_promotion':False,
        'current_quarter_live_forecast_generated':False}
    save(output/'results.json', payload)
    print(json.dumps({n:r['by_regime'] for n,r in results.items()},indent=2))
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    evaluate(parser.parse_args().out)
