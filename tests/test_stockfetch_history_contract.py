from __future__ import annotations

import pandas as pd

from instock.core import stockfetch


def test_fetch_stock_hist_adds_code_for_indicator_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        stockfetch,
        "stock_hist_cache",
        lambda *_, **__: pd.DataFrame(
            [
                {"date": "2026-08-11", "open": 9.0, "close": 10.0, "high": 11.0, "low": 8.0, "volume": 100.0, "amount": 1000.0, "amplitude": 1.0, "quote_change": 1.0, "ups_downs": 1.0, "turnover": 1.0},
                {"date": "2026-08-12", "open": 10.0, "close": 11.0, "high": 12.0, "low": 9.0, "volume": 100.0, "amount": 1100.0, "amplitude": 1.0, "quote_change": 1.0, "ups_downs": 1.0, "turnover": 1.0},
            ]
        ),
    )

    result = stockfetch.fetch_stock_hist(("2026-08-12", "600000", "测试"), "20260801", False)

    assert result["code"].tolist() == ["600000", "600000"]
    assert result["p_change"].iloc[0] == 0


def test_a_stock_filter_includes_star_and_beijing_boards() -> None:
    assert stockfetch.is_a_stock("688001")
    assert stockfetch.is_a_stock("430047")
    assert not stockfetch.is_a_stock("900901")
