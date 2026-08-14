#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os.path
import datetime
import numpy as np
import pandas as pd
import talib as tl
import instock.core.tablestructure as tbs
from instock.core.stock_universe import filter_stock_dataframe, get_stock_code_prefixes
import instock.lib.trade_time as trd
import instock.core.crawling.trade_date_hist as tdh
import instock.core.crawling.fund_etf_em as fee
import instock.core.crawling.stock_selection as sst
import instock.core.crawling.stock_lhb_em as sle
import instock.core.crawling.stock_lhb_sina as sls
import instock.core.crawling.stock_dzjy_em as sde
import instock.core.crawling.stock_hist_em as she
import instock.core.crawling.stock_zh_a_tx as sht
import instock.core.crawling.stock_fund_em as sff
import instock.core.crawling.stock_fund_ths as sft
import instock.core.crawling.stock_sector_fund_ths as ssft
import instock.core.crawling.stock_fhps_em as sfe
import instock.core.crawling.stock_chip_race as scr
import instock.core.crawling.stock_limitup_reason as slr

__author__ = 'myh '
__date__ = '2023/3/10 '

# 设置基础目录，每次加载使用。
cpath_current = os.path.dirname(os.path.dirname(__file__))
stock_hist_cache_path = os.path.join(cpath_current, 'cache', 'hist')
if not os.path.exists(stock_hist_cache_path):
    os.makedirs(stock_hist_cache_path)  # 创建多个文件夹结构。
stock_sector_fund_flow_cache_path = os.path.join(cpath_current, 'cache', 'sector_fund_flow')
if not os.path.exists(stock_sector_fund_flow_cache_path):
    os.makedirs(stock_sector_fund_flow_cache_path)


# 600 601 603 605开头的股票是上证A股
# 600开头的股票是上证A股，属于大盘股，其中6006开头的股票是最早上市的股票，
# 6016开头的股票为大盘蓝筹股；900开头的股票是上证B股；
# 688开头的是上证科创板股票；
# 000开头的股票是深证A股，001、002开头的股票也都属于深证A股，
# 其中002开头的股票是深证A股中小企业股票；
# 200开头的股票是深证B股；
# 300、301开头的股票是创业板股票；400开头的股票是三板市场股票。
# 430、83、87开头的股票是北证A股
def is_a_stock(code):
    # 上证/深证主板、创业板、科创板和北交所 A 股；排除 200/900 等 B 股。
    return str(code).zfill(6).startswith(
        (
            '600', '601', '603', '605', '688', '689',
            '000', '001', '002', '003', '300', '301',
            '430', '83', '87', '88', '92',
        )
    )


# 过滤掉 st 股票。
def is_not_st(name):
    return not name.startswith(('*ST', 'ST'))


# 过滤价格，如果没有基本上是退市了。
def is_open(price):
    return not np.isnan(price)


def is_open_with_line(price):
    return price != '-'


# 读取股票交易日历数据
def fetch_stocks_trade_date():
    try:
        data = tdh.tool_trade_date_hist_sina()
        if data is None or len(data.index) == 0:
            return None
        data_date = set(data['trade_date'].values.tolist())
        return data_date
    except Exception as e:
        logging.error(f"stockfetch.fetch_stocks_trade_date处理异常：{e}")
    return None


# 读取当天股票数据
def fetch_etfs(date):
    try:
        data = fee.fund_etf_spot_em()
        if data is None or len(data.index) == 0:
            return None
        if date is None:
            data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
        else:
            data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        data.columns = list(tbs.TABLE_CN_ETF_SPOT['columns'])
        data = data.loc[data['new_price'].apply(is_open)]
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_etfs处理异常：{e}")
    return None


