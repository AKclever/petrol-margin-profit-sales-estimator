from datetime import date

import pytest

from musa_nowcast.data import MarketWeek
from musa_nowcast.shadow import ShadowError, _append_csv
from musa_nowcast.timing import transform_market


def test_shadow_models_use_the_frozen_timing_transforms():
    rows = [
        MarketWeek(date(2026, 1, 5), "Gulf", 300.0, 200.0),
        MarketWeek(date(2026, 1, 12), "Gulf", 310.0, 220.0),
        MarketWeek(date(2026, 1, 19), "Gulf", 320.0, 260.0),
    ]
    assert transform_market(rows, "A_LAG_1_WEEK")[-1].wholesale_cpg == 220.0


def test_append_only_ledger_rejects_schema_changes(tmp_path):
    path = tmp_path / "ledger.csv"
    _append_csv(path, [{"checkpoint": "one", "value": 1}])
    with pytest.raises(ShadowError, match="schema changed"):
        _append_csv(path, [{"checkpoint": "two", "different": 2}])
