# 东方财富 `push2.eastmoney.com` 失败排查报告

## 背景

在重跑 `basic_data_other_daily_job.py 2026-08-07` 时，`cn_stock_fund_flow_industry` 一直没有写入数据，且早期数据库里也没有这张表。随后进一步排查发现，行业资金流抓取链路在访问东方财富 `push2.eastmoney.com` 时持续失败。

## 现象

- `instockdb` 中最初没有 `cn_stock_fund_flow_industry` 和 `cn_stock_fund_flow_concept`
- 重跑 `basic_data_other_daily_job.py 2026-08-07` 后，行业资金流和概念资金流都没有入库
- 日志中反复出现以下错误类型：
  - `ProxyError('Unable to connect to proxy', RemoteDisconnected(...))`
  - `ConnectionError`
  - `RemoteDisconnected('Remote end closed connection without response')`
  - `SSLCertVerificationError`，在尝试 IP 直连时出现

## 根因分析

### 1. 数据库表缺失不是查询问题，而是建表路径不完整

一开始 `init_job.py` 只在“数据库不存在”时才创建基础表。

这意味着：
- 数据库已经存在时，缺失的新表不会被补齐
- `cn_stock_fund_flow_industry` 和 `cn_stock_fund_flow_concept` 只能在首次成功入库时由 `to_sql()` 隐式创建
- 只要当天抓取失败，这两张表就会一直不存在

### 2. 东方财富请求最初受系统代理劫持

本机环境存在系统代理：

```bash
HTTP_PROXY=http://127.0.0.1:7897
HTTPS_PROXY=http://127.0.0.1:7897
```

而项目自身的 `proxy.txt` 为空。

这说明：
- 项目配置没有显式代理
- 但 `requests` 默认会读取环境变量代理
- 东财请求会先走本机 `7897` 代理
- 代理链路不稳定时，就会出现 `ProxyError` 和 `RemoteDisconnected`

### 3. 去掉代理后，东财域名直连仍不稳定

后续做了以下处理：
- `session.trust_env = False`
- 清理任务入口的 `HTTP_PROXY / HTTPS_PROXY / ALL_PROXY`
- 强制请求 `proxies={"http": None, "https": None}`
- 去掉 IP 直连分支，只保留域名直连

但最小请求仍然失败，最终表现为：

```text
HTTPSConnectionPool(host='push2.eastmoney.com', port=443)
RemoteDisconnected('Remote end closed connection without response')
```

这说明当前问题已经不再是本机代理劫持，而是东方财富请求在当前网络出口下仍会被对端断开。

## 已实施的修复

### 数据库侧

1. 修复了表存在性检查
   - `checkTableIsExist()` 现在按 `table_schema + table_name` 检查
   - 避免跨库误判

2. 补齐初始化建表
   - `init_job.py` 现在在数据库存在时也会执行基础表补齐
   - 新增显式创建：
     - `cn_stock_fund_flow_industry`
     - `cn_stock_fund_flow_concept`

3. 增加空表兜底
   - 行业资金流任务开始前，如果表不存在会先创建空表
   - 这样前端不会再因为“表不存在”直接报错

### 任务日志侧

在行业资金流链路上补了更细日志：
- 开始抓取
- 每个子任务返回情况
- 空数据情况
- 合并后数据行数
- 入库前后
- 异常堆栈

### 网络侧

1. 禁止 `requests` 自动读取系统代理
2. 清理任务入口的代理环境变量
3. 去掉 IP 直连，避免 HTTPS 证书与 IP 不匹配
4. 保留域名直连 + 明确禁代理的最小请求链路

## 阶段性结论（初次排查）

截至目前，问题可以分成两层：

### 已解决

- `cn_stock_fund_flow_industry` 和 `cn_stock_fund_flow_concept` 的缺失建表问题
- 系统代理干扰问题
- 日志不够明确的问题

### 尚未彻底解决

- 东方财富 `push2.eastmoney.com` 在当前网络出口下仍然会断开连接
- 这导致行业资金流和概念资金流无法稳定抓取
- 因此 `2026-08-07` 仍然没有真实写入记录

## 初次排查时的数据库状态

当前 `instockdb` 已存在：

- `cn_stock_attention`
- `cn_stock_blocktrade`
- `cn_stock_bonus`
- `cn_stock_chip_race_end`
- `cn_stock_chip_race_open`
- `cn_stock_fund_flow_concept`
- `cn_stock_fund_flow_industry`
- `cn_stock_lhb`
- `cn_stock_limitup_reason`
- `cn_stock_selection`