# 读取当天股票数据
def fetch_stocks(date):
    source = os.getenv("STOCK_MARKET_DATA_SOURCE", "tencent").strip().lower()
    fetchers = (
        (("腾讯", sht.stock_zh_a_spot_tx), ("东方财富", she.stock_zh_a_spot_em))
        if source != "eastmoney"
        else (("东方财富", she.stock_zh_a_spot_em), ("腾讯", sht.stock_zh_a_spot_tx))
    )
    for source_name, fetcher in fetchers:
        try:
            data = fetcher()
            if data is None or len(data.index) == 0:
                continue
            if date is None:
                data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
            else:
                data.insert(0, 'date', date.strftime("%Y-%m-%d"))
            data.columns = list(tbs.TABLE_CN_STOCK_SPOT['columns'])
            data = data.loc[data['code'].apply(is_a_stock)].loc[data['new_price'].apply(is_open)]
            all_a_stock_count = len(data.index)
            data = filter_stock_dataframe(data)
            prefixes = get_stock_code_prefixes()
            logging.info(
                "stockfetch.fetch_stocks source=%s prefixes=%s input=%s selected=%s",
                source_name,
                ",".join(prefixes) if prefixes else "all",
                all_a_stock_count,
                len(data.index),
            )
            return data
        except Exception as e:
            logging.warning("stockfetch.fetch_stocks source=%s failed: %s", source_name, e)
    return None


def fetch_stock_selection():
    try:
        data = sst.stock_selection()
        if data is None or len(data.index) == 0:
            return None
        data.columns = list(tbs.TABLE_CN_STOCK_SELECTION['columns'])
        data.drop_duplicates('code', keep='last', inplace=True)
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stocks_selection处理异常：{e}")
    return None


# 读取股票资金流向
def fetch_stocks_fund_flow(index):
    try:
        cn_flow = tbs.CN_STOCK_FUND_FLOW[index]
        source = os.environ.get('STOCK_FUND_FLOW_SOURCE', 'ths').strip().lower()
        if source not in {'ths', 'eastmoney', 'auto'}:
            raise ValueError("STOCK_FUND_FLOW_SOURCE 仅支持 ths、eastmoney 或 auto")
        data = None
        if source in {'eastmoney', 'auto'}:
            try:
                data = sff.stock_individual_fund_flow_rank(indicator=cn_flow['cn'])
            except Exception as exc:
                if source == 'eastmoney':
                    raise
                logging.warning("东方财富个股资金流不可用，切换同花顺: %s", exc)
        if data is None or len(data.index) == 0:
            if source == 'eastmoney':
                return None
            data = sft.stock_individual_fund_flow_rank_ths(indicator=cn_flow['cn'])
            logging.info("stockfetch.fetch_stocks_fund_flow数据源=同花顺 indicator=%s rows=%s", cn_flow['cn'], len(data.index))
        if data is None or len(data.index) == 0:
            return None
        data.columns = list(cn_flow['columns'])
        # THS occasionally returns non-security rows whose identifiers share a
        # Beijing-exchange prefix but are longer than the six-character schema
        # key.  ``is_a_stock`` intentionally only checks a market prefix for
        # other callers, so validate the storage contract here before MySQL.
        codes = data['code'].astype(str).str.strip()
        invalid_code_count = int((~codes.str.fullmatch(r'\d{6}')).sum())
        if invalid_code_count:
            logging.warning("个股资金流已过滤非六位代码: rows=%s", invalid_code_count)
        data = data.loc[codes.str.fullmatch(r'\d{6}').fillna(False)]
        data = data.loc[data['code'].apply(is_a_stock)].loc[data['new_price'].apply(is_open_with_line)]
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stocks_fund_flow处理异常：{e}")
    return None


