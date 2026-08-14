#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""腾讯证券 A 股快照与日线，作为 EastMoney 失效时的独立行情来源。"""

from __future__ import annotations

import logging

import pandas as pd
import requests

import instock.core.tablestructure as tbs


_QUOTE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://gu.qq.com/",
}
_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
_SPOT_URL = "https://proxy.finance.qq.com/cgi/cgi-bin/rank/hs/getBoardRankList"


def _symbol(code: str) -> str:
    normalized = str(code).strip().lower().replace("sh", "").replace("sz", "").replace("bj", "")
    if not normalized.isdigit() or len(normalized) != 6:
        raise ValueError(f"无效 A 股代码: {code}")
    if normalized.startswith(("6", "9")):
        return f"sh{normalized}"
    if normalized.startswith(("4", "8")):
        return f"bj{normalized}"
    return f"sz{normalized}"


def _as_number(series: pd.Series, multiplier: float = 1.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce") * multiplier


def _direct_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(_QUOTE_HEADERS)
    return session


def _fetch_spot_page(session: requests.Session, offset: int, timeout: int) -> dict:
    response = session.get(
        _SPOT_URL,
        params={
            "_appver": "11.17.0",
            "board_code": "aStock",
            "sort_type": "price",
            "direct": "down",
            "offset": str(offset),
            "count": "200",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def stock_zh_a_spot_tx(timeout: int = 15) -> pd.DataFrame:
    """Return Tencent all-market snapshot in InStock's pre-date spot contract."""
    session = _direct_session()
    first_page = _fetch_spot_page(session, 0, timeout)
    payload = first_page.get("data") or {}
    raw_rows = list(payload.get("rank_list") or [])
    total = int(payload.get("total") or 0)
    for offset in range(200, total, 200):
        page = _fetch_spot_page(session, offset, timeout)
        raw_rows.extend((page.get("data") or {}).get("rank_list") or [])
    raw = pd.DataFrame(raw_rows).drop_duplicates(subset=["code"], keep="first")
    if raw is None or raw.empty:
        return pd.DataFrame()
    data = pd.DataFrame(index=raw.index)
    data["code"] = raw["code"].astype(str).str.extract(r"(\d{6})", expand=False).str.zfill(6)
    data["name"] = raw["name"].astype(str)
    data["new_price"] = _as_number(raw["zxj"])
    data["change_rate"] = _as_number(raw["zdf"])
    data["ups_downs"] = _as_number(raw["zd"])
    # 腾讯的 volume 为万股、turnover 为万元；转换为项目既有的股/元单位。
    data["volume"] = _as_number(raw["volume"], 10_000)
    data["deal_amount"] = _as_number(raw["turnover"], 10_000)
    data["amplitude"] = _as_number(raw["zf"])
    data["turnoverrate"] = _as_number(raw["hsl"])
    data["volume_ratio"] = _as_number(raw["lb"])
    data["open_price"] = pd.NA
    data["high_price"] = pd.NA
    data["low_price"] = pd.NA
    data["pre_close_price"] = data["new_price"] - data["ups_downs"]
    data["speed_increase"] = _as_number(raw["speed"])
    data["speed_increase_5"] = pd.NA
    data["speed_increase_60"] = _as_number(raw["zdf_d60"])
    data["speed_increase_all"] = _as_number(raw["zdf_y"])
    data["dtsyl"] = _as_number(raw["pe_ttm"])
    data["pe9"] = _as_number(raw["pe_ttm"])
    data["pe"] = pd.NA
    data["pbnewmrq"] = _as_number(raw["pn"])
    for column in (
        "basic_eps", "bvps", "per_capital_reserve", "per_unassign_profit", "roe_weight",
        "sale_gpr", "debt_asset_ratio", "total_operate_income", "toi_yoy_ratio",
        "parent_netprofit", "netprofit_yoy_ratio", "report_date", "total_shares",
        "free_shares", "industry", "listing_date",
    ):
        data[column] = pd.NA
    data["total_market_cap"] = _as_number(raw["zsz"], 100_000_000)
    data["free_cap"] = _as_number(raw["ltsz"], 100_000_000)
    # ``stockfetch.fetch_stocks`` inserts date then assigns the legacy table
    # columns positionally, so this order is a strict persistence contract.
    return data[list(tbs.TABLE_CN_STOCK_SPOT["columns"].keys())[1:]]


def stock_zh_a_hist_tx(
    symbol: str,
    start_date: str = "19900101",
    end_date: str = "20500101",
    adjust: str = "qfq",
    timeout: int = 10,
) -> pd.DataFrame:
    """Return Tencent daily OHLCV normalized to ``CN_STOCK_HIST_DATA`` fields."""
    if adjust not in ("", "qfq"):
        raise ValueError("腾讯日线当前仅支持未复权或 qfq")
    exchange_symbol = _symbol(symbol)
    session = _direct_session()
    start = _format_date(start_date)
    end = _format_date(end_date)

    def _fetch_rows(request_adjust: str) -> list:
        key = "qfqday" if request_adjust == "qfq" else "day"
        response = session.get(
            _KLINE_URL,
            params={"param": f"{exchange_symbol},day,{start},{end},640,{request_adjust or 'day'}"},
            timeout=timeout,
        )
        response.raise_for_status()
        return (response.json().get("data", {}).get(exchange_symbol, {}) or {}).get(key, [])

    rows = _fetch_rows(adjust)
    # Tencent can publish the unadjusted close before the adjusted series is
    # refreshed. Prefer same-source raw OHLCV over a stale qfq series so an
    # after-close indicator run includes the target trading date.
    if adjust == "qfq" and rows:
        qfq_last_date = pd.to_datetime(rows[-1][0], errors="coerce").date()
        requested_end = pd.to_datetime(end, errors="raise").date()
        if qfq_last_date < requested_end:
            raw_rows = _fetch_rows("")
            if raw_rows and pd.to_datetime(raw_rows[-1][0], errors="coerce").date() > qfq_last_date:
                logging.warning(
                    "腾讯 qfq 日线落后于目标日期 %s（最新 %s），本次改用同源未复权日线",
                    requested_end,
                    qfq_last_date,
                )
                rows = raw_rows
    if not rows:
        return pd.DataFrame()
    data = pd.DataFrame(rows)
    if data.shape[1] < 6:
        return pd.DataFrame()
    data = data.iloc[:, :6]
    data.columns = ["date", "open", "close", "high", "low", "volume"]
    for column in ("open", "close", "high", "low", "volume"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.date
    data = data.dropna(subset=["date", "open", "close", "high", "low"])
    # 腾讯返回的成交量单位为手；项目历史合同也沿用手。成交额以 close 近似，
    # 仅用于技术指标/回测，不冒充交易所精确成交额。
    data["amount"] = data["volume"] * 100 * data["close"]
    previous_close = data["close"].shift(1)
    data["amplitude"] = (data["high"] - data["low"]) / previous_close * 100
    data["quote_change"] = data["close"].pct_change() * 100
    data["ups_downs"] = data["close"].diff()
    data["turnover"] = pd.NA
    return data[
        ["date", "open", "close", "high", "low", "volume", "amount", "amplitude", "quote_change", "ups_downs", "turnover"]
    ].reset_index(drop=True)


def _format_date(value: str) -> str:
    parsed = pd.to_datetime(value, errors="raise")
    return parsed.strftime("%Y-%m-%d")
