#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import time
import datetime
import concurrent.futures
import logging
import os.path
import sys

# 在项目运行时，临时将项目路径添加到环境变量
cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
log_path = os.path.join(cpath_current, 'log')
if not os.path.exists(log_path):
    os.makedirs(log_path)
# 配置控制台与文件双向日志输出
logger = logging.getLogger()
logger.setLevel(logging.INFO)
if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    file_handler = logging.FileHandler(os.path.join(log_path, 'stock_execute_job.log'), encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

import init_job as bj
import basic_data_daily_job as hdj
import basic_data_other_daily_job as hdtj
import basic_data_after_close_daily_job as acdj
import indicators_data_daily_job as gdj
import strategy_data_daily_job as sdj
import backtest_data_daily_job as bdj
import klinepattern_data_daily_job as kdj
import selection_data_daily_job as sddj

__author__ = 'myh '
__date__ = '2023/3/10 '


def main():
    start = time.time()
    _start = datetime.datetime.now()
    logging.info("=" * 60)
    logging.info(f"🚀 ######## 每日盘后 Job 任务开始执行: {_start.strftime('%Y-%m-%d %H:%M:%S.%f')} #######")
    logging.info("=" * 60)
    
    # 第1步创建数据库
    logging.info("📌 [步骤 1/5] 初始化数据库结构 (init_job)...")
    bj.main()
    
    # 第2.1步创建股票基础数据表
    logging.info("📌 [步骤 2/5] 抓取并保存股票/ETF基础行情数据 (basic_data_daily_job)...")
    hdj.main()
    
    # 第2.2步创建综合股票数据表
    logging.info("📌 [步骤 3/5] 抓取并保存综合选股分类数据 (selection_data_daily_job)...")
    sddj.main()
    
    logging.info("📌 [步骤 4/5] 抓取其它基础数据: 龙虎榜、资金流向、板块资金流向、分红 (basic_data_other_daily_job)...")
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # 第3.1步创建股票其它基础数据表
        future_hdtj = executor.submit(hdtj.main)
        future_hdtj.result()

    # 第7步创建股票闭盘后才有的数据
    logging.info("📌 [步骤 5/5] 抓取闭盘后大宗交易与尾盘抢筹数据 (basic_data_after_close_daily_job)...")
    acdj.main()

    logging.info("=" * 60)
    logging.info(f"🎉 ######## 完成所有每日 Job 任务, 总耗时: {time.time() - start:.2f} 秒 #######")
    logging.info("=" * 60)


# main函数入口
if __name__ == '__main__':
    main()