# 读取板块资金流向
def fetch_stocks_sector_fund_flow(index_sector, index_indicator):
    sector_name = tbs.CN_STOCK_SECTOR_FUND_FLOW[0][index_sector]
    cn_flow = tbs.CN_STOCK_SECTOR_FUND_FLOW[1][index_indicator]
    try:
        source = os.environ.get('STOCK_SECTOR_FUND_FLOW_SOURCE', 'ths').strip().lower()
        if source not in {'ths', 'eastmoney', 'auto'}:
            raise ValueError("STOCK_SECTOR_FUND_FLOW_SOURCE 仅支持 ths、eastmoney 或 auto")

        logging.info(
            f"stockfetch.fetch_stocks_sector_fund_flow开始抓取: sector={sector_name}, "
            f"indicator={cn_flow['cn']}, index_sector={index_sector}, index_indicator={index_indicator}, source={source}"
        )

        data = None
        if source in {'eastmoney', 'auto'}:
            try:
                data = sff.stock_sector_fund_flow_rank(indicator=cn_flow['cn'], sector_type=sector_name)
                if data is not None and len(data.index) > 0:
                    data.columns = list(cn_flow['columns'])
            except Exception as exc:
                if source == 'eastmoney':
                    raise
                logging.warning(f"东方财富板块资金流不可用，切换同花顺: {exc}")

        if data is None or len(data.index) == 0:
            if source == 'eastmoney':
                return _load_sector_fund_flow_cache(sector_name, cn_flow['cn'])
            data = ssft.stock_sector_fund_flow_rank_ths(indicator=cn_flow['cn'], sector_type=sector_name)
            logging.info(
                f"stockfetch.fetch_stocks_sector_fund_flow数据源=同花顺: sector={sector_name}, "
                f"indicator={cn_flow['cn']}, rows={len(data.index)}"
            )

        if data is None or len(data.index) == 0:
            logging.warning(
                f"stockfetch.fetch_stocks_sector_fund_flow返回空数据: sector={sector_name}, "
                f"indicator={cn_flow['cn']}"
            )
            return _load_sector_fund_flow_cache(sector_name, cn_flow['cn'])

        logging.info(
            f"stockfetch.fetch_stocks_sector_fund_flow抓取成功: sector={sector_name}, "
            f"indicator={cn_flow['cn']}, rows={len(data.index)}, cols={list(data.columns)}"
        )
        _save_sector_fund_flow_cache(sector_name, cn_flow['cn'], data)
        return data
    except Exception as e:
        logging.exception(
            f"stockfetch.fetch_stocks_sector_fund_flow处理异常: sector={sector_name}, "
            f"index_indicator={index_indicator}, error={e}"
        )
        return _load_sector_fund_flow_cache(sector_name, cn_flow['cn'])


def _sector_fund_flow_cache_file(sector_name, indicator_cn):
    safe_sector = sector_name.replace('/', '_').replace(' ', '_')
    safe_indicator = indicator_cn.replace('/', '_').replace(' ', '_')
    return os.path.join(stock_sector_fund_flow_cache_path, f"{safe_sector}_{safe_indicator}.gzip.pickle")


def _save_sector_fund_flow_cache(sector_name, indicator_cn, data):
    cache_file = _sector_fund_flow_cache_file(sector_name, indicator_cn)
    try:
        data.to_pickle(cache_file, compression="gzip")
        logging.info(f"stockfetch._save_sector_fund_flow_cache已缓存: {cache_file}")
    except Exception as e:
        logging.exception(f"stockfetch._save_sector_fund_flow_cache处理异常: file={cache_file}, error={e}")


def _load_sector_fund_flow_cache(sector_name, indicator_cn):
    cache_file = _sector_fund_flow_cache_file(sector_name, indicator_cn)
    if not os.path.isfile(cache_file):
        logging.warning(f"stockfetch._load_sector_fund_flow_cache未命中缓存: {cache_file}")
        return None
    try:
        data = pd.read_pickle(cache_file, compression="gzip")
        # 调度层据此拒绝将历史快照写为本次交易日的真实数据。
        data.attrs['is_stale_cache'] = True
        logging.warning(f"stockfetch._load_sector_fund_flow_cache命中缓存: {cache_file}, rows={len(data.index)}")
        return data
    except Exception as e:
        logging.exception(f"stockfetch._load_sector_fund_flow_cache处理异常: file={cache_file}, error={e}")
        return None


# 读取股票分红配送
def fetch_stocks_bonus(date):
    try:
        data = sfe.stock_fhps_em(date=trd.get_bonus_report_date())
        if data is None or len(data.index) == 0:
            return None
        if date is None:
            data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
        else:
            data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        data.columns = list(tbs.TABLE_CN_STOCK_BONUS['columns'])
        data = data.loc[data['code'].apply(is_a_stock)]
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stocks_bonus处理异常：{e}")
    return None


# 股票近三月上龙虎榜且必须有2次以上机构参与的
def fetch_stock_top_entity_data(date):
    run_date = date + datetime.timedelta(days=-90)
    start_date = run_date.strftime("%Y%m%d")
    end_date = date.strftime("%Y%m%d")
    code_name = '代码'
    entity_amount_name = '买方机构数'
    try:
        data = sle.stock_lhb_jgmmtj_em(start_date, end_date)
        if data is None or len(data.index) == 0:
            return None

        # 机构买入次数大于1计算方法，首先：每次要有买方机构数(>0),然后：这段时间买方机构数求和大于1
        mask = (data[entity_amount_name] > 0)  # 首先：每次要有买方机构数(>0)
        data = data.loc[mask]

        if len(data.index) == 0:
            return None

        grouped = data.groupby(by=data[code_name])
        data_series = grouped[entity_amount_name].sum()
        data_code = set(data_series[data_series > 1].index.values)  # 然后：这段时间买方机构数求和大于1

        if not data_code:
            return None

        return data_code
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_top_entity_data处理异常：{e}")
    return None

