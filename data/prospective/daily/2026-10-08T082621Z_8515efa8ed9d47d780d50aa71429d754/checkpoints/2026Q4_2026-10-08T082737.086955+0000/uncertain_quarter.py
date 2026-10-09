"""Prospective, mechanical partial-quarter margin assimilation.

This is a shadow estimator: it never changes the production forecast and contains no fitted
disclosure coefficients or calibrated probabilities.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


OBSERVED_COMPANY_GALLON_SHARE = "OBSERVED_COMPANY_GALLON_SHARE"
PIT_MODELLED_GALLON_SHARE = "PIT_MODELLED_GALLON_SHARE"


@dataclass(frozen=True)
class PartialQuarterEstimate:
    role: str
    status: str
    production_forecast_cpg: float
    observed_gallon_share: float
    disclosed_margin_low_cpg: float
    disclosed_margin_high_cpg: float
    remaining_margin_cpg: float
    full_quarter_low_cpg: float
    full_quarter_high_cpg: float
    disclosure_target: str
    remaining_target: str

    @property
    def full_quarter_central_cpg(self) -> float:
        return (self.full_quarter_low_cpg + self.full_quarter_high_cpg) / 2

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def assimilate(production_forecast_cpg: float, observed_gallon_share: float,
               disclosed_low_cpg: float, disclosed_high_cpg: float,
               remaining_margin_cpg: float, disclosure_target: str = "retail_margin",
               remaining_target: str = "retail_margin") -> PartialQuarterEstimate:
    """Combine verified same-basis evidence with a remaining-period estimate."""
    allowed_targets = {"retail_margin", "all_in_margin"}
    if disclosure_target not in allowed_targets or remaining_target not in allowed_targets:
        raise ValueError("targets must be retail_margin or all_in_margin")
    if disclosure_target != remaining_target:
        raise ValueError("disclosure and remaining estimate must use the same margin basis")
    if not 0 <= observed_gallon_share <= 1:
        raise ValueError("observed_gallon_share must be between zero and one")
    if disclosed_low_cpg > disclosed_high_cpg:
        raise ValueError("disclosed low margin exceeds high margin")
    remaining_share = 1.0 - observed_gallon_share
    return PartialQuarterEstimate(
        "PROSPECTIVE_SHADOW_ESTIMATOR", "COMPANY_ANCHORED", production_forecast_cpg,
        observed_gallon_share, disclosed_low_cpg, disclosed_high_cpg, remaining_margin_cpg,
        observed_gallon_share * disclosed_low_cpg + remaining_share * remaining_margin_cpg,
        observed_gallon_share * disclosed_high_cpg + remaining_share * remaining_margin_cpg,
        disclosure_target, remaining_target,
    )


def _replay(record: Mapping[str, Any], *, allow_modelled_gallon_share: bool) -> dict[str, Any]:
    """Run a timestamp-preserving historical mechanical replay.

    Missing PIT gallons or a remaining-period forecast vintage is an explicit block, never a
    request to approximate the share using calendar days or revised market data.
    """
    result = dict(record)
    result["evaluation_role"] = "RETROSPECTIVE_MECHANICAL_REPLAY"
    evidence_type = result.get("gallon_share_evidence_type", OBSERVED_COMPANY_GALLON_SHARE)
    if evidence_type not in {OBSERVED_COMPANY_GALLON_SHARE, PIT_MODELLED_GALLON_SHARE}:
        raise ValueError("unknown gallon-share evidence type")
    if evidence_type == PIT_MODELLED_GALLON_SHARE and not allow_modelled_gallon_share:
        result["status"] = "BLOCKED_MODELLED_GALLON_SHARE_NOT_ALLOWED_IN_STRICT_REPLAY"
        return result
    required_timestamps = (
        "disclosure_available_at", "disclosure_period_start", "disclosure_period_end",
        "remaining_period_start", "remaining_period_end", "remaining_market_forecast_as_of",
    )
    missing = [field for field in required_timestamps if not result.get(field)]
    if missing:
        raise ValueError(f"replay is missing timestamps: {', '.join(missing)}")
    if result["disclosure_available_at"] < result["disclosure_period_end"]:
        raise ValueError("disclosure cannot be available before its observed period ends")
    if result["remaining_market_forecast_as_of"] < result["disclosure_available_at"]:
        raise ValueError("remaining-period forecast as_of cannot precede disclosure availability")
    missing_inputs = []
    if result.get("observed_gallon_share") is None:
        missing_inputs.append("PIT_GALLON_SHARE")
    if result.get("remaining_margin_estimate_cpg") is None:
        missing_inputs.append("REMAINING_PERIOD_VINTAGE")
    if missing_inputs:
        result["status"] = ("BLOCKED_PIT_EVIDENCE_INSUFFICIENT"
                            if record.get("status") == "BLOCKED_PIT_EVIDENCE_INSUFFICIENT"
                            else "BLOCKED_MISSING_" + "_AND_".join(missing_inputs))
        return result
    if result.get("production_forecast_at_same_as_of") is None:
        raise ValueError("replay requires production_forecast_at_same_as_of")
    disclosed_low = result.get("disclosed_margin_low_cpg", result.get("disclosed_margin_cpg"))
    disclosed_high = result.get("disclosed_margin_high_cpg", disclosed_low)
    if disclosed_low is None:
        raise ValueError("replay requires a numeric disclosed margin")
    estimate = assimilate(
        float(result["production_forecast_at_same_as_of"]),
        float(result["observed_gallon_share"]), float(disclosed_low), float(disclosed_high),
        float(result["remaining_margin_estimate_cpg"]),
        str(result.get("disclosed_target", "retail_margin")),
        str(result.get("remaining_target", result.get("disclosed_target", "retail_margin"))),
    )
    result.update({
        "shadow_low_cpg": estimate.full_quarter_low_cpg,
        "shadow_central_cpg": estimate.full_quarter_central_cpg,
        "shadow_high_cpg": estimate.full_quarter_high_cpg,
        "status": "COMPLETE_UNSCORED" if result.get("eventual_actual_margin_cpg") is None else "COMPLETE_SCORED",
    })
    if result.get("eventual_actual_margin_cpg") is not None:
        actual = float(result["eventual_actual_margin_cpg"])
        result["shadow_error_cpg"] = estimate.full_quarter_central_cpg - actual
        result["shadow_abs_error_cpg"] = abs(float(result["shadow_error_cpg"]))
        production = result.get("production_forecast_at_same_as_of")
        result["production_error_cpg"] = None if production is None else float(production) - actual
        result["production_abs_error_cpg"] = (
            None if result["production_error_cpg"] is None else abs(float(result["production_error_cpg"]))
        )
        result["incremental_abs_error_improvement_cpg"] = (
            None if result["production_abs_error_cpg"] is None
            else float(result["production_abs_error_cpg"]) - float(result["shadow_abs_error_cpg"])
        )
    return result


def mechanical_replay(record: Mapping[str, Any]) -> dict[str, Any]:
    """Strict replay: only a company-observed gallon share may be used."""
    return _replay(record, allow_modelled_gallon_share=False)


def modelled_gallon_share_replay(record: Mapping[str, Any]) -> dict[str, Any]:
    """Separate research replay accepting only explicitly labelled PIT-modelled shares.

    The caller must preserve a frozen model version, as-of date, and input hashes in the record.
    This is retrospective mechanical replay, never prospective validation.
    """
    if record.get("gallon_share_evidence_type") != PIT_MODELLED_GALLON_SHARE:
        raise ValueError("modelled replay requires PIT_MODELLED_GALLON_SHARE evidence")
    if record.get("replay_blockers"):
        result = dict(record)
        result["evaluation_role"] = "RETROSPECTIVE_MECHANICAL_REPLAY"
        result["status"] = ("BLOCKED_PIT_EVIDENCE_INSUFFICIENT"
                            if record.get("status") == "BLOCKED_PIT_EVIDENCE_INSUFFICIENT"
                            else "BLOCKED_UNSUPPORTED_PIT_RECONSTRUCTIONS")
        return result
    missing = [field for field in ("gallon_share_as_of", "gallon_share_model_version", "gallon_share_input_hashes")
               if not record.get(field)]
    if missing:
        result = dict(record)
        result["evaluation_role"] = "RETROSPECTIVE_MECHANICAL_REPLAY"
        result["status"] = "BLOCKED_MISSING_PIT_MODELLED_GALLON_SHARE_EVIDENCE"
        result["missing_evidence"] = missing
        return result
    return _replay(record, allow_modelled_gallon_share=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mechanically assimilate a verified MUSA retail-margin disclosure")
    parser.add_argument("--production-cpg", type=float)
    parser.add_argument("--observed-gallon-share", type=float)
    parser.add_argument("--disclosed-low-cpg", type=float)
    parser.add_argument("--disclosed-high-cpg", type=float)
    parser.add_argument("--remaining-margin-cpg", type=float)
    parser.add_argument("--disclosure-target", default="retail_margin")
    parser.add_argument("--remaining-target", default="retail_margin")
    replay_mode = parser.add_mutually_exclusive_group()
    replay_mode.add_argument("--replay-json", type=Path,
                             help="Run strict replay: a modelled share is forbidden")
    replay_mode.add_argument("--modelled-gallon-share-replay-json", type=Path,
                             help="Run the separately labelled modelled-share replay")
    args = parser.parse_args(argv)
    if args.replay_json:
        print(json.dumps(mechanical_replay(json.loads(args.replay_json.read_text())), indent=2, sort_keys=True))
        return 0
    if args.modelled_gallon_share_replay_json:
        payload = json.loads(args.modelled_gallon_share_replay_json.read_text())
        print(json.dumps(modelled_gallon_share_replay(payload), indent=2, sort_keys=True))
        return 0
    if any(value is None for value in (args.production_cpg, args.observed_gallon_share,
                                       args.disclosed_low_cpg, args.remaining_margin_cpg)):
        parser.error("production, gallon share, disclosed low, and remaining margin are required outside replay mode")
    result = assimilate(args.production_cpg, args.observed_gallon_share, args.disclosed_low_cpg,
                        args.disclosed_high_cpg if args.disclosed_high_cpg is not None else args.disclosed_low_cpg,
                        args.remaining_margin_cpg, args.disclosure_target, args.remaining_target)
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
