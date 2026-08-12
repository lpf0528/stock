#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import logging
import concurrent.futures
import os.path
import os
import sys
import random
import time
import gc
import pandas as pd

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)

# 强制清理系统代理，避免东方财富请求被本机代理劫持
for _proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_proxy_key, None)

import instock.lib.run_template as runt
import instock.core.tablestructure as tbs
import instock.lib.database as mdb
import instock.core.stockfetch as stf

__author__ = 'myh '
__date__ = '2023/3/10 '

# 每日股票龙虎榜
def save_nph_stock_lhb_data(date, before=True):
    if before:
        return

    try:
        data = stf.fetch_stock_lhb_data(date)
        if data is None or len(data.index) == 0:
            return

        table_name = tbs.TABLE_CN_STOCK_lHB['name']
        # 删除老数据。
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` where `date` = '{date}'"
            mdb.executeSql(del_sql)
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_lHB['columns'])
        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")
    except Exception as e:
        logging.error(f"basic_data_other_daily_job.save_stock_lhb_data处理异常：{e}")
    stock_spot_buy(date)

# 每日股票龙虎榜(新浪)
def save_nph_stock_top_data(date, before=True):
    if before:
        return

    try:
        data = stf.fetch_stock_top_data(date)
        if data is None or len(data.index) == 0:
            return

        table_name = tbs.TABLE_CN_STOCK_TOP['name']
        # 删除老数据。
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` where `date` = '{date}'"
            mdb.executeSql(del_sql)
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_TOP['columns'])
        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")
    except Exception as e:
        logging.error(f"basic_data_other_daily_job.save_stock_top_data处理异常：{e}")
    stock_spot_buy(date)


