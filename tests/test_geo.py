from __future__ import annotations

from datetime import date

import pytest

from musa_nowcast.geo import GeoError, _retail_mapping, _wholesale_mapping, parse_eia


def test_geographic_hierarchy_and_explicit_wholesale_missingness():
    assert _retail_mapping("Texas") == ("PET.EMM_EPMR_PTE_STX_DPG.W", "STATE")
    assert _retail_mapping("Georgia") == ("PET.EMM_EPMR_PTE_R1Z_DPG.W", "PADD_SUBDIVISION")
    assert _retail_mapping("Arkansas") == ("PET.EMM_EPMR_PTE_R30_DPG.W", "PADD")
    assert _wholesale_mapping("Florida") == "PET.EER_EPMRU_PF4_Y35NY_DPG.W"
    assert _wholesale_mapping("Ohio") == "PET.EER_EPMRU_PF4_RGC_DPG.W"
    assert _wholesale_mapping("Colorado") is None


def test_eia_parser_normalizes_week_and_rejects_duplicates():
    raw = b'{"response":{"data":[{"period":"2026-09-21","value":3.5}]}}'
    assert parse_eia(raw, "TEST", date(2026, 9, 1), date(2026, 9, 30)) == {
        date(2026, 9, 21): 350.0
    }
    duplicate = b'{"response":{"data":[{"period":"2026-09-21","value":3.5},{"period":"2026-09-22","value":3.6}]}}'
    with pytest.raises(GeoError, match="Duplicate EIA week"):
        parse_eia(duplicate, "TEST", date(2026, 9, 1), date(2026, 9, 30))
