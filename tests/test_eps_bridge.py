import csv

import pytest

from musa_nowcast.eps_bridge import BridgeError, build


FIELDS = [
    "quarter", "as_of", "fuel_status", "retail_margin_cpg", "supply_rin_cpg",
    "all_in_margin_cpg", "fuel_gallons_million", "merchandise_contribution_million",
    "store_operating_expense_ex_payment_fees_million", "payment_fees_million", "sga_million",
    "depreciation_amortization_million", "interest_expense_million",
    "other_income_expense_million", "tax_rate", "diluted_shares_million",
    "street_consensus_eps", "notes",
]


def _write(path, values):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(values)


def test_bridge_refuses_to_turn_blanks_into_zero(tmp_path):
    source, output = tmp_path / "input.csv", tmp_path / "output.json"
    _write(source, {
        "quarter": "2026Q3", "as_of": "2026-09-28", "fuel_status": "PRODUCTION",
        "retail_margin_cpg": "29.54", "supply_rin_cpg": "2.95",
        "all_in_margin_cpg": "32.49",
    })
    result = build(source, output)
    assert result["status"] == "BLOCKED_MISSING_INPUTS"
    assert "fuel_gallons_million" in result["missing_inputs"]
    assert "bridge" not in result


def test_complete_bridge_reconciles_to_eps(tmp_path):
    source, output = tmp_path / "input.csv", tmp_path / "output.json"
    _write(source, {
        "quarter": "2026Q3", "as_of": "2026-09-28", "fuel_status": "PRODUCTION",
        "retail_margin_cpg": "29.54", "supply_rin_cpg": "2.95",
        "all_in_margin_cpg": "32.49", "fuel_gallons_million": "1200",
        "merchandise_contribution_million": "200", "store_operating_expense_ex_payment_fees_million": "250",
        "payment_fees_million": "30", "sga_million": "60", "depreciation_amortization_million": "40",
        "interest_expense_million": "15", "other_income_expense_million": "0",
        "tax_rate": "0.25", "diluted_shares_million": "20", "street_consensus_eps": "7.0",
    })
    result = build(source, output)
    assert result["status"] == "READY"
    assert result["bridge"]["fuel_contribution_million"] == pytest.approx(389.88)
    assert result["bridge"]["eps"] == pytest.approx(7.308)


def test_bridge_rejects_experimental_fuel(tmp_path):
    source, output = tmp_path / "input.csv", tmp_path / "output.json"
    _write(source, {
        "quarter": "2026Q3", "as_of": "2026-09-28", "fuel_status": "TIMING_C",
        "retail_margin_cpg": "28.04", "supply_rin_cpg": "2.95",
        "all_in_margin_cpg": "30.99",
    })
    with pytest.raises(BridgeError, match="production fuel inputs only"):
        build(source, output)
