from datetime import date
import json
from types import SimpleNamespace

import pytest

from musa_nowcast.free_information_suite import archived_mechanical_examples, parse_rack, rack_adjustment


class SpotFixture:
    def _weekly_basket(self,start,end):
        return [(start,300.,200.+(start.year-2020))]
    def features(self,start,end):
        return SimpleNamespace(coverage=1.)


def monthly_fixture():
    return {date(y,m,1):200.+2*(y-2020) for y in [2020,2021] for m in [4,5,6]}


def test_rack_change_not_absolute_basis_used():
    monthly=monthly_fixture();result=rack_adjustment('2021Q2',monthly,SpotFixture())
    assert result['correction_cpg']==-.5
    shifted={d:v+50 for d,v in monthly.items()}
    assert rack_adjustment('2021Q2',shifted,SpotFixture())['correction_cpg']==result['correction_cpg']
    assert result['company_rack_cost_observed'] is False


def test_no_month_filler_or_post_2022_extrapolation():
    monthly=monthly_fixture();monthly.pop(date(2021,5,1))
    with pytest.raises(ValueError,match='MISSING_CURRENT_OR_PRIOR_RACK_MONTHS'):
        rack_adjustment('2021Q2',monthly,SpotFixture())
    with pytest.raises(ValueError,match='MISSING_CURRENT_OR_PRIOR_RACK_MONTHS'):
        rack_adjustment('2026Q3',monthly_fixture(),SpotFixture())


def test_monthly_source_labels_not_release_dates():
    from pathlib import Path
    monthly=parse_rack(Path('data/free_information_suite/2026-10-08_v2/rack.xls').read_bytes())
    assert min(monthly)==date(1994,1,1)
    assert max(monthly)==date(2022,3,1)
    assert monthly[date(2022,3,1)]==pytest.approx(313.3)


def test_all_archived_disclosure_examples_not_only_winner():
    rows=archived_mechanical_examples()
    assert {r['quarter'] for r in rows}=={'2023Q1','2024Q2','2025Q2'}
    assert all(r['new_validation'] is False for r in rows)
    loser=next(r for r in rows if r['quarter']=='2023Q1')
    assert loser['shadow_abs_error_cpg']>loser['production_abs_error_cpg']
