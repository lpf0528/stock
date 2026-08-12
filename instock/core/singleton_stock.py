#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import concurrent.futures
import os
import instock.core.stockfetch as stf
import instock.core.tablestructure as tbs
import instock.lib.trade_time as trd
from instock.lib.singleton_type import singleton_type
from instock.core.stock_universe import (
    DEFAULT_STOCK_CODE_PREFIXES,
    LEGACY_HISTORY_CODE_PREFIXES_ENV,
    filter_stock_records,
    get_stock_code_prefixes,
)

__author__ = 'myh '
__date__ = '2023/3/10 '


# 保留旧导入名称，避免项目外调用方在升级后失效。
HISTORY_CODE_PREFIXES_ENV = LEGACY_HISTORY_CODE_PREFIXES_ENV
DEFAULT_HISTORY_CODE_PREFIXES = DEFAULT_STOCK_CODE_PREFIXES
get_history_code_prefixes = get_stock_code_prefixes
filter_history_universe = filter_stock_records


# 读取当天股票数据
class stock_data(metaclass=singleton_type):
    def __init__(self, date):
        try:
            self.data = stf.fetch_stocks(date)
        except Exception as e:
            logging.error(f"singleton.stock_data处理异常：{e}")

    def get_data(self):
        return self.data


# 读取股票历史数据
class stock_hist_data(metaclass=singleton_type):
    def __init__(self, date=None, stocks=None, workers=None):
        if workers is None:
            # 腾讯日线是一股票一请求；保守默认值避免在首次全量历史回补时
            # 触发上游限流。可由环境变量在已验证的网络环境中逐步提高。
            workers = max(1, int(os.getenv("STOCK_HIST_WORKERS", "4")))
        if stocks is None:
            _raw_data = stock_data(date).get_data()
            if _raw_data is None:
                self.data = None
                return
            _subset = _raw_data[list(tbs.TABLE_CN_STOCK_FOREIGN_KEY['columns'])]
            stocks = [tuple(x) for x in _subset.values]
            prefixes = get_stock_code_prefixes()
            unfiltered_count = len(stocks)
            stocks = filter_stock_records(stocks, prefixes)
            logging.info(
                "singleton.stock_hist_data历史股票池前缀=%s input=%s selected=%s",
                ",".join(prefixes) if prefixes else "all",
                unfiltered_count,
                len(stocks),
            )
            batch_offset = max(0, int(os.getenv("STOCK_HIST_BATCH_OFFSET", "0")))
            batch_limit = max(0, int(os.getenv("STOCK_HIST_BATCH_LIMIT", "0")))
            if batch_limit:
                stocks = stocks[batch_offset:batch_offset + batch_limit]
                logging.info(
                    "singleton.stock_hist_data受控历史批次 offset=%s limit=%s selected=%s",
                    batch_offset,
                    batch_limit,
                    len(stocks),
                )
        if not stocks:
            self.data = None
            return
        date_start, is_cache = trd.get_trade_hist_interval(stocks[0][0])  # 提高运行效率，只运行一次
        _data = {}
        try:
            # max_workers是None还是没有给出，将默认为机器cup个数*5
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_stock = {executor.submit(stf.fetch_stock_hist, stock, date_start, is_cache): stock for stock
                                   in stocks}
                for future in concurrent.futures.as_completed(future_to_stock):
                    stock = future_to_stock[future]
                    try:
                        __data = future.result()
                        if __data is not None:
                            _data[stock] = __data
                    except Exception as e:
                        logging.error(f"singleton.stock_hist_data处理异常：{stock[1]}代码{e}")
        except Exception as e:
            logging.error(f"singleton.stock_hist_data处理异常：{e}")
        if not _data:
            self.data = None
        else:
            self.data = _data

    def get_data(self):
        return self.data
