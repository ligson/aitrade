# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this backend project.

## 项目概览

`aitrade` 是一个 Web 化自动交易后端，当前支持四类可配置策略：
- `gpt`：通过兼容 OpenAI 的客户端生成 AI 交易信号
- `btc_spot_breakout`：面向 BTC 现货的 long-only 单周期规则突破策略
- `btc_spot_trend_breakout`：面向 BTC 现货的 long-only 趋势突破策略，固定 `1h` 执行并使用 `4h` 趋势过滤
- `spot_multi_signal_fusion`：面向现货的结构化多源融合策略，可选择已有 K 线策略档案、内建技术面节点和独立信号源档案参与融合

当前文件所在目录 `aitrade-be/` 是后端项目根目录。

后端已经收敛为 **Web-only**：
- 唯一运行入口是 `python -m aitrade.web_runner`
- Web 服务启动后不会自动运行交易任务
- 交易任务由管理台页面启动、停止、查看状态和查看任务日志
- 不再支持独立 `python -m aitrade` 或 `start.sh / status.sh / stop.sh` 的 Bot/CLI 直跑模式

## 常用命令

### 环境准备

默认优先使用后端目录提供的脚本入口：

```bash
bash init-env.sh
```

`init-env.sh` 当前策略是：
- 使用 `uv` 按 `.python-version` 固定的 Python `3.14` 创建并同步 `.venv/`
- 依赖由 `pyproject.toml` 与 `uv.lock` 管理
- 首次执行时自动从 `config.example.yaml` 生成 `config.yaml`
- 如果缺少 `uv`，只输出安装提示

如需手动准备环境，保持以下最小流程：

```bash
cp config.example.yaml config.yaml
uv sync --python 3.14 --locked
```

### 本地运行

前台运行入口：

```bash
uv run python -m aitrade.web_runner
```

后台运行：

```bash
bash start-web.sh
bash status-web.sh
bash stop-web.sh
```

管理台控制补充说明：
- `python -m aitrade.web_runner` 只启动 Web API，不会自动启动交易任务
- 交易任务可在管理台“交易中心 / 任务中心”页按任务配置逐条开始 / 停止，并在同页查看概览、配置和运行态
- 交易任务运行事件日志可在“交易中心 / 任务日志”页按 runner / runId 查询
- 页面开始任务时会先生成数据库快照；之后再改页面配置，不会影响当前已运行任务
- Web 场景下，`config.yaml` 仅继续承载系统级配置与部署级配置；任务级参数以数据库任务配置、系统设置和运行快照为准
- 系统会为每条任务配置自动分配独立 `runnerName`；当前版本支持不同交易对并发运行，但同一交易对仍不支持并发启动
- 本地联调默认优先复用已运行的 `be-web` / `fe-dev` 进程；Web API 默认复用 `config.yaml` 中的监听端口（当前常用 `127.0.0.1:18081`），前端默认复用 `127.0.0.1:5173`，非用户明确要求不要为了验证随意改端口或额外起进程
- 如果需要按 IDE 约定启动，优先使用仓库内 `.idea/runConfigurations/be_web.xml` 与 `.idea/runConfigurations/fe_dev.xml` 定义的命令和工作目录

### 源码打包

`bash package.sh` 会在 `dist/` 下生成带时间戳的 `tar.gz` 源码包，默认排除 `.venv`、日志文件和本地 `config.yaml`。

```bash
bash package.sh
```

### 查询交易记录

```bash
bash query-trades.sh latest 20
bash query-trades.sh strategy gpt 20
bash query-trades.sh side buy 20
bash query-trades.sh failed 20
bash query-trades.sh position
```

### 测试与 lint

当前后端中没有测试套件、lint 命令、格式化配置或正式的构建系统。文档里不要虚构这些命令。如果需要验证改动，优先做和改动相关的定向冒烟验证，并明确说明哪些内容已验证、哪些没有验证。

## 配置模型

运行时配置通过 `aitrade/config/config_file.py` 从 `config.yaml` 加载。

Web 场景下，`config.yaml` 需要保留的最小顶层结构包括：
- `app.http_client`：代理开关与代理地址
- `app.data_root_dir`：部署级数据根目录
- `app.web`：至少保留 `port / jwt_secret / cors_allow_origins`；其他 Web 参数缺省时使用代码默认值
- `app.backtest`：至少保留 `freqtrade_bin`
- `app.trade.persistence`：保留结构占位

补充说明：
- Web 管理台“系统设置”页会把一部分系统参数保存到数据库，并在 Web 场景下覆盖 `config.yaml` 中对应字段
- 当前允许网页维护的主要是 `app.gpt.provider / model / api_key / base_url`、`app.trade.persistence.persist_position / restore_position_on_startup`、`app.trade.market_feeds.trade_flow.*`、`app.backtest.supported_* / default_* / download_timerange / data_format_ohlcv / export_archive_format`
- 管理台“交易所设置”页会按用户维护 `exchange type / api_key / api_secret / password`，任务启动时会读取该用户配置并冻结到 run snapshot；因此 Web 场景不再要求在 `config.yaml` 中保留 `app.exchange`
- 管理台“部署设置”页会直接写回 `config.yaml`，现在只维护 `app.data_root_dir`；SQLite、系统日志、历史数据目录和 Freqtrade `user_data` 目录都会由它自动派生
- `app.web.jwt_secret`、`app.http_client.*`、`app.data_root_dir`、`app.web.port/cors_allow_origins`、`app.backtest.freqtrade_bin` 等敏感或部署期配置仍只来自 `config.yaml`
- 融合策略与信号源的可复用实例配置不再放入 `config.yaml`，而是通过 `strategy_profiles` 与 `signal_source_profiles` 在管理台维护；任务启动时会把引用关系和实际生效参数一起冻结到 run snapshot
- 真实交易任务运行前，会把“系统级生效配置 + 用户交易所设置 + 本次 run snapshot”组装成任务运行态配置，并做严格校验；若用户未配置交易所凭证，启动会被明确拦截

