# 本地 Docker 快速启动指令

```bash
# 启动 colima (如果使用 colima)
colima start

# 创建并启动 MariaDB 数据库容器
docker run -d \
  --name instockdb \
  -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=root \
  mariadb:latest
```

---

# InStock 项目分析、脚本执行指导与高效使用指南

## 一、 项目架构与数据流分析

InStock 是一套集 **数据抓取 ➔ 因子指标计算 ➔ 筹码/形态识别 ➔ 策略选股 ➔ 胜率回测 ➔ Web可视化与自动化交易** 于一体的完整 A 股/ETF 量化系统。其核心架构与数据流如下：

```
[东方财富/新浪 API]
       │ (crawling / fetcher)
       ▼
 [ 1. 基础行情与扩展数据 ] ──> (basic_data_daily_job.py / selection_data_daily_job.py)
       │
       ▼
 [ 2. 技术指标与筹码 CYQ ] ──> (indicators_data_daily_job.py / cyq.py / TA-Lib 30+指标)
       │
       ▼
 [ 3. K线形态 & 11种策略选股 ] ──> (klinepattern_data_daily_job.py / strategy_data_daily_job.py)
       │
       ▼
 [ 4. 1~20日胜率统计回测 ] ──> (backtest_data_daily_job.py / rate_stats.py)
       │
       ▼
[ Web 交互控制台 (Tornado:9988) ]  &  [ EasyTrader 自动化交易 / 自动打新 ]
```

---

## 二、 脚本执行意见与优化建议

在实际执行 Job 脚本时，请重点注意以下几点：

### 1. 严格遵循 Job 依赖顺序
在 `instock/job/execute_daily_job.py` 中，各计算任务存在强依赖关系：
- **正确逻辑顺序**：`数据库初始化` ➔ `基础数据/综合选股数据` ➔ `指标计算` ➔ `K线形态` ➔ `策略计算` ➔ `胜率回测` ➔ `闭盘后数据`。
- **诊断意见**：检查 `execute_daily_job.py` 中是否注释掉了部分子任务（如 `gdj.main()` / `sdj.main()` / `bdj.main()`）。必须确保指标和策略计算在基础数据就绪后顺序执行，否则策略选股会因缺失最新指标而出错。

### 2. 巧妙运用批量与历史补数功能
项目内置了强大的历史区间补数机制（在 `instock/lib/run_template.py` 中实现）：
```bash
# 1. 跑指定单日任务
python instock/job/execute_daily_job.py 2024-06-01

# 2. 跑多日任务（逗号分隔）
python instock/job/execute_daily_job.py 2024-06-01,2024-06-02

# 3. 跑历史区间任务（补全过去半年的回测数据）
python instock/job/execute_daily_job.py 2024-01-01 2024-06-30
```

### 3. 执行时间节点建议
- **最佳盘后执行时间**：交易日 **16:30 ~ 17:00**（东方财富/新浪的收盘大宗交易、龙虎榜及完整成交数据通常在 16:30 前后全部结算更新完毕）。
- **自动化定时任务**：结合 Docker / Supervisor，将 `cron/cron.workdayly/run_workdayly` 设为每个交易日 16:30 自动触发。

### 4. 规避反爬与接口限流
- 频繁批量抓取数据容易触发东方财富的反爬机制（HTTP 429 或返回空值）。
- **优化方案**：
  - 在 `instock/config/proxy.txt` 中配置有效的代理 IP 池。
  - 在 `instock/core/eastmoney_fetcher.py` 抓取函数中确保有重试机制与适度的延迟。

---

## 三、 如何才能更好地充分使用这个项目？

为了让系统真正转化为辅助量化决策与交易的利器，建议按以下路线充分挖掘项目潜力：

### 路线 1：建立“策略胜率”导向的动态选股机制
- **不要迷信单一策略**：项目内置了 11 种策略（如放量突破、多头排列、海龟交易等）。
- **充分利用回测**：在 Web UI（端口 9988）中观察“策略胜率”面板。
  - 关注**近 60/120 个交易日胜率 > 60% 且 3日/5日平均收益显著为正**的策略。
  - 大盘处于不同阶段（牛市、熊市、震荡市）时，策略胜率会剧烈波动。依据当前行情环境，动态切到高胜率策略。

### 路线 2：深度结合 CYQ 筹码分布 + Bokeh K线图进行人工复核
- 策略筛选出股票后，进入 Web 控制台点击具体股票：
  - 查看 **CYQ 筹码成本分布**（获利盘比例、筹码密集峰位置）。
  - **最佳入场形态**：策略触发 + 股价刚突破下方筹码密集峰（上方无套牢盘压力）。

### 路线 3：二次开发与自定义选股策略
默认策略只是起点，你可以非常方便地扩展自己的因子策略：
1. **添加策略算法**：在 `instock/core/strategy/` 目录下新增策略文件（如 `my_strategy.py`）。
2. **注册表结构**：在 `instock/core/tablestructure.py` 中增加表定义。
3. **集成到 Job**：在 `instock/job/strategy_data_daily_job.py` 中增加策略调度。

### 路线 4：联动 EasyTrader 实现自动打新与低成本实盘
- 项目 `instock/trade/` 整合了 EasyTrader。
- **无风险/低风险收益**：配置 `trade_client.json` 开启每日自动申购新股与可转债（自动打新）。
- **条件单自动化**：选股策略盘后出结果后，可进一步编写脚本将高胜率标的自动推送至交易客户端下条件单。

### 路线 5：工程化与部署最佳实践
- 推荐使用 Docker + MariaDB 部署数据库，设置合适的 `innodb_buffer_pool_size`（如 2G/4G）以保障大数据量下的指标计算速度。
- 开启日志监控（`log/stock_execute_job.log`），及时发现接口变动或网络异常。

---

## 四、 快速启动与验证清单

```bash
# 1. 启动数据库容器
docker run -d --name instockdb -p 3306:3306 -e MYSQL_ROOT_PASSWORD=root mariadb:latest

# 2. 环境配置
export PYTHONPATH=$(pwd)
export db_host=localhost
export db_port=3306
export db_user=root
export db_password=root
export db_database=instockdb

# 3. 初始化数据库结构
python instock/job/init_job.py

# 4. 执行盘后每日任务
python instock/job/execute_daily_job.py

# 5. 启动 Web 控制台 (访问 http://localhost:9988)
python instock/web/web_service.py
```