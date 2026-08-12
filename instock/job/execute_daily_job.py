#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import time
import datetime
import logging
import os.path
import sys
import os

# 在项目运行时，临时将项目路径添加到环境变量
cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)

# 强制清理系统代理，避免东方财富请求被本机代理劫持
for _proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_proxy_key, None)

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

from instock.job.daily_fetch_pipeline import DEFAULT_RECEIPT_PATH, default_date, run_fetches

__author__ = 'myh '
__date__ = '2023/3/10 '


def main():
    start = time.time()
    _start = datetime.datetime.now()
    logging.info("=" * 60)
    logging.info(f"🚀 ######## 每日盘后 Job 任务开始执行: {_start.strftime('%Y-%m-%d %H:%M:%S.%f')} #######")
    logging.info("=" * 60)
    
    logging.info("📌 执行可观测的独立抓取项；每项以目标日期数据库行数验收...")
    payload = run_fetches(date=default_date())
    logging.info("每日抓取终态=%s，回执=%s", payload["status"], DEFAULT_RECEIPT_PATH)

    logging.info("=" * 60)
    logging.info(f"🎉 ######## 完成所有每日 Job 任务, 总耗时: {time.time() - start:.2f} 秒 #######")
    logging.info("=" * 60)
    return 0 if payload["status"] == "completed" else 1


# main函数入口
if __name__ == '__main__':
    raise SystemExit(main())
