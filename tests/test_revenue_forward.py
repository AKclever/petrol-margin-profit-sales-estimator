from datetime import date

import pytest

from musa_nowcast.data import QuarterActual
from musa_nowcast.revenue_forward import cutoff_two_quarters_ahead, decompose, forward_rows, revenue_pairs


def test_cutoffs_cross_year():
    assert cutoff_two_quarters_ahead(date(2026, 7, 1)) == date(2026, 3, 31)
    assert cutoff_two_quarters_ahead(date(2026, 1, 1)) == date(2025, 9, 30)


def test_decomposition_is_identity_not_observed_cost():
    r = decompose(3500, 3000, 1000, 1000, 40, 35, 30)
    assert r['revenue_proxy_error_cpg'] == 10
    assert r['implied_cost_residual_cpg'] == 5
    assert r['identity_reconciliation_cpg'] == 0
    with pytest.raises(ValueError):
        decompose(3500, 3000, 0, 1000, 40, 35, 30)


def test_publication_filter_excludes_late_and_cutoff_day_results():
    actuals = []
    verified = {}
    for year in range(2019, 2023):
        for q in range(1, 5):
            start = date(year, 3*q-2, 1)
            end = cutoff_two_quarters_ahead(date(year+(q>2), ((q+1)%4)*3+1, 1))
            a = QuarterActual(f'{year}Q{q}', start, end, year-2000+q)
            actuals.append(a); verified[a.quarter] = {'available_at': str(end)}
    target = next(a for a in actuals if a.quarter == '2022Q3')
    verified['2022Q1']['available_at'] = '2022-03-31'
    verified['2021Q4']['available_at'] = '2022-04-01'
    r = next(r for r in forward_rows(actuals, verified) if r['quarter'] == target.quarter)
    assert '2022Q1' not in r['known_quarters']
    assert '2021Q4' not in r['known_quarters']


def test_revenue_duplicate_columns_must_agree():
    raw = b'<table><tr><td>Petroleum product sales (at retail) 1</td><td>1,200.0</td><td>1,200.0</td><td>900.0</td><td>900.0</td></tr></table>'
    assert revenue_pairs(raw)[0][:2] == (1200, 900)
    with pytest.raises(ValueError):
        revenue_pairs(raw.replace(b'900.0</td></tr>', b'901.0</td></tr>'))
