from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instock.job.daily_fetch_pipeline import FetchJob, failed_job_ids, run_fetches


def test_receipt_marks_only_verified_items_completed(tmp_path: Path) -> None:
    calls: list[str] = []
    jobs = [
        FetchJob("ok", "成功项", "table_ok", lambda _date: calls.append("ok")),
        FetchJob("empty", "空项", "table_empty", lambda _date: calls.append("empty")),
    ]

    payload = run_fetches(
        date=date(2026, 8, 12), receipt_path=tmp_path / "receipt.json", jobs=jobs,
        initialize=lambda: calls.append("init"), row_counter=lambda table, _date: 3 if table == "table_ok" else 0,
    )

    assert calls == ["init", "ok", "empty"]
    assert payload["status"] == "partial_failed"
    assert [item["status"] for item in payload["items"]] == ["completed", "failed"]
    saved = json.loads((tmp_path / "receipt.json").read_text(encoding="utf-8"))
    assert saved["items"][1]["error"].startswith("抓取返回后未验收")


def test_retry_selection_uses_only_the_previous_failures(tmp_path: Path) -> None:
    prior = {"trading_date": "2026-08-12", "items": [{"id": "ok", "status": "completed"}, {"id": "retry", "status": "failed"}]}
    assert failed_job_ids(prior, date(2026, 8, 12)) == {"retry"}
    calls: list[str] = []
    jobs = [FetchJob("ok", "成功项", "ok_table", lambda _date: calls.append("ok")), FetchJob("retry", "失败项", "retry_table", lambda _date: calls.append("retry"))]
    payload = run_fetches(date=date(2026, 8, 12), receipt_path=tmp_path / "retry.json", jobs=jobs, selected_ids={"retry"}, initialize=lambda: None, row_counter=lambda _table, _date: 1)

    assert calls == ["retry"]
    assert payload["retry_mode"] is True
    assert payload["status"] == "completed"


def test_empty_retry_is_a_successful_no_op(tmp_path: Path) -> None:
    payload = run_fetches(
        date=date(2026, 8, 12), receipt_path=tmp_path / "empty.json", jobs=[], selected_ids=set(),
        initialize=lambda: None,
    )

    assert payload["items"] == []
    assert payload["status"] == "completed"