# 每日股票资金流向
def save_nph_stock_fund_flow_data(date, before=True):
    if before:
        return

    try:
        data = build_stock_fund_flow_data(tuple(range(4)))
        if data is None:
            return

        if data is None or len(data.index) == 0:
            return

        data.insert(0, 'date', date.strftime("%Y-%m-%d"))

        table_name = tbs.TABLE_CN_STOCK_FUND_FLOW['name']
        # 删除老数据。
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` where `date` = '{date}'"
            mdb.executeSql(del_sql)
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_FUND_FLOW['columns'])

        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")
    except Exception as e:
        logging.error(f"basic_data_other_daily_job.save_nph_stock_fund_flow_data处理异常：{e}")


def build_stock_fund_flow_data(times):
    """Fetch periods one at a time and retain only fields needed for the merge.

    A full THS ranking has thousands of rows and many empty legacy columns.
    Keeping all four rankings at once caused the daily process to be killed
    after the final fetch, before the database write.  Streaming the merge
    bounds memory while preserving the existing table contract.
    """
    data = None
    for index in times:
        period = stf.fetch_stocks_fund_flow(index)
        if period is None or period.empty:
            logging.warning("个股资金流周期无数据: index=%s", index)
            continue
        duplicated = int(period.duplicated(subset=['code'], keep='last').sum())
        if duplicated:
            logging.warning("个股资金流周期存在重复代码，按最后一条保留: index=%s duplicates=%s", index, duplicated)
            period = period.drop_duplicates(subset=['code'], keep='last').copy()
        if index == 0:
            data = period.copy()
        else:
            # name/new_price already come from the instant ranking.  Empty
            # legacy order-size columns must not be carried through merges.
            columns = [column for column in period.columns if column == 'code' or (column not in {'name', 'new_price'} and period[column].notna().any())]
            data = pd.merge(data, period.loc[:, columns], on=['code'], how='left', validate='one_to_one')
        del period
        gc.collect()
    if data is None or data.empty:
        return None
    return data


def run_check_stock_fund_flow(times):
    data = {}
    try:
        for k in times :
            _data = stf.fetch_stocks_fund_flow(k)
            if _data is not None:
                data[k] = _data
    except Exception as e:
        logging.error(f"basic_data_other_daily_job.run_check_stock_fund_flow处理异常：{e}")
    # try:
    #     with concurrent.futures.ThreadPoolExecutor(max_workers=len(times)) as executor:
    #         future_to_data = {executor.submit(stf.fetch_stocks_fund_flow, k): k for k in times}
    #         for future in concurrent.futures.as_completed(future_to_data):
    #             _time = future_to_data[future]
    #             try:
    #                 _data_ = future.result()
    #                 if _data_ is not None:
    #                     data[_time] = _data_
    #             except Exception as e:
    #                 logging.error(f"basic_data_other_daily_job.run_check_stock_fund_flow处理异常：代码{e}")
    # except Exception as e:
    #     logging.error(f"basic_data_other_daily_job.run_check_stock_fund_flow处理异常：{e}")
    if not data:
        return None
    else:
        return data


# 每日行业资金流向
def save_nph_stock_sector_fund_flow_data(date, before=True):
    if before:
        return

    stock_sector_fund_flow_data(date, 0)
    stock_sector_fund_flow_data(date, 1)

def stock_sector_fund_flow_data(date, index_sector):
    sector_label = "行业资金流向 (cn_stock_fund_flow_industry)" if index_sector == 0 else "概念资金流向 (cn_stock_fund_flow_concept)"
    logging.info(f"📊 开始抓取并处理 {sector_label} (日期: {date})...")
    try:
        tbs_table = tbs.TABLE_CN_STOCK_FUND_FLOW_INDUSTRY if index_sector == 0 else tbs.TABLE_CN_STOCK_FUND_FLOW_CONCEPT
        table_name = tbs_table['name']
        if not mdb.checkTableIsExist(table_name):
            logging.warning(f"📊 {sector_label} 表不存在，先创建空表: {table_name}")
            pd.DataFrame(columns=list(tbs_table['columns'].keys())).to_sql(
                name=table_name,
                con=mdb.engine(),
                if_exists='replace',
                index=False,
                dtype=tbs.get_field_types(tbs_table['columns']),
            )

        times = tuple(range(3))
        results = run_check_stock_sector_fund_flow(index_sector, times)
        if results is None:
            logging.warning(f"⚠️ 未获取到 {sector_label} 数据")
            return

        logging.info(f"📊 {sector_label} 子任务返回: {sorted(results.keys())}")
        for t in times:
            if t == 0:
                data = results.get(t)
                if data is not None:
                    logging.info(f"📊 {sector_label} 主表数据行数: {len(data.index)}")
            else:
                r = results.get(t)
                if r is not None:
                    logging.info(f"📊 {sector_label} 合并前指标{t}数据行数: {len(r.index)}")
                    data = pd.merge(data, r, on=['name'], how='left')

        if data is None or len(data.index) == 0:
            logging.warning(f"⚠️ {sector_label} 数据为空")
            return

        if any(result.attrs.get('is_stale_cache', False) for result in results.values()):
            logging.warning(f"⚠️ {sector_label} 本次仅获得历史缓存，跳过入库以避免伪造 {date} 的实时数据")
            return

        data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        logging.info(f"📊 {sector_label} 处理后数据行数: {len(data.index)}, 列数: {len(data.columns)}")
        # 删除老数据。
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` where `date` = '{date}'"
            logging.info(f"📊 {sector_label} 表已存在，先删除旧数据: {del_sql}")
            mdb.executeSql(del_sql)
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs_table['columns'])
            logging.info(f"📊 {sector_label} 表不存在，将按字段类型自动创建: {table_name}")

        logging.info(f"📊 {sector_label} 开始入库: table={table_name}")
        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`name`")
        logging.info(f"✅ 成功保存 {sector_label} -> 数据量: {len(data.index)} 条，表名: `{table_name}`")
    except Exception as e:
        logging.exception(f"basic_data_other_daily_job.stock_sector_fund_flow_data处理异常：{e}")


