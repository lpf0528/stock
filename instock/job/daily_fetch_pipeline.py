#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run and verify Stock's daily data fetches as independently retryable items.

Legacy jobs log and swallow many provider exceptions.  This module turns each
fetch into an explicit terminal result by checking the target-date rows after
the fetch has returned.  Its JSON receipt is the contract consumed by the
cross-project console; a ``--only-failed`` run never replays successful items.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPT_PATH = PROJECT_ROOT / "runtime" / "job_receipts" / "daily_fetch_latest.json"


@dataclass(frozen=True)
class FetchJob:
    id: str
    name: str
    table_name: str
    runner: Callable[[dt.date], None]


def _jobs() -> list[FetchJob]:
    # Imports remain lazy so that ``--help`` and receipt inspection do not
    # attempt a database connection.
    from instock.job import basic_data_after_close_daily_job as after_close
    from instock.job import basic_data_daily_job as basic
    from instock.job import basic_data_other_daily_job as other
    from instock.job import selection_data_daily_job as selection

    return [
        FetchJob("stock-spot", "股票行情", "cn_stock_spot", lambda date: basic.save_nph_stock_spot_data(date, False)),
        FetchJob("stock-selection", "综合选股", "cn_stock_selection", lambda date: selection.save_nph_stock_selection_data(date, False)),
        FetchJob("stock-lhb", "龙虎榜", "cn_stock_lhb", lambda date: other.save_nph_stock_lhb_data(date, False)),
        FetchJob("stock-fund-flow", "个股资金流", "cn_stock_fund_flow", lambda date: other.save_nph_stock_fund_flow_data(date, False)),
        FetchJob("industry-fund-flow", "行业资金流", "cn_stock_fund_flow_industry", lambda date: other.stock_sector_fund_flow_data(date, 0)),
        FetchJob("concept-fund-flow", "概念资金流", "cn_stock_fund_flow_concept", lambda date: other.stock_sector_fund_flow_data(date, 1)),
        FetchJob("stock-bonus", "分红配送", "cn_stock_bonus", lambda date: other.save_nph_stock_bonus(date, False)),
        FetchJob("chip-race-open", "早盘抢筹", "cn_stock_chip_race_open", other.stock_chip_race_open_data),
        FetchJob("limitup-reason", "涨停原因", "cn_stock_limitup_reason", other.stock_imitup_reason_data),
        FetchJob("stock-blocktrade", "大宗交易", "cn_stock_blocktrade", after_close.save_after_close_stock_blocktrade_data),
        FetchJob("chip-race-end", "尾盘抢筹", "cn_stock_chip_race_end", after_close.save_after_close_stock_chip_race_end_data),
    ]


def write_receipt(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def read_receipt(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"无法读取抓取回执 {path}: {exc}") from exc


def count_rows(table_name: str, date: dt.date) -> int:
    from instock.lib import database as mdb

    if not mdb.checkTableIsExist(table_name):
        return 0
    return mdb.executeSqlCount(f"SELECT COUNT(*) FROM `{table_name}` WHERE `date` = %s", (date.isoformat(),))


def default_date() -> dt.date:
    from instock.lib import trade_time as trade

    _, latest = trade.get_trade_date_last()
    return latest


def failed_job_ids(receipt: dict, date: dt.date) -> set[str]:
    if receipt.get("trading_date") != date.isoformat():
        raise RuntimeError("上次抓取回执的交易日与本次不一致；拒绝跨日期重试")
    return {item["id"] for item in receipt.get("items", []) if item.get("status") == "failed"}


def resolve_job_ids(selectors: Iterable[str], jobs: Iterable[FetchJob]) -> set[str]:
    """Resolve CLI selectors from a stable job id, table name, or display name."""
    by_selector: dict[str, str] = {}
    for job in jobs:
        for selector in (job.id, job.table_name, job.name):
            previous = by_selector.setdefault(selector, job.id)
            if previous != job.id:
                raise RuntimeError(f"抓取项选择器不唯一: {selector}")
    unknown = sorted(set(selectors) - set(by_selector))
    if unknown:
        raise RuntimeError(f"未知抓取项: {', '.join(unknown)}")
    return {by_selector[selector] for selector in selectors}


def run_fetches(
    *,
    date: dt.date,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    jobs: Iterable[FetchJob] | None = None,
    selected_ids: set[str] | None = None,
    initialize: Callable[[], None] | None = None,
    row_counter: Callable[[str, dt.date], int] = count_rows,
) -> dict:
    selected_jobs = [job for job in (list(jobs) if jobs is not None else _jobs()) if selected_ids is None or job.id in selected_ids]
    if selected_ids is not None:
        unknown = selected_ids - {job.id for job in selected_jobs}
        if unknown:
            raise RuntimeError(f"未知抓取项: {', '.join(sorted(unknown))}")

    started_at = dt.datetime.now().astimezone()
    payload: dict = {
        "schema_version": "1.0",
        "job": "daily_fetch_pipeline",
        "trading_date": date.isoformat(),
        "started_at": started_at.isoformat(),
        "finished_at": None,
        "status": "failed",
        "retry_mode": selected_ids is not None,
        "items": [],
    }
    try:
        if initialize is None:
            from instock.job import init_job
            initialize = init_job.main
        initialize()
        for job in selected_jobs:
            item = {"id": job.id, "name": job.name, "table_name": job.table_name, "status": "failed", "attempts": 1,
                    "started_at": dt.datetime.now().astimezone().isoformat(), "finished_at": None, "row_count": 0,
                    "error": None}
            try:
                job.runner(date)
                item["row_count"] = row_counter(job.table_name, date)
                if item["row_count"] > 0:
                    item["status"] = "completed"
                else:
                    item["error"] = f"抓取返回后未验收到 {date.isoformat()} 的 {job.table_name} 数据"
            except Exception as exc:
                item["error"] = str(exc)
                item["traceback"] = traceback.format_exc(limit=5)
            finally:
                item["finished_at"] = dt.datetime.now().astimezone().isoformat()
                payload["items"].append(item)
        # A retry with no failed items is a successful no-op, not a new failure.
        payload["status"] = "completed" if all(item["status"] == "completed" for item in payload["items"]) else "partial_failed"
    except Exception as exc:
        payload["error"] = f"抓取初始化失败: {exc}"
    finally:
        payload["finished_at"] = dt.datetime.now().astimezone().isoformat()
        write_receipt(receipt_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="独立执行并验收 stock 每日抓取项")
    parser.add_argument("--date", type=dt.date.fromisoformat, help="交易日 YYYY-MM-DD；默认最近交易日")
    parser.add_argument("--only-failed", action="store_true", help="仅重试同一交易日的上次失败项")
    parser.add_argument("--task", action="append", metavar="ID_OR_TABLE", help="仅运行指定抓取项；可重复，接受任务 ID、表名或中文名称")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH, help="抓取回执路径")
    args = parser.parse_args()
    date = args.date or default_date()
    if args.only_failed and args.task:
        parser.error("--only-failed 与 --task 不能同时使用")
    jobs = _jobs()
    selected_ids = failed_job_ids(read_receipt(args.receipt), date) if args.only_failed else None
    if args.task:
        selected_ids = resolve_job_ids(args.task, jobs)
    payload = run_fetches(date=date, receipt_path=args.receipt, jobs=jobs, selected_ids=selected_ids)
    print(f"抓取状态：{payload['status']}；回执：{args.receipt}")
    return 0 if payload["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
