#!/usr/local/bin/python3
# -*- coding: utf-8 -*-


import json
from abc import ABC
from tornado import gen
# import logging
import datetime
import instock.lib.trade_time as trd
import instock.core.singleton_stock_web_module_data as sswmd
import instock.web.base as webBase
import instock.lib.database as mdb

__author__ = 'myh '
__date__ = '2023/3/10 '


class MyEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, bytes):
            return "是" if ord(obj) == 1 else "否"
        elif isinstance(obj, datetime.date):
            delta = datetime.datetime.combine(obj, datetime.time.min) - datetime.datetime(1899, 12, 30)
            return f'/OADate({float(delta.days) + (float(delta.seconds) / 86400)})/'  # 86,400 seconds in day
            # return obj.isoformat()
        else:
            return json.JSONEncoder.default(self, obj)


# 获得页面数据。
class GetStockHtmlHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        name = self.get_argument("table_name", default=None, strip=False)
        web_module_data = sswmd.stock_web_module_data().get_data(name)
        run_date, run_date_nph = trd.get_trade_date_last()
        if web_module_data.is_realtime:
            date_now_str = run_date_nph.strftime("%Y-%m-%d")
        else:
            date_now_str = run_date.strftime("%Y-%m-%d")
        # When verified historical rows exist but current date is empty,
        # fallback to the latest date available so user doesn't see a blank page.
        if (mdb.checkTableIsExist(web_module_data.table_name)
                and mdb.executeSqlCount(
                    f"SELECT COUNT(*) FROM `{web_module_data.table_name}` WHERE `date` = %s",
                    (date_now_str,),
                ) == 0):
            latest = mdb.executeSqlFetch(f"SELECT MAX(`date`) FROM `{web_module_data.table_name}`")
            if latest and latest[0][0] is not None:
                date_now_str = latest[0][0].isoformat()
        self.render("stock_web.html", web_module_data=web_module_data, date_now=date_now_str,
                    leftMenu=webBase.GetLeftMenu(self.request.uri))


# 获得股票数据内容。
class GetStockDataHandler(webBase.BaseHandler, ABC):
    def get(self):
        name = self.get_argument("name", default=None, strip=False)
        date = self.get_argument("date", default=None, strip=False)
        web_module_data = sswmd.stock_web_module_data().get_data(name)
        self.set_header('Content-Type', 'application/json;charset=UTF-8')

        if date is None:
            where = ""
        else:
            # where = f" WHERE `date` = '{date}'"
            where = f" WHERE `date` = %s"

        order_by = ""
        if web_module_data.order_by is not None:
            order_by = f" ORDER BY {web_module_data.order_by}"

        order_columns = ""
        if web_module_data.order_columns is not None:
            order_columns = f",{web_module_data.order_columns}"

        # 检查表是否存在，避免在每日任务未运行时出现 Table doesn't exist 错误
        if not mdb.checkTableIsExist(web_module_data.table_name):
            self.write(json.dumps([], cls=MyEncoder))
            return

        sql = f" SELECT *{order_columns} FROM `{web_module_data.table_name}`{where}{order_by}"
        try:
            if date is None:
                data = self.db.query(sql)
            else:
                data = self.db.query(sql, date)
        except Exception:
            # 表可能在检查后被删除，或数据库状态和缓存不一致
            self.write(json.dumps([], cls=MyEncoder))
            return

        self.write(json.dumps(data, cls=MyEncoder))