def run_check_stock_sector_fund_flow(index_sector, times):
    data = {}
    try:
        logging.info(f"basic_data_other_daily_job.run_check_stock_sector_fund_flow开始: index_sector={index_sector}, times={times}")
        # 东财 push2 会对同一出口的并发访问快速限流；三个指标必须串行抓取。
        for _time in times:
            try:
                _data_ = stf.fetch_stocks_sector_fund_flow(index_sector, _time)
                if _data_ is not None:
                    data[_time] = _data_
                    logging.info(f"basic_data_other_daily_job.run_check_stock_sector_fund_flow完成: index_sector={index_sector}, index_indicator={_time}, rows={len(_data_.index)}")
                else:
                    logging.warning(f"basic_data_other_daily_job.run_check_stock_sector_fund_flow为空: index_sector={index_sector}, index_indicator={_time}")
            except Exception as e:
                logging.exception(f"basic_data_other_daily_job.run_check_stock_sector_fund_flow处理异常：index_sector={index_sector}, index_indicator={_time}, error={e}")
            # 与接口内部重试叠加的节流，避免三个指标紧邻发起。
            time.sleep(random.uniform(2, 5))
    except Exception as e:
        logging.exception(f"basic_data_other_daily_job.run_check_stock_sector_fund_flow处理异常：{e}")
    if not data:
        logging.warning(f"basic_data_other_daily_job.run_check_stock_sector_fund_flow最终无可用数据: index_sector={index_sector}")
        return None
    else:
        return data


# 每日股票分红配送
def save_nph_stock_bonus(date, before=True):
    if before:
        return

    try:
        data = stf.fetch_stocks_bonus(date)
        if data is None or len(data.index) == 0:
            return

        table_name = tbs.TABLE_CN_STOCK_BONUS['name']
        # 删除老数据。
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` where `date` = '{date}'"
            mdb.executeSql(del_sql)
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_BONUS['columns'])
        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")
    except Exception as e:
        logging.error(f"basic_data_other_daily_job.save_nph_stock_bonus处理异常：{e}")


# 基本面选股
def stock_spot_buy(date):
    try:
        _table_name = tbs.TABLE_CN_STOCK_SPOT['name']
        if not mdb.checkTableIsExist(_table_name):
            return

        sql = f'''SELECT * FROM `{_table_name}` WHERE `date` = '{date}' and 
                `pe9` > 0 and `pe9` <= 20 and `pbnewmrq` <= 10 and `roe_weight` >= 15'''
        data = pd.read_sql(sql=sql, con=mdb.engine())
        data = data.drop_duplicates(subset="code", keep="last")
        if len(data.index) == 0:
            return

        table_name = tbs.TABLE_CN_STOCK_SPOT_BUY['name']
        # 删除老数据。
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` where `date` = '{date}'"
            mdb.executeSql(del_sql)
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_SPOT_BUY['columns'])

        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")
    except Exception as e:
        logging.error(f"basic_data_other_daily_job.stock_spot_buy处理异常：{e}")


# 每日早盘抢筹
def stock_chip_race_open_data(date):
    try:
        data = stf.fetch_stock_chip_race_open(date)
        if data is None or len(data.index) == 0:
            return

        table_name = tbs.TABLE_CN_STOCK_CHIP_RACE_OPEN['name']
        # 删除老数据。
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` where `date` = '{date}'"
            mdb.executeSql(del_sql)
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_CHIP_RACE_OPEN['columns'])

        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")
    except Exception as e:
        logging.error(f"basic_data_other_daily_job.stock_chip_race_open_data：{e}")


# 每日涨停原因
def stock_imitup_reason_data(date):
    try:
        data = stf.fetch_stock_limitup_reason(date)
        if data is None or len(data.index) == 0:
            return

        table_name = tbs.TABLE_CN_STOCK_LIMITUP_REASON['name']
        # 删除老数据。
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` where `date` = '{date}'"
            mdb.executeSql(del_sql)
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_LIMITUP_REASON['columns'])

        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")
    except Exception as e:
        logging.error(f"basic_data_other_daily_job.stock_imitup_reason_data：{e}")

def main():
    runt.run_with_args(save_nph_stock_lhb_data)
    runt.run_with_args(save_nph_stock_bonus)
    runt.run_with_args(save_nph_stock_fund_flow_data)
    runt.run_with_args(save_nph_stock_sector_fund_flow_data)
    runt.run_with_args(stock_chip_race_open_data)
    runt.run_with_args(stock_imitup_reason_data)


# main函数入口
if __name__ == '__main__':
    main()
