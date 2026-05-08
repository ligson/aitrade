# 后端说明

## 项目位置

后端项目根目录为：

- `aitrade-be/`

默认工作目录应保持在 `aitrade-be/`，因为运行时配置固定读取 `./config.yaml`。

## 环境准备

推荐执行：

```bash
cd aitrade-be
bash init-env.sh
```

初始化流程会：

- 使用 `uv` 按 `.python-version` 固定的 Python `3.14` 创建 `.venv/`
- 根据 `pyproject.toml` 与 `uv.lock` 同步依赖
- 在缺少 `config.yaml` 时从 `config.example.yaml` 自动生成

## 启动方式

### Web API 前台调试

```bash
cd aitrade-be
uv run python -m aitrade.web_runner
```

### Web 后台脚本

```bash
cd aitrade-be
bash start-web.sh
bash status-web.sh
bash stop-web.sh
```

当前仓库已经收敛为 Web-only，不再支持 `python -m aitrade` 或 `start.sh / status.sh / stop.sh` 的独立 Bot/CLI 直跑入口。

## 配置模型

运行时配置由 `aitrade-be/aitrade/config/config_file.py` 从 `config.yaml` 加载。

Web 场景最小必留项包括：

- `app.http_client`：代理开关与代理地址
- `app.data_root_dir`：部署级数据根目录
- `app.web`：至少保留 `port / jwt_secret / cors_allow_origins`
- `app.backtest`：至少保留 `freqtrade_bin`
- `app.trade.persistence`：保留结构占位，运行时由系统设置与任务快照补齐持久化/执行相关参数

补充说明：

- Web 管理台“系统设置”页会把一部分系统参数保存到数据库，并在 Web 场景下覆盖 `config.yaml` 中对应字段
- Web 管理台“交易所设置”页会按用户保存交易所类型与凭证，因此 Web 场景不再要求在 `config.yaml` 中保留 `app.exchange`
- “部署设置”页会直接写回 `config.yaml`，当前只维护 `app.data_root_dir`
- 真实交易任务参数由数据库任务配置、用户交易所设置和启动快照决定，不要求用户在 `config.yaml` 中手动填写任务级字段
- 任务真正运行前，会把系统级生效配置、用户交易所设置与任务快照组装成运行态配置，并做严格校验；若用户未配置交易所凭证，启动会被明确拦截

## 交易任务运行链路

Web-only 后，交易任务仍复用统一执行内核：

1. Web 服务启动后加载 `config.yaml`
2. 系统设置页维护 AI、交易默认值、历史数据/回测默认值等非部署级参数
3. 交易任务页维护任务配置
4. 启动任务时生成 run snapshot
5. `trade_task_service.py` 把系统级生效配置与 snapshot 合并为任务运行态配置
6. 创建 `OptimizedCryptoBot` 驱动 `TradingBot` 执行周期

因此不要把 `trade/trading_system/*`、`trade/trade.py`、`trade/strategies/*` 误判为“旧 Bot 代码”；它们仍是 Web 任务执行内核。

## 持久化与查询

默认通过 SQLAlchemy 同步 ORM 写入：

- `sqlite:///~/.aitrade/trades.sqlite3`

主要表：

- `trade_records`：交易记录
- `position_state`：持仓快照
- `trade_task_profiles`：任务配置档案
- `trade_task_runs`：任务运行快照
- `trade_task_logs`：任务运行事件日志
- `trade_task_runtime`：当前运行态

本地查询推荐脚本：

```bash
bash query-trades.sh latest 20
bash query-trades.sh strategy gpt 20
bash query-trades.sh side buy 20
bash query-trades.sh failed 20
bash query-trades.sh position
```

## Web API 模块

当前主要模块包括：

- `api/auth`：登录、验证码、当前用户、退出登录
- `api/users`：用户分页、创建、更新、重置密码、状态切换
- `api/trade-logs`：交易日志分页、当前持仓、筛选选项
- `api/strategies`：策略定义、策略配置列表、保存、删除
- `api/backtests`：历史数据管理、回测任务创建、任务详情与成交明细查询
- `api/system`：系统概览、系统设置、部署设置、日志查看、任务中心、任务日志等

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

## 重要实现约束

- 配置路径固定为 `./config.yaml`，因此脚本必须在 `aitrade-be/` 目录执行，或通过仓库根目录兼容脚本转发到这里。
- 后端程序控制运行态保存在 `aitrade-be/.aitrade/`，shell 启动辅助日志保存在 `aitrade-be/logs/`。
- 默认业务数据目录按 `app.data_root_dir`（默认 `~/.aitrade/`）自动派生。
- 当前缺少正式测试套件，验证方式以定向冒烟为主。
- 网络相关代码如遇连接失败、超时等问题，日志必须清晰包含错误信息、失败位置和上下文。
- `restore_position_on_startup` 默认应保持 `false`，避免本地快照与真实交易所状态不一致时自动恢复。
