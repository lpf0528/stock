# 每日作业回执

`cron/cron.workdayly/run_workdayly` 现在调用 `instock/job/run_daily_pipeline_with_receipt.py`。该包装器按以下顺序执行：

1. 原有 `execute_daily_job.py`；
2. 原有 `strategy_data_daily_job.py`，在当前环境缺少 `cn_stock_spot` 时会生成降级策略观察名单；
3. 校验本次新生成的 `stock_strategy_selection_analysis_YYYY-MM-DD.md` 是否包含数据交易日；
4. 原子写入 `runtime/job_receipts/latest.json`。

回执无论成功或失败都会写入，字段契约如下：

```json
{
  "schema_version": "1.0",
  "job": "daily_pipeline_with_receipt",
  "trading_date": "2026-08-12",
  "started_at": "2026-08-12T17:30:00+08:00",
  "finished_at": "2026-08-12T17:42:16+08:00",
  "status": "completed",
  "exit_code": 0,
  "strategy_report_path": "/data/stock_strategy_selection_analysis_2026-08-12.md"
}
```

只有当两个命令均成功返回，且策略报告是本次作业生成并含有交易日时，`status` 才为 `completed`。失败回执额外包含 `error`，控制台应据此阻断跨项目分析。回执内容属于运行产物，不提交 Git。

现有子作业可能记录错误后继续返回；因此回执不只依赖进程退出码，还以新鲜、可解析的策略报告作为候选池就绪证据。它不代表所有东方财富数据源均已恢复，也不构成自动交易信号。
