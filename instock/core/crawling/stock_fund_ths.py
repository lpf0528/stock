#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同花顺公开个股资金流排行，作为东方财富不可用时的降级来源。

同花顺不公开超大/大/中/小单拆分；本模块只填充其实际返回的净额、阶段涨跌幅，
以及即时榜可由净额/成交额推导的净占比。其余字段保持空值。
"""

from __future__ import annotations

from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup
import py_mini_racer

from akshare.stock_feature.stock_fund_flow import _get_file_content_ths

import instock.core.tablestructure as tbs


_INDICATOR_TO_THS = {"今日": "即时", "3日": "3日排行", "5日": "5日排行", "10日": "10日排行"}
_BASE_URL = "http://data.10jqka.com.cn/funds/ggzjl/field/code/order/desc/ajax/1/free/1/"
_PAGE_URLS = {
    "即时": "http://data.10jqka.com.cn/funds/ggzjl/field/zdf/order/desc/page/{}/ajax/1/free/1/",
    "3日排行": "http://data.10jqka.com.cn/funds/ggzjl/board/3/field/zdf/order/desc/page/{}/ajax/1/free/1/",
    "5日排行": "http://data.10jqka.com.cn/funds/ggzjl/board/5/field/zdf/order/desc/page/{}/ajax/1/free/1/",
    "10日排行": "http://data.10jqka.com.cn/funds/ggzjl/board/10/field/zdf/order/desc/page/{}/ajax/1/free/1/",
}


def _direct_session() -> requests.Session:
    """同花顺公开接口不继承本机 Clash/系统代理。"""
    session = requests.Session()
    session.trust_env = False
    return session


def _headers(js_code: py_mini_racer.MiniRacer) -> dict[str, str]:
    """Build headers with a token from the period-scoped V8 instance."""
    hexin_v = js_code.call("v")
    return {
        "Accept": "text/html, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "http://data.10jqka.com.cn/funds/hyzjl/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "hexin-v": hexin_v,
    }


def _page_count(html: str) -> int:
    page_info = BeautifulSoup(html, features="lxml").find("span", class_="page_info")
    if page_info is None or "/" not in page_info.get_text():
        raise RuntimeError("同花顺个股资金流未返回分页信息")
    return int(page_info.get_text(strip=True).split("/")[-1])


def _fetch_raw(indicator: str, timeout: int = 15) -> pd.DataFrame:
    session = _direct_session()
    # Hold one V8 engine for the entire pagination cycle.  THS can invalidate
    # a token mid-run, but recalculating it on this instance avoids spawning
    # hundreds of native V8/semaphore resources in a daily run.
    with py_mini_racer.MiniRacer() as js_code:
        js_code.eval(_get_file_content_ths("ths.js"))
        headers = _headers(js_code)
        first = session.get(_BASE_URL, headers=headers, timeout=timeout)
        first.raise_for_status()
        pages = _page_count(first.text)
        frames: list[pd.DataFrame] = []
        for page in range(1, pages + 1):
            response = session.get(_PAGE_URLS[indicator].format(page), headers=headers, timeout=timeout)
            if response.status_code in {401, 403}:
                headers = _headers(js_code)
                response = session.get(_PAGE_URLS[indicator].format(page), headers=headers, timeout=timeout)
            response.raise_for_status()
            try:
                frames.append(pd.read_html(StringIO(response.text))[0])
            except ValueError as exc:
                raise RuntimeError(f"同花顺个股资金流第 {page}/{pages} 页未返回表格") from exc
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _as_number(values: pd.Series) -> pd.Series:
    text = values.astype(str).str.strip().str.replace(",", "", regex=False)
    multiplier = pd.Series(1.0, index=text.index)
    multiplier.loc[text.str.endswith("亿")] = 100_000_000
    multiplier.loc[text.str.endswith("万")] = 10_000
    text = text.str.replace("亿", "", regex=False).str.replace("万", "", regex=False).str.replace("%", "", regex=False)
    return pd.to_numeric(text.replace({"--": None, "-": None, "nan": None}), errors="coerce") * multiplier


def _column(raw: pd.DataFrame, name: str) -> pd.Series:
    """THS may suffix numeric headers with ``(元)``; accept either form."""
    if name in raw.columns:
        return raw[name]
    matched = next((column for column in raw.columns if str(column).startswith(name)), None)
    if matched is None:
        raise KeyError(f"同花顺个股资金流缺少字段: {name}; actual={raw.columns.tolist()}")
    return raw[matched]


def normalize_individual_fund_flow(raw: pd.DataFrame, indicator: str) -> pd.DataFrame:
    """Map a THS ranking response to the established InStock fund-flow contract."""
    if raw is None or raw.empty:
        return pd.DataFrame()
    if indicator not in _INDICATOR_TO_THS:
        raise ValueError(f"不支持的资金流周期: {indicator}")

    suffix = {"今日": "", "3日": "_3", "5日": "_5", "10日": "_10"}[indicator]
    columns = list(tbs.CN_STOCK_FUND_FLOW[("今日", "3日", "5日", "10日").index(indicator)]["columns"])
    data = pd.DataFrame(index=raw.index, columns=columns)
    data["code"] = _column(raw, "股票代码").astype(str).str.extract(r"(\d{6})", expand=False).str.zfill(6)
    data["name"] = _column(raw, "股票简称").astype(str)
    data["new_price"] = _as_number(_column(raw, "最新价"))
    change_column = "涨跌幅" if indicator == "今日" else "阶段涨跌幅"
    data[f"change_rate{suffix}"] = _as_number(_column(raw, change_column))
    if indicator == "今日":
        data["fund_amount"] = _as_number(_column(raw, "净额"))
        deal_amount = _as_number(_column(raw, "成交额"))
        data["fund_rate"] = data["fund_amount"].div(deal_amount).mul(100).where(deal_amount.ne(0))
    else:
        data[f"fund_amount{suffix}"] = _as_number(_column(raw, "资金流入净额"))
    return data


def stock_individual_fund_flow_rank_ths(indicator: str, timeout: int = 15) -> pd.DataFrame:
    """Fetch a complete THS ranking and normalize it to the legacy column order."""
    if indicator not in _INDICATOR_TO_THS:
        raise ValueError(f"不支持的资金流周期: {indicator}")
    return normalize_individual_fund_flow(_fetch_raw(_INDICATOR_TO_THS[indicator], timeout), indicator)
