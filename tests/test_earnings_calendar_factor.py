from copy import deepcopy
from datetime import date
import json

import pytest

from musa_nowcast.earnings_calendar_factor import (
    ARCHIVE, ROOT, calendar_inputs, factor_forecast, latent_fit,
    period_weights, select_peer, shift_month,
)
from musa_nowcast.historical_evidence_extension import peer_corrections


def inputs():
    peers = json.loads((ARCHIVE/'reviewed_peer_history.json').read_text())['peer_predictions']
    baseline = {r['quarter']:r for r in json.loads((ROOT/'results.json').read_text())['baseline_rows']}
    targets = {r['quarter']:r for r in json.loads((ROOT/'historical_targets.json').read_text())['quarters']}
    return baseline, targets, peers


def test_calendar_accepts_later_report_but_never_same_day():
    row = {'quarter':'F2020Q1','start':'2020-02-01','end':'2020-04-30','available_at':'2020-06-10'}
    assert select_peer([row],date(2020,4,1),date(2020,6,30),'2020-06-10') is None
    assert select_peer([row],date(2020,4,1),date(2020,6,30),'2020-06-11') == row
    late = row | {'available_at':'2020-07-10'}
    assert select_peer([late],date(2020,4,1),date(2020,6,30),'2020-06-30') is None
    assert select_peer([late],date(2020,4,1),date(2020,6,30),'2020-07-20') == late


def test_interval_weights_are_normalized_actual_days():
    months = [date(2024,1,1),date(2024,2,1),date(2024,3,1)]
    weights = period_weights(date(2024,1,31),date(2024,3,1),months)
    assert weights == pytest.approx([1/31,29/31,1/31])
    assert sum(weights) == pytest.approx(1)
    assert shift_month(date(2024,1,1),-1) == date(2023,12,1)
    with pytest.raises(ValueError):
        period_weights(date(2023,12,31),date(2024,3,1),months)


def test_latent_offsets_keep_company_differences_separate():
    months = [date(2024,1,1)]
    rows = [{'company':c,'start':'2024-01-01','end':'2024-01-31','surprise_cpg':v}
            for c,v in [('CASY',10),('ATD',-10),('MUSA',0)]]
    fit = latent_fit(rows,months)
    assert fit['monthly_factor_cpg']['2024-01-01'] == pytest.approx(0,abs=1e-10)
    assert fit['company_offsets_cpg']['CASY'] > 0
    assert fit['company_offsets_cpg']['ATD'] < 0


def test_own_outcome_never_changes_forecasts():
    baseline, targets, peers = inputs()
    q = '2023Q3'; cutoff = targets[q]['available_at']
    before, reason = factor_forecast(q,baseline,targets,peers,cutoff)
    assert reason is None
    altered = deepcopy(baseline); altered[q]['actual_cpg'] = 999
    after, _ = factor_forecast(q,altered,targets,peers,cutoff)
    assert before == after
    matched, _ = calendar_inputs(baseline,targets,peers,True)
    altered_matched, _ = calendar_inputs(altered,targets,peers,True)
    first, _ = peer_corrections(matched); last, _ = peer_corrections(altered_matched)
    assert first[q]['prediction_cpg'] == last[q]['prediction_cpg']


def test_post_cutoff_peer_values_do_not_change_factor():
    baseline, targets, peers = inputs()
    q = '2023Q3'; cutoff = targets[q]['available_at']
    before, _ = factor_forecast(q,baseline,targets,peers,cutoff)
    altered = deepcopy(peers)
    for rows in altered.values():
        for row in rows:
            if row['available_at'] >= cutoff:
                row['surprise_cpg'] = 999
    after, _ = factor_forecast(q,baseline,targets,altered,cutoff)
    assert before == after


def test_archived_scope_and_training_provenance():
    root = 'data/earnings_calendar_factor/2026-10-08_v2/'
    frozen = json.load(open(root+'frozen_forecasts.json'))
    results = json.load(open(root+'results.json'))
    assert not results['production_changed']
    assert not results['strict_market_pit_verified']
    assert not results['automatic_promotion']
    for name, forecasts in frozen['forecasts'].items():
        assert len(results['models'][name]['by_regime']['later_regime']['quarters']) == 14
        assert not results['models'][name]['by_regime']['later_regime']['metrics']['passes_pre_registered_gate']
        for q, row in forecasts.items():
            assert all(p<q for p in row['training_quarters'])
            if name.startswith('factor'):
                assert not row['interval_weights_are_gallon_shares']
                for obs in row['observations']:
                    assert obs['available_at'] < row['cutoff']
                    assert obs['end'] < row['cutoff']
                    if obs['company'] == 'MUSA':
                        assert obs['quarter'] != q
                        assert obs['source_sha256']
    assert all(not c['models']['calendar_pre_report'] and not c['models']['factor_pre_report']
               for c in results['large_miss_coverage'] if c['quarter'] < '2023Q1')
    assert all(r['incremental_abs_error_improvement_cpg'] == 0
               for r in results['checkpoint_comparisons']['calendar'] if r['quarter'] >= '2021Q1')
