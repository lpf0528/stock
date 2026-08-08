# InStock Agent 运行上下文

开始任何数据分析、任务排障或功能评估前，必须先阅读：

- [`docs/database_capability_context.md`](docs/database_capability_context.md)

该文件基于实际 MySQL 数据库快照，记录当前存在的表、数据新鲜度、可用功能，以及因东方财富 `push2` 接口不可用而受阻的功能。

工作规则：

1. 不要仅依据 `tablestructure.py` 或代码声明推断某功能可用；先检查共享快照，必要时重新查询数据库。
2. 数据分析优先使用快照中标记为“已有数据”的表。
3. 涉及实时股票池、每日行情、指标、策略、回测或 K 线形态时，先确认对应表已创建且有最新交易日数据。
4. 任何补数、初始化建表或数据源修复完成后，更新 `docs/database_capability_context.md` 的表清单、行数、最新日期与结论。
5. `.agents/AGENTS.md` 包含长期项目架构说明；本文件与数据库快照优先描述当前运行状态。
