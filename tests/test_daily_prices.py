from datetime import date
import pytest
from musa_nowcast.daily_prices import daily_diagnostics, exact_pairs, parse_aaa


def test_daily_exact_join_does_not_fill_weekly_retail():
    r=[{'observed_at':'2026-07-01','wholesale_series':'USGC','retail_cpg':300,'available_at':'2026-07-01T12:00:00+00:00'}]
    w=[{'observed_at':'2026-07-02','series':'USGC','wholesale_cpg':200,'available_at':'2026-07-03T12:00:00+00:00'}]
    assert exact_pairs(r,w)==[]
    w[0]['observed_at']='2026-07-01'
    assert exact_pairs(r,w)[0]['spread_cpg']==100
    assert exact_pairs(r,w)[0]['available_at']==w[0]['available_at']


def test_state_mapping_must_be_explicit():
    r=[{'observed_at':'2026-07-01','state':'TX','retail_cpg':300}]
    w=[{'observed_at':'2026-07-01','series':'USGC','wholesale_cpg':200}]
    assert exact_pairs(r,w)==[]


def test_aaa_incomplete_snapshot_blocks():
    with pytest.raises(ValueError,match='incomplete'):
        parse_aaa(b'<html>Price as of 10/7/26<script>TX,Texas,$3.80,https://gasprices.aaa.com?state=TX;</script></html>')


def test_aaa_requires_observation_date():
    with pytest.raises(ValueError,match='explicit observation date'):
        parse_aaa(b'<html>No dated price</html>')


def test_daily_diagnostics_separate_rises_and_falls():
    rows=[{'observed_at':f'2026-07-0{i}','wholesale_cpg':v} for i,v in [(6,200),(7,230),(8,190)]]
    d=daily_diagnostics(rows,date(2026,7,1),date(2026,7,31))
    assert d['positive_daily_move_total_cpg']==30
    assert d['negative_daily_move_magnitude_total_cpg']==40
    assert d['maximum_within_week_range_cpg']==40


def test_daily_real_source_parser():
    from pathlib import Path
    from musa_nowcast.daily_prices import parse_wholesale
    root=Path('data/daily_prices/2026-10-07_v1')
    if not (root/'aaa_snapshot.html').exists():pytest.skip('local raw AAA archive not installed')
    assert len(parse_aaa((root/'aaa_snapshot.html').read_bytes()))==51
    assert len(parse_wholesale((root/'USGC.xls').read_bytes(),'USGC'))>9000
