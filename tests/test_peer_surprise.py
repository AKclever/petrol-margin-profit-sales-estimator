from datetime import date

import pytest

from musa_nowcast.peer_surprise import eligible_training, fit_correction, overlap_days, select_peer


def peer(start='2026-05-01', end='2026-07-31', available='2026-09-08'):
    return {'start':start, 'end':end, 'available_at':available, 'surprise_cpg':5.0}


def test_peer_overlap_is_not_full_quarter():
    p = peer()
    assert overlap_days(date(2026,7,1),date(2026,9,30),p) == 31
    assert select_peer([p],date(2026,7,1),date(2026,9,30)) == p


def test_late_same_day_and_nonoverlapping_reports_excluded():
    start, end = date(2026,7,1),date(2026,9,30)
    assert select_peer([peer(available='2026-10-01')],start,end) is None
    assert select_peer([peer(available='2026-09-30')],start,end) is None
    assert select_peer([peer(start='2026-04-01',end='2026-06-30')],start,end) is None


def test_latest_eligible_period_selected():
    first = peer(start='2026-06-01',end='2026-07-15')
    second = peer()
    assert select_peer([first,second],date(2026,7,1),date(2026,9,30)) == second


def test_unavailable_residuals_never_train():
    rows = [{'available_at':'2026-10-01'}, {'available_at':'2026-09-30'},
            {'available_at':'2026-08-05'}]
    assert eligible_training(rows,date(2026,9,30)) == [rows[2]]


def test_minimum_history_is_blocking():
    with pytest.raises(ValueError,match='INSUFFICIENT'):
        fit_correction([],date(2026,9,30))


def test_future_outcome_cannot_change_fitted_correction():
    rows = [{'quarter':str(i),'available_at':'2025-01-01','peer':{'surprise_cpg':i},
             'actual_cpg':30+i, 'prediction_cpg':30} for i in range(8)]
    model, training = fit_correction(rows,date(2026,9,30))
    future = {'available_at':'2026-10-30','peer':{'surprise_cpg':999},
              'actual_cpg':9999,'prediction_cpg':0}
    other, _ = fit_correction(rows+[future],date(2026,9,30))
    assert other.coefficients == model.coefficients
    assert len(training) == 8
