#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同花顺公开板块（行业/概念）资金流排行，作为东方财富不可用时的降级来源。

同花顺不公开超大/大/中/小单拆分；本模块只填充其实际返回的净额、阶段涨跌幅、
由流入流出推导的净占比，以及今日榜中的领涨股。其余字段保持空值。
"""

from __future__ import annotations

from io import StringIO
import time
from typing import Literal

import pandas as pd
import requests
from bs4 import BeautifulSoup
import py_mini_racer

from akshare.stock_feature.stock_fund_flow import _get_file_content_ths
import instock.core.tablestructure as tbs


_INDICATOR_KEYS = {"今日": 0, "5日": 1, "10日": 2}
_SECTOR_MAP = {"行业资金流": "hy", "概念资金流": "gn", "hy": "hy", "gn": "gn"}

_PAGE_URLS = {
    ("hy", "今日"): "http://data.10jqka.com.cn/funds/hyzjl/field/tradezdf/order/desc/page/{}/ajax/1/free/1/",
    ("hy", "5日"): "http://data.10jqka.com.cn/funds/hyzjl/board/5/field/tradezdf/order/desc/page/{}/ajax/1/free/1/",
    ("hy", "10日"): "http://data.10jqka.com.cn/funds/hyzjl/board/10/field/tradezdf/order/desc/page/{}/ajax/1/free/1/",
    ("gn", "今日"): "http://data.10jqka.com.cn/funds/gnzjl/field/tradezdf/order/desc/page/{}/ajax/1/free/1/",
    ("gn", "5日"): "http://data.10jqka.com.cn/funds/gnzjl/board/5/field/tradezdf/order/desc/page/{}/ajax/1/free/1/",
    ("gn", "10日"): "http://data.10jqka.com.cn/funds/gnzjl/board/10/field/tradezdf/order/desc/page/{}/ajax/1/free/1/",
}


def _direct_session() -> requests.Session:
    """同花顺公开接口不继承本机 Clash/系统代理。"""
    session = requests.Session()
    session.trust_env = False
    return session


def _headers(js_code: py_mini_racer.MiniRacer, sector_code: str) -> dict[str, str]:
    """构建携带 hexin-v token 的请求头。"""
    hexin_v = js_code.call("v")
    referer = "http://data.10jqka.com.cn/funds/hyzjl/" if sector_code == "hy" else "http://data.10jqka.com.cn/funds/gnzjl/"
    return {
        "Accept": "text/html, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "hexin-v": hexin_v,
    }


def _page_count(html: str) -> int:
    page_info = BeautifulSoup(html, features="lxml").find("span", class_="page_info")
    if page_info is None or "/" not in page_info.get_text():
        return 1
    return int(page_info.get_text(strip=True).split("/")[-1])


import random

def _fetch_raw(sector_code: str, indicator: str, timeout: int = 15) -> pd.DataFrame:
    session = _direct_session()
    url_template = _PAGE_URLS.get((sector_code, indicator))
    if not url_template:
        raise ValueError(f"不支持的板块或周期类型: sector={sector_code}, indicator={indicator}")

    with py_mini_racer.MiniRacer() as js_code:
        js_code.eval(_get_file_content_ths("ths.js"))
        headers = _headers(js_code, sector_code)
        first = session.get(url_template.format(1), headers=headers, timeout=timeout)
        first.raise_for_status()
        pages = _page_count(first.text)
        frames: list[pd.DataFrame] = []
        try:
            frames.append(pd.read_html(StringIO(first.text))[0])
        except ValueError as exc:
            raise RuntimeError(f"同花顺板块资金流第 1/{pages} 页未返回表格") from exc

        for page in range(2, pages + 1):
            time.sleep(random.uniform(0.6, 1.2))
            headers = _headers(js_code, sector_code)
            response = session.get(url_template.format(page), headers=headers, timeout=timeout)
            if response.status_code in {401, 403}:
                time.sleep(random.uniform(2.0, 3.5))
                headers = _headers(js_code, sector_code)
                response = session.get(url_template.format(page), headers=headers, timeout=timeout)
            response.raise_for_status()
            try:
                frames.append(pd.read_html(StringIO(response.text))[0])
            except ValueError as exc:
                raise RuntimeError(f"同花顺板块资金流第 {page}/{pages} 页未返回表格") from exc

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _as_number(values: pd.Series, col_name: str = "") -> pd.Series:
    text = values.astype(str).str.strip().str.replace(",", "", regex=False)
    multiplier = pd.Series(1.0, index=text.index)
    if "(亿)" in col_name or "亿" in col_name:
        multiplier = multiplier * 100_000_000
    elif "(万)" in col_name or "万" in col_name:
        multiplier = multiplier * 10_000
    else:
        multiplier.loc[text.str.endswith("亿")] = 100_000_000
        multiplier.loc[text.str.endswith("万")] = 10_000

    text = text.str.replace("亿", "", regex=False).str.replace("万", "", regex=False).str.replace("%", "", regex=False)
    numeric_series = pd.to_numeric(text.replace({"--": None, "-": None, "nan": None, "None": None}), errors="coerce")
    return numeric_series * multiplier


def _column(raw: pd.DataFrame, name: str) -> tuple[str, pd.Series]:
    if name in raw.columns:
        return name, raw[name]
    matched = next((column for column in raw.columns if str(column).startswith(name)), None)
    if matched is None:
        raise KeyError(f"同花顺板块资金流缺少字段: {name}; actual={raw.columns.tolist()}")
    return matched, raw[matched]


def normalize_sector_fund_flow(raw: pd.DataFrame, indicator: str) -> pd.DataFrame:
    """Map a THS sector ranking response to the established InStock table contract."""
    if raw is None or raw.empty:
        return pd.DataFrame()
    if indicator not in _INDICATOR_KEYS:
        raise ValueError(f"不支持的资金流周期: {indicator}")

    indicator_idx = _INDICATOR_KEYS[indicator]
    suffix = {"今日": "", "5日": "_5", "10日": "_10"}[indicator]
    columns = list(tbs.CN_STOCK_SECTOR_FUND_FLOW[1][indicator_idx]["columns"].keys())
    data = pd.DataFrame(index=raw.index, columns=columns)

    # 1. 行业/概念名称
    _, name_col = _column(raw, "行业")
    data["name"] = name_col.astype(str).str.strip()

    # 2. 涨跌幅
    change_header = "涨跌幅" if indicator == "今日" else "阶段涨跌幅"
    actual_change_col, change_series = _column(raw, change_header)
    data[f"change_rate{suffix}"] = _as_number(change_series, actual_change_col)

    # 3. 主力净额 (转化为元)
    actual_net_col, net_series = _column(raw, "净额")
    net_inflow = _as_number(net_series, actual_net_col)
    data[f"fund_amount{suffix}"] = net_inflow

    # 4. 主力净占比: 净额 / (流入资金 + 流出资金) * 100
    try:
        actual_in_col, in_series = _column(raw, "流入资金")
        actual_out_col, out_series = _column(raw, "流出资金")
        in_flow = _as_number(in_series, actual_in_col)
        out_flow = _as_number(out_series, actual_out_col)
        total_flow = in_flow + out_flow
        data[f"fund_rate{suffix}"] = (net_inflow.div(total_flow).mul(100)).where(total_flow.ne(0))
    except Exception:
        pass

    # 5. 今日领涨股
    if indicator == "今日" and "领涨股" in raw.columns:
        data["stock_name"] = raw["领涨股"].astype(str).str.strip()

    # 去重保留最后一条
    data = data.drop_duplicates(subset=["name"], keep="last").reset_index(drop=True)
    return data


def stock_sector_fund_flow_rank_ths(indicator: str = "今日", sector_type: str = "行业资金流", timeout: int = 15) -> pd.DataFrame:
    """获取同花顺板块资金流（行业/概念）排行数据并标准化字段。"""
    if indicator not in _INDICATOR_KEYS:
        raise ValueError(f"不支持的资金流周期: {indicator}")
    sector_code = _SECTOR_MAP.get(sector_type)
    if not sector_code:
        raise ValueError(f"不支持的板块类型: {sector_type}")

    raw = _fetch_raw(sector_code, indicator, timeout=timeout)
    return normalize_sector_fund_flow(raw, indicator)
