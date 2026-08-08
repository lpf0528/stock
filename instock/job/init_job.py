#!/usr/local/bin/python3
# -*- coding: utf-8 -*-


import logging
import pymysql
import os.path
import sys
import pandas as pd

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
import instock.lib.database as mdb
import instock.core.tablestructure as tbs

__author__ = 'myh '
__date__ = '2023/3/10 '


# 创建新数据库。
def create_new_database():
    _MYSQL_CONN_DBAPI = mdb.MYSQL_CONN_DBAPI.copy()
    _MYSQL_CONN_DBAPI['database'] = "mysql"
    with pymysql.connect(**_MYSQL_CONN_DBAPI) as conn:
        with conn.cursor() as db:
            try:
                create_sql = f"CREATE DATABASE IF NOT EXISTS `{mdb.db_database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
                db.execute(create_sql)
                create_new_base_table()
            except Exception as e:
                logging.error(f"init_job.create_new_database处理异常：{e}")


# 创建基础表。
def create_new_base_table():
    with pymysql.connect(**mdb.MYSQL_CONN_DBAPI) as conn:
        with conn.cursor() as db:
            create_table_sql = """CREATE TABLE IF NOT EXISTS `cn_stock_attention` (
                                  `datetime` datetime(0) NULL DEFAULT NULL, 
                                  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
                                  PRIMARY KEY (`code`) USING BTREE,
                                  INDEX `INIX_DATETIME`(`datetime`) USING BTREE
                                  ) CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;"""
            db.execute(create_table_sql)
    # 个股资金流表不能依赖首次成功入库时由 to_sql 隐式创建；
    # 上游抓取暂时不可用时，也必须保留可查询的空表。
    create_table_from_structure(tbs.TABLE_CN_STOCK_FUND_FLOW)
    create_table_from_structure(tbs.TABLE_CN_STOCK_FUND_FLOW_INDUSTRY)
    create_table_from_structure(tbs.TABLE_CN_STOCK_FUND_FLOW_CONCEPT)


def create_table_from_structure(table_def):
    table_name = table_def['name']
    if mdb.checkTableIsExist(table_name):
        logging.info(f"init_job.create_table_from_structure表已存在: {table_name}")
        return

    df = pd.DataFrame(columns=list(table_def['columns'].keys()))
    try:
        df.to_sql(
            name=table_name,
            con=mdb.engine(),
            if_exists='replace',
            index=False,
            dtype=tbs.get_field_types(table_def['columns']),
        )
        logging.info(f"init_job.create_table_from_structure创建成功: {table_name}")
    except Exception as e:
        logging.exception(f"init_job.create_table_from_structure处理异常：{table_name}, {e}")


def check_database():
    with pymysql.connect(**mdb.MYSQL_CONN_DBAPI) as conn:
        with conn.cursor() as db:
            db.execute(" select 1 ")


def main():
    logging.info(
        "init_job.database_target host=%s port=%s user=%s database=%s charset=%s",
        mdb.db_host,
        mdb.db_port,
        mdb.db_user,
        mdb.db_database,
        mdb.db_charset,
    )
    # 检查，如果执行 select 1 失败，说明数据库不存在，然后创建一个新的数据库。
    try:
        check_database()
    except Exception as e:
        logging.error("执行信息：数据库不存在，将创建。")
        # 检查数据库失败，
        create_new_database()
    # 数据库已存在也要补齐缺失表。
    create_new_base_table()


# main函数入口
if __name__ == '__main__':
    main()
