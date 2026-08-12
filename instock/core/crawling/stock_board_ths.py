#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同花顺行业/概念板块的成分股和历史行情。

同花顺与东方财富板块分类口径不同；本模块仅提供同花顺自身的
``board_type/name/code/source`` 合同，禁止将结果混写为东财概念或资金流。
"""

from __future__ import annotations

import time
from io import StringIO
from typing import Literal, Optional

import pandas as pd
from bs4 import BeautifulSoup

from instock.core.crawling.stock_concept_rank import _direct_session


BoardType = Literal["industry", "concept"]

_BOARD_URLS = {
    "industry": "https://q.10jqka.com.cn/thshy/detail/code/{code}/",
    "concept": "https://q.10jqka.com.cn/gn/detail/code/{code}/",
}
_BOARD_AJAX_BASE = {
    "industry": "https://q.10jqka.com.cn/thshy/detail",
    "concept": "https://q.10jqka.com.cn/gn/detail",
}


def _validate_board_type(board_type: str) -> BoardType:
    if board_type not in _BOARD_URLS:
        raise ValueError("board_type 只支持 'industry' 或 'concept'")
    return board_type  # type: ignore[return-value]


def _name_code_map(board_type: BoardType) -> dict[str, str]:
    import akshare as ak

    source = (
        ak.stock_board_industry_name_ths()
        if board_type == "industry"
        else ak.stock_board_concept_name_ths()
    )
    return dict(zip(source["name"].astype(str), source["code"].astype(str)))


def resolve_board_code_ths(board_type: BoardType, symbol: str) -> str:
    """Resolve a THS board name or return the supplied numeric board code."""
    _validate_board_type(board_type)
    value = str(symbol).strip()
    if value.isdigit():
        return value
    code = _name_code_map(board_type).get(value)
    if not code:
        raise KeyError(f"未找到同花顺{('行业' if board_type == 'industry' else '概念')}板块: {value}")
    return code


def stock_board_constituents_ths(
    board_type: BoardType,
    symbol: str,
    *,
    timeout: int = 10,
    max_pages: Optional[int] = None,
) -> pd.DataFrame:
    """Fetch all available THS constituent pages for an industry or concept.

    Returns the public page fields and immutable source metadata.  ``max_pages``
    is useful for bounded smoke tests; omit it for the complete constituent list.
    """
    board_type = _validate_board_type(board_type)
    code = resolve_board_code_ths(board_type, symbol)
    session = _direct_session()

    def _get(url: str, *, retry: bool = False):
        """Retry a challenged page with fresh THS ``v`` cookies and backoff."""
        nonlocal session
        attempts = 3 if retry else 1
        last_status = None
        for attempt in range(attempts):
            response = session.get(url, timeout=timeout)
            last_status = response.status_code
            if response.status_code not in (403, 429):
                response.raise_for_status()
                return response
            if attempt + 1 < attempts:
                time.sleep(1.2 * (attempt + 1))
                session = _direct_session()
        raise RuntimeError(f"同花顺成分股请求被限流或拦截: HTTP {last_status}")

    response = _get(_BOARD_URLS[board_type].format(code=code))
    first_soup = BeautifulSoup(response.text, "lxml")
    page_info = first_soup.select_one(".page_info")
    total_pages = int(page_info.get_text(strip=True).split("/")[-1]) if page_info else 1
    if max_pages is not None:
        total_pages = min(total_pages, max(1, int(max_pages)))

    frames: list[pd.DataFrame] = []
    for page in range(1, total_pages + 1):
        url = _BOARD_URLS[board_type].format(code=code)
        if page == 1:
            html = response.text
        else:
            url = (
                f"{_BOARD_AJAX_BASE[board_type]}/field/199112/order/desc/"
                f"page/{page}/ajax/1/code/{code}/"
            )
            # THS 的 Ajax 分页对连续请求很敏感。小间隔加一次新 Cookie 重试，
            # 比高速并发后写入残缺成分股名单更安全。
            time.sleep(0.25)
            page_response = _get(url, retry=True)
            html = page_response.text
        try:
            tables = pd.read_html(StringIO(html))
        except ValueError:
            # THS 有时以 200 返回挑战页而非 403。刷新 v Cookie 后只重试
            # 当前页一次；仍无表格就停止，避免产生不完整的“全量”结果。
            time.sleep(0.8)
            session = _direct_session()
            retry_response = _get(url, retry=True)
            try:
                tables = pd.read_html(StringIO(retry_response.text))
            except ValueError as exc:
                raise RuntimeError(f"同花顺成分股第 {page}/{total_pages} 页未返回表格") from exc
        if not tables:
            raise RuntimeError(f"同花顺成分股第 {page}/{total_pages} 页返回空表格")
        frame = tables[0]
        frame.columns = [str(column).strip() for column in frame.columns]
        frames.append(frame)

    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, ignore_index=True)
    result["代码"] = result["代码"].astype(str).str.extract(r"(\d{6})", expand=False).str.zfill(6)
    for column in ("现价", "涨跌幅(%)", "涨跌", "涨速(%)", "换手(%)", "量比", "振幅(%)", "市盈率"):
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.drop_duplicates(subset=["代码"], keep="first")
    result.insert(0, "板块类型", "同花顺行业" if board_type == "industry" else "同花顺概念")
    result.insert(1, "板块名称", str(symbol))
    result.insert(2, "板块代码", code)
    result["数据源"] = "同花顺"
    return result.reset_index(drop=True)


def stock_board_index_history_ths(
    board_type: BoardType,
    symbol: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Fetch THS board index OHLCV and normalize it to the project history contract."""
    board_type = _validate_board_type(board_type)
    import akshare as ak

    raw = (
        ak.stock_board_industry_index_ths(symbol, start_date, end_date)
        if board_type == "industry"
        else ak.stock_board_concept_index_ths(symbol, start_date, end_date)
    )
    if raw is None or raw.empty:
        return pd.DataFrame()
    data = raw.rename(
        columns={
            "日期": "date",
            "开盘价": "open",
            "收盘价": "close",
            "最高价": "high",
            "最低价": "low",
            "成交量": "volume",
            "成交额": "amount",
        }
    ).copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.date
    data = data.dropna(subset=["date", "close"]).sort_values("date")
    data["amplitude"] = (data["high"] - data["low"]) / data["close"].shift(1) * 100
    data["quote_change"] = data["close"].pct_change() * 100
    data["ups_downs"] = data["close"].diff()
    data["turnover"] = pd.NA
    data["board_type"] = "ths_industry" if board_type == "industry" else "ths_concept"
    data["board_name"] = symbol
    data["source"] = "ths"
    return data.reset_index(drop=True)
