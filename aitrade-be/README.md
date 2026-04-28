aitrade
=================================
A simple trading system for AI.

## 项目位置

当前后端已迁移到 `aitrade-be/` 子目录中。

本文档描述的是 **后端子项目**，默认工作目录就是 `aitrade-be/`。

## 配置

1. 复制 `config.example.yaml` 为 `config.yaml`
2. Web 场景下，`config.yaml` 只需要保留仍然由文件负责的系统级配置：交易所凭证、代理、Web 服务参数、持久化数据库连接，以及回测目录/外部命令
3. Web 管理台中的“系统设置”页会把一部分系统参数保存到数据库，其中 AI 设置页负责 `app.gpt.provider / model / api_key / base_url`，交易设置页负责 `app.trade.persistence.persist_position / restore_position_on_startup`、`app.trade.market_feeds.trade_flow.*`，数据设置页负责 `app.backtest.supported_* / default_* / download_timerange / data_format_ohlcv / export_archive_format`
4. 因此 `config.example.yaml` 已按 Web 场景精简，不再保留上述可网页维护字段；首次打开系统设置页时，会基于文件中的当前值或运行时默认值初始化数据库记录
5. 如果你只启动 Web 管理台，`config.yaml` 不再要求保留任务级交易参数；真实交易任务参数以数据库任务配置和启动快照为准
6. 如果你要直接运行 Bot（`uv run python -m aitrade` / `bash start.sh`），再额外补齐 `app.trade.trade_mode / paper_balance / symbol / timeframe / limit / strategy.*`；其中 `trade_mode` 支持 `live / sandbox / paper`，旧 `sandbox_trade` 仍可兼容映射为 `sandbox / live`
7. `app.trade.strategy.type` 仅在 Bot/CLI 直跑场景下用于切换交易策略：
   - `gpt`：保留原有 AI 信号策略
   - `btc_spot_breakout`：BTC 现货 long-only 单周期突破策略
   - `btc_spot_trend_breakout`：BTC 现货趋势突破策略，固定 `1h` 执行并使用 `4h` 趋势过滤
   - `spot_multi_signal_fusion`：现货多源融合策略，第一阶段综合技术面与成交流信号，优先用于 `paper` 实时模拟验证
8. 默认会把结构化交易记录写入 `sqlite:///./.aitrade/trades.sqlite3`

## 初始化与运行

推荐在 `aitrade-be/` 目录执行以下命令：

```bash
bash init-env.sh
bash start.sh
bash status.sh
bash stop.sh
```

如需从仓库根目录执行，也可以使用同名兼容脚本，它们会自动转发到 `aitrade-be/`。

当前后端包含两个入口方向：

- Bot：`uv run python -m aitrade`
- Web：`uv run python -m aitrade.web_runner`

其中：

- `start.sh / status.sh / stop.sh` 主要服务 Bot 运行链路
- `start-web.sh / status-web.sh / stop-web.sh` 负责 Web 服务的后台启动、状态查看与停止

### 管理台控制交易任务

当前 Web 管理台已经支持在“交易中心”下分别控制和查看交易任务：

- `交易任务配置` 页维护多套交易任务配置
- 在 `交易任务控制` 页选择一套启用中的任务配置开始运行，并查看当前状态
- 开始运行时先生成数据库快照，再按快照驱动本次任务
- 在 `交易任务控制` 页停止当前交易任务
- 在 `交易任务控制` 页运行中自动轮询状态
- 在 `任务日志` 页查看最近一次到多次运行的数据库事件日志

补充约束：

- Web 服务启动后**不会自动运行**交易任务
- 页面开始任务时，任务级参数以数据库配置与启动快照为准
- 页面后续修改任务配置，不会影响已经运行中的任务实例
- 手续费率、滑点率、单日亏损停机开关与阈值属于任务级执行参数：系统设置只提供新建任务默认值，真正生效值保存在任务配置，并在启动时固化到本次 run snapshot
- Web 场景下，`config.yaml` 只要求保留系统级配置与 `app.trade.persistence`；不再要求保留任务级交易参数占位
- Web 场景下，系统设置页保存的非敏感参数会覆盖 `config.yaml` 中对应的 `app.gpt`、`app.trade.persistence` 和 `app.backtest` 字段，并作用于后续新回测/新任务
- AI 密钥与可选 Base URL 已迁到“AI 设置”页维护；交易所凭证、数据库连接、代理、监听地址、目录路径和外部命令等部署期配置仍只来自 `config.yaml`
- CLI/Bot 直跑场景下，仍需在 `config.yaml` 中提供 `trade_mode / paper_balance / symbol / timeframe / limit / strategy.*`；旧 `sandbox_trade` 仍兼容，但新配置推荐统一使用 `trade_mode`
- 当前页面控制采用 Web 进程内单实例 Runner，只允许同一时刻有一个交易任务运行

