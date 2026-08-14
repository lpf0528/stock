#!/usr/local/bin/python
# -*- coding: utf-8 -*-


import logging
import datetime
import concurrent.futures
import sys
import time
import instock.lib.trade_time as trd

__author__ = 'myh '
__date__ = '2023/3/10 '


import os

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    cpath_current = os.path.dirname(os.path.dirname(__file__))
    log_path = os.path.join(cpath_current, 'log')
    if not os.path.exists(log_path):
        os.makedirs(log_path)

    has_stream = any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in logger.handlers)
    has_file = any(isinstance(h, logging.FileHandler) for h in logger.handlers)

    if not has_file:
        fh = logging.FileHandler(os.path.join(log_path, 'stock_execute_job.log'), encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    if not has_stream:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        logger.addHandler(sh)

# 通用函数，获得日期参数，支持批量作业。
def run_with_args(run_fun, *args):
    setup_logging()
    trade_date_data = trd.stock_trade_date().get_data()
    trade_date_available = bool(trade_date_data)
    if not trade_date_available:
        logging.warning(f"run_template.run_with_args未加载到交易日历，显式日期模式将跳过交易日校验: {run_fun.__name__}")
    if len(sys.argv) == 3:
        # 区间作业 python xxx.py 2023-03-01 2023-03-21
        tmp_year, tmp_month, tmp_day = sys.argv[1].split("-")
        start_date = datetime.datetime(int(tmp_year), int(tmp_month), int(tmp_day)).date()
        tmp_year, tmp_month, tmp_day = sys.argv[2].split("-")
        end_date = datetime.datetime(int(tmp_year), int(tmp_month), int(tmp_day)).date()
        run_date = start_date
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                while run_date <= end_date:
                    if trade_date_available and not trd.is_trade_date(run_date):
                        logging.info(f"run_template.run_with_args跳过非交易日: {run_date}")
                        run_date += datetime.timedelta(days=1)
                        continue
                    logging.info(f"▶️ 执行子任务: {run_fun.__name__} (日期范围: {run_date})")
                    if run_fun.__name__.startswith('save_nph'):
                        executor.submit(run_fun, run_date, False)
                    else:
                        executor.submit(run_fun, run_date, *args)
                    time.sleep(2)
                    run_date += datetime.timedelta(days=1)
        except Exception as e:
            logging.error(f"run_template.run_with_args处理异常：{run_fun}{sys.argv}{e}")
    elif len(sys.argv) == 2:
        # N个时间作业 python xxx.py 2023-03-01,2023-03-02
        dates = sys.argv[1].split(',')
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                for date in dates:
                    tmp_year, tmp_month, tmp_day = date.split("-")
                    run_date = datetime.datetime(int(tmp_year), int(tmp_month), int(tmp_day)).date()
                    if trade_date_available and not trd.is_trade_date(run_date):
                        logging.info(f"run_template.run_with_args跳过非交易日: {run_date}")
                        continue
                    logging.info(f"▶️ 执行子任务: {run_fun.__name__} (指定日期: {run_date})")
                    if run_fun.__name__.startswith('save_nph'):
                        executor.submit(run_fun, run_date, False)
                    else:
                        executor.submit(run_fun, run_date, *args)
                    time.sleep(2)
        except Exception as e:
            logging.error(f"run_template.run_with_args处理异常：{run_fun}{sys.argv}{e}")
    else:
        # 当前时间作业 python xxx.py
        try:
            if trade_date_available:
                run_date, run_date_nph = trd.get_trade_date_last()
            else:
                run_date = datetime.datetime.now().date()
                run_date_nph = run_date
                logging.warning(f"run_template.run_with_args使用当前日期作为回退: {run_date}")
            logging.info(f"▶️ 执行子任务: {run_fun.__name__} (实时/最新交易日: {run_date_nph})")
            if run_fun.__name__.startswith('save_nph'):
                run_fun(run_date_nph, False)
            elif run_fun.__name__.startswith('save_after_close'):
                run_fun(run_date, *args)
            else:
                run_fun(run_date_nph, *args)
        except Exception as e:
            logging.error(f"run_template.run_with_args处理异常：{run_fun}{sys.argv}{e}")
