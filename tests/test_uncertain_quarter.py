import pytest

from musa_nowcast.uncertain_quarter import (
    PIT_MODELLED_GALLON_SHARE, assimilate, mechanical_replay, modelled_gallon_share_replay,
)


def test_volume_weighted_partial_quarter_assimilation():
    result = assimilate(29.54, 0.60, 32.0, 32.0, 27.0)
    assert result.full_quarter_low_cpg == pytest.approx(30.0)
    assert result.full_quarter_low_cpg <= result.full_quarter_central_cpg <= result.full_quarter_high_cpg
    assert result.status == "COMPANY_ANCHORED"


def test_mixed_margin_bases_are_rejected_but_all_in_can_be_same_basis():
    with pytest.raises(ValueError, match="same margin basis"):
        assimilate(28.5, 0.33, 35, 40, 32, "all_in_margin", "retail_margin")
    assert assimilate(28.5, 0.33, 35, 40, 32, "all_in_margin", "all_in_margin").full_quarter_low_cpg > 0


def test_replay_blocks_missing_pit_gallon_share_without_a_calendar_proxy():
    replay = mechanical_replay({
        "quarter": "2025Q2", "disclosure_available_at": "2025-06-16",
        "disclosure_period_start": "2025-04-01", "disclosure_period_end": "2025-05-31",
        "remaining_period_start": "2025-06-01", "remaining_period_end": "2025-06-30",
        "remaining_market_forecast_as_of": "2025-06-16", "observed_gallon_share": None,
    })
    assert replay["status"] == "BLOCKED_MISSING_PIT_GALLON_SHARE_AND_REMAINING_PERIOD_VINTAGE"


def test_modelled_share_is_a_separate_route_and_never_accepted_by_strict_replay():
    record = {
        "quarter": "2025Q2", "disclosure_available_at": "2025-06-16",
        "disclosure_period_start": "2025-04-01", "disclosure_period_end": "2025-05-31",
        "remaining_period_start": "2025-06-01", "remaining_period_end": "2025-06-30",
        "remaining_market_forecast_as_of": "2025-06-16", "observed_gallon_share": 0.66,
        "remaining_margin_estimate_cpg": 28.5, "disclosed_margin_cpg": 29.6,
        "production_forecast_at_same_as_of": 30.0, "eventual_actual_margin_cpg": 29.2,
        "gallon_share_evidence_type": PIT_MODELLED_GALLON_SHARE,
        "gallon_share_as_of": "2025-06-16", "gallon_share_model_version": "V1",
        "gallon_share_input_hashes": {"inputs": "frozen"},
    }
    assert mechanical_replay(record)["status"] == "BLOCKED_MODELLED_GALLON_SHARE_NOT_ALLOWED_IN_STRICT_REPLAY"
    replay = modelled_gallon_share_replay(record)
    assert replay["evaluation_role"] == "RETROSPECTIVE_MECHANICAL_REPLAY"
    assert replay["shadow_abs_error_cpg"] == pytest.approx(0.026)
    assert replay["production_abs_error_cpg"] == pytest.approx(0.8)
    assert replay["incremental_abs_error_improvement_cpg"] == pytest.approx(0.774)


def test_modelled_replay_remains_explicitly_blocked_without_its_frozen_evidence():
    replay = modelled_gallon_share_replay({"gallon_share_evidence_type": PIT_MODELLED_GALLON_SHARE})
    assert replay["status"] == "BLOCKED_MISSING_PIT_MODELLED_GALLON_SHARE_EVIDENCE"