当前 Web API 主要服务 `aitrade-fe/` 管理台，默认本地联调地址如下：

- 前端开发服务：`http://127.0.0.1:5173`
- 后端 Web API：`http://127.0.0.1:18081`
- 健康检查：`GET /health` 或 `POST /health`

这里的 `18081` 是本地联调约定；远端正式部署当前默认仍使用 `app.web.port=18080`。

### `bash init-env.sh`

- 使用 `uv` 按 `.python-version` 固定的 Python `3.14` 创建并同步 `.venv/`
- 依赖来源为 `pyproject.toml` 与 `uv.lock`
- 如果不存在 `config.yaml`，会从 `config.example.yaml` 自动生成
- 执行结束后会提示下一步编辑配置再启动

如果本机缺少 `uv`：
- macOS / Linux：按脚本提示先安装 `uv`，再重新执行初始化

### `bash start.sh`

- 自动以 `aitrade-be/` 作为后端项目根目录启动，避免 `./config.yaml` 路径错误
- 启动前会先校验 `config.yaml`，配置错误会直接输出具体配置项和原因
- 使用 `.venv/bin/python -m aitrade` 后台运行
- 运行态写入 `.aitrade/`
- 启动辅助日志写入 `logs/launcher.log`
- 启动失败时会输出最近的启动辅助日志和应用日志，便于快速定位原因

### `bash status.sh`

- 展示 `running / stopped / stale` 状态
- 展示 PID、启动时间、配置文件路径、日志目录
- 主日志以 `logs/` 下的 Python 日志为准

### `bash stop.sh`

- 优先优雅停止
- 超时后自动强制停止
- 已停止或运行态陈旧时会做幂等清理

## 配置

### GPT 策略

- 沿用原有 AI 信号生成链路
- 通过 `app.trade.strategy.gpt.min_confidence` 控制最小置信度
- `app.gpt.model` 可显式指定模型名，默认 `deepseek-chat`

### BTC 现货突破策略

默认策略名：`btc_spot_breakout`

该策略适用于 BTC 现货 long-only 场景，核心规则为：

- `Donchian(20)` 突破入场
- `EMA(96)` 趋势过滤
- EMA 斜率向上过滤
- 可选 `MACD histogram > 0` 确认
- 可选成交量放大确认
- `ATR(14)` 初始止损 + 追踪止损
- `Donchian(10)` 跌破辅助出场

> 默认参数为 15 分钟周期做了保守过滤，但 15 分钟噪音仍然较大，建议优先在沙盒环境观察信号质量。

### BTC 现货趋势突破策略

默认策略名：`btc_spot_trend_breakout`

该策略与旧 `btc_spot_breakout` 独立存在，固定语义为“`1h` 执行 + `4h` 趋势过滤”，核心规则为：

- 仅当 `4h EMA20 > EMA50` 且 `ADX` 达到阈值时，允许 `1h` 入场
- `1h close` 突破最近 `20` 根已完成 K 线高点时考虑做多
- 当前 `1h` 成交量需高于 `20` 均量乘数阈值
- 止损基于 `ATR`，止盈采用 `ATR` 追踪止损
- 仅支持 BTC 现货 long-only 场景

补充约束：

- 当前任务配置与 Bot/CLI 直跑都应使用 `1h` 作为执行周期
- live / paper / sandbox 会同时加载 `1h` 主周期数据与 `4h` 上下文数据
- 回测也会按 `1h` 驱动，并在每根 `1h` K 线决策时仅使用当时已闭合的 `4h` 数据，避免未来数据泄漏
- 若缺少 `4h` 历史数据，live 校验或回测会直接报错

### 现货多源融合策略

默认策略名：`spot_multi_signal_fusion`

