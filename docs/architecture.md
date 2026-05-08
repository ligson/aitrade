# 架构总览

## 仓库结构

当前仓库采用前后端并存布局：

- `aitrade-be/`：Python 后端，包含 FastAPI Web API、交易任务执行内核、配置、脚本与打包逻辑
- `aitrade-fe/`：Vue 3 管理台，包含登录、系统设置、交易任务、任务日志、交易日志、策略配置、历史数据管理与策略回测页面

根目录保留少量兼容脚本：

```bash
bash init-env.sh
bash package.sh
bash query-trades.sh latest 20
bash deploy.sh chenws-japan
```

这些脚本只做薄转发，实际都在 `aitrade-be/` 内执行。

## 后端分层

后端已经收敛为一条主入口：

- Web API：`python -m aitrade.web_runner`

后台控制脚本：

- `aitrade-be/start-web.sh`
- `aitrade-be/status-web.sh`
- `aitrade-be/stop-web.sh`

Web 服务启动后不会自动运行交易任务；交易任务由管理台通过 API 启动和停止。

### 运行入口

- `aitrade-be/aitrade/web_runner.py`：Web API 入口，负责加载配置、初始化日志、启动 FastAPI + Uvicorn
- `aitrade-be/aitrade/web/app.py`：FastAPI 应用装配点，负责挂载认证、系统、策略、日志、回测等模块

### 交易任务执行链路

虽然仓库已经 Web-only，但交易任务运行仍复用统一执行内核：

- `aitrade-be/aitrade/web/modules/system/trade_task_service.py`：维护任务配置、运行快照、运行状态和任务日志；在启动任务时组装运行态配置
- `aitrade-be/aitrade/trade/trade.py`：`OptimizedCryptoBot` 轻量封装
- `aitrade-be/aitrade/trade/trading_system/trading_bot.py`：主调度器，按周期拉取行情、生成信号、执行交易、处理止损与等待下一轮

当前链路是：
1. Web 服务读取 `config.yaml` 与系统设置
2. 任务启动时读取所选交易任务配置并生成 run snapshot
3. `trade_task_service.py` 把“系统级生效配置 + 任务快照”组装为任务运行态配置
4. 创建 `OptimizedCryptoBot` 并驱动 `TradingBot` 周期执行

### 配置分层

- `config.yaml`：部署级和系统启动级配置，如代理、监听端口、`app.data_root_dir`、`freqtrade_bin`
- 系统设置（数据库）：AI 参数、持仓持久化默认值、历史数据/回测默认值等
- 用户交易所设置（数据库）：按用户维护 `exchange type / api_key / api_secret / password`
- 交易任务配置（数据库）：交易对、周期、策略配置引用、交易方式、执行参数等
- 运行快照（数据库）：任务启动时冻结的最终参数，包含当次使用的交易所配置，运行中不回读页面后续修改

### 策略层

策略抽象位于 `aitrade-be/aitrade/trade/strategies/`：

- `base_strategy.py`：统一策略接口
- `gpt_strategy.py`：AI 信号策略
- `btc_spot_breakout_strategy.py`：BTC 现货突破策略
- `btc_spot_trend_breakout_strategy.py`：BTC 现货趋势突破策略
- `factory.py`：按配置创建策略实例
- `registry.py`：策略定义、展示名、默认参数与参数 schema
- `fusion_profile.py`：多源融合策略结构化 profile 的归一、摘要与运行态参数适配

### GPT 信号链路

- `aitrade-be/aitrade/trade/gpt_signal/signal_generator.py`
- `technical_analyzer.py`
- `market_analyzer.py`
- `prompt_builder.py`
- `response_parser.py`

这条链路负责技术指标总结、市场环境分析、提示词构造、模型调用与结果解析。

### 持久化层

默认通过 SQLAlchemy 同步 ORM 写入：

- `app.data_root_dir/trades.sqlite3`（默认 `sqlite:///~/.aitrade/trades.sqlite3`）

交易记录与任务运行相关核心表包括：
- `trade_records`
- `position_state`
- `trade_task_profiles`
- `trade_task_runs`
- `trade_task_logs`
- `trade_task_runtime`

## 前端分层

前端基于：

- Vue 3
- TypeScript
- Vite
- Pinia
- Vue Router
- ant-design-vue

主要结构如下：

- `aitrade-fe/src/layouts/BasicLayout.vue`：后台整体布局
- `aitrade-fe/src/router/index.ts`：路由与登录态守卫
- `aitrade-fe/src/api/`：Axios 封装与业务 API
- `aitrade-fe/src/views/trade-logs/TradeTaskControlView.vue`：任务中心页，统一承载任务配置、运行状态与详情抽屉
- `aitrade-fe/src/views/trade-logs/TradeTaskProfileView.vue`：旧交易任务配置页实现，当前主要保留为历史兼容与可复用逻辑来源
- `aitrade-fe/src/views/trade-logs/TradeTaskLogView.vue`：任务日志页
- `aitrade-fe/src/views/strategies/`：策略配置页
- `aitrade-fe/src/views/backtests/`：历史数据管理与回测页
- `aitrade-fe/src/views/system/`：系统概览、AI 设置、交易设置、数据设置、部署设置、系统日志页

## 本地联调关系

当前本地开发默认采用：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:18081`

开发环境中，前端通过 Vite 代理把 `/api` 与 `/health` 转发到后端，避免浏览器直连后端时触发 CORS。

## 运行态与目录边界

后端程序目录统一位于 `aitrade-be/`：

- `config.yaml`
- `.venv/`
- `.aitrade/`
- `logs/`
- `dist/`

后端业务数据默认派生到 `app.data_root_dir`（默认 `~/.aitrade/`）。不要再把新的后端运行态文件放回仓库根目录。
