# InStock 项目 Agent 上下文与上下文指南 (.agents/AGENTS.md)

本文档是该项目的 AI Agent 上下文配置文件。任何 AI Assistant（如 Antigravity）在访问本工作区时，会自动载入此文件作为项目的上下文与规范指导。

---

## 1. 项目简介

**InStock** 是一套开源的 **A 股 / ETF 量化分析、因子计算、策略选股、胜率回测与自动交易系统**。
- **目标**：每日抓取股票及 ETF 行情数据，计算 30+ 技术指标与筹码分布 (CYQ)，识别 61 种 K 线形态，运行 11 种选股策略并回测 1/3/5/10/20 日胜率。
- **架构**：Tornado Web 控制台 + Python 核心计算 Job + EasyTrader 自动交易 + MariaDB/MySQL 持久化 + Docker 容器化部署。

---

## 2. 目录结构全景图

```
stock/
├── .agents/
│   └── AGENTS.md                  # Agent 自动载入的项目上下文 (本文档)
├── .github/                       # GitHub Actions 自动化工作流
├── .vscode/                       # VS Code 调试与配置 (launch.json)
├── cron/                          # Cron 定时任务 (hourly, monthly, workdayly)
├── docker/                        # Docker 镜像构建与 Compose 部署配置
├── img/                           # 项目架构图与界面截图
├── instock/                       # 核心 Python 源码
│   ├── bin/                       # Linux/Windows 部署与启动脚本 (.sh, .bat)
│   ├── config/                    # 配置文件 (trade_client.json, proxy.txt 等)
│   ├── core/                      # 核心算法与数据处理模块
│   │   ├── backtest/              # 策略胜率回测模块 (rate_stats.py)
│   │   ├── crawling/              # 行情/资金流/大宗/龙虎榜数据爬虫
│   │   ├── indicator/             # 基于 TA-Lib 的 30+ 技术指标计算
│   │   ├── kline/                 # K 线图及筹码成本分布算法 (cyq.py)
│   │   ├── pattern/               # 61 种 K 线形态匹配与识别 (pattern_recognitions.py)
│   │   ├── strategy/              # 11 种量化选股策略 (enter.py, keep_increasing.py等)
│   │   ├── eastmoney_fetcher.py   # 东方财富接口封装
│   │   ├── singleton_*.py         # 数据单例缓存 (股票列表、代理、交易日等)
│   │   ├── stockfetch.py          # 统一数据抓取调度入口
│   │   └── tablestructure.py      # MySQL 数据库表结构全集声明
│   ├── job/                       # 盘后每日数据计算 Job 作业集
│   │   ├── execute_daily_job.py   # 每日 Job 调度入口
│   │   ├── init_job.py            # 数据库初始化建表 Job
│   │   ├── basic_data_*.py        # 基础数据抓取与存储 Job
│   │   ├── indicators_data_daily_job.py  # 指标计算 Job
│   │   ├── klinepattern_data_daily_job.py # K线形态识别 Job
│   │   ├── strategy_data_daily_job.py     # 选股策略计算 Job
│   │   └── backtest_data_daily_job.py     # 胜率回测 Job
│   ├── lib/                       # 工具库 (数据库连接池, 加密, 交易时间)
│   │   ├── database.py            # MySQL/MariaDB 数据库操作
│   │   ├── torndb.py              # Tornado DB 轻量 ORM
│   │   └── trade_time.py          # A股交易日与交易时间判断工具
│   ├── trade/                     # 自动化交易模块 (easytrader 集成)
│   │   ├── robot/                 # 实盘交易机器人
│   │   ├── strategies/            # 交易策略实现
│   │   └── trade_service.py       # 自动化交易/自动打新服务入口
│   └── web/                       # Tornado Web 控制台
│       ├── static/                # 静态资源 (JS, CSS, DataTables, Bokeh)
│       ├── templates/             # HTML 模板
│       └── web_service.py         # Web 服务器启动主程序
├── supervisor/                    # Supervisor 进程守候配置 (supervisord.conf)
├── LICENSE                        # Apache 2.0 开源协议
├── NOTE.md                        # 本地 Docker 数据库快速启动指令
├── PROJECT_ANALYSIS.md            # 项目完整架构分析与调试指南
├── README.md                      # 项目说明文档
└── requirements.txt               # Python 依赖库清单
```

