"""Transparent operating-to-EPS bridge with hard input-completeness checks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


SPEC_ID = "MUSA_OPERATING_TO_EPS_BRIDGE_V1"
PRODUCTION_FUEL_STATUS = "PRODUCTION"
NUMERIC_FIELDS = (
    "retail_margin_cpg",
    "supply_rin_cpg",
    "all_in_margin_cpg",
    "fuel_gallons_million",
    "merchandise_contribution_million",
    "store_operating_expense_ex_payment_fees_million",
    "payment_fees_million",
    "sga_million",
    "depreciation_amortization_million",
    "interest_expense_million",
    "other_income_expense_million",
    "tax_rate",
    "diluted_shares_million",
    "street_consensus_eps",
)
REQUIRED_FOR_EPS = NUMERIC_FIELDS


class BridgeError(RuntimeError):
    """Raised when an EPS bridge input is inconsistent or unsafe."""


def research_spec() -> dict[str, object]:
    return {
        "id": SPEC_ID,
        "status": "FROZEN",
        "fuel_policy": {
            "accepted_status": PRODUCTION_FUEL_STATUS,
            "retail_margin_cpg": 29.54,
            "supply_rin_cpg": 2.95,
            "all_in_margin_cpg": 32.49,
            "timing_A_B_C": "SHADOW_ONLY",
            "D6_RIN": "SCENARIO_ONLY",
        },
        "calculation": [
            "fuel contribution = gallons million * all-in cpg / 100",
            "total contribution = fuel contribution + merchandise contribution",
            "EBITDA proxy = total contribution - store opex ex payment fees - payment fees - SG&A",
            "EBIT = EBITDA proxy - D&A",
            "pretax income = EBIT - interest expense + other income/expense",
            "net income = pretax income * (1 - tax rate)",
            "EPS = net income / diluted shares million",
            "surprise gap = EPS - same-time Street consensus",
        ],
        "hard_rules": [
            "blank is never zero",
            "reported actuals and forecast assumptions remain distinguishable",
            "payment fees must not also be included in store opex",
            "no EPS output until every required operating input is present",
        ],
    }


def _spec_hash() -> str:
    return hashlib.sha256(
        json.dumps(research_spec(), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _load_one(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if len(rows) != 1:
        raise BridgeError("EPS bridge input must contain exactly one forecast row")
    missing_columns = {"quarter", "as_of", "fuel_status", *NUMERIC_FIELDS} - set(rows[0])
    if missing_columns:
        raise BridgeError(f"Missing columns: {', '.join(sorted(missing_columns))}")
    return rows[0]


def build(input_path: Path, output_path: Path) -> dict[str, object]:
    row = _load_one(input_path)
    if row["fuel_status"].strip() != PRODUCTION_FUEL_STATUS:
        raise BridgeError("EPS bridge accepts production fuel inputs only")
    parsed: dict[str, float | None] = {}
    for field in NUMERIC_FIELDS:
        value = row[field].strip()
        try:
            parsed[field] = float(value) if value else None
        except ValueError as exc:
            raise BridgeError(f"Invalid numeric input for {field}: {value!r}") from exc
    fuel_values = [parsed[name] for name in (
        "retail_margin_cpg", "supply_rin_cpg", "all_in_margin_cpg"
    )]
    if any(value is None for value in fuel_values):
        raise BridgeError("Production retail, supply/RIN, and all-in margins are required")
    retail, supply, all_in = (float(value) for value in fuel_values)
    if abs((retail + supply) - all_in) > 0.001:
        raise BridgeError("All-in fuel margin must equal retail margin plus supply/RIN")
    if row["quarter"] == "2026Q3" and (retail, supply, all_in) != (29.54, 2.95, 32.49):
        raise BridgeError("Q3 2026 must use the frozen production fuel inputs")
    missing = [field for field in REQUIRED_FOR_EPS if parsed[field] is None]
    result: dict[str, object] = {
        "spec_id": SPEC_ID,
        "research_spec_hash": _spec_hash(),
        "quarter": row["quarter"],
        "as_of": row["as_of"],
        "fuel_status": PRODUCTION_FUEL_STATUS,
        "production_fuel": {
            "retail_margin_cpg": retail,
            "supply_rin_cpg": supply,
            "all_in_margin_cpg": all_in,
        },
        "status": "BLOCKED_MISSING_INPUTS" if missing else "READY",
        "missing_inputs": missing,
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
    }
    if not missing:
        gallons = float(parsed["fuel_gallons_million"])
        merchandise = float(parsed["merchandise_contribution_million"])
        store_opex = float(parsed["store_operating_expense_ex_payment_fees_million"])
        payment_fees = float(parsed["payment_fees_million"])
        sga = float(parsed["sga_million"])
        depreciation = float(parsed["depreciation_amortization_million"])
        interest = float(parsed["interest_expense_million"])
        other = float(parsed["other_income_expense_million"])
        tax_rate = float(parsed["tax_rate"])
        shares = float(parsed["diluted_shares_million"])
        if gallons <= 0 or shares <= 0 or not 0 <= tax_rate <= 1:
            raise BridgeError("Gallons and shares must be positive; tax_rate must be between 0 and 1")
        fuel_contribution = gallons * all_in / 100.0
        total_contribution = fuel_contribution + merchandise
        ebitda_proxy = total_contribution - store_opex - payment_fees - sga
        ebit = ebitda_proxy - depreciation
        pretax = ebit - interest + other
        tax_expense = pretax * tax_rate
        net_income = pretax - tax_expense
        eps = net_income / shares
        consensus = parsed["street_consensus_eps"]
        result["bridge"] = {
            "fuel_contribution_million": round(fuel_contribution, 4),
            "merchandise_contribution_million": merchandise,
            "total_contribution_million": round(total_contribution, 4),
            "store_operating_expense_ex_payment_fees_million": store_opex,
            "payment_fees_million": payment_fees,
            "sga_million": sga,
            "ebitda_proxy_million": round(ebitda_proxy, 4),
            "depreciation_amortization_million": depreciation,
            "ebit_million": round(ebit, 4),
            "interest_expense_million": interest,
            "other_income_expense_million": other,
            "pretax_income_million": round(pretax, 4),
            "tax_rate": tax_rate,
            "tax_expense_million": round(tax_expense, 4),
            "net_income_million": round(net_income, 4),
            "diluted_shares_million": shares,
            "eps": round(eps, 4),
            "street_consensus_eps": consensus,
            "expected_surprise_gap_eps": round(eps - float(consensus), 4)
            if consensus is not None else None,
        }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Build MUSA operating-to-EPS bridge V1")
    result.add_argument("--input", type=Path, default=Path("data/eps_bridge/q3_2026_inputs.csv"))
    result.add_argument("--output", type=Path, default=Path("data/eps_bridge/q3_2026_output.json"))
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = build(args.input, args.output)
    except (BridgeError, OSError) as exc:
        parser().error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
