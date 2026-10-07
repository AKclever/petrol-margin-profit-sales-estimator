import json

import pytest

from musa_nowcast import prospective as p


def test_initial_gallon_freeze_is_append_only_and_labels_late_capture(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "now", lambda: "2026-10-07T12:00:00+00:00")
    source = tmp_path / "input.json"
    source.write_text(json.dumps({
        "quarter": "2026Q4", "quarter_start": "2026-10-01",
        "information_cutoff": "2026-10-07T11:00:00+00:00",
        "methodology_version": "TEST_ONLY", "update_rule": "NO_UPDATES",
        "input_hashes": {"test": "test"},
        "expected_gallon_share_by_month": {"2026-10": .3, "2026-11": .3, "2026-12": .4},
    }))
    result = json.loads(p.freeze_gallons(tmp_path, source).read_text())
    assert result["freeze_timing"] == "LATE_INITIAL_FREEZE"
    assert result["gallon_share_evidence_type"] == "PIT_MODELLED_GALLON_SHARE"
    with pytest.raises(FileExistsError):
        p.freeze_gallons(tmp_path, source)


def test_market_tampering_blocks_checkpoint_before_model_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "now", lambda: "2026-10-07T12:00:00+00:00")
    market = tmp_path / "market.csv"
    market.write_text("tampered")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"information_cutoff": "2026-10-07T11:00:00+00:00",
                                   "market_file": "market.csv", "market_sha256": "wrong"}))
    with pytest.raises(ValueError, match="hash mismatch"):
        p.checkpoint(tmp_path, manifest, tmp_path / "weights.csv", tmp_path / "actuals.csv",
                     "2026Q4", p.date(2026, 10, 1), p.date(2026, 12, 31))


def test_scoring_rejects_earnings_known_before_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "now", lambda: "2027-02-01T12:00:00+00:00")
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(json.dumps({"evaluation_role": "PROSPECTIVE_CAPTURE",
                                     "forecast_created_at": "2026-12-15T12:00:00+00:00"}))
    with pytest.raises(ValueError, match="after capture"):
        p.score(tmp_path, checkpoint, 30, "2026-12-01T12:00:00+00:00", tmp_path / "raw", "https://issuer")


def test_score_uses_frozen_forecasts_and_preserves_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "now", lambda: "2027-02-01T12:00:00+00:00")
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(json.dumps({
        "evaluation_role": "PROSPECTIVE_CAPTURE", "quarter": "2026Q4",
        "forecast_created_at": "2026-12-15T12:00:00+00:00",
        "production_forecast": {"retail_margin_cpg": 32},
        "partial_quarter_shadow": {"full_quarter_central_cpg": 30.1},
    }))
    original = checkpoint.read_bytes()
    raw = tmp_path / "raw"
    raw.write_text("earnings evidence")
    result = json.loads(p.score(tmp_path, checkpoint, 30, "2027-01-25T12:00:00+00:00", raw, "https://issuer").read_text())
    assert result["incremental_abs_error_improvement_cpg"] == pytest.approx(1.9)
    assert checkpoint.read_bytes() == original
    with pytest.raises(FileExistsError):
        p.score(tmp_path, checkpoint, 30, "2027-01-25T12:00:00+00:00", raw, "https://issuer")