该策略面向现货多源融合场景，当前第一阶段已升级为“结构化融合策略 profile + 可复用信号源档案”的配置模型，并继续复用现有统一 signal 执行链路。

当前融合策略 profile 由以下结构化字段组成：

- `klineNodes`：选择已有 K 线策略档案或内建技术面节点参与融合，并为每个节点维护启用状态、权重、快照参数与固定周期约束
- `signalSourceNodes`：选择已有信号源档案参与融合，并维护节点权重、是否必需、阈值与参数快照
- `filters`：维护最少可用节点数、是否允许降级、最低综合置信度、买卖阈值等门槛
- `riskControls`：维护共享 `ATR` 风控参数与默认单笔风险比例
- `decisionPolicy`：当前第一阶段固定为 `weighted_score`

第一阶段当前可实际参与运行时融合的节点包括：

- `builtin_technical`：内建技术面节点，基于 `EMA / 突破 / RSI / MACD / 成交量` 综合打分
- `btc_spot_breakout`：复用 BTC 单周期突破策略的核心判断，作为 K 线融合节点输出倾向
- `btc_spot_trend_breakout`：复用 `1h + 4h` 趋势突破策略的核心判断，作为 K 线融合节点输出倾向
- `trade_flow`：基于近期成交的买卖盘占比与名义金额失衡度打分的信号源节点

同时系统已新增独立信号源档案，当前支持：

- `trade_flow`
- `news`
- `indicator`
- `market_activity`
- `external_signal`

其中只有 `trade_flow` 在第一阶段已接入运行时，其余类型先提供配置落点与详情展示。

当前行为与约束：

- 融合策略列表与详情会展示 `K 线节点数 / 信号源节点数 / 最少可用节点数 / 固定周期约束` 摘要，交易任务页也会展示同类摘要，帮助快速判断是否适合当前任务配置
- 运行前会把融合策略结构化配置、被引用的 K 线策略档案、被引用的信号源档案以及相关系统默认值一起冻结进 run snapshot，运行中不再回查活跃配置
- 运行时仍会将结构化快照适配为当前第一阶段执行内核所需的参数，并继续输出 `signal_sources / signal_score / degraded / meta.node_signals` 便于任务日志和交易日志排障
- 最终止损与追踪止损继续由融合层统一按共享 `ATR` 参数生成，不直接复用子节点独立止损口径
- 仅支持现货场景，优先用于 `paper` 实时模拟验证
- 第一阶段尚未接入新闻、情绪、链上或动态数据源的真实运行时消费，也不支持真正 DAG/画布式编排器
- 当前注册表显式标记 `backtestSupported=false`，不进入正式回测链路
- 系统设置页中的 `trade_flow` feed 开关、新鲜度和回看成交数只影响后续新启动任务，运行中的实例继续使用启动快照
- 当 optional feed 缺失或过期时，若策略允许降级运行，会输出 `degraded=true` 而不是直接抛错失败
- 若所选 K 线节点中包含 `btc_spot_trend_breakout`，交易任务周期当前固定为 `1h`，并会额外装配 `4h` 上下文数据

### 交易记录持久化

- 默认通过 SQLAlchemy 同步 ORM 把交易执行结果写入 `sqlite:///./.aitrade/trades.sqlite3`
- 默认会持久化当前本地持仓、止损和追踪止损状态到 `position_state` 表
- 主配置项是 `app.trade.persistence.database_url`，将来可切到 MySQL 等数据库；`sqlite_path` 仅作为兼容旧配置的别名
- `app.trade.persistence.restore_position_on_startup` 默认是 `false`，避免本地快照与真实交易所状态不一致时自动恢复
- `trade_records` 会记录策略、时间、方向、价格、数量、原因、止损/追踪止损、订单结果、失败原因等字段
- 交易记录现已补齐 `fee_rate / slippage_rate / estimated_fill_price / estimated_fee / realized_pnl / realized_pnl_net / daily_loss_snapshot` 等执行成本与风控审计字段
- 后端运行态目录继续统一收敛在 `aitrade-be/`：`config.yaml`、`.venv/`、`.aitrade/`、`logs/`、`dist/` 都视为本地运行或打包产物，不应再在仓库根目录保留新的同类文件

常见查询方式：

```bash
bash query-trades.sh latest 20
bash query-trades.sh strategy gpt 20
bash query-trades.sh side buy 20
bash query-trades.sh failed 20
bash query-trades.sh position
```

