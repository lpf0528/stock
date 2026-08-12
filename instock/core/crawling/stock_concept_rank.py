#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""概念/题材实时排行。

同花顺题材排行与东方财富概念排行的口径不同。默认使用同花顺的公开
题材排行页，避免把 ``AkShare`` 包装的 EastMoney 接口误当成独立数据源。
东方财富仅作为显式指定的备用源，且仍可能受 ``push2`` 风控影响。
"""

from __future__ import annotations

from io import StringIO
from typing import Literal

import pandas as pd
import requests
from bs4 import BeautifulSoup
import json


THS_RANK_URL = (
    "https://q.10jqka.com.cn/gn/index/field/199112/order/desc/page/{page}/ajax/1/"
)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"
)


def _direct_session() -> requests.Session:
    """返回带同花顺动态 Cookie 且不继承系统代理的会话。"""
    # 同花顺排行 Ajax 页要求 ``v`` Cookie。AkShare 已维护其生成脚本；这里
    # 只复用该公开数据源的会话准备逻辑，不调用其 EastMoney 概念排行。
    from akshare.stock_feature.stock_board_concept_ths import _get_file_content_ths
    import py_mini_racer

    javascript = py_mini_racer.MiniRacer()
    javascript.eval(_get_file_content_ths("ths.js"))
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": USER_AGENT, "Referer": "https://q.10jqka.com.cn/gn/"})
    session.cookies.set("v", javascript.call("v"), domain="q.10jqka.com.cn")
    return session


def _find_rank_table(html: str) -> pd.DataFrame:
    """从同花顺 Ajax HTML 中定位概念排行数据。"""
    soup = BeautifulSoup(html, "lxml")
    section = soup.find("input", attrs={"id": "gnSection"})
    if section and section.get("value"):
        # 页面表格只作为骨架；完整实时排行在这个隐藏 JSON 中。
        source = json.loads(section["value"])
        result = pd.DataFrame(
            [
                {
                    "题材": item.get("platename"),
                    "题材代码": item.get("platecode"),
                    "涨跌幅": item.get("199112"),
                    "主力净流入": item.get("zjjlr"),
                    "成分股数量": item.get("zfl"),
                }
                for item in source.values()
            ]
        )
        result["涨跌幅"] = pd.to_numeric(result["涨跌幅"], errors="coerce")
        result["主力净流入"] = pd.to_numeric(result["主力净流入"], errors="coerce")
        result["成分股数量"] = pd.to_numeric(result["成分股数量"], errors="coerce")
        result = result.dropna(subset=["题材", "涨跌幅"]).sort_values(
            "涨跌幅", ascending=False, kind="stable"
        )
        result.insert(0, "排名", range(1, len(result) + 1))
        return result.reset_index(drop=True)

    tables = pd.read_html(StringIO(html))
    for table in tables:
        columns = {str(column).strip() for column in table.columns}
        if "概念" in columns or "板块" in columns:
            return table
    raise ValueError("同花顺响应中未找到概念/题材排行表")


def stock_concept_theme_rank_ths(
    pages: int = 1, timeout: int = 10, session: requests.Session | None = None
) -> pd.DataFrame:
    """获取同花顺概念/题材涨跌幅排行。

    每个响应含完整题材列表；``pages`` 仅为兼容同花顺分页页面并在后续页面
    可用时继续合并。返回字段保持上游中文列名，并新增 ``数据源``，便于同
    EastMoney 的概念资金流区分。
    """
    if pages < 1:
        raise ValueError("pages 必须大于 0")

    request_session = session or _direct_session()
    frames: list[pd.DataFrame] = []
    for page in range(1, pages + 1):
        response = request_session.get(THS_RANK_URL.format(page=page), timeout=timeout)
        response.raise_for_status()
        frame = _find_rank_table(response.text)
        if frame.empty:
            break
        frames.append(frame)

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    result.columns = [str(column).strip() for column in result.columns]
    if "题材" in result.columns and "涨跌幅" in result.columns:
        result = result.drop_duplicates(subset=["题材"], keep="first").sort_values(
            "涨跌幅", ascending=False, kind="stable"
        )
        result["排名"] = range(1, len(result) + 1)
        result["数据源"] = "同花顺题材排行"
        return result.reset_index(drop=True)
    rank_column = "序号" if "序号" in result.columns else result.columns[0]
    result[rank_column] = pd.to_numeric(result[rank_column], errors="coerce")
    result = result.dropna(subset=[rank_column]).copy()
    result[rank_column] = result[rank_column].astype(int)
    for column in ("涨跌幅", "换手率", "领涨股涨跌幅"):
        if column in result.columns:
            result[column] = pd.to_numeric(
                result[column].astype(str).str.rstrip("%"), errors="coerce"
            )
    result["数据源"] = "同花顺题材排行"
    return result.reset_index(drop=True)


def stock_concept_theme_rank(
    source: Literal["ths", "eastmoney"] = "ths", **kwargs
) -> pd.DataFrame:
    """获取概念/题材排行；默认同花顺，EastMoney 需显式指定。"""
    if source == "ths":
        return stock_concept_theme_rank_ths(**kwargs)
    if source == "eastmoney":
        # 延迟导入，使同花顺抓取不会因可选依赖或东财链路而受影响。
        import akshare as ak

        result = ak.stock_board_concept_name_em()
        result["数据源"] = "东方财富概念排行（AkShare）"
        return result
    raise ValueError("source 只支持 'ths' 或 'eastmoney'")


if __name__ == "__main__":
    print(stock_concept_theme_rank_ths().to_string(index=False))
