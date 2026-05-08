aitrade
=================================
A simple trading system for AI.

## 项目位置

当前后端位于 `aitrade-be/` 子目录中。

本文档描述的是 **后端子项目**，默认工作目录就是 `aitrade-be/`。

## 当前运行模式

后端现已收敛为 **Web-only**：

- 唯一启动入口：`uv run python -m aitrade.web_runner`
- 后台脚本：`bash start-web.sh / status-web.sh / stop-web.sh`
- 交易任务由管理台页面启动、停止和查看状态
- 不再支持独立 `uv run python -m aitrade` 或 `bash start.sh / status.sh / stop.sh`

## 配置

1. 复制 `config.example.yaml` 为 `config.yaml`
2. Web 场景下，`config.yaml` 的最小必留项已经收敛到：`app.http_client`、`app.data_root_dir`、`app.web.port / jwt_secret / cors_allow_origins`、`app.backtest.freqtrade_bin`
3. 交易所类型、`api_key`、`api_secret` 与 OKX `password` 已改为由管理台“交易所设置”页按用户维护，因此本地 `config.yaml` 不再要求保留 `app.exchange`
4. `config.example.yaml` 现在就是按这套最小模板提供示例；`host / debug / show_trace / jwt 过期时间 / captcha 过期时间 / init_admin` 等未写出的 Web 参数会直接使用代码默认值
5. Web 管理台中的“系统设置”页会把一部分系统参数保存到数据库，其中 AI 设置页负责 `app.gpt.provider / model / api_key / base_url`，交易设置页负责 `app.trade.persistence.persist_position / restore_position_on_startup`、`app.trade.market_feeds.trade_flow.*`，数据设置页负责 `app.backtest.supported_* / default_* / download_timerange / data_format_ohlcv / export_archive_format`
6. 管理台“部署设置”页会直接写回后端 `config.yaml`，现在只维护 `app.data_root_dir` 这一个部署级数据根目录；SQLite、系统日志、历史数据目录与 Freqtrade `user_data` 目录都会由它自动派生，保存后通常需要重启后端才能完全生效
7. `config.yaml` 不再要求保留任务级交易参数；真实交易任务参数以数据库任务配置、用户交易所设置和启动快照为准
8. 若用户尚未在“交易所设置”页完成凭证配置，任务启动会被明确拦截
9. 默认会把结构化交易记录写入 `sqlite:///~/.aitrade/trades.sqlite3`

## 初始化与运行

推荐在 `aitrade-be/` 目录执行以下命令：

```bash
bash init-env.sh
bash start-web.sh
bash status-web.sh
bash stop-web.sh
```

### 管理台控制交易任务

当前 Web 管理台已经支持在“交易中心”下统一维护和查看交易任务：

- `任务中心` 页把任务配置、运行状态与排障抽屉收敛到同一主工作区
- `任务中心` 会按任务配置展示独立 runner，可在概览 / 配置 / 运行三个视图中切换
- 开始运行时先生成数据库快照，再按快照驱动本次任务
- `任务日志` 页可按 runner / runId 查看数据库事件日志，并返回任务中心继续处理

补充约束：

- Web 服务启动后**不会自动运行**交易任务
- 页面开始任务时，任务级参数以数据库配置与启动快照为准
- 页面后续修改任务配置，不会影响已经运行中的任务实例
- 手续费率、滑点率、单日亏损停机开关与阈值属于任务级执行参数：系统设置只提供新建任务默认值，真正生效值保存在任务配置，并在启动时固化到本次 run snapshot
- Web 场景下，系统设置页保存的非敏感参数会覆盖 `config.yaml` 中对应的 `app.gpt`、`app.trade.persistence` 和 `app.backtest` 字段，并作用于后续新回测/新任务
- AI 密钥与可选 Base URL 已迁到“AI 设置”页维护；交易所凭证已迁到“交易所设置”页按用户维护，代理、监听地址、目录路径和外部命令等部署期配置仍只来自 `config.yaml`
- 系统会为每条任务配置自动分配独立 `runnerName`，当前版本支持不同交易对并发运行；同一交易对仍不支持并发启动

当前 Web API 主要服务 `aitrade-fe/` 管理台，默认本地联调地址如下：

- 前端开发服务：`http://127.0.0.1:5173`
- 后端 Web API：`http://127.0.0.1:18081`
- 健康检查：`GET /health` 或 `POST /health`

这里的 `18081` 是本地联调约定；远端正式部署当前默认仍使用 `app.web.port=18080`。

### `bash init-env.sh`

- 使用 `uv` 按 `.python-version` 固定的 Python `3.14` 创建并同步 `.venv/`
- 依赖来源为 `pyproject.toml` 与 `uv.lock`
- 如果不存在 `config.yaml`，会从 `config.example.yaml` 自动生成
- 执行结束后会提示下一步编辑配置再启动 Web

### `bash start-web.sh`

- 自动以 `aitrade-be/` 作为后端项目根目录启动，避免 `./config.yaml` 路径错误
- 启动前会先校验 `config.yaml`，配置错误会直接输出具体配置项和原因
- 使用 `.venv/bin/python -m aitrade.web_runner` 后台运行
- PID 文件等程序控制运行态仍写入 `aitrade-be/.aitrade/`
- 结构化交易记录、历史数据、Freqtrade `user_data` 与 Python 应用日志默认按 `app.data_root_dir`（默认 `~/.aitrade/`）自动派生
- 启动辅助日志当前仍写入 `aitrade-be/logs/web-launcher.log`
- 启动失败时会输出最近的启动辅助日志和应用日志，便于快速定位原因

### `bash status-web.sh`

- 展示 `running / stopped / stale` 状态
- 展示 PID、启动时间、配置文件路径、日志目录、监听 PID
- 主日志以当前 `app.data_root_dir/logs`（默认 `~/.aitrade/logs/`）下的 Python 日志为准

### `bash stop-web.sh`

- 优先优雅停止
- 超时后自动强制停止
- 已停止或运行态陈旧时会做幂等清理

## 策略与任务运行

当前支持四类可配置策略：

- `gpt`：通过兼容 OpenAI 的客户端生成 AI 交易信号
- `btc_spot_breakout`：面向 BTC 现货的 long-only 单周期规则突破策略
- `btc_spot_trend_breakout`：面向 BTC 现货的 long-only 趋势突破策略，固定 `1h` 执行并使用 `4h` 趋势过滤
- `spot_multi_signal_fusion`：现货多源融合策略，可选择已有 K 线策略档案、内建技术面节点和独立信号源档案参与融合

这些策略不再通过 `config.yaml` 直接切换运行，而是通过策略配置页、任务配置页与运行快照驱动。

## 交易记录持久化

- 默认通过 SQLAlchemy 同步 ORM 把交易执行结果写入 `app.data_root_dir/trades.sqlite3`（默认即 `sqlite:///~/.aitrade/trades.sqlite3`）
- 默认会持久化当前本地持仓、止损和追踪止损状态到 `position_state` 表
- 新配置推荐只维护 `app.data_root_dir`；运行时会自动派生本地 SQLite 地址。旧 `app.trade.persistence.database_url / sqlite_path` 仍可读取兼容，但部署设置页新保存会收敛回单根目录模型
- `app.trade.persistence.restore_position_on_startup` 默认是 `false`，避免本地快照与真实交易所状态不一致时自动恢复

常见查询方式：

```bash
bash query-trades.sh latest 20
bash query-trades.sh strategy gpt 20
bash query-trades.sh side buy 20
bash query-trades.sh failed 20
bash query-trades.sh position
```