## 交易方式

当前统一支持三种交易方式：

- `live` / 真实交易：真实行情，真实下单
- `sandbox` / 沙盒交易：沙盒行情，沙盒下单
- `paper` / 纸上交易：真实行情，不真实下单

兼容说明：

- 新配置推荐使用 `app.trade.trade_mode`
- 旧 `app.trade.sandbox_trade=true` 会自动映射为 `sandbox`
- 旧 `app.trade.sandbox_trade=false` 会自动映射为 `live`
- `app.trade.paper_balance` 用于纸上交易的本地虚拟 USDT 余额，默认 `10000`
- `app.trade.task_defaults.*` 仅提供新建任务默认值；`app.trade.execution.*` 表示某次运行快照里的真实执行参数
- `paper` 模式会按 `fee_rate / slippage_rate` 估算成交价与手续费；`live / sandbox` 优先使用交易所回包中的成交均价、金额和手续费，缺失时再按配置估算
- 任务级单日亏损停机当前按“当前 run + UTC 当日 + 卖出已实现净亏损”口径执行，达到阈值后停止后续周期，不会把该次停止记为失败

## 项目流程

程序启动后会按如下顺序循环执行：

1. 从交易所拉取 K 线和基础市场数据
2. 根据配置选择策略生成交易信号
3. 经过风控判断后执行下单
4. 持仓时动态更新止损位
5. 检查止损条件
6. 等待下一个交易周期

## Web 管理接口

当前 Web API 采用统一响应格式：

```json
{
  "success": true,
  "message": "",
  "trace": "",
  "httpCode": 200,
  "data": {}
}
```

已提供的管理台接口分组包括：

- `api/auth`：图形验证码、登录、当前用户、退出登录
- `api/users`：用户分页、创建、编辑、重置密码、状态切换
- `api/trade-logs`：交易日志分页、当前持仓
- `api/strategies`：策略定义、策略配置列表、保存、删除
- `api/signal-sources`：信号源定义、信号源配置列表、保存、删除
- `api/backtests`：历史数据管理、回测任务创建、任务详情与成交明细查询
- `api/system`：系统设置、系统日志、交易任务状态/启动/停止、任务日志分页查询

其中分页接口统一返回 `data.total`、`data.size`、`data.offset` 与 `data.data`。

### 历史数据管理与文件回测

- 历史数据管理统一复用 `api/backtests/data/*` 子接口，包含：
  - `POST /api/backtests/data/options`
  - `POST /api/backtests/data/catalog`
  - `POST /api/backtests/data/download`
  - `POST /api/backtests/data/export`
  - `POST /api/backtests/data/import`
  - `POST /api/backtests/data/delete`
- 历史数据由 freqtrade CLI 下载到 `app.backtest.data_dir`
- freqtrade 运行所需的 `user_data` 与最小 `config.json` 会由后端自动初始化到 `app.backtest.user_data_dir`
- 前端不再让用户输入下载时间范围，下载统一按 `app.backtest.download_timerange` 从最早范围执行到当前时点
- 历史数据管理页可选交易对来自 `app.backtest.supported_symbols`
- 导入与导出统一使用 zip 压缩包；导出压缩包内会附带 `manifest.json`
- 回测任务创建优先按历史文件发起，`data_source_json` 会记录文件名、路径、格式、大小和文件覆盖时间范围
- 回测任务当前支持 `feeRate` 与 `slippageRate` 两个成交成本参数；`slippageRate` 默认为 `0`
- `btc_spot_trend_breakout` 回测固定按 `1h` 主周期运行，并额外要求可用的 `4h` 历史数据
- 如果开启了 `app.http_client.proxy_enable`，回测历史数据下载会自动复用同一代理配置访问 Binance
- 若仍出现证书校验失败，通常是本机代理链路或证书环境问题，不是回测目录路径问题

## 核心结构

