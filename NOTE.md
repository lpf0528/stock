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

---

## 五、 故障排查：东方财富接口连接失败 (push2.eastmoney.com)

> 记录时间：2026-08-08
> 症状：执行 `execute_daily_job.py` 时，步骤2（基础行情抓取）报错
> `RemoteDisconnected('Remote end closed connection without response')`

### 问题根因分析

`push2.eastmoney.com`（实时行情推送 API）与 `data.eastmoney.com` / `push2his.eastmoney.com` 不同，它对访问来源有**严格限制**：

| 接口域名 | 访问限制 |
|---|---|
| `push2.eastmoney.com` | 需要**有效登录 Cookie** + **大陆 IP** 直连，否则返回空响应 |
| `push2his.eastmoney.com` | 无需 Cookie，大陆直连即可 |
| `data.eastmoney.com` | 无需 Cookie，代理也可访问 |

### 现象梳理

1. **DNS 解析正常**：`nslookup push2.eastmoney.com` 返回大陆 IP（上海电信 `101.226.30.206`）
2. **TLS 握手成功**：`curl -v` 显示 SSL 证书验证通过
3. **HTTP 响应为空**：服务器建立连接后立即关闭，无任何 HTTP 响应头/体
4. **代理无效**：无论是否走 Clash 代理，结果相同（代理出口 IP 为海外节点时更差）

### 解决方案（按优先级排序）

#### ✅ 方案 A：配置有效的东方财富登录 Cookie（**已实施，推荐**）

`push2.eastmoney.com` 需要携带合法会话 Cookie 才返回数据。

**操作步骤：**
1. 用 Chrome 登录 https://passport2.eastmoney.com/
2. 打开 https://quote.eastmoney.com/
3. 按 F12 → Network → 找任意一个 `push2.eastmoney.com` 请求
4. 右键 → Copy → Copy Request Headers → 提取 `Cookie: ...` 的值
5. 将完整 Cookie 字符串写入：

```bash
echo "你的Cookie内容" > instock/config/eastmoney_cookie.txt
```

**代码读取优先级**（`eastmoney_fetcher.py`）：
1. 环境变量 `EAST_MONEY_COOKIE`
2. 文件 `instock/config/eastmoney_cookie.txt`
3. 内置默认 Cookie（可能已过期）

> ⚠️ **注意**：Cookie 有效期约 7~30 天，定期更新。

---

#### ✅ 方案 B：运行时取消代理环境变量（**已实施**）

Clash Verge 开启系统代理后，`HTTP_PROXY` / `HTTPS_PROXY` 环境变量会被注入当前 Shell，导致 Python `requests` 库通过海外代理节点访问东方财富，被服务器拒绝。

**每次运行前执行：**

```bash
unset HTTPS_PROXY HTTP_PROXY https_proxy http_proxy
source .venv/bin/activate
python instock/job/execute_daily_job.py
```

或写成一条命令：

```bash
env -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy python instock/job/execute_daily_job.py
```

---

#### ✅ 方案 C：Clash 规则中为 push2.eastmoney.com 添加直连规则（**已实施**）

若使用 Clash Verge，需在 Clash 配置 `fake-ip-filter` 和 `rules` 中显式排除 EastMoney 域名，避免 Fake-IP DNS 和代理规则干扰直连。

**在 Clash 配置文件（`profiles/*.yaml`）中添加：**

```yaml
dns:
  fake-ip-filter:
    - '*.eastmoney.com'   # 新增：不对 eastmoney.com 使用 Fake-IP

rules:
  # 新增（放在所有规则最前面）：
  - 'DOMAIN,push2.eastmoney.com,🎯 全球直连'
  - 'DOMAIN,push2his.eastmoney.com,🎯 全球直连'
```

修改后需在 Clash Verge 中**重载配置文件**才能生效。

---

#### ✅ 方案 D：分页请求定期刷新 Session（**已实施**）

`push2.eastmoney.com` 对单个 TCP 连接的请求数量有限制（约 5 页/连接，每页 500 条）。当抓取全量股票（约 5300+支）时，第 6 页开始会被服务器强制断连。

**修复方案**（已写入 `stock_hist_em.py`）：每 5 页刷新一次 HTTP session，并适当增加请求间延迟。

```python
# 每5页刷新一次session，避免服务器端连接被关闭
if page_current % 5 == 1:
    fetcher.session = fetcher._create_session()
time.sleep(random.uniform(1.5, 2.5))  # 延迟从1-1.5s提高到1.5-2.5s
```

---

### 资金流与板块降级落地

资金流向接口（个股资金流、行业资金流、概念资金流）已全面接入同花顺公开排行榜降级源（默认 `STOCK_FUND_FLOW_SOURCE=ths`，`STOCK_SECTOR_FUND_FLOW_SOURCE=ths`），不再受东财并发限流影响，支持今日、3日、5日、10日榜单合并入库。

---

## 六、 故障排查：基本面选股与策略页面无数据

> 记录时间：2026-08-15  
> 症状：访问 `http://localhost:9988/instock/data?table_name=cn_stock_spot_buy` 显示空白无数据。

### 原因定位
1. **数据源字段不齐**：`cn_stock_spot_buy`（基本面选股）的筛选条件为 `pe9 > 0 and pe9 <= 20 and pbnewmrq <= 10 and roe_weight >= 15`。腾讯全市场快照源不提供 `roe_weight`（加权净资产收益率）等财报字段，在 `cn_stock_spot` 表中该列为 NULL，导致旧逻辑单表查询时匹配结果为 0 行，表未被创建。
2. **调度脱节**：`stock_spot_buy` 原本挂在龙虎榜任务末尾作为副产物，未在每日作业管线 `daily_fetch_pipeline.py` 中作为独立作业编排。
3. **Web API 空参兼容**：后端 `dataTableHandler.py` 在未传 `date` 参数时未做参数分离，触发 SQL 绑定异常回退为空数组。

### 修复方案
1. **跨表联合补全**：在 `basic_data_other_daily_job.py` 的 `stock_spot_buy` 中，将 `cn_stock_spot` 行情表与包含完整财务数据的 `cn_stock_selection`（综合选股表）按 `date` + `code` 进行左连接，合并 `roe_weight`、`sale_gpr`、`debt_asset_ratio` 等指标并执行策略筛选。
2. **入库与每日调度编排**：在 `daily_fetch_pipeline.py` 中注册 `FetchJob("stock-spot-buy", "基本面选股", "cn_stock_spot_buy", ...)`，并加入 `basic_data_other_daily_job.main()` 显式执行。
3. **Web 处理器适配**：优化 `dataTableHandler.py`，兼容 `date is None` 的查询场景。

---

### 快速诊断命令

```bash
# 1. 验证基本面选股数据生成
python -c "import instock.lib.database as mdb; print(mdb.executeSqlFetch('SELECT COUNT(*), MAX(date) FROM cn_stock_spot_buy'))"

# 2. 验证 Web API 接口输出
curl -s "http://localhost:9988/instock/api_data?name=cn_stock_spot_buy&date=2026-08-14" | head -c 200

# 3. 运行 K 线形态批量识别 (新浪日线高可用通道)
python instock/job/klinepattern_data_daily_job.py
```