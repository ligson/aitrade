# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this backend project.

## 项目概览

`aitrade` 是一个小型 Python 自动交易机器人，当前支持两类可配置策略：
- `gpt`：通过兼容 OpenAI 的客户端生成 AI 交易信号
- `btc_spot_breakout`：面向 BTC 现货的 long-only 规则突破策略

当前文件所在目录 `aitrade-be/` 是后端项目根目录。

主运行入口是 `python -m aitrade`。在 Bot/CLI 直跑场景下，程序会加载 `./config.yaml`，构建交易系统，获取市场数据，根据配置选择策略生成信号，经过风控后执行交易，再按 `trade.timeframe` 的分钟数休眠。

当前 Web 管理台已支持在“交易中心 / 交易任务”页维护多套交易任务配置，并基于所选配置开始 / 停止 / 查看状态；任务启动时会把任务级参数固化为数据库快照，并在独立“交易中心 / 任务日志”页查询运行事件日志；Web 服务启动后默认不自动运行交易任务。

## 常用命令

### 环境准备

默认优先使用后端目录提供的脚本入口：

```bash
bash init-env.sh
bash start.sh
bash status.sh
bash stop.sh
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
uv run python -m aitrade
uv run python -m aitrade.web_runner
```

其中：
- `python -m aitrade`：启动交易机器人 Bot 主链路
- `python -m aitrade.web_runner`：启动 Web API

管理台控制补充说明：
- `python -m aitrade.web_runner` 只启动 Web API，不会自动启动交易任务
- 交易任务可在管理台“交易中心 / 交易任务”页通过页面配置开始 / 停止
- 交易任务运行事件日志可在管理台“交易中心 / 任务日志”页查询
- 页面开始任务时会先生成数据库快照；之后再改页面配置，不会影响当前已运行任务
- Web 场景下，`config.yaml` 仅继续承载系统级配置与 `app.trade.persistence`；任务级参数以数据库配置为准
- CLI/Bot 直跑场景下，仍需在 `config.yaml` 中提供 `sandbox_trade / symbol / timeframe / limit / strategy.*`
- 本地联调默认优先复用已运行的 `be-web` / `fe-dev` 进程；Web API 默认复用 `config.yaml` 中的监听端口（当前常用 `127.0.0.1:18081`），前端默认复用 `127.0.0.1:5173`，非用户明确要求不要为了验证随意改端口或额外起进程
- 如果需要按 IDE 约定启动，优先使用仓库内 `.idea/runConfigurations/be_web.xml` 与 `.idea/runConfigurations/fe_dev.xml` 定义的命令和工作目录

后台运行：

```bash
bash start.sh
bash status.sh
bash stop.sh
```

现有后台脚本主要服务 Bot 运行链路。它们会自动以 `aitrade-be/` 为工作目录执行，因为 `aitrade/__main__.py` 与 `aitrade/web_runner.py` 都固定读取 `./config.yaml`，而 `aitrade/config/log_config.py` 会把日志写到当前工作目录下的 `logs/`。

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

Web 场景下，`config.yaml` 需要保留的顶层结构包括：
- `app.exchange`：交易所类型、凭证，以及可选的 OKX 密码
- `app.http_client`：代理开关与代理地址
- `app.trade.persistence`：至少保留 `database_url`
- `app.web`：Web 服务配置
- `app.backtest`：至少保留 `data_dir / user_data_dir / freqtrade_bin`

补充说明：
- Web 管理台“系统设置”页会把一部分系统参数保存到数据库，并在 Web 场景下覆盖 `config.yaml` 中对应字段
- 当前允许网页维护的主要是 `app.gpt.provider / model / api_key / base_url`、`app.trade.persistence.persist_position / restore_position_on_startup`、`app.backtest.supported_* / default_* / download_timerange / data_format_ohlcv / export_archive_format`
- `config.example.yaml` 已按 Web 场景精简，不再保留上述可网页维护字段；首次创建系统设置记录时，会基于文件中的当前值或运行时默认值补齐
- `app.exchange.*`、`app.web.jwt_secret`、`app.trade.persistence.database_url`、`app.http_client.*`、`app.web.host/port/debug/show_trace/cors_allow_origins`、`app.backtest.data_dir/user_data_dir/freqtrade_bin` 等敏感或部署期配置仍只来自 `config.yaml`

仅在 Bot/CLI 直跑场景下，才额外要求：
- `app.trade.sandbox_trade`
- `app.trade.symbol`
- `app.trade.timeframe`
- `app.trade.limit`
- `app.trade.strategy.*`

Bot/CLI 配置切换示例：

