import pytest

from musa_nowcast.combined_challengers import crosses_diesel_break, blend, joint, select_peer


def test_diesel_break_crossing_exact_quarters():
    assert not crosses_diesel_break('2022Q1')
    for q in ['2022Q2','2022Q3','2022Q4','2023Q1','2023Q2']:
        assert crosses_diesel_break(q)
    assert not crosses_diesel_break('2023Q3')


def test_peer_future_and_nonoverlap_excluded():
    rows = [{'start':'2025-02-01','end':'2025-04-30','available_at':'2025-06-10','surprise_cpg':1},
            {'start':'2025-05-01','end':'2025-07-31','available_at':'2025-09-01','surprise_cpg':2},
            {'start':'2024-11-01','end':'2025-01-31','available_at':'2025-03-01','surprise_cpg':3}]
    assert select_peer(rows,'2025Q2')['surprise_cpg'] == 1
    rows[0]['available_at'] = '2025-06-30'
    assert select_peer(rows,'2025Q2') is None


def test_fixed_blend_requires_all_components():
    baseline = {'2025Q1':{'actual_cpg':25,'seasonal_cpg':24},'2025Q2':{'actual_cpg':25,'seasonal_cpg':24}}
    a = {'2025Q1':{'prediction_cpg':20},'2025Q2':{'prediction_cpg':22}}
    b = {'2025Q1':{'prediction_cpg':30}}
    result = blend({'a':a,'b':b},baseline)
    assert list(result) == ['2025Q1']
    assert result['2025Q1']['prediction_cpg'] == 25


def test_joint_publication_cutoff_and_heldout_leakage():
    from musa_nowcast.history_floor_basis import bounds
    rows = []
    for q in [f'{y}Q{n}' for y in [2021,2022] for n in range(1,5)]+['2023Q1']:
        rows.append({'quarter':q,'quarter_end':str(bounds(q)[1]),'outcome_available_at':str(bounds(q)[1]),
                     'actual_cpg':30.,'prediction_cpg':29.,'seasonal_cpg':28.,'features':[1.,2.]})
    result,_ = joint(rows); point = result['2023Q1']['prediction_cpg']
    rows[-1]['actual_cpg'] = 999
    assert joint(rows)[0]['2023Q1']['prediction_cpg'] == point
    rows[0]['outcome_available_at'] = '2023-03-31'
    assert '2023Q1' not in joint(rows)[0]