额外的持久化约定：
- 默认通过 SQLAlchemy 同步 ORM 把结构化交易记录写入 `app.data_root_dir/trades.sqlite3`（默认即 `sqlite:///~/.aitrade/trades.sqlite3`）
- `trade_records` 表用于查询交易记录，`position_state` 表用于保存本地持仓快照
- 新配置推荐只维护 `app.data_root_dir`；旧 `app.trade.persistence.database_url / sqlite_path` 仍保留读取兼容，但新部署设置保存会收敛回单根目录模型
- `app.trade.persistence.restore_position_on_startup` 默认应保持 `false`，除非明确接受用本地快照恢复持仓的风险
- 如需本地查询，使用 `bash query-trades.sh`，不要虚构其他不存在的查询命令

## 架构说明

### 运行入口

- `aitrade/web_runner.py`：初始化日志、加载 `./config.yaml`、创建 FastAPI 应用并启动 Uvicorn。
- `aitrade/web/modules/system/trade_task_service.py`：在 Web 进程内维护交易任务配置、运行快照、运行态和事件日志，并负责启动/停止任务线程。
- `aitrade/trade/trade.py`：对 `TradingBot` 的轻量封装。

### 核心调度

`aitrade/trade/trading_system/trading_bot.py` 是主调度器。每个周期会：
1. 获取增强后的市场数据
2. 获取当前持仓
3. 通过 `aitrade/trade/strategies/factory.py` 按配置实例化并调用策略
4. 持仓时先更新止损与追踪止损
5. 对 `buy` / `sell` 信号执行交易
6. 检查内存持仓是否触发止损
7. 按配置周期等待下一轮

### 策略层

`aitrade/trade/strategies/` 是策略抽象层：
- `base_strategy.py`：统一策略接口，并声明策略所需的主周期 / 上下文周期数据规格
- `gpt_strategy.py`：对原有 GPT 信号链路的包装
- `btc_spot_breakout_strategy.py`：BTC 现货突破策略
- `btc_spot_trend_breakout_strategy.py`：BTC 现货趋势突破策略
- `factory.py`：根据配置创建策略实例
- `fusion_profile.py`：融合策略结构化 profile 的兼容归一、摘要生成和运行时参数适配
- `signal_source_registry.py`：信号源 definition 注册表，维护 source type、默认参数与 schema

### AI 信号链路

`aitrade/trade/gpt_signal/signal_generator.py` 负责串联：
- 技术指标总结
- 市场环境分析
- 提示词构建
- 模型调用
- 响应解析与校验

配套模块包括：
- `technical_analyzer.py`
- `market_analyzer.py`
- `prompt_builder.py`
- `response_parser.py`

## 重要实现约束

- 持仓状态会同时保存在 `trade_executor.py` 的内存对象和持久化存储中；默认数据库地址是 `sqlite:///~/.aitrade/trades.sqlite3`，只有在显式开启 `app.trade.persistence.restore_position_on_startup` 时，才会在启动时从本地快照恢复。
- 配置路径写死为 `./config.yaml`，因此脚本必须先在 `aitrade-be/` 目录执行，或通过仓库根目录兼容脚本转发到这里。
- 默认数据目录与程序目录分离：结构化交易记录、历史数据、Freqtrade `user_data` 与 Python 应用日志默认按 `app.data_root_dir`（默认 `~/.aitrade/`）自动派生；`aitrade-be/.aitrade/` 仅继续承担 PID 等程序控制运行态，shell 启动辅助日志仍保留在 `aitrade-be/logs/`。
- 当前缺少测试，验证方式以手工和定向检查为主。
- `btc_spot_trend_breakout` 当前固定使用 `1h` 执行周期和 `4h` 趋势过滤；不要在页面或实现里把它放宽为任意周期组合。
- `spot_multi_signal_fusion` 若所选 K 线节点中包含 `btc_spot_trend_breakout`，同样必须固定使用 `1h` 主周期并加载 `4h` 上下文数据；不要静默降级成单周期运行。
- 如果修改 live / backtest 的多周期装配逻辑，必须确保 `4h` 上下文数据在任一 `1h` 决策点都只使用当时已闭合的 K 线，避免未来数据泄漏。
- 修改脚本或文档时，要确保命令与仓库里实际存在的脚本和入口保持一致。
- 修改 `*.sh` 脚本时，默认要同时兼容 macOS 与 Linux；优先使用两边都支持的命令、选项和路径处理方式，不要依赖 GNU 独有参数。
- **网络错误日志清晰**：代码中涉及网络调用（交易所连接、API 请求等）的地方，如遇连接失败、超时等网络问题，日志输出必须清晰明确，包含具体的错误信息、失败位置和上下文，便于问题排查。

## 文档协作规则

- 每次有意义的仓库改动，都要同步更新仓库根目录 `CHANGELOG.md`，简要记录本次变更。
- 当对话中沉淀出对后续贡献者有帮助的长期流程知识、操作约束或非显而易见的项目使用经验时，要把这些内容写入项目文档，不要只保留在聊天记录里。
- 优先更新现有文档，例如后端 `README.md`、后端 `CLAUDE.md` 或其他聚焦型项目文档，避免创建重复说明。
- 注释、文档、说明性文字默认使用中文，除非用户明确要求使用其他语言。