- `aitrade/__main__.py`：程序入口，负责日志初始化和加载 `config.yaml`
- `aitrade/trade/trading_system/trading_bot.py`：主循环调度与策略切换入口
- `aitrade/trade/strategies/`：策略抽象层，包含 GPT、K 线策略、结构化融合策略，以及融合 profile / signal source 定义注册与兼容归一逻辑
- `aitrade/trade/trading_system/market_data_fetcher.py`：行情获取与指标整理
- `aitrade/trade/gpt_signal/`：GPT 信号分析、提示词构建、响应解析
- `aitrade/trade/trading_system/risk_manager.py`：风控检查与仓位计算
- `aitrade/trade/trading_system/trade_executor.py`：下单、持仓状态、止损信息管理，以及结构化交易记录落库
- `aitrade/trade/trading_system/sqlalchemy_trade_store.py`：基于 SQLAlchemy 的交易记录查询与持仓快照持久化

## 当前限制

- 持仓状态会同时保存在进程内存和持久化存储中；默认数据库地址是 `sqlite:///./.aitrade/trades.sqlite3`，但默认不会在启动时自动恢复；如需恢复，需要显式打开 `app.trade.persistence.restore_position_on_startup`
- 当前仓库未内置测试套件，本次主要做了脚本语法检查与定向验证
- `start.sh` / `status.sh` / `stop.sh` 依赖 `aitrade-be/` 下的 `.aitrade/` 运行态目录
- 主应用日志、交易日志和启动辅助日志默认写入 `aitrade-be/logs/`
- 如果本地配置指向真实交易环境，运行脚本前请先确认 `config.yaml` 中的 `trade_mode`、交易所凭证与代理配置；其中 `paper` 会读取真实行情但不会真实下单

## 打包

执行后会在 `dist/` 目录下生成一个带时间戳的 `tar.gz` 源码包，并排除本地 `.venv`、日志和 `config.yaml`：

```bash
bash package.sh
```

## 远端部署

当前已提供最小远端部署链路，默认通过本机 SSH 别名把版本发布到远端 `/data/aitrade`：

```bash
bash deploy.sh chenws-japan
```

部署脚本会完成：

- 执行后端 `bash package.sh`
- 执行前端 `pnpm --dir ../aitrade-fe build`
- 上传后端源码包到远端 `releases/`
- 解压为版本目录并准备 `/data/aitrade/shared/config.yaml`
- 在当前版本的 `aitrade-be/` 下把 `config.yaml` 软链到共享配置
- 上传前端静态产物到固定共享目录 `/data/aitrade/shared/public`
- 先停止当前 `current` 版本的 Web 服务，再切换 `/data/aitrade/current` 到新版本
- 自动执行远端 `init-env.sh`、`start-web.sh`、`status-web.sh`
- 自动校验 `/data/aitrade/shared/public/index.html`、`http://127.0.0.1:18080/health`、`current` 软链目标，以及 `openapi.json` 中的关键路由

远端正式目录约定：

- 当前后端版本：`/data/aitrade/current/aitrade-be`
- 共享配置：`/data/aitrade/shared/config.yaml`
- 前端静态目录：`/data/aitrade/shared/public`

Nginx 静态站点根目录应固定指向 `/data/aitrade/shared/public`，不要指向某个具体 release 目录，也不要继续依赖 `/data/aitrade/current/aitrade-fe-dist`。

首次把线上 Nginx 静态目录切到共享目录时，建议执行：

```bash
nginx -t
systemctl reload nginx
```

如果远端启用了 SELinux，需确保 `/data/aitrade/shared/public` 被标记为 `httpd_sys_content_t`；当前部署脚本会自动尝试写入 `semanage fcontext` 并执行 `restorecon`。

Web 服务默认监听 `app.web.port`，远端正式部署当前默认端口为 `18080`。

如果部署完成后页面新接口仍然 404，不要只看 `/health`；还要继续检查：

- `bash status-web.sh` 输出里的 `PID` 与 `监听 PID` 是否一致
- `readlink /data/aitrade/current` 是否指向本次 release
- `curl http://127.0.0.1:18080/openapi.json` 是否已经包含目标路径

本次就出现过“`current` 已切到新版本，但旧 Web 进程仍占着 `18080`，导致线上继续提供旧路由表”的情况。

## 协作文档约定

- 每次有意义的仓库改动都同步更新仓库根目录 `CHANGELOG.md`
- 如果对话中沉淀出对后续使用者有帮助的流程、约束或经验，优先写入项目文档，而不是只留在聊天记录里
- 注释、文档、说明性文字默认使用中文，除非用户明确要求使用其他语言
- 机器人运行依赖 `aitrade-be/` 目录下的 `config.yaml`
- `.aitrade/` 是本地运行态目录，不需要手工提交
