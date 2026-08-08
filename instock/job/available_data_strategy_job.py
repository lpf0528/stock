#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""使用当前可用数据库表生成降级策略观察名单。"""

import datetime
import logging
import os
import sys

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)

import instock.lib.database as mdb


CODE_PREFIX = "60"


def fetch_candidates(date):
    """从综合选股快照中筛选可用的 60 开头股票。"""
    sql = """
        SELECT code, name, industry, new_price, change_rate, volume_ratio,
               turnoverrate, pe9, roe_weight, netprofit_yoy_ratio,
               toi_yoy_ratio, debt_asset_ratio, net_inflow, ddx,
               ((net_inflow > 0) + (ddx > 0) + (volume_ratio >= 1.5)
                + (change_rate > 0 AND change_rate < 9.9) + (roe_weight >= 10)
                + (netprofit_yoy_ratio >= 0) + (toi_yoy_ratio >= 0)
                + (turnoverrate BETWEEN 3 AND 20) + (pe9 BETWEEN 0 AND 50)
                - 2 * (debt_asset_ratio >= 70)) AS score
        FROM cn_stock_selection
        WHERE date = %s AND code LIKE %s
        HAVING score >= 7
        ORDER BY score DESC, net_inflow DESC, volume_ratio DESC
        LIMIT 20
    """
    return mdb.executeSqlFetch(sql, (date, f"{CODE_PREFIX}%")) or []


def latest_selection_date():
    rows = mdb.executeSqlFetch("SELECT MAX(date) FROM cn_stock_selection")
    return rows[0][0] if rows and rows[0][0] else None


def write_report(date, candidates):
    report_path = os.path.join(os.path.dirname(cpath), f"stock_strategy_selection_analysis_{date:%Y-%m-%d}.md")
    lines = [
        "# 60 开头股票降级策略选股",
        "",
        f"数据交易日：{date:%Y-%m-%d}",
        f"生成时间：{datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "本报告仅使用当前可用的综合选股快照；行情、指标、K线和回测表缺失时自动启用。",
        "结果是观察名单，不构成投资建议，也不得接入自动交易。",
        "",
        "| 代码 | 名称 | 行业 | 得分 | 涨跌幅 | 量比 | 换手率 | PE TTM | ROE | 净利润增长 | 营收增长 | 净流入 | DDX |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in candidates:
        code, name, industry, _, change_rate, volume_ratio, turnoverrate, pe9, roe, profit_growth, income_growth, _, net_inflow, ddx, score = row
        lines.append(
            f"| {code} | {name} | {industry or ''} | {score} | {change_rate:.2f} | {volume_ratio:.2f} | "
            f"{turnoverrate:.2f} | {pe9:.2f} | {roe:.2f} | {profit_growth:.2f} | {income_growth:.2f} | "
            f"{net_inflow / 100000000:.2f}亿 | {ddx:.3f} |"
        )
    if not candidates:
        lines.extend(["| - | 当日无符合规则的候选 | - | - | - | - | - | - | - | - | - | - | - |", "", "请检查数据新鲜度和筛选阈值。"])
    with open(report_path, "w", encoding="utf-8") as report:
        report.write("\n".join(lines) + "\n")
    return report_path


def main():
    if not mdb.checkTableIsExist("cn_stock_selection"):
        logging.error("available_data_strategy_job缺少 cn_stock_selection，无法执行降级策略")
        return None
    date = latest_selection_date()
    if date is None:
        logging.error("available_data_strategy_job综合选股表没有可用日期")
        return None
    candidates = fetch_candidates(date)
    report_path = write_report(date, candidates)
    logging.info("available_data_strategy_job完成: date=%s candidates=%s report=%s", date, len(candidates), report_path)
    return report_path


if __name__ == "__main__":
    main()
