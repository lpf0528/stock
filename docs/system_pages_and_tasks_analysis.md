# InStock 项目全系统页面与任务深度分析报告

> 更新日期：2026-08-15  
> 本文档对 InStock 项目的所有 Web 页面、关联关系、底层数据表、数据来源、后台 Job 任务 ID 及执行命令进行全景梳理。

---

## 目录

- [一、页面架构与交互总览](#一页面架构与交互总览)
- [二、系统基础与首页](#二系统基础与首页)
- [三、综合选股模块](#三综合选股模块)
- [四、股票基本数据模块](#四股票基本数据模块)
- [五、股票指标数据模块](#五股票指标数据模块)
- [六、股票K线形态模块](#六股票k线形态模块)
- [七、股票策略数据模块](#七股票策略数据模块)
- [八、详情交互与可视化图表](#八详情交互与可视化图表)
- [九、胜率回测计算体系](#九胜率回测计算体系)
- [十、任务ID与运维执行命令汇总表](#十任务id与运维执行命令汇总表)

---

## 一、页面架构与交互总览

系统采用 **Tornado Web** 框架驱动，前端基于 **Ace Admin + SpreadJS (表格控件) + Bokeh (交互式量化图表)** 构建。

- **Web 控制台服务启动**：`python instock/web/web_service.py` （默认端口 `9988`，访问 `http://localhost:9988/`）
- **通用交互下钻链路**：在全系统任何数据表格中，点击任意股票代码的超链接，均会打开新的标签页下钻跳转至该个股的 **【股票指标与 K 线/筹码分布图】**（`/instock/data/indicators`）。
- **自选股置顶机制**：全系统报表均通过子查询关联关注表 `cn_stock_attention`，用户已关注的个股在表格初次加载时排在最前列。

---

## 二、系统基础与首页

### 1. InStock 系统首页 / ima 知识库概览
* **页面名称**：首页 (InStock股票系统 / ima知识库)
* **页面地址**：`/` 或 `/instock/`
* **功能与作用**：系统主门户与知识库入口，展示项目量化架构体系、使用说明及左侧主功能导航树。
* **关联页面**：左侧菜单直达所有数据页面；点击菜单项跳转至对应报表。
* **涉及数据表**：无（纯模板渲染与版本信息展示）。
* **数据来源**：静态文档与系统元数据。
* **任务 ID 与执行命令**：随 Web 服务启动（`python instock/web/web_service.py`）。

---

## 三、综合选股模块

### 2. 综合选股
* **页面名称**：综合选股
* **页面地址**：`/instock/data?table_name=cn_stock_selection`
* **功能与作用**：全市场股票池基础及多维指标筛选中心（包含行情、基本面财务指标、估值比率、所处行业等全量字段）。
* **关联页面**：
  - 点击股票代码跳转至 `/instock/data/indicators?code=...`（K 线指标图）
  - 数据接口：`/instock/api_data?name=cn_stock_selection&date=...`
* **涉及数据表**：
  - 主表：`cn_stock_selection`
  - 关联表：`cn_stock_attention`（用于排序置顶）
* **数据来源**：东方财富网选股中心接口 / 腾讯行情综合快照。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-selection`
  - **单项命令**：`python -m instock.job.selection_data_daily_job`
  - **Pipeline 执行**：`python instock/job/daily_fetch_pipeline.py --jobs stock-selection`

---

## 四、股票基本数据模块

### 3. 每日股票数据
* **页面名称**：每日股票数据
* **页面地址**：`/instock/data?table_name=cn_stock_spot`
* **功能与作用**：全市场股票日收盘全景行情看板（现价、涨跌幅、成交量额、换手率、量比、市盈率、市净率、总市值、流通市值等）。
* **关联页面**：点击代码跳转至 K 线详情图；关联关注表。
* **涉及数据表**：`cn_stock_spot`、`cn_stock_attention`
* **数据来源**：腾讯公开行情接口（全市场快照）。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-spot`
  - **单项命令**：`python -m instock.job.basic_data_daily_job`
  - **Pipeline 执行**：`python instock/job/daily_fetch_pipeline.py --jobs stock-spot`

---

### 4. 早盘抢筹
* **页面名称**：早盘抢筹
* **页面地址**：`/instock/data?table_name=cn_stock_chip_race_open`
* **功能与作用**：集合竞价阶段资金异动与抢筹排行分析，监控开盘主力资金异动个股。
* **关联页面**：点击代码跳转至 K 线详情图；关联关注表。
* **涉及数据表**：`cn_stock_chip_race_open`、`cn_stock_attention`
* **数据来源**：东方财富/同花顺竞价异动排行榜。
* **任务 ID 与执行命令**：
  - **任务 ID**：`chip-race-open`
  - **单项命令**：`python -m instock.job.basic_data_other_daily_job`
  - **Pipeline 执行**：`python instock/job/daily_fetch_pipeline.py --jobs chip-race-open`

---

### 5. 尾盘抢筹
* **页面名称**：尾盘抢筹
* **页面地址**：`/instock/data?table_name=cn_stock_chip_race_end`
* **功能与作用**：临近收盘（14:30~15:00）主力抢筹异动排行，用于挖掘次日可能高开的标的。
* **关联页面**：点击代码跳转至 K 线详情图；关联关注表。
* **涉及数据表**：`cn_stock_chip_race_end`、`cn_stock_attention`
* **数据来源**：东方财富/同花顺尾盘资金异动监控。
* **任务 ID 与执行命令**：
  - **任务 ID**：`chip-race-end`
  - **单项命令**：`python -m instock.job.basic_data_after_close_daily_job`
  - **Pipeline 执行**：`python instock/job/daily_fetch_pipeline.py --jobs chip-race-end`

---

### 6. 涨停原因
* **页面名称**：涨停原因
* **页面地址**：`/instock/data?table_name=cn_stock_limitup_reason`
* **功能与作用**：当日涨停个股的题材概念归属、封板时间、封单资金量及涨停驱动原因深度解析。
* **关联页面**：点击代码跳转至 K 线详情图；关联概念/行业资金流向页面。
* **涉及数据表**：`cn_stock_limitup_reason`、`cn_stock_attention`
* **数据来源**：东方财富涨停复盘与题材归因数据源。
* **任务 ID 与执行命令**：
  - **任务 ID**：`limitup-reason`
  - **单项命令**：`python -m instock.job.basic_data_other_daily_job`
  - **Pipeline 执行**：`python instock/job/daily_fetch_pipeline.py --jobs limitup-reason`

---

### 7. 股票资金流向 (个股资金流)
* **页面名称**：股票资金流向
* **页面地址**：`/instock/data?table_name=cn_stock_fund_flow`
* **功能与作用**：展示个股今日、3日、5日、10日的主力净流入净额、净占比及超大单/大单分布。
* **关联页面**：点击代码跳转至 K 线详情图；联动行业/概念资金流。
* **涉及数据表**：`cn_stock_fund_flow`、`cn_stock_attention`
* **数据来源**：同花顺公开排行榜降级数据源（支持今日、3日、5日、10日榜单多维度合并）。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-fund-flow`
  - **单项命令**：`python -m instock.job.basic_data_other_daily_job`
  - **Pipeline 执行**：`python instock/job/daily_fetch_pipeline.py --jobs stock-fund-flow`

---

### 8. 股票分红配送
* **页面名称**：股票分红配送
* **页面地址**：`/instock/data?table_name=cn_stock_bonus`
* **功能与作用**：展示各股送转总比例、现金分红比例、股息率、预案公告日、股权登记日及除权除息日。
* **关联页面**：点击代码跳转至 K 线详情图。
* **涉及数据表**：`cn_stock_bonus`、`cn_stock_attention`
* **数据来源**：东方财富高送转与分红派息公告数据。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-bonus`
  - **单项命令**：`python -m instock.job.basic_data_other_daily_job`
  - **Pipeline 执行**：`python instock/job/daily_fetch_pipeline.py --jobs stock-bonus`

---

### 9. 股票龙虎榜
* **页面名称**：股票龙虎榜
* **页面地址**：`/instock/data?table_name=cn_stock_lhb`
* **功能与作用**：每日机构席位与知名游资买卖明细、龙虎榜净买额、成交占比、上榜原因及后1/2/5/10日表现追踪。
* **关联页面**：点击代码跳转至 K 线详情图；关联涨停原因页面。
* **涉及数据表**：`cn_stock_lhb`、`cn_stock_attention`
* **数据来源**：东方财富/新浪财经龙虎榜每日披露数据。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-lhb`
  - **单项命令**：`python -m instock.job.basic_data_other_daily_job`
  - **Pipeline 执行**：`python instock/job/daily_fetch_pipeline.py --jobs stock-lhb`

---

### 10. 股票大宗交易
* **页面名称**：股票大宗交易
* **页面地址**：`/instock/data?table_name=cn_stock_blocktrade`
* **功能与作用**：盘后大宗交易成交明细（成交均价、折溢价率、成交笔数、成交额占流通市值比）。
* **关联页面**：点击代码跳转至 K 线详情图。
* **涉及数据表**：`cn_stock_blocktrade`、`cn_stock_attention`
* **数据来源**：东方财富大宗交易盘后统计。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-blocktrade`
  - **单项命令**：`python -m instock.job.basic_data_after_close_daily_job`
  - **Pipeline 执行**：`python instock/job/daily_fetch_pipeline.py --jobs stock-blocktrade`

---

### 11. 行业资金流向
* **页面名称**：行业资金流向
* **页面地址**：`/instock/data?table_name=cn_stock_fund_flow_industry`
* **功能与作用**：按行业板块统计今日、5日、10日的主力资金净流入净额、净占比及各行业今日/5日/10日领涨龙头股。
* **关联页面**：与概念资金流向、个股资金流向形成板块协同分析。
* **涉及数据表**：`cn_stock_fund_flow_industry`
* **数据来源**：同花顺行业资金流排行榜（今日/5日/10日合并）。
* **任务 ID 与执行命令**：
  - **任务 ID**：`industry-fund-flow`
  - **单项命令**：`python -m instock.job.basic_data_other_daily_job`
  - **Pipeline 执行**：`python instock/job/daily_fetch_pipeline.py --jobs industry-fund-flow`

---

### 12. 概念资金流向
* **页面名称**：概念资金流向
* **页面地址**：`/instock/data?table_name=cn_stock_fund_flow_concept`
* **功能与作用**：按热门题材概念统计今日、5日、10日主力净流入、涨跌幅及领涨龙头股。
* **关联页面**：与涨停原因、行业资金流联动分析热点轮动。
* **涉及数据表**：`cn_stock_fund_flow_concept`
* **数据来源**：同花顺概念资金流排行榜（今日/5日/10日合并）。
* **任务 ID 与执行命令**：
  - **任务 ID**：`concept-fund-flow`
  - **单项命令**：`python -m instock.job.basic_data_other_daily_job`
  - **Pipeline 执行**：`python instock/job/daily_fetch_pipeline.py --jobs concept-fund-flow`

---

### 13. 每日 ETF 数据
* **页面名称**：每日ETF数据
* **页面地址**：`/instock/data?table_name=cn_etf_spot`
* **功能与作用**：全市场场内 ETF 基金最新行情看板（最新价、涨跌幅、成交额、流通市值等）。
* **关联页面**：点击代码跳转至 ETF 对应 K 线详情图。
* **涉及数据表**：`cn_etf_spot`
* **数据来源**：东方财富/腾讯场内基金实时与历史日线数据源。
* **任务 ID 与执行命令**：
  - **任务 ID**：`etf-spot`（扩展项）
  - **执行命令**：`python -m instock.job.basic_data_daily_job`

---

## 五、股票指标数据模块

### 14. 股票指标数据
* **页面名称**：股票指标数据
* **页面地址**：`/instock/data?table_name=cn_stock_indicators`
* **功能与作用**：全市场股票的 30+ 种经典技术指标每日计算汇总看板（MACD, KDJ, BOLL, RSI, TRIX, CR, VR, ROC, DMI, WR, CCI, ATR, DMA, OBV, SAR, PSY, BRAR, EMV, BIAS, MFI, VWMA, SuperTrend, ForceIndex, ENE 等）。
* **关联页面**：点击代码直接跳转至 Bokeh K 线与量化指标子图。
* **涉及数据表**：`cn_stock_indicators`、`cn_stock_attention`
* **数据来源**：新浪财经 / 腾讯历史日线数据 + 本地 TA-Lib / 计算引擎运算。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-indicators-daily`
  - **执行命令**：`python instock/job/indicators_data_daily_job.py`

---

### 15. 股票指标买入
* **页面名称**：股票指标买入
* **页面地址**：`/instock/data?table_name=cn_stock_indicators_buy`
* **功能与作用**：基于技术指标超卖反转、底部共振等组合条件（如 KDJ、RSI、CR 超卖拐头向上等）自动筛选出提示买入信号的标的，并包含后续 1~100 日收益率回测字段。
* **关联页面**：点击代码跳转至 K 线详情图；关联胜率回测分析。
* **涉及数据表**：`cn_stock_indicators_buy`、`cn_stock_attention`
* **数据来源**：`cn_stock_indicators` 指标结果 + 指标买入算法筛选。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-indicators-buy-calc`
  - **执行命令**：随 `python instock/job/indicators_data_daily_job.py` 内部触发计算。

---

### 16. 股票指标卖出
* **页面名称**：股票指标卖出
* **页面地址**：`/instock/data?table_name=cn_stock_indicators_sell`
* **功能与作用**：基于指标超买钝化或破位等组合条件（如极度超买、顶背离等）筛选提示风险/卖出信号的股票。
* **关联页面**：点击代码跳转至 K 线详情图。
* **涉及数据表**：`cn_stock_indicators_sell`、`cn_stock_attention`
* **数据来源**：`cn_stock_indicators` 指标结果 + 指标卖出算法筛选。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-indicators-sell-calc`
  - **执行命令**：随 `python instock/job/indicators_data_daily_job.py` 内部触发计算。

---

## 六、股票K线形态模块

### 17. 股票 K 线形态
* **页面名称**：K线形态
* **页面地址**：`/instock/data?table_name=cn_stock_pattern` (`cn_stock_pattern_recognitions`)
* **功能与作用**：调用 TA-Lib 的 61 种 K 线形态识别算法（两只乌鸦、三只乌鸦、早晨之星、黄昏之星、吞没形态、三仙归洞、锤头线、射击之星等），输出全市场命中特定形态的股票列表及形态评分。
* **关联页面**：点击代码跳转至 K 线详情图核对形态。
* **涉及数据表**：`cn_stock_pattern` (`cn_stock_pattern_recognitions`)、`cn_stock_attention`
* **数据来源**：新浪/腾讯历史日线序列 + TA-Lib C 语言形态匹配函数。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-kline-pattern-job`
  - **执行命令**：`python instock/job/klinepattern_data_daily_job.py`

---

## 七、股票策略数据模块

### 18. 基本面选股
* **页面名称**：基本面选股
* **页面地址**：`/instock/data?table_name=cn_stock_spot_buy`
* **功能与作用**：基于财务价值投资逻辑筛选低估值、高盈利成长标的（筛选规则：市盈率 $\text{PE} \le 20$、市净率 $\text{PB} \le 10$、加权净资产收益率 $\text{ROE} \ge 15\%$）。
* **关联页面**：点击代码跳转至 K 线详情图；关联 `cn_stock_selection`。
* **涉及数据表**：`cn_stock_spot_buy`、`cn_stock_attention`
* **数据来源**：从每日股票行情 `cn_stock_spot` 与综合选股财报数据中关联计算提取。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-spot-buy`
  - **单项命令**：`python -m instock.job.basic_data_other_daily_job`
  - **Pipeline 执行**：`python instock/job/daily_fetch_pipeline.py --jobs stock-spot-buy`

---

### 19. 放量上涨策略
* **页面名称**：放量上涨
* **页面地址**：`/instock/data?table_name=cn_stock_strategy_enter`
* **功能与作用**：量价配合突破策略。筛选当日成交量放大（量比超阈值）且价格涨幅明确突破短期均线的个股。
* **关联页面**：点击代码跳转至 K 线详情图；回测后续 1~20 日胜率收益。
* **涉及数据表**：`cn_stock_strategy_enter`、`cn_stock_attention`
* **数据来源**：历史日线数据 + `instock.core.strategy.enter` 算法。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-strategy-enter`
  - **执行命令**：`python instock/job/strategy_data_daily_job.py`

---

### 20. 均线多头策略
* **页面名称**：均线多头
* **页面地址**：`/instock/data?table_name=cn_stock_strategy_keep_increasing`
* **功能与作用**：趋势跟踪策略。筛选 MA5 > MA10 > MA20 > MA30 > MA60 且均线系统向上发散的强趋势个股。
* **关联页面**：点击代码跳转至 K 线详情图。
* **涉及数据表**：`cn_stock_strategy_keep_increasing`、`cn_stock_attention`
* **数据来源**：历史日线数据 + `instock.core.strategy.keep_increasing` 算法。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-strategy-keep-increasing`
  - **执行命令**：`python instock/job/strategy_data_daily_job.py`

---

### 21. 停机坪策略
* **页面名称**：停机坪
* **页面地址**：`/instock/data?table_name=cn_stock_strategy_parking_apron`
* **功能与作用**：强势股二波起涨策略。股票拉出大阳线/涨停后，在高位窄幅缩量横盘整理 3~5 日（类似飞机在停机坪蓄势）即将再次拉升的形态。
* **关联页面**：点击代码跳转至 K 线详情图。
* **涉及数据表**：`cn_stock_strategy_parking_apron`、`cn_stock_attention`
* **数据来源**：历史日线数据 + `instock.core.strategy.parking_apron` 算法。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-strategy-parking-apron`
  - **执行命令**：`python instock/job/strategy_data_daily_job.py`

---

### 22. 回踩年线策略
* **页面名称**：回踩年线
* **页面地址**：`/instock/data?table_name=cn_stock_strategy_backtrace_ma250`
* **功能与作用**：牛熊转换支撑策略。股票在 250 日均线（年线）上方获得有效支撑缩量企稳并重拾升势的选股信号。
* **关联页面**：点击代码跳转至 K 线详情图。
* **涉及数据表**：`cn_stock_strategy_backtrace_ma250`、`cn_stock_attention`
* **数据来源**：历史日线数据 + `instock.core.strategy.backtrace_ma250` 算法。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-strategy-backtrace-ma250`
  - **执行命令**：`python instock/job/strategy_data_daily_job.py`

---

### 23. 突破平台策略
* **页面名称**：突破平台
* **页面地址**：`/instock/data?table_name=cn_stock_strategy_breakthrough_platform`
* **功能与作用**：箱体/平台突破策略。股票经历较长时间横盘整理（箱体振幅受限）后，当日大阳线伴随成交量有效突破箱体上轨。
* **关联页面**：点击代码跳转至 K 线详情图。
* **涉及数据表**：`cn_stock_strategy_breakthrough_platform`、`cn_stock_attention`
* **数据来源**：历史日线数据 + `instock.core.strategy.breakthrough_platform` 算法。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-strategy-breakthrough-platform`
  - **执行命令**：`python instock/job/strategy_data_daily_job.py`

---

### 24. 无大幅回撤策略
* **页面名称**：无大幅回撤
* **页面地址**：`/instock/data?table_name=cn_stock_strategy_low_backtrace_increase`
* **功能与作用**：稳健长牛股策略。筛选近 60 个交易日累计涨幅超 60%，且上涨过程中无单日跌幅超 7% 或连续两日跌幅超 10% 的稳健大牛股。
* **关联页面**：点击代码跳转至 K 线详情图。
* **涉及数据表**：`cn_stock_strategy_low_backtrace_increase`、`cn_stock_attention`
* **数据来源**：历史日线数据 + `instock.core.strategy.low_backtrace_increase` 算法。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-strategy-low-backtrace`
  - **执行命令**：`python instock/job/strategy_data_daily_job.py`

---

### 25. 海龟交易法则策略
* **页面名称**：海龟交易法则
* **页面地址**：`/instock/data?table_name=cn_stock_strategy_turtle_trade`
* **功能与作用**：经典海龟突破法则。价格突破过去 20 日最高价入场（唐奇安通道上轨），辅以 ATR 真实波幅波动率过滤。
* **关联页面**：点击代码跳转至 K 线详情图。
* **涉及数据表**：`cn_stock_strategy_turtle_trade`、`cn_stock_attention`
* **数据来源**：历史日线数据 + `instock.core.strategy.turtle_trade` 算法。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-strategy-turtle-trade`
  - **执行命令**：`python instock/job/strategy_data_daily_job.py`

---

### 26. 高而窄的旗形策略
* **页面名称**：高而窄的旗形
* **页面地址**：`/instock/data?table_name=cn_stock_strategy_high_tight_flag`
* **功能与作用**：极强势旗形动量策略。股票在短期内暴涨（如数周内涨幅超 90%），随后在高位紧凑横盘整理（旗面回撤 $\le 20\sim25\%$）待再创新高。
* **关联页面**：点击代码跳转至 K 线详情图。
* **涉及数据表**：`cn_stock_strategy_high_tight_flag`、`cn_stock_attention`
* **数据来源**：历史日线数据 + `instock.core.strategy.high_tight_flag` 算法。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-strategy-high-tight-flag`
  - **执行命令**：`python instock/job/strategy_data_daily_job.py`

---

### 27. 放量跌停策略
* **页面名称**：放量跌停
* **页面地址**：`/instock/data?table_name=cn_stock_strategy_climax_limitdown`
* **功能与作用**：恐慌盘博弈反弹策略。监控个股连续跌停或盘中跌停但爆出巨量（巨额换手/大单翘板），寻找恐慌盘释放完毕后的左侧/超跌博弈机会。
* **关联页面**：点击代码跳转至 K 线详情图。
* **涉及数据表**：`cn_stock_strategy_climax_limitdown`、`cn_stock_attention`
* **数据来源**：历史日线数据 + `instock.core.strategy.climax_limitdown` 算法。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-strategy-climax-limitdown`
  - **执行命令**：`python instock/job/strategy_data_daily_job.py`

---

### 28. 低 ATR 成长策略
* **页面名称**：低ATR成长
* **页面地址**：`/instock/data?table_name=cn_stock_strategy_low_atr`
* **功能与作用**：低波动蓄势策略。筛选上市满 250 天、长期处于低 ATR 波动窄幅盘整、均线高度粘合、即将选择向上突破方向的成长股。
* **关联页面**：点击代码跳转至 K 线详情图。
* **涉及数据表**：`cn_stock_strategy_low_atr`、`cn_stock_attention`
* **数据来源**：历史日线数据 + `instock.core.strategy.low_atr` 算法。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-strategy-low-atr`
  - **执行命令**：`python instock/job/strategy_data_daily_job.py`

---

## 八、详情交互与可视化图表

### 29. 股票指标与 K 线/筹码分布可视化页面
* **页面名称**：股票指标数据 (Bokeh 交互式 K 线与筹码图)
* **页面地址**：`/instock/data/indicators?code=<code>&date=<date>&name=<name>`
* **功能与作用**：
  1. 渲染交互式 Bokeh K 线图（含 MA5/10/20/30/60、成交量量能柱、MACD / KDJ / RSI 等多子图联动）。
  2. 实时计算并展示 **CYQ 筹码成本分布曲线**（获利盘比例、90% 筹码集中度、70% 筹码集中度、主力平均持仓成本）。
  3. 提供右上角 **【关注 / 取关】** 按钮，点击通过 Ajax 将个股写入/移出自选股表 `cn_stock_attention`。
* **关联页面**：
  - 由全系统所有表格页面的股票代码超链接点击直达
  - 异步关注接口：`/instock/control/attention?code=<code>&otype=<0/1>`
* **涉及数据表**：`cn_stock_attention`（读写自选状态）
* **数据来源**：实时调取新浪/腾讯个股历史行情日线（`stf.fetch_stock_hist` / `stf.fetch_etf_hist`）并进行动态图形生成。
* **任务 ID 与执行命令**：Web 容器动态按需渲染，无需离线落库 Job。

---

## 九、胜率回测计算体系

### 30. 策略胜率回测作业 (后台驱动)
* **功能与作用**：针对买入指标表（`cn_stock_indicators_buy`）和 10 大选股策略表中的历史选股结果，批量计算未来第 1、2、3、5、10、20 至 100 个交易日的区间收益率与胜率统计。
* **涉及数据表**：`cn_stock_backtest_data` 以及各个策略表内嵌的 `rate_1` ~ `rate_100` 字段。
* **任务 ID 与执行命令**：
  - **任务 ID**：`stock-backtest-daily`
  - **执行命令**：`python instock/job/backtest_data_daily_job.py`

---

## 十、任务ID与运维执行命令汇总表

| 任务类别 | 任务 ID | 执行命令 | 触发方式 / 调度周期 |
| :--- | :--- | :--- | :--- |
| **数据库初始化** | `stock-db-init` | `python instock/job/init_job.py` | 首次部署 / 重建表结构 |
| **基础行情/资金流管线** | `daily_fetch_pipeline` | `python instock/job/daily_fetch_pipeline.py` | 盘后 15:30 (支持 `--only-failed` 重试) |
| **带回执的每日全流程** | `daily-pipeline-receipt`| `python instock/job/run_daily_pipeline_with_receipt.py` | 工作日定时任务 `cron/cron.workdayly/run_workdayly` |
| **每日完整任务作业** | `stock-execute-daily` | `python instock/job/execute_daily_job.py` | 每个交易日盘后 16:00 |
| **技术指标批量计算** | `stock-indicators` | `python instock/job/indicators_data_daily_job.py` | 行情入库后执行 |
| **K线形态识别计算** | `stock-klinepattern` | `python instock/job/klinepattern_data_daily_job.py` | 行情入库后执行 |
| **策略选股计算** | `stock-strategies` | `python instock/job/strategy_data_daily_job.py` | 指标/形态完成后执行 |
| **策略收益率胜率回测** | `stock-backtest` | `python instock/job/backtest_data_daily_job.py` | 策略入库后执行 |
| **Web 控制台服务** | `stock-web-service` | `python instock/web/web_service.py` | 常驻后台 / Supervisor |
