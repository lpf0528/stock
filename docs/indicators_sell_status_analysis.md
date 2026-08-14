# 股票指标卖出数据（cn_stock_indicators_sell）无数据分析与状态说明

## 1. 现象描述

用户访问 Web 控制台页面：
`http://localhost:9988/instock/data?table_name=cn_stock_indicators_sell`
页面呈现空表格，后台接口 `/instock/api_data?name=cn_stock_indicators_sell&date=2026-08-14` 正常返回空数组 `[]`。

---

## 2. 结论

**该现象属于量化筛选的正常结果，并非程序故障、数据源缺失或系统异常。**

- 当前交易日（2026-08-14）全市场已完成技术指标计算的 **3,208 只个股**中，**0 只股票同时满足指标卖出策略的 8 重极度超卖筛选条件**。
- 系统设计为：当无符合条件的个股时，每日任务不向数据库写入空记录，Web 端优雅返回空列表 `[]`。

---

## 3. 策略算法与筛选逻辑

指标卖出策略定义于 [`instock/job/indicators_data_daily_job.py`](file:///Users/liupengfei/workplace/github_project/stock/instock/job/indicators_data_daily_job.py#L143-L175) 中的 `guess_sell(date)` 函数。

其核心筛选 SQL 为：

```sql
SELECT `code`, `name`, `date` 
FROM `cn_stock_indicators` 
WHERE `date` = '{date}'
  AND `kdjk` < 20 
  AND `kdjd` < 30 
  AND `kdjj` < 10 
  AND `rsi_6` < 20 
  AND `cci` < -100 
  AND `cr` < 40 
  AND `wr_6` < -80 
  AND `vr` < 40;
```

该策略要求个股在同一交易日**同时命中以下全部 8 项极度超卖/弱势指标**：

1. **KDJ - K值**：`kdjk < 20`（处于严重超卖区）
2. **KDJ - D值**：`kdjd < 30`（处于超卖区）
3. **KDJ - J值**：`kdjj < 10`（极度超卖，钝化区）
4. **RSI**：`rsi_6 < 20`（6日相对强弱指标极度超卖）
5. **CCI**：`cci < -100`（顺势指标进入常态弱势/超卖区）
6. **CR**：`cr < 40`（带状能量指标极度萎缩）
7. **WR**：`wr_6 < -80`（6日威廉指标进入超卖区）
8. **VR**：`vr < 40`（成交量变异率处于极度低迷区）

---

## 4. 2026-08-14 市场指标实际分布实测

对 `instockdb` 数据库中最新交易日（2026-08-14）的 **3,208 只股票**指标数据进行单项条件统计：

| 筛选条件 | 满足股票数 | 占比 | 条件说明 |
| :--- | :---: | :---: | :--- |
| `kdjk < 20` | 267 | 8.32% | K值超卖 |
| `kdjd < 30` | 233 | 7.26% | D值超卖 |
| `kdjj < 10` | 678 | 21.13% | J值超卖 |
| `rsi_6 < 20` | 12 | 0.37% | RSI 严重超卖（较少见） |
| `cci < -100` | 405 | 12.62% | CCI 超卖 |
| `cr < 40` | 89 | 2.77% | CR 能量极低 |
| `wr_6 < -80` | 780 | 24.31% | WR 超卖 |
| `vr < 40` | 3 | 0.09% | VR 成交量极度低迷（极罕见） |
| **8 项条件全部同时满足 (AND)** | **0** | **0.00%** | **交集为 0 只** |

> 注：满足 `vr < 40` 的仅 3 只，满足 `rsi_6 < 20` 的仅 12 只，二者与其他 6 个指标求交集后无任何股票符合全部 8 项极端条件。

---

## 5. 对照验证：指标买入策略（`cn_stock_indicators_buy`）

作为对照，指标买入策略 `guess_buy(date)` 采用 8 重超买条件（`kdjk >= 80 and kdjd >= 70 and kdjj >= 100 and rsi_6 >= 80 and cci >= 100 and cr >= 300 and wr_6 >= -20 and vr >= 160`）：

- **计算结果**：2026-08-14 筛选出 **1 只股票**（603848 爱丽家居）命中全部 8 项超买指标；
- **入库状态**：数据表 `cn_stock_indicators_buy` 已成功创建并写入 1 条记录，Web 页面正常展示。

---

## 6. 系统运行机制说明

1. **Job 写入逻辑**：
   在 [`indicators_data_daily_job.py:L157-158`](file:///Users/liupengfei/workplace/github_project/stock/instock/job/indicators_data_daily_job.py#L157-L158) 中，如果筛选结果数据行数为 0（`len(data.index) == 0`），函数直接退出，不创建空表或写入空数据。
2. **Web 安全容错**：
   在 [`dataTableHandler.py:L80-82`](file:///Users/liupengfei/workplace/github_project/stock/instock/web/dataTableHandler.py#L80-L82) 中，当对应表不存在或无记录时，API 拦截并返回 `[]`，确保前端 SpreadJS 渲染空状态而不发生 500 报错。
