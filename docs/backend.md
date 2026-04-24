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

### Bot 主链路

```bash
cd aitrade-be
uv run python -m aitrade
```

### Web API

```bash
cd aitrade-be
uv run python -m aitrade.web_runner
```

### 后台脚本

```bash
cd aitrade-be
bash start.sh
bash status.sh
bash stop.sh
```

### Web 专用脚本

```bash
cd aitrade-be
bash start-web.sh
bash status-web.sh
bash stop-web.sh
```

当前仓库已经提供 Web 专用后台脚本；如需本地调试，也可以直接前台执行 `uv run python -m aitrade.web_runner`。

## 配置模型

运行时配置由：

- `aitrade-be/aitrade/config/config_file.py`

从 `config.yaml` 加载。

核心配置包括：

- `app.gpt`：模型提供方、API Key、模型名
- `app.exchange`：交易所类型、凭证，以及可选的 OKX 密码
- `app.http_client`：代理开关与代理地址
- `app.web`：Web API 地址、JWT、CORS、验证码、初始化管理员等配置
- `app.trade`：交易对、周期、策略、持久化等配置

### 策略切换

```yaml
app:
  trade:
    strategy:
      type: gpt
```

或：

```yaml
app:
  trade:
    strategy:
      type: btc_spot_breakout
```

## 持久化与查询

默认持久化通过 SQLAlchemy 同步 ORM 写入：

- `sqlite:///./.aitrade/trades.sqlite3`

主要表：

- `trade_records`：交易记录
- `position_state`：持仓快照

本地查询推荐脚本：

```bash
bash query-trades.sh latest 20
bash query-trades.sh strategy gpt 20
bash query-trades.sh side buy 20
bash query-trades.sh failed 20
bash query-trades.sh position
```

## Web API 模块

### 认证接口

- `POST /api/auth/captcha`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/me`
- `POST /api/auth/logout`

登录要求用户名、密码、图形验证码。验证码错误、过期、已使用等情况会返回统一业务错误结构。

### 用户接口

- `POST /api/users/page`
- `POST /api/users/create`
- `POST /api/users/update`
- `POST /api/users/reset-password`
- `POST /api/users/change-status`

### 交易日志接口

- `POST /api/trade-logs/page`
- `POST /api/trade-logs/positions`
- `POST /api/trade-logs/filter-options`

其中日志分页筛选支持：

- `strategy`
- `side`
- `result`
- `symbol`
- `createdFrom`
- `createdTo`

### 策略接口

- `POST /api/strategies/definitions`
- `POST /api/strategies/list`
- `POST /api/strategies/save`
- `POST /api/strategies/delete`

### 历史数据与回测接口

- `POST /api/backtests/data/options`
- `POST /api/backtests/data/catalog`
- `POST /api/backtests/data/download`
- `POST /api/backtests/data/export`
- `POST /api/backtests/data/import`
- `POST /api/backtests/data/delete`
- `POST /api/backtests/run`
- `POST /api/backtests/stop`
- `POST /api/backtests/page`
- `POST /api/backtests/detail`
- `POST /api/backtests/trades`

当前历史数据与回测链路约束：

- 历史数据下载不再让前端输入时间范围，统一按 `app.backtest.download_timerange` 下载到当前时点
- 可选交易对来自 `app.backtest.supported_symbols`
- 可选周期来自 `app.backtest.supported_timeframes`，默认支持 `5m / 15m / 30m / 1h / 4h / 1d`
- 历史数据导入导出统一使用 zip 压缩包
- 回测优先按历史文件发起，任务数据源会记录文件名、路径、格式、大小和文件时间范围
- 回测任务创建前由前端先展示确认信息，用户确认后才调用 `/api/backtests/run`
- 回测运行中支持通过 `/api/backtests/stop` 发起协作式停止，状态流转为 `pending -> running -> stop_requested -> stopped`
- 回测任务会持续写入 `progress_current`、`progress_total`、`estimated_finish_at`、`last_progress_at`、`stop_requested_at`，旧 SQLite 表会在服务初始化时自动补齐新增列

### 系统设置与系统日志接口

- `POST /api/system/settings`
- `POST /api/system/logs/files`
- `POST /api/system/logs/content`

当前 system 模块职责：

- 返回历史数据目录、Freqtrade `user_data` 目录、日志目录与关键只读配置
- 分页列出 `logs/` 目录下的日志文件，并区分应用日志与交易日志类型
- 按文件读取最后若干行日志内容
- 限制日志读取范围在 `logs/` 目录内，拒绝路径穿越与非 `.log` 文件访问

## 重要实现约束

- 配置路径固定为 `./config.yaml`，所以必须保证工作目录正确。
- 后端运行态保存在 `.aitrade/`，日志保存在 `logs/`。
- 当前缺少正式测试套件，验证方式以定向冒烟为主。
- 网络相关代码如遇连接失败、超时等问题，日志必须清晰包含错误信息、失败位置和上下文。
- `restore_position_on_startup` 默认应保持 `false`，避免本地快照与真实交易所状态不一致时自动恢复。
