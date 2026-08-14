from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instock.core import stockfetch


def test_limitup_reason_rejects_upstream_data_for_a_different_day(monkeypatch) -> None:
    columns = list(stockfetch.tbs.TABLE_CN_STOCK_LIMITUP_REASON["columns"])
    source = pd.DataFrame({column: [None] for column in columns})
    source["date"] = ["2026-08-12"]
    source["code"] = ["600000"]
    monkeypatch.setattr(stockfetch.slr, "stock_limitup_reason", lambda _date: source)

    assert stockfetch.fetch_stock_limitup_reason(date(2026, 8, 13)) is None
