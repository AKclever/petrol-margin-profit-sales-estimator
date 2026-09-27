from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import pytest

from musa_nowcast.rin import RinDownloadError, build_vintage_diff, transform_d6


def _csv(fieldnames, rows):
    target = io.StringIO()
    writer = csv.DictWriter(target, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return target.getvalue().encode()


def test_transform_d6_joins_separated_volume_and_combines_qap_types():
    prices = _csv(
        ["Transfer Date by Week", "Transfer Year", "RIN Year", "Fuel (D Code)",
         "QAP Service Type", "RIN Price"],
        [
            {"Transfer Date by Week": "7/6/2026", "Transfer Year": "2026", "RIN Year": "2026",
             "Fuel (D Code)": "D6", "QAP Service Type": "Unverified", "RIN Price": "$0.50"},
            {"Transfer Date by Week": "7/6/2026", "Transfer Year": "2026", "RIN Year": "2026",
             "Fuel (D Code)": "D6", "QAP Service Type": "Q-RIN", "RIN Price": "$0.80"},
            {"Transfer Date by Week": "7/6/2026", "Transfer Year": "2026", "RIN Year": "2026",
             "Fuel (D Code)": "D4", "QAP Service Type": "Unverified", "RIN Price": "$1.00"},
        ],
    )
    volumes = _csv(
        ["Transfer Date by Week", "Transfer Year", "RIN Year", "Fuel (D Code)", "Assignment",
         "QAP Type", "Total RINs Traded"],
        [
            {"Transfer Date by Week": "7/6/2026", "Transfer Year": "2026", "RIN Year": "2026",
             "Fuel (D Code)": "D6", "Assignment": "Separated", "QAP Type": "Unverified",
             "Total RINs Traded": "1,000"},
            {"Transfer Date by Week": "7/6/2026", "Transfer Year": "2026", "RIN Year": "2026",
             "Fuel (D Code)": "D6", "Assignment": "Separated", "QAP Type": "Q-RIN",
             "Total RINs Traded": "3,000"},
            {"Transfer Date by Week": "7/6/2026", "Transfer Year": "2026", "RIN Year": "2026",
             "Fuel (D Code)": "D6", "Assignment": "Assigned", "QAP Type": "Unverified",
             "Total RINs Traded": "99,000"},
        ],
    )
    captured = datetime(2026, 9, 27, 19, 30, tzinfo=timezone.utc)
    rows, stats = transform_d6(prices, volumes, captured)
    assert len(rows) == 1
    assert rows[0].weekly_vwap_usd_per_rin == pytest.approx(0.725)
    assert rows[0].transaction_volume_rins == 4000
    assert rows[0].available_at == captured
    assert stats["matched_price_volume_rows"] == 2


def test_transform_d6_rejects_duplicate_price_key():
    header = ["Transfer Date by Week", "Transfer Year", "RIN Year", "Fuel (D Code)",
              "QAP Service Type", "RIN Price"]
    row = {"Transfer Date by Week": "7/6/2026", "Transfer Year": "2026", "RIN Year": "2026",
           "Fuel (D Code)": "D6", "QAP Service Type": "Unverified", "RIN Price": "$0.50"}
    prices = _csv(header, [row, row])
    volumes = _csv(
        ["Transfer Date by Week", "Transfer Year", "RIN Year", "Fuel (D Code)", "Assignment",
         "QAP Type", "Total RINs Traded"],
        [{"Transfer Date by Week": "7/6/2026", "Transfer Year": "2026", "RIN Year": "2026",
          "Fuel (D Code)": "D6", "Assignment": "Separated", "QAP Type": "Unverified",
          "Total RINs Traded": "1000"}],
    )
    with pytest.raises(RinDownloadError, match="Duplicate EPA price row"):
        transform_d6(prices, volumes, datetime.now(timezone.utc))


def test_vintage_diff_ignores_capture_metadata_and_finds_revisions(tmp_path):
    fields = [
        "transfer_week", "d_code", "rin_year", "weekly_vwap_usd_per_rin",
        "transaction_volume_rins", "captured_at",
    ]
    previous = tmp_path / "previous.csv"
    current = tmp_path / "current.csv"
    previous.write_bytes(_csv(fields, [
        {"transfer_week": "2026-08-03", "d_code": "D6", "rin_year": "2026",
         "weekly_vwap_usd_per_rin": "1.000000", "transaction_volume_rins": "100",
         "captured_at": "2026-09-01T00:00:00Z"},
        {"transfer_week": "2026-08-10", "d_code": "D6", "rin_year": "2026",
         "weekly_vwap_usd_per_rin": "1.100000", "transaction_volume_rins": "200",
         "captured_at": "2026-09-01T00:00:00Z"},
    ]))
    current.write_bytes(_csv(fields, [
        {"transfer_week": "2026-08-03", "d_code": "D6", "rin_year": "2026",
         "weekly_vwap_usd_per_rin": "1.000000", "transaction_volume_rins": "100",
         "captured_at": "2026-09-27T00:00:00Z"},
        {"transfer_week": "2026-08-10", "d_code": "D6", "rin_year": "2026",
         "weekly_vwap_usd_per_rin": "1.200000", "transaction_volume_rins": "200",
         "captured_at": "2026-09-27T00:00:00Z"},
        {"transfer_week": "2026-08-17", "d_code": "D6", "rin_year": "2026",
         "weekly_vwap_usd_per_rin": "1.300000", "transaction_volume_rins": "300",
         "captured_at": "2026-09-27T00:00:00Z"},
    ]))
    summary, details = build_vintage_diff(previous, current, "old", "new")
    assert summary["unchanged_rows"] == 1
    assert summary["changed_existing_rows"] == 1
    assert summary["new_rows"] == 1
    assert summary["deleted_rows"] == 0
    assert {row["status"] for row in details} == {"NEW", "CHANGED"}
