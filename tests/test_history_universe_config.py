from __future__ import annotations

import pandas as pd

from instock.core.stock_universe import (
    DEFAULT_STOCK_CODE_PREFIXES,
    STOCK_CODE_PREFIXES_ENV,
    filter_stock_dataframe,
    filter_stock_records,
    get_stock_code_prefixes,
)


def test_stock_universe_defaults_to_60_and_00(monkeypatch) -> None:
    monkeypatch.delenv(STOCK_CODE_PREFIXES_ENV, raising=False)

    assert get_stock_code_prefixes() == DEFAULT_STOCK_CODE_PREFIXES
    stocks = [
        ("2026-08-12", "600000", "浦发银行"),
        ("2026-08-12", "000001", "平安银行"),
        ("2026-08-12", "300001", "特锐德"),
        ("2026-08-12", "688001", "华兴源创"),
    ]

    assert [stock[1] for stock in filter_stock_records(stocks)] == ["600000", "000001"]


def test_stock_universe_accepts_configured_prefixes_and_all(monkeypatch) -> None:
    stocks = [
        ("2026-08-12", "600000", "浦发银行"),
        ("2026-08-12", "000001", "平安银行"),
        ("2026-08-12", "300001", "特锐德"),
    ]
    monkeypatch.setenv(STOCK_CODE_PREFIXES_ENV, "30, 60")

    assert get_stock_code_prefixes() == ("30", "60")
    assert [stock[1] for stock in filter_stock_records(stocks)] == ["600000", "300001"]

    monkeypatch.setenv(STOCK_CODE_PREFIXES_ENV, "all")
    assert get_stock_code_prefixes() == ()
    assert filter_stock_records(stocks) == stocks


def test_stock_universe_filters_realtime_dataframe(monkeypatch) -> None:
    monkeypatch.setenv(STOCK_CODE_PREFIXES_ENV, "60,00")
    data = pd.DataFrame({"code": ["600000", "000001", "300001"], "name": ["甲", "乙", "丙"]})

    assert filter_stock_dataframe(data)["code"].tolist() == ["600000", "000001"]
