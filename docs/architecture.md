# 架构总览

## 仓库结构

当前仓库采用前后端并存布局：

- `aitrade-be/`：Python 后端，包含交易机器人、FastAPI Web API、配置、脚本与打包逻辑
- `aitrade-fe/`：Vue 3 管理台，包含登录、用户维护、交易日志查询、策略配置、历史数据管理与策略回测页面

根目录保留了一组兼容脚本：

```bash
bash init-env.sh
bash start.sh
bash status.sh
bash stop.sh
bash query-trades.sh latest 20
bash package.sh
```

这些脚本只做薄转发，实际都在 `aitrade-be/` 内执行。

## 后端分层

后端入口分为两条主线：

- Bot 主链路：`python -m aitrade`
- Web API：`python -m aitrade.web_runner`

核心分层如下：

### 运行入口

- `aitrade-be/aitrade/__main__.py`：Bot 入口，负责初始化日志、加载配置、启动交易主循环
- `aitrade-be/aitrade/web_runner.py`：Web API 入口，负责启动 FastAPI + Uvicorn

### 交易主链路

- `aitrade-be/aitrade/trade/trading_system/trading_bot.py`：主调度器，按周期拉取行情、生成信号、执行交易、处理止损与休眠
- `aitrade-be/aitrade/trade/trading_system/market_data_fetcher.py`：行情获取与指标整理
- `aitrade-be/aitrade/trade/trading_system/risk_manager.py`：风控检查与仓位计算
- `aitrade-be/aitrade/trade/trading_system/trade_executor.py`：下单执行、持仓状态、交易记录落库

### 策略层

策略抽象位于 `aitrade-be/aitrade/trade/strategies/`：

- `base_strategy.py`：统一策略接口
- `gpt_strategy.py`：AI 信号策略
- `btc_spot_breakout_strategy.py`：BTC 现货突破策略
- `factory.py`：按配置创建策略实例
- `registry.py`：策略定义、展示名、默认参数与参数 schema

### GPT 信号链路

- `aitrade-be/aitrade/trade/gpt_signal/signal_generator.py`
- `technical_analyzer.py`
- `market_analyzer.py`
- `prompt_builder.py`
- `response_parser.py`

这条链路负责技术指标总结、市场环境分析、提示词构造、模型调用与结果解析。

### 持久化层

交易持久化当前通过 `TradeStore` 抽象统一：

- `aitrade-be/aitrade/trade/trading_system/trade_store.py`
- `trade_store_factory.py`
- `sqlalchemy_trade_store.py`
- `sqlite_trade_store.py`

默认配置会把交易记录与持仓快照写入：

- `aitrade-be/.aitrade/trades.sqlite3`

### Web API 层

FastAPI 应用位于：

- `aitrade-be/aitrade/web/app.py`

当前挂载的模块包括：

- `api/auth`：登录、验证码、当前用户、退出登录
- `api/users`：用户分页、创建、更新、重置密码、状态切换
- `api/trade-logs`：交易日志分页、当前持仓、筛选选项
- `api/strategies`：策略定义、策略配置列表、保存、删除
- `api/backtests`：历史数据管理、回测任务创建、任务详情与成交明细查询

统一响应结构为：

```json
{
  "success": true,
  "message": "",
  "trace": "",
  "httpCode": 200,
  "data": {}
}
```

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
- `aitrade-fe/src/stores/auth.ts`：登录态与用户恢复
- `aitrade-fe/src/api/`：Axios 封装与业务 API
- `aitrade-fe/src/views/login/`：登录页
- `aitrade-fe/src/views/trade-logs/`：交易日志页
- `aitrade-fe/src/views/strategies/`：策略配置页
- `aitrade-fe/src/views/backtests/BacktestDataView.vue`：历史数据管理页
- `aitrade-fe/src/views/backtests/BacktestView.vue`：策略回测页
- `aitrade-fe/src/views/users/`：用户管理页

## 本地联调关系

当前本地开发默认采用：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:18080`

开发环境中，前端通过 Vite 代理把 `/api` 与 `/health` 转发到后端，避免浏览器直连后端时触发 CORS。

## 运行态与目录边界

后端运行文件统一位于 `aitrade-be/`：

- `config.yaml`
- `.venv/`
- `.aitrade/`
- `logs/`
- `dist/`

不要再把新的后端运行态文件放回仓库根目录。

## 文档边界

当前建议的文档分层：

- 根目录 `README.md`：仓库导航与快速入口
- 根目录 `CLAUDE.md`：Claude 协作规则与仓库边界
- `docs/`：架构、模块、接口与运维说明
- `aitrade-be/README.md` / `aitrade-be/CLAUDE.md`：后端运行与实现约束