其中，行业资金流和概念资金流表已创建，但 `2026-08-07` 这一天仍为 0 条记录。

## 初步备选方案

### 方案 A

切换一个对东方财富可用的网络出口，再重跑任务。

### 方案 B

接备用数据源或本地缓存导入，避免东财接口不可用时整天空表。

### 方案 C

保留当前代码修复，继续作为稳定的任务框架：
- 表存在性检查正确
- 建表路径完整
- 日志可定位
- 代理干扰已清除

但把数据源失败作为外部依赖问题处理。

## 后续稳定性改造（已实施）

为降低 `push2` 的频控和连接复用风险，已补充以下处理：

1. 行业和概念资金流的“今日 / 5 日 / 10 日”指标改为串行抓取，指标之间随机等待 2–5 秒；不再同时发起 3 个请求。
2. `push2.eastmoney.com` 每次请求尝试使用独立 HTTP 会话，并发送 `Connection: close`，避免复用已被服务端关闭的连接。
3. 请求实际传入完整的浏览器风格请求头（包括 Cookie、Referer 和 User-Agent）。
4. 已有本地缓存仅用于降级读取；只要本轮结果包含历史缓存，任务就跳过当日入库，避免将旧快照标记成当天真实资金流。

这些改造会减少由并发、连接池和缓存语义造成的失败或脏数据，但不能绕过服务端对登录会话和网络出口的限制。若最小直连请求仍被断开，应继续采用有效登录 Cookie 的浏览器验证，或使用可访问东财的国内采集节点作为主备来源。

### 专用出口配置

如有可用的大陆 HTTP/HTTPS 代理或国内采集网关，可在启动任务前设置 `EASTMONEY_PROXY`。该变量只会用于 `*.eastmoney.com` 请求；系统的 `HTTP_PROXY`、`HTTPS_PROXY` 和 `ALL_PROXY` 仍保持禁用，避免重新引入全局代理干扰。

```bash
EASTMONEY_PROXY=http://<国内出口地址>:<端口> \
  .venv/bin/python instock/job/basic_data_other_daily_job.py 2026-08-07
```

## 最终验证与处理（2026-08-08）

本机 Chrome 可以正常访问行情页面。对同一 `push2` 请求的对照结果为：

- 常规 `requests`（直连、携带 Cookie）仍被服务端断开；
- 常规 `curl` 经本机代理或直连也收到空响应；
- 使用 `curl_cffi` 模拟 Chrome 指纹、携带有效登录 Cookie 后返回 HTTP 200 和有效 JSON。

因此将 `push2.eastmoney.com` 专门改为 `curl_cffi` 的 Chrome 传输层；其他东财域名仍使用原有 `requests`。这避免把浏览器 Cookie 导出到第三方服务，同时保留了自动化任务的运行方式。`curl_cffi==0.16.0` 已加入依赖清单。

## 显式日期重跑修复（2026-08-08）

进一步验证发现，`run_template.py` 在传入单个日期或日期区间时，没有为 `save_nph_*` 任务传入 `before=False`。这会使任务在函数入口直接返回，表面上完成但没有实际抓取或写入。现已与无参数的每日模式保持一致：所有显式日期的 `save_nph_*` 任务都会以 `before=False` 执行。

## 最终结论与重跑结果（2026-08-08）

经过浏览器、命令行和 Python 客户端的对照，这个问题并不是“本机无法访问东财”。本机 Chrome 可以正常打开东方财富行情页；真正的差异在于 `push2` 会同时识别登录会话和客户端网络特征。普通 `requests` 即使禁用了系统代理、带上 Cookie，也会被服务端主动断开；普通 `curl` 无论经本机代理还是强制直连，同样得到空响应。

最终可用的组合是：有效的东方财富登录 Cookie，加上 `curl_cffi` 提供的 Chrome TLS/HTTP2 指纹。该组合已用行业资金流接口验证为 HTTP 200，并返回有效 JSON。项目现在只对 `push2.eastmoney.com` 使用这条传输链路，其他域名继续使用原有 `requests`，这样改动范围最小，也不会影响其余抓取器。

Cookie 必须由本机已登录的 Chrome 提供。浏览器刷新页面不会自动更新项目配置；需要在开发者工具的 Network 面板中找到 `push2` 请求，将最新 `Cookie` 值覆盖到 `instock/config/eastmoney_cookie.txt`。Cookie 属于登录凭据，不能写入文档、日志或提交到版本库；如曾在不安全位置暴露，应退出后重新登录以轮换会话。