```yaml
app:
  trade:
    strategy:
      type: gpt
```

```yaml
app:
  trade:
    strategy:
      type: btc_spot_breakout
```

新环境初始化时，以精简后的 `config.example.yaml` 作为 Web 场景配置结构的权威示例；如需直跑 Bot，再按文档补齐任务级字段。

额外的持久化约定：
- 默认通过 SQLAlchemy 同步 ORM 把结构化交易记录写入 `sqlite:///./.aitrade/trades.sqlite3`
- `trade_records` 表用于查询交易记录，`position_state` 表用于保存本地持仓快照
- `app.trade.persistence.database_url` 是主配置项；`sqlite_path` 仅作为兼容旧配置的别名
- `app.trade.persistence.restore_position_on_startup` 默认应保持 `false`，除非明确接受用本地快照恢复持仓的风险
- 如需本地查询，使用 `bash query-trades.sh`，不要虚构其他不存在的查询命令

## 架构说明

### 运行入口

- `aitrade/__main__.py`：初始化日志、加载 `./config.yaml`、创建 `OptimizedCryptoBot` 并启动主循环。
- `aitrade/trade/trade.py`：对 `TradingBot` 的轻量封装。

### 核心调度

`aitrade/trade/trading_system/trading_bot.py` 是主调度器。每个周期会：
1. 获取增强后的市场数据
2. 获取当前持仓
3. 通过 `aitrade/trade/strategies/factory.py` 按配置实例化并调用策略
4. 持仓时先更新止损与追踪止损
5. 对 `buy` / `sell` 信号执行交易
6. 检查内存持仓是否触发止损
7. 按配置周期休眠，等待下一轮

### 策略层

`aitrade/trade/strategies/` 是新增的策略抽象层：
- `base_strategy.py`：统一策略接口
- `gpt_strategy.py`：对原有 GPT 信号链路的包装
- `btc_spot_breakout_strategy.py`：BTC 现货突破策略
- `factory.py`：根据配置创建策略实例

`GPTStrategy` 自身负责最小置信度阈值，不再由 `TradingBot` 写死全局 `0.7`。

### 行情与执行分层

- `market_data_fetcher.py`：负责连接交易所、拉取 OHLCV 数据并整理衍生指标；当前会返回 `opens/highs/lows/closes/volumes/ohlcv/timestamps`。
- `trade_executor.py`：负责余额读取、下单、最小下单量校验，以及内存中的持仓状态和止损信息维护。
- `risk_manager.py`：负责交易前检查和仓位计算；当前对 GPT 与规则策略做了不同处理。

行情获取和交易执行各自维护自己的 CCXT 客户端，当前没有共享的交易所服务层。

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

提供方切换通过 `GPTStrategy` 内部解析 `provider -> base_url`，同时 `SignalGenerator` 已支持从配置读取模型名，不再写死 `deepseek-chat`。

## 重要实现约束

- 持仓状态会同时保存在 `trade_executor.py` 的内存对象和持久化存储中；默认数据库地址是 `sqlite:///./.aitrade/trades.sqlite3`，只有在显式开启 `app.trade.persistence.restore_position_on_startup` 时，才会在启动时从本地快照恢复。
- 配置路径写死为 `./config.yaml`，因此脚本必须先在 `aitrade-be/` 目录执行，或通过仓库根目录兼容脚本转发到这里。
- 后台运行态保存在 `.aitrade/`；主应用日志、交易日志和启动辅助日志保存在 `logs/`。
- 当前缺少测试，验证方式以手工和定向检查为主。
- 15 分钟 BTC 突破策略已做过滤，但仍可能受噪音影响，优先建议沙盒联调。
- 修改脚本或文档时，要确保命令与仓库里实际存在的脚本和入口保持一致。
- **网络错误日志清晰**：代码中涉及网络调用（交易所连接、API 请求等）的地方，如遇连接失败、超时等网络问题，日志输出必须清晰明确，包含具体的错误信息、失败位置和上下文，便于问题排查。

## 文档协作规则

- 每次有意义的仓库改动，都要同步更新仓库根目录 `CHANGELOG.md`，简要记录本次变更。
- 当对话中沉淀出对后续贡献者有帮助的长期流程知识、操作约束或非显而易见的项目使用经验时，要把这些内容写入项目文档，不要只保留在聊天记录里。
- 优先更新现有文档，例如后端 `README.md`、后端 `CLAUDE.md` 或其他聚焦型项目文档，避免创建重复说明。
- 注释、文档、说明性文字默认使用中文，除非用户明确要求使用其他语言。
