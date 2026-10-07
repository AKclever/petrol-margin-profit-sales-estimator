from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from musa_nowcast.risk_ledger import RiskLedgerError, checkpoint, score


ROOT = Path(__file__).parents[1]


def test_checkpoint_and_score_are_append_only(tmp_path):
    checkpoint_root = tmp_path / "risk"
    payload = checkpoint(
        ROOT / "data" / "market.csv", ROOT / "data" / "weights.csv", ROOT / "data" / "actuals.csv",
        checkpoint_root, "2026Q3", date(2026, 7, 1), date(2026, 9, 30), date(2026, 9, 30), 29.54,
        created_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
    )
    path = checkpoint_root / "checkpoints" / f"{payload['checkpoint_id']}.json"
    result = score(path, checkpoint_root, 28.0, date(2026, 10, 20), "https://example.com/result")

    assert payload["expected_error_class"] == "ABOVE_NORMAL_RISK"
    assert result["production_error_cpg"] == pytest.approx(-1.54)
    assert result["directional_mechanism_that_matched"] == "RISING_SQUEEZE"
    with pytest.raises(RiskLedgerError, match="already scored"):
        score(path, checkpoint_root, 28.0, date(2026, 10, 20), "https://example.com/result")
