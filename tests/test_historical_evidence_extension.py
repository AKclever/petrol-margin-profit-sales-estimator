from datetime import date
import json
from pathlib import Path

import pytest

from musa_nowcast.historical_evidence_extension import atd_target, caseys_target, monthly_series, peer_corrections, select_peer

ROOT = Path('data/historical_evidence_extension/2026-10-08_review_v3')
SOURCES = Path('data/historical_evidence_extension/2026-10-08_sources_v2')
OLDER = Path('data/older_peer_evidence/2026-10-08_v1')


def test_rack_and_resale_are_not_conflated():
    rack = monthly_series(SOURCES/'EMA_EPMR_PRA_R20_DPG.xls', 'EMA_EPMR_PRA_R20_DPG')
    resale = monthly_series(SOURCES/'EMA_EPMR_PWG_R20_DPG.xls', 'EMA_EPMR_PWG_R20_DPG')
    assert max(rack) == date(2011,2,1)
    assert max(resale) == date(2022,3,1)
    assert date(2021,4,1) not in rack
    with pytest.raises(ValueError):
        monthly_series(SOURCES/'EMA_EPMR_PRA_R20_DPG.xls', 'EMA_EPMR_PWG_R20_DPG')


def test_quarterly_caseys_not_annual_goal_or_ytd():
    record = caseys_target((OLDER/'CASY_000072695818000008_release.html').read_bytes(), {'quarter':'F2018Q3','end':'2018-01-31'})
    assert record['retail_margin_cpg'] == 18.6
    assert record['retail_margin_cpg'] != 19.2  # YTD
    assert record['payment_fee_basis'] == 'EXCLUDING_CREDIT_CARD_FEES'


def test_atd_missing_title_is_reconciled():
    checks = json.loads((SOURCES/'source_checks.json').read_text())['checks']
    check = next(r for r in checks if r['id']=='atd_f2018q2')
    row = atd_target((SOURCES/check['raw_file']).read_bytes(),check['source_url'])
    assert row['quarter']=='F2018Q2'
    assert row['retail_margin_cpg']-row['payment_fees_cpg'] == pytest.approx(row['after_payment_margin_cpg'],abs=.021)
    assert (date.fromisoformat(row['end'])-date.fromisoformat(row['start'])).days+1 == row['weeks']*7


def test_same_day_and_post_report_peers_block():
    row = {'available_at':'2021-06-30','start':'2021-04-01','end':'2021-04-30'}
    assert select_peer([row],date(2021,4,1),date(2021,6,30),'2021-07-30') is None
    earlier = row | {'available_at':'2021-06-01'}
    assert select_peer([earlier],date(2021,4,1),date(2021,6,30),'2021-05-30') is None
    assert select_peer([earlier],date(2021,4,1),date(2021,6,30),'2021-07-30') == earlier


def test_final_outcome_not_used_to_fit_own_peer_correction():
    data = json.loads((ROOT/'frozen_peer_forecasts.json').read_text())
    rows = data['matched_inputs']; before,_ = peer_corrections(rows)
    changed = [r | {'actual_cpg':999.} if r['quarter']=='2023Q3' else r for r in rows]
    after,_ = peer_corrections(changed)
    assert before['2023Q3']['prediction_cpg'] == after['2023Q3']['prediction_cpg']
    assert '2023Q3' not in before['2023Q3']['training_quarters']


def test_scope_blocks_and_publication_trails():
    history = json.loads((ROOT/'reviewed_peer_history.json').read_text())
    assert history['older_reconciled_counts']=={'CASY':24,'ATD':20}
    results = json.loads((ROOT/'peer_results.json').read_text())
    assert len(results['rows']) == 16
    assert len(results['by_regime']['later_regime']['quarters']) == 14
    assert sum(r['scored'] for r in results['large_miss_coverage']) == 2
    assert all(r['published_pair_present'] for r in results['large_miss_coverage'])
    assert not results['production_changed']
    assert not results['by_regime']['later_regime']['metrics']['passes_pre_registered_gate']
    for row in results['rows']:
        assert all(q<row['quarter'] for q in row['training_quarters'])
        for peer in row['peers'].values():
            assert peer['available_at'] < row['cutoff'] < row['available_at']
    perimeter = json.loads((ROOT/'perimeter_audit.json').read_text())
    assert len(perimeter['quarters']) == 52
    by_q = {r['quarter']:r for r in perimeter['quarters']}
    assert by_q['2021Q1']['quickchek_comparability']=='PARTIAL_ACQUISITION_QUARTER_NOT_LIKE_FOR_LIKE'
    assert by_q['2022Q1']['quickchek_comparability']=='ANCHOR_HAS_PARTIAL_QUICKCHEK_PERIOD'
    assert all(r['retail_margin_adjustment_cpg'] is None for r in perimeter['quarters'])
