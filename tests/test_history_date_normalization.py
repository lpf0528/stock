from __future__ import annotations

from datetime import date

import pandas as pd

from instock.core.backtest.rate_stats import get_rates
from instock.core.indicator.calculate_indicator import get_indicators


def test_indicator_accepts_date_objects_for_end_date_filter() -> None:
    history = pd.DataFrame(
        [
            {"date": date(2026, 8, 11), "open": 9.0, "close": 10.0, "high": 11.0, "low": 8.0, "volume": 100.0, "amount": 1000.0, "p_change": 0.0, "code": "600000"},
            {"date": date(2026, 8, 12), "open": 10.0, "close": 11.0, "high": 12.0, "low": 9.0, "volume": 100.0, "amount": 1100.0, "p_change": 10.0, "code": "600000"},
        ]
    )

    result = get_indicators(history, end_date="2026-08-12", threshold=1, calc_threshold=2)

    assert result is not None
    assert len(result) == 1


def test_backtest_accepts_date_objects() -> None:
    history = pd.DataFrame(
        [
            {"date": date(2026, 8, 11), "close": 10.0},
            {"date": date(2026, 8, 12), "close": 11.0},
        ]
    )

    result = get_rates((date(2026, 8, 11), "600000", "测试"), history, ["date", "code", "rate_1"])

    assert result["rate_1"] == 10.0