---

## 3. 核心功能与模块映射

| 功能模块 | 对应源码路径 | 说明 |
| :--- | :--- | :--- |
| **数据库表定义** | [tablestructure.py](file:///Users/liupengfei/workplace/github_project/stock/instock/core/tablestructure.py) | 定义行情、指标、选股表结构 |
| **数据抓取层** | [crawling](file:///Users/liupengfei/workplace/github_project/stock/instock/core/crawling) | 东方财富/新浪数据抓取 |
| **指标计算层** | [calculate_indicator.py](file:///Users/liupengfei/workplace/github_project/stock/instock/core/indicator/calculate_indicator.py) | MACD, KDJ, BOLL, RSI, ATR, VWMA 等 |
| **筹码分布 CYQ** | [cyq.py](file:///Users/liupengfei/workplace/github_project/stock/instock/core/kline/cyq.py) | 筹码密集度与衰减分布算法 |
| **K线形态识别** | [pattern_recognitions.py](file:///Users/liupengfei/workplace/github_project/stock/instock/core/pattern/pattern_recognitions.py) | TA-Lib 61 种 K 线形态判定与评分 |
| **选股策略库** | [strategy](file:///Users/liupengfei/workplace/github_project/stock/instock/core/strategy) | 11 种策略 (突破、多头、海龟交易等) |
| **策略胜率回测** | [rate_stats.py](file:///Users/liupengfei/workplace/github_project/stock/instock/core/backtest/rate_stats.py) | 1~20 日后续胜率统计 |
| **每日任务调度** | [execute_daily_job.py](file:///Users/liupengfei/workplace/github_project/stock/instock/job/execute_daily_job.py) | 盘后计算与策略筛选 Job |
| **Web 控制台** | [web_service.py](file:///Users/liupengfei/workplace/github_project/stock/instock/web/web_service.py) | Tornado Web UI (端口 9988) |
| **自动化交易** | [trade_service.py](file:///Users/liupengfei/workplace/github_project/stock/instock/trade/trade_service.py) | EasyTrader 实盘及自动打新 |

---

## 4. 关键运行与调试指令

### 数据库启动 (Docker MariaDB)
```bash
docker run -d \
  --name instockdb \
  -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=root \
  mariadb:latest
```

### 环境初始化与依赖
```bash
brew install ta-lib
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 调试环境运行 (命令行)
```bash
# 环境变量配置
export PYTHONPATH=$(pwd)
export db_host=localhost
export db_port=3306
export db_user=root
export db_password=root
export db_database=instockdb

# 1. 初始化数据库结构
python instock/job/init_job.py

# 2. 执行盘后每日任务
python instock/job/execute_daily_job.py

# 3. 启动 Web 控制台
python instock/web/web_service.py
```

---

## 5. 开发与修改规范

1. **数据库驱动限制**：项目依赖 `pymysql` 及 MySQL/MariaDB 特有 SQL 语法，勿随意调整为 SQLite 或 PostgreSQL。
2. **TA-Lib 依赖**：技术指标依赖 C 语言 native 库 `ta-lib`，开发与容器环境均需正确安装库文件。
3. **单例数据结构**：`instock/core/singleton_*.py` 实现了多线程/并发环境下的单例数据缓存，修改数据抓取逻辑时请注意缓存刷新策略。
4. **代码修改规范**：新增选股策略时，需在 `instock/core/strategy/` 中增加算法文件，并在 `instock/core/tablestructure.py` 中增加策略表字段映射。
