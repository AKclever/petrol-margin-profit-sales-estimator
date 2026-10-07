import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from musa_nowcast.pit_replay import gallon_share, parse_company, parse_demand, score


def company_page(month="June", current=2025, date_text="July 30, 2025", blanks=False):
    empty = "<tr><td></td></tr>" if blanks else ""
    return (f'<span class="evergreen-news-date-text">{date_text}</span><table>{empty}'
            f'<tr><td>Fuel</td></tr>{empty}'
            f'<tr><td>Three Months Ended {month} 30,</td></tr>'
            f'<tr><td>Key Operating Metrics</td><td>{current}</td><td>{current-1}</td></tr>'
            '<tr><td>Retail fuel margin (cpg)</td><td>29.2</td><td>29.7</td></tr></table>').encode()


def test_explicit_quarter_columns_with_spacer_rows():
    published, year, quarter, values = parse_company(company_page(blanks=True))
    assert (published, year, quarter) == (date(2025, 7, 30), 2025, 2)
    assert values == [29.2, 29.7]


def test_annual_basis_is_not_treated_as_quarterly():
    raw = company_page().replace(b"Three Months", b"Twelve Months")
    with pytest.raises(ValueError, match="three-month"):
        parse_company(raw)


def test_demand_uses_single_week_not_comparison_or_average():
    raw = (b'"STUB_1","STUB_2","6/6/25","5/30/25","6/7/24"\n'
           b'"Products Supplied ","(31)     Finished Motor Gasoline","9,170","8,263","9,040"\n')
    assert parse_demand(raw) == (date(2025, 6, 6), 9170)


def demand_fixture():
    observations = {}
    week = date(2025, 4, 4)
    while week <= date(2025, 7, 4):
        observations[week-timedelta(days=364)] = 100 if week.month < 6 else 200
        if week <= date(2025, 6, 6):
            observations[week] = observations[week-timedelta(days=364)]
        week += timedelta(days=7)
    return observations


def test_share_is_demand_weighted_and_not_calendar_fraction():
    share, days = gallon_share(demand_fixture())
    assert 0 < share < 1
    assert share < 61/91
    assert len(days) == 91
    assert days[-1]["method"] == "52_WEEK_PRIOR_SCALED"
    assert sum(d["demand_rate"] for d in days if d["day"] <= "2025-05-31") / sum(
        d["demand_rate"] for d in days) == share


def test_missing_prior_demand_blocks_instead_of_using_calendar_proxy():
    with pytest.raises(KeyError):
        gallon_share({date(2025, 4, 4): 100})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 0])
def test_invalid_proxy_rate_rejected(value):
    observations = demand_fixture()
    observations[date(2025, 4, 4)] = value
    with pytest.raises(ValueError):
        gallon_share(observations)


def test_blocked_replay_cannot_be_scored(tmp_path):
    p = tmp_path / "forecast.json"
    p.write_text(json.dumps({"status": "BLOCKED_PIT_EVIDENCE_INSUFFICIENT"}))
    with pytest.raises(ValueError, match="blocked replay"):
        score(p, tmp_path / "score")
    assert not (tmp_path / "score").exists()


def test_changed_inputs_prevent_outcome_fetch(tmp_path):
    inp = tmp_path / "input.json"
    inp.write_text("changed")
    p = tmp_path / "forecast.json"
    p.write_text(json.dumps({"status": "FROZEN_UNSCORED_RESEARCH_REPLAY", "input_hashes": {str(inp): "wrong"}}))
    with pytest.raises(ValueError, match="input changed"):
        score(p, tmp_path / "score")
    assert not (tmp_path / "score").exists()