# 描述: 获取东方财富-龙虎榜-个股上榜统计
def fetch_stock_lhb_data(date,count=12):
    try:
        start_date = trd.get_previous_trade_date(date,count).strftime("%Y%m%d")
        end_date = date.strftime("%Y%m%d")

        data = sle.stock_lhb_detail_em(start_date, end_date)
        if data is None or len(data.index) == 0:
            return None
        _columns = list(tbs.TABLE_CN_STOCK_lHB['columns'])
        _columns.pop(0)
        data.columns = _columns
        data = data.loc[data['code'].apply(is_a_stock)]
        data.drop_duplicates('code', keep='last', inplace=True)
        # data = data.sort_values(by='ranking_times', ascending=False)
        if date is None:
            data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
        else:
            data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_lhb_data处理异常：{e}")
    return None

# 描述: 获取新浪财经-龙虎榜-个股上榜统计
def fetch_stock_top_data(date):
    try:
        data = sls.stock_lhb_ggtj_sina()
        if data is None or len(data.index) == 0:
            return None
        _columns = list(tbs.TABLE_CN_STOCK_TOP['columns'])
        _columns.pop(0)
        data.columns = _columns
        data = data.loc[data['code'].apply(is_a_stock)]
        data.drop_duplicates('code', keep='last', inplace=True)
        if date is None:
            data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
        else:
            data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_top_data处理异常：{e}")
    return None


# 描述: 获取东方财富网-数据中心-大宗交易-每日统计
def fetch_stock_blocktrade_data(date):
    date_str = date.strftime("%Y%m%d")
    try:
        data = sde.stock_dzjy_mrtj(start_date=date_str, end_date=date_str)
        if data is None or len(data.index) == 0:
            return None

        columns = list(tbs.TABLE_CN_STOCK_BLOCKTRADE['columns'])
        columns.insert(0, 'index')
        data.columns = columns
        data = data.loc[data['code'].apply(is_a_stock)]
        data.drop('index', axis=1, inplace=True)
        return data
    except TypeError:
        logging.error("处理异常：目前还没有大宗交易数据，请17:00点后再获取！")
        return None
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_blocktrade_data处理异常：{e}")
    return None

# 读取早盘抢筹
def fetch_stock_chip_race_open(date):
    try:
        date_str =""
        if date != datetime.datetime.now().date():
            date_str = date.strftime("%Y%m%d")
        data = scr.stock_chip_race_open(date_str)
        if data is None or len(data.index) == 0:
            return None
        if date is None:
            data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
        else:
            data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        data.columns = list(tbs.TABLE_CN_STOCK_CHIP_RACE_OPEN['columns'])
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_chip_race_open处理异常：{e}")
    return None

# 读取尾盘抢筹
def fetch_stock_chip_race_end(date):
    try:
        date_str =""
        if date != datetime.datetime.now().date():
            date_str = date.strftime("%Y%m%d")
        data = scr.stock_chip_race_end(date_str)
        if data is None or len(data.index) == 0:
            return None
        if date is None:
            data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
        else:
            data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        data.columns = list(tbs.TABLE_CN_STOCK_CHIP_RACE_END['columns'])
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_chip_race_end处理异常：{e}")
    return None

# 读取涨停原因
def fetch_stock_limitup_reason(date):

    try:
        data = slr.stock_limitup_reason(date.strftime("%Y-%m-%d"))
        if data is None or len(data.index) == 0:
            return None
        data.columns = list(tbs.TABLE_CN_STOCK_LIMITUP_REASON['columns'])
        requested_date = date.strftime("%Y-%m-%d")
        returned_dates = data['date'].astype(str).str[:10]
        if not returned_dates.eq(requested_date).all():
            logging.warning(
                "涨停原因上游日期不匹配，拒绝写入: requested=%s returned=%s",
                requested_date,
                sorted(returned_dates.dropna().unique().tolist()),
            )
            return None
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_limitup_reason处理异常：{e}")
    return None

