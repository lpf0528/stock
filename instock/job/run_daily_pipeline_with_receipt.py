#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run Stock's daily pipeline and atomically publish an auditable completion receipt.

This is the workday scheduler entry point for cross-project orchestration.  It
does not alter data collection behaviour: it executes the existing daily job,
then the existing strategy job.  A receipt is marked completed only when a
fresh, date-bearing strategy report was produced by this invocation.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RECEIPT_PATH = PROJECT_ROOT / "runtime" / "job_receipts" / "latest.json"
FETCH_RECEIPT_PATH = PROJECT_ROOT / "runtime" / "job_receipts" / "daily_fetch_latest.json"
REPORT_PATTERN = re.compile(r"数据交易日：\s*(\d{4}-\d{2}-\d{2})")


def now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def write_receipt(receipt_path: Path, payload: dict) -> None:
    """Publish either terminal outcome atomically so readers never see partial JSON."""
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, receipt_path)


def expected_report_path(trading_date: str) -> Path:
    return PROJECT_ROOT.parent / f"stock_strategy_selection_analysis_{trading_date}.md"


def validate_report(report_path: Path, started_at: dt.datetime) -> str:
    if not report_path.is_file():
        raise RuntimeError(f"未生成策略报告：{report_path}")
    modified_at = dt.datetime.fromtimestamp(report_path.stat().st_mtime, tz=started_at.tzinfo)
    if modified_at < started_at - dt.timedelta(seconds=1):
        raise RuntimeError(f"策略报告不是本次作业新生成：{report_path}")
    content = report_path.read_text(encoding="utf-8")
    matched = REPORT_PATTERN.search(content)
    if not matched:
        raise RuntimeError(f"策略报告缺少数据交易日：{report_path}")
    return matched.group(1)


def run_command(command: list[str]) -> None:
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def run_pipeline(
    *,
    receipt_path: Path = RECEIPT_PATH,
    command_runner: Callable[[list[str]], None] = run_command,
    started_at: dt.datetime | None = None,
) -> dict:
    """Run existing jobs and return the terminal receipt payload for tests and CLI."""
    started_at = started_at or now()
    payload: dict = {
        "schema_version": "1.0",
        "job": "daily_pipeline_with_receipt",
        "trading_date": None,
        "started_at": started_at.isoformat(),
        "finished_at": None,
        "status": "failed",
        "exit_code": 1,
        "strategy_report_path": None,
        "fetch_receipt_path": None,
    }
    try:
        command_runner([sys.executable, "instock/job/execute_daily_job.py"])
        # execute_daily_job writes the per-fetch terminal evidence.  Preserve
        # compatibility with injected test runners, while a real invocation
        # must not advance to strategy generation after partial collection.
        if FETCH_RECEIPT_PATH.is_file():
            fetch_receipt = json.loads(FETCH_RECEIPT_PATH.read_text(encoding="utf-8"))
            payload["fetch_receipt_path"] = str(FETCH_RECEIPT_PATH)
            if fetch_receipt.get("status") != "completed":
                failed = [item.get("id", "unknown") for item in fetch_receipt.get("items", []) if item.get("status") == "failed"]
                raise RuntimeError(f"每日抓取未全部验收成功，失败项：{', '.join(failed) or '未提供明细'}")
        command_runner([sys.executable, "instock/job/strategy_data_daily_job.py"])

        # The fallback strategy selects the database's latest available date.
        # Locate only reports made by this invocation and validate its declared date.
        reports = sorted(PROJECT_ROOT.parent.glob("stock_strategy_selection_analysis_*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
        if not reports:
            raise RuntimeError("未找到策略报告")
        trading_date = validate_report(reports[0], started_at)
        payload.update({"trading_date": trading_date, "strategy_report_path": str(reports[0]), "status": "completed", "exit_code": 0})
    except Exception as exc:
        logging.exception("daily pipeline failed before receipt validation")
        payload["error"] = str(exc)
    finally:
        payload["finished_at"] = now().isoformat()
        write_receipt(receipt_path, payload)
    return payload


def main() -> int:
    payload = run_pipeline()
    logging.info("daily_pipeline_with_receipt terminal status=%s receipt=%s", payload["status"], RECEIPT_PATH)
    return int(payload["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
