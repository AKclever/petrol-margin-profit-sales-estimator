from copy import deepcopy
import json

import pytest

from musa_nowcast.anchor_reliability import ROOT
from musa_nowcast.simple_economic import EconomicCalibration, fit_at, route_forecast, two_features, disclosure_example


def record():
    return {
        'quarter': '2025Q2', 'disclosure_verified': True,
        'disclosed_target': 'retail_margin', 'remaining_target': 'retail_margin',
        'disclosure_period_start': '2025-04-01', 'disclosure_period_end': '2025-05-31',
        'disclosure_available_at': '2025-06-16T09:00:00Z',
        'remaining_period_start': '2025-06-01', 'remaining_period_end': '2025-06-30',
        'remaining_market_forecast_as_of': '2025-06-16T10:00:00Z',
        'remaining_forecast_information_cutoff': '2025-06-16T10:00:00Z',
        'production_information_cutoff': '2025-06-16T10:00:00Z',
        'gallon_share_information_cutoff': '2025-06-16T09:00:00Z',
        'remaining_forecast_created_at': '2025-06-16T10:01:00Z',
        'observed_gallon_share': .6, 'gallon_share_method': 'EXPLICIT_TEST_FIXTURE_NOT_REAL_EVIDENCE',
        'gallon_share_evidence_type': 'OBSERVED_COMPANY_GALLON_SHARE',
        'disclosed_margin_low_cpg': 29., 'disclosed_margin_high_cpg': 31.,
        'remaining_margin_estimate_cpg': 25., 'input_hashes': {'fixture': 'test-only'},
    }


def test_market_only_route_not_prior_year_anchor():
    assert route_forecast(27., 30.)['shadow_forecast_cpg'] == 27.
    assert two_features([70., -4., 8.]) == [70., 4.]


def test_mechanical_range_and_sensitivity():
    result = route_forecast(27., 30., record())
    assert result['shadow_low_cpg'] == pytest.approx(.6*29+.4*25)
    assert result['shadow_central_cpg'] == pytest.approx(.6*30+.4*25)
    assert result['shadow_high_cpg'] == pytest.approx(.6*31+.4*25)
    r = record(); r['remaining_margin_estimate_cpg'] += 10
    assert route_forecast(27.,30.,r)['shadow_central_cpg']-result['shadow_central_cpg'] == pytest.approx(4)


def test_no_calendar_fill_and_no_all_in_conversion():
    r = record(); r['observed_gallon_share'] = None
    assert route_forecast(27.,30.,r)['status'] == 'BLOCKED_MISSING_OBSERVED_GALLON_SHARE'
    r = record(); r['disclosed_target'] = 'all_in_margin'
    assert route_forecast(27.,30.,r)['status'] == 'BLOCKED_INCOMPATIBLE_MARGIN_BASIS'


def test_modelled_share_separate_opt_in():
    r = record(); r['gallon_share_evidence_type'] = 'PIT_MODELLED_GALLON_SHARE'
    assert route_forecast(27.,30.,r)['status'].startswith('BLOCKED_MODELLED')
    assert route_forecast(27.,30.,r,allow_modelled=True)['status'] == 'BLOCKED_MISSING_PIT_MODELLED_GALLON_SHARE_EVIDENCE'
    r.update(gallon_share_as_of='2025-06-16T09:00:00Z',
             gallon_share_model_version='TEST_FIXTURE_V1', gallon_share_input_hashes={'fixture': 'test-only'})
    assert route_forecast(27.,30.,r,allow_modelled=True)['status'] == 'COMPLETE_UNSCORED'


def test_no_intraday_future_leakage_and_no_gap():
    r = record(); r['disclosure_available_at'] = '2025-06-16T11:00:00Z'
    with pytest.raises(ValueError,match='after remaining'):
        route_forecast(27.,30.,r)
    r = record(); r['gallon_share_information_cutoff'] = '2025-06-16T10:30:00Z'
    with pytest.raises(ValueError,match='gallon share uses information'):
        route_forecast(27.,30.,r)
    r = record(); r['remaining_period_start'] = '2025-06-02'
    with pytest.raises(ValueError,match='partition'):
        route_forecast(27.,30.,r)


def test_invalid_share_nonfinite_and_future_remaining_block():
    r = record(); r['observed_gallon_share'] = 1.1
    with pytest.raises(ValueError,match='between zero and one'):
        route_forecast(27.,30.,r)
    r = record(); r['remaining_margin_estimate_cpg'] = float('inf')
    with pytest.raises(ValueError,match='finite numeric'):
        route_forecast(27.,30.,r)
    r = record(); r['remaining_market_forecast_as_of'] = '2025-06-17'
    with pytest.raises(ValueError,match='same information cutoff'):
        route_forecast(27.,30.,r)


def test_nonnegative_calibration_does_not_fit_negative_slope():
    model = EconomicCalibration().fit([[i,0.] for i in range(8)],[-i for i in range(8)])
    assert model.predict([0.,0.]) == pytest.approx(model.predict([7.,0.]))
    assert all(c >= 0 for c in model.model.coefficients[1:])


def test_training_no_heldout_outcomes_and_publication_filter():
    targets = {r['quarter']:r for r in json.loads((ROOT/'historical_targets.json').read_text())['quarters']}
    features = {q:[float(i),float(i%3)] for i,q in enumerate(sorted(targets))}
    before, training = fit_at('2023Q3',targets,features)
    changed = deepcopy(targets)
    for q,r in changed.items():
        if q >= '2023Q3': r['retail_margin_cpg'] = 1000.
    after, other = fit_at('2023Q3',changed,features)
    assert other == training
    assert before.predict([30.,2.]) == pytest.approx(after.predict([30.,2.]))
    changed['2023Q2']['available_at'] = '2023-09-30'
    assert '2023Q2' not in fit_at('2023Q3',changed,features)[1]


def test_archived_disclosure_hash_and_average_reproduced():
    result = disclosure_example()
    assert result['recomputed_shadow_forecast_cpg'] == pytest.approx(28.897799221448192)
    assert result['new_replay_or_validation'] is False
    assert result['strict_replay_status'].startswith('BLOCKED')
