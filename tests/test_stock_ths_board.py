from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from instock.core.crawling import stock_board_ths


class _Response:
    def __init__(self, text: str) -> None:
        self.text = text
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None


class _Session:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, url: str, timeout: int) -> _Response:
        self.calls.append(url)
        code = "600001" if "page/1" in url or "/code/" in url and "page/" not in url else "600002"
        page = "1" if code == "600001" else "2"
        return _Response(
            f"""
            <table><thead><tr><th>序号</th><th>代码</th><th>名称</th><th>现价</th><th>涨跌幅(%)</th></tr></thead>
            <tbody><tr><td>{page}</td><td>{code}</td><td>测试{page}</td><td>10.0</td><td>1.2</td></tr></tbody></table>
            <span class='page_info'>1/2</span>
            """
        )


def test_constituents_fetches_all_pages_and_marks_ths_source(monkeypatch) -> None:
    session = _Session()
    monkeypatch.setattr(stock_board_ths, "_direct_session", lambda: session)

    result = stock_board_ths.stock_board_constituents_ths("concept", "308614")

    assert result["代码"].tolist() == ["600001", "600002"]
    assert result["板块类型"].tolist() == ["同花顺概念", "同花顺概念"]
    assert result["数据源"].tolist() == ["同花顺", "同花顺"]
    assert any("page/2/ajax/1/code/308614" in url for url in session.calls)


def test_board_history_normalizes_ohlcv(monkeypatch) -> None:
    fake_akshare = SimpleNamespace(
        stock_board_concept_index_ths=lambda *_: pd.DataFrame(
            [{"日期": "2026-08-12", "开盘价": 10, "收盘价": 11, "最高价": 12, "最低价": 9, "成交量": 100, "成交额": 1100}]
        )
    )
    monkeypatch.setitem(__import__("sys").modules, "akshare", fake_akshare)

    result = stock_board_ths.stock_board_index_history_ths("concept", "测试概念", "20260812", "20260812")

    assert result.loc[0, "source"] == "ths"
    assert result.loc[0, "board_type"] == "ths_concept"
    assert result.loc[0, "close"] == 11