### 本次实际写入

在更新 Cookie 后，按 `2026-08-07` 定向重跑板块资金流，数据库最终状态如下：

| 表 | 写入条数 | 日期 |
| --- | ---: | --- |
| `cn_stock_fund_flow_industry` | 496 | `2026-08-07` |
| `cn_stock_fund_flow_concept` | 504 | `2026-08-07` |

概念资金流在第一次连续请求时仍出现过短时断连。刷新浏览器会话后，先用单个“今日”请求确认恢复，再执行概念资金流的定向写入，最终入库成功。这说明服务端存在短时频控：不应在失败后立即反复执行整套 `basic_data_other_daily_job.py`，因为其中的个股资金流请求会进一步消耗限额。

### 推荐运行方式

日常任务继续通过 `basic_data_other_daily_job.py` 执行；现在显式日期和日期区间也会正确运行 `save_nph_*` 任务。出现 `push2` 断连时，应按下面顺序处理：

1. 在 Chrome 登录并刷新东方财富行情页，更新本地 Cookie 文件。
2. 先验证一个小分页请求是否返回数据，再抓取目标板块。
3. 仅重跑失败的行业或概念资金流，避免立刻执行完整任务。
4. 若仍被断开，停止重试并等待一段时间；本地缓存只作展示降级，不能伪装成当天真实数据。

`EASTMONEY_PROXY` 仍保留为可选能力，用于确有国内专用出口的部署场景；当前本机已证明不依赖该配置也可以完成抓取。

## 用户操作指南

日常使用时不需要手动配置系统代理。真正需要维护的是东方财富的登录会话：当日志里出现 `RemoteDisconnected`、`Connection closed abruptly`，或板块资金流没有新增数据时，按下面步骤更新会话并重试即可。

### 1. 在 Chrome 中刷新东方财富会话

先在本机 Chrome 登录东方财富，打开 `https://quote.eastmoney.com/` 并刷新页面。随后按 F12 打开开发者工具，进入 Network 面板；筛选 `push2.eastmoney.com`，点开任意一个 `api/qt/clist/get` 请求，在 Request Headers 中复制完整的 `Cookie` 值。

将 Cookie 覆盖写入 `instock/config/eastmoney_cookie.txt`，文件中只保留一行 Cookie 字符串，不要附带 `Cookie:` 前缀、引号或其他请求头。Cookie 是登录凭据，不要发送到聊天、提交到 Git，也不要写入日志。

### 2. 安装或更新依赖

首次拉取本次改造后的代码时，需要安装 `curl_cffi`。在项目根目录执行：

```bash
uv pip install --python .venv/bin/python -r requirements.txt
```

安装完成后，`push2` 会自动使用 Chrome 指纹传输层，无需额外开关。

### 3. 正常执行每日任务

日常盘后可以直接运行完整任务。显式指定日期时，`save_nph_*` 任务现在也会正确执行：

```bash
.venv/bin/python instock/job/basic_data_other_daily_job.py 2026-08-07
```

如果只需运行最新交易日，则不传日期：

```bash
.venv/bin/python instock/job/basic_data_other_daily_job.py
```

### 4. 只补跑失败的板块资金流

若行业或概念资金流单独失败，不要马上重跑整套任务。完整任务还会请求个股资金流，容易进一步触发东财的短时频控。可按需执行下面的定向命令；`0` 表示行业资金流，`1` 表示概念资金流：

```bash
.venv/bin/python -c "import datetime; from instock.job.basic_data_other_daily_job import stock_sector_fund_flow_data; stock_sector_fund_flow_data(datetime.date(2026, 8, 7), 0)"
```

```bash
.venv/bin/python -c "import datetime; from instock.job.basic_data_other_daily_job import stock_sector_fund_flow_data; stock_sector_fund_flow_data(datetime.date(2026, 8, 7), 1)"
```

### 5. 遇到再次断连时的处理

如果更新 Cookie 后仍被断连，停止连续重试，等待一段时间后再从 Chrome 刷新页面并更新 Cookie。先用一个小分页请求确认恢复，再补跑失败的单个板块。`EASTMONEY_PROXY` 只适用于确实拥有可用国内专用出口的场景；本机 Chrome 能正常访问时，不应为了排障盲目切换代理。
