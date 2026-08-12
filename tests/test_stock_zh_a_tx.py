from __future__ import annotations

from instock.core.crawling import stock_zh_a_tx


def test_tencent_spot_normalizes_project_contract(monkeypatch) -> None:
    monkeypatch.setattr(stock_zh_a_tx, "_direct_session", lambda: object())
    monkeypatch.setattr(
        stock_zh_a_tx,
        "_fetch_spot_page",
        lambda *_: {"data": {"total": 1, "rank_list": [{"code": "sh600000", "name": "测试", "zxj": "10", "zdf": "1.2", "zd": "0.12", "volume": "2", "turnover": "3", "zf": "2", "hsl": "3", "lb": "1.1", "speed": "0.2", "zdf_d60": "5", "zdf_y": "7", "pe_ttm": "8", "pn": "0.9", "zsz": "100", "ltsz": "80"}]}},
    )

    result = stock_zh_a_tx.stock_zh_a_spot_tx()

    assert result.loc[0, "code"] == "600000"
    assert result.loc[0, "volume"] == 20_000
    assert result.loc[0, "deal_amount"] == 30_000
    assert result.loc[0, "pre_close_price"] == 9.88
    assert result.columns[-4:].tolist() == ["total_market_cap", "free_cap", "industry", "listing_date"]


def test_tencent_history_normalizes_daily_rows(monkeypatch) -> None:
    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"data": {"sh600000": {"qfqday": [["2026-08-11", "9", "10", "11", "8", "100"]]}}}

    class _Session:
        def get(self, *_, **__):
            return _Response()

    monkeypatch.setattr(stock_zh_a_tx, "_direct_session", lambda: _Session())

    result = stock_zh_a_tx.stock_zh_a_hist_tx("600000", "20260811", "20260811")

    assert result.columns.tolist() == ["date", "open", "close", "high", "low", "volume", "amount", "amplitude", "quote_change", "ups_downs", "turnover"]
    assert result.loc[0, "amount"] == 100_000


def test_tencent_history_uses_current_raw_when_qfq_lags(monkeypatch) -> None:
    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"data": {"sh600000": {"qfqday": [["2026-08-11", "9", "10", "11", "8", "100"]], "day": [["2026-08-11", "9", "10", "11", "8", "100"], ["2026-08-12", "10", "11", "12", "9", "100"]]}}}

    class _Session:
        def get(self, *_, **__):
            return _Response()

    monkeypatch.setattr(stock_zh_a_tx, "_direct_session", lambda: _Session())

    result = stock_zh_a_tx.stock_zh_a_hist_tx("600000", "20260811", "20260812", "qfq")

    assert result["date"].max().isoformat() == "2026-08-12"
