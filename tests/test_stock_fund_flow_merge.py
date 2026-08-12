from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instock.job import basic_data_other_daily_job as job


def test_fund_flow_periods_are_merged_incrementally(monkeypatch) -> None:
    frames = {
        0: pd.DataFrame({"code": ["600001", "600002"], "name": ["甲", "乙"], "new_price": [10, 20], "fund_amount": [1, 2]}),
        1: pd.DataFrame({"code": ["600001", "600002", "600002"], "name": ["甲", "乙", "乙"], "new_price": [10, 20, 20], "fund_amount_3": [3, 4, 40], "fund_rate_3": [None, None, None]}),
        2: pd.DataFrame({"code": ["600001", "600002"], "name": ["甲", "乙"], "new_price": [10, 20], "fund_amount_5": [5, 6]}),
        3: pd.DataFrame({"code": ["600001", "600002"], "name": ["甲", "乙"], "new_price": [10, 20], "fund_amount_10": [7, 8]}),
    }
    monkeypatch.setattr(job.stf, "fetch_stocks_fund_flow", lambda index: frames[index])

    result = job.build_stock_fund_flow_data((0, 1, 2, 3))

    assert result is not None
    assert result.columns.tolist() == ["code", "name", "new_price", "fund_amount", "fund_amount_3", "fund_amount_5", "fund_amount_10"]
    assert result["fund_amount_3"].tolist() == [3, 40]
    assert result["fund_amount_10"].tolist() == [7, 8]
