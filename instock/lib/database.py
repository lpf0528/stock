#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import pymysql
from sqlalchemy import create_engine
from sqlalchemy.types import NVARCHAR
from sqlalchemy import inspect

__author__ = 'myh '
__date__ = '2023/3/10 '

db_host = "localhost"  # 数据库服务主机
db_user = "root"  # 数据库访问用户
db_password = "root"  # 数据库访问密码
db_database = "instockdb"  # 数据库名称
db_port = 3306  # 数据库服务端口
db_charset = "utf8mb4"  # 数据库字符集

import json

# 1. 尝试读取配置文件 instock/config/database.json
_config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'database.json')
if os.path.exists(_config_file):
    try:
        with open(_config_file, 'r', encoding='utf-8') as _f:
            _db_cfg = json.load(_f)
            db_host = _db_cfg.get('db_host', db_host)
            db_user = _db_cfg.get('db_user', db_user)
            db_password = _db_cfg.get('db_password', db_password)
            db_database = _db_cfg.get('db_database', db_database)
            db_port = int(_db_cfg.get('db_port', db_port))
            db_charset = _db_cfg.get('db_charset', db_charset)
    except Exception as _e:
        logging.warning(f"读取数据库配置文件 {_config_file} 失败: {_e}")

# 2. 尝试读取根目录 .env 配置文件
_env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
if os.path.exists(_env_file):
    try:
        with open(_env_file, 'r', encoding='utf-8') as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith('#') and '=' in _line:
                    _k, _v = _line.split('=', 1)
                    _k, _v = _k.strip(), _v.strip().strip("'\"")
                    if _k == 'db_host': db_host = _v
                    elif _k == 'db_user': db_user = _v
                    elif _k == 'db_password': db_password = _v
                    elif _k == 'db_database': db_database = _v
                    elif _k == 'db_port': db_port = int(_v)
                    elif _k == 'db_charset': db_charset = _v
    except Exception as _e:
        pass

# 3. 使用环境变量获得数据库,docker -e 传递 (优先级最高)
_db_host = os.environ.get('db_host')
if _db_host is not None:
    db_host = _db_host
_db_user = os.environ.get('db_user')
if _db_user is not None:
    db_user = _db_user
_db_password = os.environ.get('db_password')
if _db_password is not None:
    db_password = _db_password
_db_database = os.environ.get('db_database')
if _db_database is not None:
    db_database = _db_database
_db_port = os.environ.get('db_port')
if _db_port is not None:
    db_port = int(_db_port)

MYSQL_CONN_URL = "mysql+pymysql://%s:%s@%s:%s/%s?charset=%s" % (
    db_user, db_password, db_host, db_port, db_database, db_charset)
logging.info(f"数据库链接信息：{ MYSQL_CONN_URL}")

MYSQL_CONN_DBAPI = {'host': db_host, 'user': db_user, 'password': db_password, 'database': db_database,
                    'charset': db_charset, 'port': db_port, 'autocommit': True}

MYSQL_CONN_TORNDB = {'host': f'{db_host}:{str(db_port)}', 'user': db_user, 'password': db_password,
                     'database': db_database, 'charset': db_charset, 'max_idle_time': 3600, 'connect_timeout': 1000}


# 通过数据库链接 engine
def engine():
    return create_engine(MYSQL_CONN_URL)


def engine_to_db(to_db):
    _engine = create_engine(MYSQL_CONN_URL.replace(f'/{db_database}?', f'/{to_db}?'))
    return _engine


# DB Api -数据库连接对象connection
def get_connection():
    try:
        return pymysql.connect(**MYSQL_CONN_DBAPI)
    except Exception as e:
        logging.error(f"database.conn_not_cursor处理异常：{MYSQL_CONN_DBAPI}{e}")
    return None


# 定义通用方法函数，插入数据库表，并创建数据库主键，保证重跑数据的时候索引唯一。
def insert_db_from_df(data, table_name, cols_type, write_index, primary_keys, indexs=None):
    # 插入默认的数据库。
    insert_other_db_from_df(None, data, table_name, cols_type, write_index, primary_keys, indexs)


# 增加一个插入到其他数据库的方法。
def insert_other_db_from_df(to_db, data, table_name, cols_type, write_index, primary_keys, indexs=None):
    # 定义engine
    if to_db is None:
        engine_mysql = engine()
    else:
        engine_mysql = engine_to_db(to_db)
    # 使用 http://docs.sqlalchemy.org/en/latest/core/reflection.html
    # 使用检查检查数据库表是否有主键。
    ipt = inspect(engine_mysql)
    col_name_list = data.columns.tolist()
    # 如果有索引，把索引增加到varchar上面。
    if write_index:
        # 插入到第一个位置：
        col_name_list.insert(0, data.index.name)
    try:
        if cols_type is None:
            data.to_sql(name=table_name, con=engine_mysql, schema=to_db, if_exists='append',
                        index=write_index, )
        elif not cols_type:
            data.to_sql(name=table_name, con=engine_mysql, schema=to_db, if_exists='append',
                        dtype={col_name: NVARCHAR(255) for col_name in col_name_list}, index=write_index, )
        else:
            data.to_sql(name=table_name, con=engine_mysql, schema=to_db, if_exists='append',
                        dtype=cols_type, index=write_index, )
    except Exception as e:
        logging.error(f"database.insert_other_db_from_df处理异常：{table_name}表{e}")

    # 判断是否存在主键
    if not ipt.get_pk_constraint(table_name)['constrained_columns']:
        try:
            # 执行数据库插入数据。
            with get_connection() as conn:
                with conn.cursor() as db:
                    db.execute(f'ALTER TABLE `{table_name}` ADD PRIMARY KEY ({primary_keys});')
                    if indexs is not None:
                        for k in indexs:
                            db.execute(f'ALTER TABLE `{table_name}` ADD INDEX IN{k}({indexs[k]});')
        except Exception as e:
            logging.error(f"database.insert_other_db_from_df处理异常：{table_name}表{e}")


