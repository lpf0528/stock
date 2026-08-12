from __future__ import annotations

import pandas as pd

from instock.core.crawling import stock_fund_ths
from instock.core.crawling.stock_fund_ths import normalize_individual_fund_flow


class _NoopMiniRacer:
    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def eval(self, _script: str) -> None:
        return None


def test_normalize_ths_realtime_keeps_unavailable_order_breakdown_empty() -> None:
    raw = pd.DataFrame([{
        "股票代码": "600000", "股票简称": "测试", "最新价": "10.50", "涨跌幅": "2.50%",
        "净额": "1.20亿", "成交额": "4亿",
    }])

    result = normalize_individual_fund_flow(raw, "今日")

    assert result.loc[0, "code"] == "600000"
    assert result.loc[0, "fund_amount"] == 120_000_000
    assert result.loc[0, "fund_rate"] == 30
    assert pd.isna(result.loc[0, "fund_amount_super"])


def test_normalize_ths_period_rank_maps_only_available_net_amount() -> None:
    raw = pd.DataFrame([{
        "股票代码": "000001", "股票简称": "测试", "最新价": "8.2", "阶段涨跌幅": "-1.5%", "资金流入净额": "-2500万",
    }])

    result = normalize_individual_fund_flow(raw, "3日")

    assert result.loc[0, "change_rate_3"] == -1.5
    assert result.loc[0, "fund_amount_3"] == -25_000_000
    assert pd.isna(result.loc[0, "fund_amount_super_3"])


def test_ths_refreshes_token_only_after_an_unauthorized_page(monkeypatch) -> None:
    class Response:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code
            self.text = "unused"

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError("unexpected HTTP failure")

    class Session:
        def __init__(self) -> None:
            self.headers: list[str] = []
            self.responses = iter([Response(200), Response(401), Response(200)])

        def get(self, _url, *, headers, timeout):
            self.headers.append(headers["hexin-v"])
            return next(self.responses)

    session = Session()
    tokens = iter([{"hexin-v": "first"}, {"hexin-v": "refreshed"}])
    monkeypatch.setattr(stock_fund_ths, "_direct_session", lambda: session)
    monkeypatch.setattr(stock_fund_ths, "_headers", lambda *_: next(tokens))
    monkeypatch.setattr(stock_fund_ths.py_mini_racer, "MiniRacer", lambda: _NoopMiniRacer())
    monkeypatch.setattr(stock_fund_ths, "_page_count", lambda _: 1)
    monkeypatch.setattr(stock_fund_ths.pd, "read_html", lambda _: [pd.DataFrame({"股票代码": ["600000"]})])

    result = stock_fund_ths._fetch_raw("即时")

    assert len(result) == 1
    assert session.headers == ["first", "first", "refreshed"]