# 读取股票历史数据
def fetch_etf_hist(data_base, date_start=None, date_end=None, adjust='qfq'):
    date = data_base[0]
    code = data_base[1]

    if date_start is None:
        date_start, is_cache = trd.get_trade_hist_interval(date)  # 提高运行效率，只运行一次
    try:
        if date_end is not None:
            data = fee.fund_etf_hist_em(symbol=code, period="daily", start_date=date_start, end_date=date_end,
                                        adjust=adjust)
        else:
            data = fee.fund_etf_hist_em(symbol=code, period="daily", start_date=date_start, adjust=adjust)

        if data is None or len(data.index) == 0:
            return None
        data.columns = tuple(tbs.CN_STOCK_HIST_DATA['columns'])
        data = data.sort_index()  # 将数据按照日期排序下。
        if data is not None:
            data.loc[:, 'p_change'] = tl.ROC(data['close'].values, 1)
            data['p_change'].values[np.isnan(data['p_change'].values)] = 0.0
            data["volume"] = data['volume'].values.astype('double') * 100  # 成交量单位从手变成股。
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_etf_hist处理异常：{e}")
    return None


# 读取股票历史数据
def fetch_stock_hist(data_base, date_start=None, is_cache=True):
    date = data_base[0]
    code = data_base[1]

    if date_start is None:
        date_start, is_cache = trd.get_trade_hist_interval(date)  # 提高运行效率，只运行一次
        # date_end = date_end.strftime("%Y%m%d")
    try:
        data = stock_hist_cache(code, date_start, None, is_cache, 'qfq')
        if data is not None:
            # 指标计算会读取 data['code']；历史源本身只返回 OHLCV，统一在
            # 入口补齐，保证 EastMoney/Tencent 两条链路的下游合同一致。
            data = data.copy()
            data['code'] = str(code).zfill(6)
            data.loc[:, 'p_change'] = tl.ROC(data['close'].values, 1)
            data['p_change'].values[np.isnan(data['p_change'].values)] = 0.0
            data["volume"] = data['volume'].values.astype('double') * 100  # 成交量单位从手变成股。
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_hist处理异常：{e}")
    return None


# 增加读取股票缓存方法。加快处理速度。多线程解决效率
def stock_hist_cache(code, date_start, date_end=None, is_cache=True, adjust=''):
    cache_dir = os.path.join(stock_hist_cache_path, date_start[0:6], date_start)
    # 如果没有文件夹创建一个。月文件夹和日文件夹。方便删除。
    try:
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
    except Exception:
        pass
    market_source = os.getenv("STOCK_MARKET_DATA_SOURCE", "tencent").strip().lower()
    # 不复用来源不明的旧缓存；否则腾讯恢复后仍可能把东财旧数据当作本轮输入。
    cache_file = os.path.join(cache_dir, "%s_%s%s.gzip.pickle" % (code, market_source, adjust))
    # 如果缓存存在就直接返回缓存数据。压缩方式。
    try:
        if os.path.isfile(cache_file):
            return pd.read_pickle(cache_file, compression="gzip")
        else:
            if market_source == "eastmoney":
                if date_end is not None:
                    stock = she.stock_zh_a_hist(symbol=code, period="daily", start_date=date_start, end_date=date_end,
                                                adjust=adjust)
                else:
                    stock = she.stock_zh_a_hist(symbol=code, period="daily", start_date=date_start, adjust=adjust)
            else:
                stock = sht.stock_zh_a_hist_tx(
                    symbol=code,
                    start_date=date_start,
                    end_date=date_end or datetime.datetime.now().strftime("%Y%m%d"),
                    adjust=adjust,
                )

            if stock is None or len(stock.index) == 0:
                return None
            stock.columns = tuple(tbs.CN_STOCK_HIST_DATA['columns'])
            stock = stock.sort_index()  # 将数据按照日期排序下。
            try:
                if is_cache:
                    stock.to_pickle(cache_file, compression="gzip")
            except Exception:
                pass
            # time.sleep(1)
            return stock
    except Exception as e:
        logging.error(f"stockfetch.stock_hist_cache处理异常：{code}代码{e}")
    return None
