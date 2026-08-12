#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Stock 项目统一股票池配置。"""

import os
from pathlib import Path


STOCK_CODE_PREFIXES_ENV = "STOCK_CODE_PREFIXES"
LEGACY_HISTORY_CODE_PREFIXES_ENV = "STOCK_HIST_CODE_PREFIXES"
DEFAULT_STOCK_CODE_PREFIXES = ("60", "00")


def get_runtime_config(name):
    """环境变量优先；未导出时读取项目根目录 .env 中的同名配置。"""
    configured = os.getenv(name)
    if configured is not None:
        return configured

    env_file = Path(__file__).resolve().parents[2] / ".env"
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == name:
                return value.strip().strip("'\"")
    except OSError:
        pass
    return None


def get_stock_code_prefixes():
    """返回统一股票池代码前缀；``all``/``*`` 代表不限制。"""
    configured = get_runtime_config(STOCK_CODE_PREFIXES_ENV)
    if configured is None:
        # 兼容此前已配置的历史任务变量，正式配置以 STOCK_CODE_PREFIXES 为准。
        configured = get_runtime_config(LEGACY_HISTORY_CODE_PREFIXES_ENV)
    if configured is None:
        return DEFAULT_STOCK_CODE_PREFIXES
    configured = configured.strip()
    if configured.lower() in {"all", "*"}:
        return ()
    return tuple(prefix.strip() for prefix in configured.split(",") if prefix.strip())


def filter_stock_records(stocks, prefixes=None):
    """按统一股票池过滤 ``(date, code, name)`` 形式的记录，保持原始顺序。"""
    prefixes = get_stock_code_prefixes() if prefixes is None else tuple(prefixes)
    if not prefixes:
        return stocks
    return [stock for stock in stocks if len(stock) > 1 and str(stock[1]).zfill(6).startswith(prefixes)]


def filter_stock_dataframe(data, prefixes=None):
    """按统一股票池过滤包含 ``code`` 列的 DataFrame。"""
    prefixes = get_stock_code_prefixes() if prefixes is None else tuple(prefixes)
    if not prefixes or data is None or "code" not in data.columns:
        return data
    return data.loc[data["code"].astype(str).str.zfill(6).str.startswith(prefixes)].copy()
