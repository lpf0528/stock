from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "instock" / "job" / "run_daily_pipeline_with_receipt.py"
SPEC = importlib.util.spec_from_file_location("daily_pipeline_receipt", MODULE_PATH)
receipt_job = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(receipt_job)


def test_success_receipt_requires_a_fresh_date_bearing_report(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "stock"
    project_root.mkdir()
    monkeypatch.setattr(receipt_job, "PROJECT_ROOT", project_root)
    receipt_path = tmp_path / "runtime" / "latest.json"
    calls: list[list[str]] = []

    def runner(command: list[str]) -> None:
        calls.append(command)
        if command[-1].endswith("strategy_data_daily_job.py"):
            (tmp_path / "stock_strategy_selection_analysis_2026-08-12.md").write_text("# report\n\n数据交易日：2026-08-12\n", encoding="utf-8")

    result = receipt_job.run_pipeline(receipt_path=receipt_path, command_runner=runner, started_at=datetime.now().astimezone())

    assert len(calls) == 2
    assert result["status"] == "completed"
    assert result["exit_code"] == 0
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["trading_date"] == "2026-08-12"


def test_failure_receipt_is_published_when_a_command_fails(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "stock"
    project_root.mkdir()
    monkeypatch.setattr(receipt_job, "PROJECT_ROOT", project_root)
    receipt_path = tmp_path / "runtime" / "latest.json"

    def runner(_command: list[str]) -> None:
        raise RuntimeError("data source unavailable")

    result = receipt_job.run_pipeline(receipt_path=receipt_path, command_runner=runner, started_at=datetime.now().astimezone())

    assert result["status"] == "failed"
    saved = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert saved["exit_code"] == 1
    assert "data source unavailable" in saved["error"]
