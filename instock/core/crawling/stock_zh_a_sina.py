#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新浪财经 A 股历史日线行情抓取模块，作为腾讯/东财接口受阻时的稳定备选源。"""

from __future__ import annotations

import logging
import os
import time
import pandas as pd
import akshare as ak

import instock.core.tablestructure as tbs

# 强制清理环境变量中的代理，防止国内财经接口被本机/终端代理劫持产生 SSLEOFError
for _proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_proxy_key, None)


def _symbol(code: str) -> str:
    normalized = str(code).strip().lower().replace("sh", "").replace("sz", "").replace("bj", "")
    if not normalized.isdigit() or len(normalized) != 6:
        raise ValueError(f"无效 A 股代码: {code}")
    if normalized.startswith(("6", "9")):
        return f"sh{normalized}"
    if normalized.startswith(("4", "8")):
        return f"bj{normalized}"
    return f"sz{normalized}"


def stock_zh_a_hist_sina(
    symbol: str,
    start_date: str = "19900101",
    end_date: str = "20500101",
    adjust: str = "qfq",
) -> pd.DataFrame:
    """获取新浪财经历史日线数据并标准化为 CN_STOCK_HIST_DATA 列格式。"""
    for _proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(_proxy_key, None)

    sina_symbol = _symbol(symbol)
    start_clean = pd.to_datetime(start_date, errors="coerce")
    start_str = start_clean.strftime("%Y%m%d") if pd.notna(start_clean) else "19900101"
    end_clean = pd.to_datetime(end_date, errors="coerce")
    end_str = end_clean.strftime("%Y%m%d") if pd.notna(end_clean) else "20500101"

    last_error = None
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_daily(
                symbol=sina_symbol,
                start_date=start_str,
                end_date=end_str,
                adjust=adjust if adjust in ("qfq", "hfq") else "",
            )
            if df is None or df.empty:
                return pd.DataFrame()

            df = df.copy()
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
            df = df.dropna(subset=["date", "open", "close", "high", "low"])

            for col in ("open", "close", "high", "low", "volume", "amount"):
                df[col] = pd.to_numeric(df[col], errors="coerce")

            pre_close = df["close"].shift(1)
            df["amplitude"] = (df["high"] - df["low"]) / pre_close * 100
            df["quote_change"] = df["close"].pct_change() * 100
            df["ups_downs"] = df["close"].diff()
            if "turnover" not in df.columns:
                df["turnover"] = pd.NA

            target_columns = list(tbs.CN_STOCK_HIST_DATA["columns"].keys())
            return df[target_columns].reset_index(drop=True)
        except Exception as exc:
            last_error = exc
            time.sleep(0.3 * (attempt + 1))

    logging.warning("stock_zh_a_hist_sina 获取 %s 历史日线异常: %s", symbol, last_error)
    return pd.DataFrame()
