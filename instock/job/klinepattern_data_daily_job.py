#!/usr/local/bin/python3
# -*- coding: utf-8 -*-


import logging
import concurrent.futures
import pandas as pd
import os
import os.path
import sys

# 强制清理系统代理，避免国内财经接口被本机代理劫持
for _proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_proxy_key, None)

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
import instock.lib.run_template as runt
runt.setup_logging()
import instock.core.tablestructure as tbs
import instock.lib.database as mdb
from instock.core.singleton_stock import stock_hist_data
import instock.core.pattern.pattern_recognitions as kpr

__author__ = 'myh '
__date__ = '2023/3/10 '


def prepare(date):
    try:
        logging.info(f"🚀 [K线形态任务] 开始准备 {date} 历史日线数据并执行形态识别...")
        stocks_data = stock_hist_data(date=date).get_data()
        if stocks_data is None:
            logging.warning(f"⚠️ [K线形态任务] {date} 未获取到有效股票历史数据")
            return
        results = run_check(stocks_data, date=date)
        if results is None:
            logging.info(f"ℹ️ [K线形态任务] {date} 未匹配到符合特征的 K线形态")
            return

        table_name = tbs.TABLE_CN_STOCK_KLINE_PATTERN['name']
        # 删除老数据。
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` where `date` = '{date}'"
            mdb.executeSql(del_sql)
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_KLINE_PATTERN['columns'])

        dataKey = pd.DataFrame(results.keys())
        _columns = tuple(tbs.TABLE_CN_STOCK_FOREIGN_KEY['columns'])
        dataKey.columns = _columns

        dataVal = pd.DataFrame(results.values())

        data = pd.merge(dataKey, dataVal, on=['code'], how='left')
        # 单例，时间段循环必须改时间
        date_str = date.strftime("%Y-%m-%d")
        if date.strftime("%Y-%m-%d") != data.iloc[0]['date']:
            data['date'] = date_str
        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")
        logging.info(f"💾 [K线形态入库成功] {date_str} 共识别到 {len(data)} 只形态匹配股票，已成功写入 `{table_name}` 表")

    except Exception as e:
        logging.error(f"klinepattern_data_daily_job.prepare处理异常：{e}")


def run_check(stocks, date=None, workers=40):
    data = {}
    columns = tbs.STOCK_KLINE_PATTERN_DATA['columns']
    data_column = columns
    total_stocks = len(stocks)
    logging.info(f"🔍 [K线形态计算] 开始扫描 {total_stocks} 只股票的 61 种 K线形态特征 (并发线程数: {workers})...")
    step_interval = max(50, total_stocks // 20)
    processed_count = 0
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_data = {executor.submit(kpr.get_pattern_recognition, k, stocks[k], data_column, date=date): k for k in stocks}
            for future in concurrent.futures.as_completed(future_to_data):
                stock = future_to_data[future]
                processed_count += 1
                try:
                    _data_ = future.result()
                    if _data_ is not None:
                        data[stock] = _data_
                except Exception as e:
                    logging.error(f"klinepattern_data_daily_job.run_check处理异常：{stock[1]}代码{e}")

                if processed_count % step_interval == 0 or processed_count == total_stocks:
                    pct = (processed_count / total_stocks) * 100
                    logging.info(f"⏳ [形态识别进度] {processed_count}/{total_stocks} ({pct:.1f}%) - 已发现 {len(data)} 只形态匹配个股")

        logging.info(f"✅ [K线形态计算完成] 扫描 {total_stocks} 只股票，共匹配到 {len(data)} 只具有形态特征个股")
    except Exception as e:
        logging.error(f"klinepattern_data_daily_job.run_check处理异常：{e}")
    if not data:
        return None
    else:
        return data


def main():
    # 使用方法传递。
    runt.run_with_args(prepare)


# main函数入口
if __name__ == '__main__':
    main()