# 更新数据
def update_db_from_df(data, table_name, where):
    data = data.where(data.notnull(), None)
    update_string = f'UPDATE `{table_name}` set '
    where_string = ' where '
    cols = tuple(data.columns)
    with get_connection() as conn:
        with conn.cursor() as db:
            try:
                for row in data.values:
                    sql = update_string
                    sql_where = where_string
                    for index, col in enumerate(cols):
                        if col in where:
                            if len(sql_where) == len(where_string):
                                if type(row[index]) == str:
                                    sql_where = f'''{sql_where}`{col}` = '{row[index]}' '''
                                else:
                                    sql_where = f'''{sql_where}`{col}` = {row[index]} '''
                            else:
                                if type(row[index]) == str:
                                    sql_where = f'''{sql_where} and `{col}` = '{row[index]}' '''
                                else:
                                    sql_where = f'''{sql_where} and `{col}` = {row[index]} '''
                        else:
                            if type(row[index]) == str:
                                if row[index] is None or row[index] != row[index]:
                                    sql = f'''{sql}`{col}` = NULL, '''
                                else:
                                    sql = f'''{sql}`{col}` = '{row[index]}', '''
                            else:
                                if row[index] is None or row[index] != row[index]:
                                    sql = f'''{sql}`{col}` = NULL, '''
                                else:
                                    sql = f'''{sql}`{col}` = {row[index]}, '''
                    sql = f'{sql[:-2]}{sql_where}'
                    db.execute(sql)
            except Exception as e:
                logging.error(f"database.update_db_from_df处理异常：{sql}{e}")


# 检查表是否存在
def checkTableIsExist(tableName):
    with get_connection() as conn:
        with conn.cursor() as db:
            db.execute("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = '{1}'
                  AND table_name = '{0}'
                """.format(
                    tableName.replace('\'', '\'\''),
                    db_database.replace('\'', '\'\''),
                ))
            if db.fetchone()[0] == 1:
                return True
    return False


# 增删改数据
def executeSql(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as db:
            try:
                db.execute(sql, params)
            except Exception as e:
                logging.error(f"database.executeSql处理异常：{sql}{e}")


# 查询数据
def executeSqlFetch(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as db:
            try:
                db.execute(sql, params)
                return db.fetchall()
            except Exception as e:
                logging.error(f"database.executeSqlFetch处理异常：{sql}{e}")
    return None


# 计算数量
def executeSqlCount(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as db:
            try:
                db.execute(sql, params)
                result = db.fetchall()
                if len(result) == 1:
                    return int(result[0][0])
                else:
                    return 0
            except Exception as e:
                logging.error(f"database.select_count计算数量处理异常：{e}")
    return 0


# 各数据表判定为“已完整抓取”的最小预期行数阈值
TABLE_MIN_ROWS = {
    'cn_stock_spot': 1000,              # 每日全市场股票行情
    'cn_stock_selection': 1000,         # 综合选股
    'cn_stock_fund_flow': 1000,         # 个股资金流
    'cn_stock_fund_flow_industry': 50,  # 行业资金流
    'cn_stock_fund_flow_concept': 100,  # 概念资金流
    'cn_stock_lhb': 1,                  # 龙虎榜
    'cn_stock_blocktrade': 1,           # 大宗交易
    'cn_stock_bonus': 1,                # 分红配送
    'cn_stock_limitup_reason': 1,       # 涨停原因
    'cn_stock_chip_race_open': 1,       # 早盘抢筹
    'cn_stock_chip_race_end': 1,        # 尾盘抢筹
    'cn_etf_spot': 100,                 # ETF行情
    'cn_stock_indicators': 10,          # 技术指标
}


def is_table_data_completed(table_name, date, min_rows=None):
    """检查指定表在指定日期是否已经存在完整、成功抓取的数据。"""
    if not checkTableIsExist(table_name):
        return False
    date_str = date.strftime("%Y-%m-%d") if hasattr(date, 'strftime') else str(date)
    count = executeSqlCount(f"SELECT COUNT(*) FROM `{table_name}` WHERE `date` = %s", (date_str,))
    if count == 0:
        return False
    expected_min = min_rows if min_rows is not None else TABLE_MIN_ROWS.get(table_name, 1)
    if count < expected_min:
        logging.warning(f"⚠️ 表 `{table_name}` 在 {date_str} 仅存在 {count} 条数据 (低于预期完整阈值 {expected_min} 条)，需重新抓取")
        return False
    return True


def should_skip_fetch(table_name, date, min_rows=None, force=False):
    """判断是否应跳过抓取（已有成功完整数据且未强制重新抓取）。"""
    if force:
        return False
    if os.environ.get('STOCK_FORCE_REFETCH', '').strip().lower() in {'1', 'true', 'yes'}:
        return False
    return is_table_data_completed(table_name, date, min_rows)

