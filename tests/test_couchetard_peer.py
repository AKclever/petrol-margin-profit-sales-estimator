from datetime import date
from pathlib import Path
import pytest
from musa_nowcast.couchetard_peer import FiscalEngine,parse_release
from musa_nowcast.data import QuarterActual


def test_fiscal_anchor_does_not_depend_on_calendar_start_bucket():
    engine=object.__new__(FiscalEngine)
    engine.actuals=[QuarterActual('F2023Q1',date(2022,4,25),date(2022,7,17),50),
                    QuarterActual('F2024Q1',date(2023,5,1),date(2023,7,23),51)]
    assert engine._prior_year_index(1)==0


@pytest.mark.parametrize('prefix',["2021-03-17","2025-03-18","2026-06-22","2026-09-01"])
def test_original_source_date_and_payment_fee_reconciliation(prefix):
    root=Path('data/couchetard_peer/2026-10-07_v1/sources')
    if not root.exists():pytest.skip('local raw research archive not installed')
    path=next(root.glob(prefix+'*.html'))
    row=parse_release(path.read_bytes(),'https://corporate.couche-tard.com/'+path.stem)
    assert abs(row['retail_margin_cpg']-row['payment_fees_cpg']-row['after_payment_margin_cpg'])<.021
    assert row['weeks'] in (12,13,16,17)
    assert date.fromisoformat(row['end'])<date.fromisoformat(row['available_at'])
    if prefix=='2026-09-01':
        assert row['retail_margin_cpg']==53.87
        assert row['start']=='2026-04-27' and row['end']=='2026-07-19'
    if prefix=='2025-03-18':assert row['weeks']==16
