# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

`aitrade` 是一个小型 Python 自动交易机器人，当前支持两类可配置策略：
- `gpt`：通过兼容 OpenAI 的客户端生成 AI 交易信号
- `btc_spot_breakout`：面向 BTC 现货的 long-only 规则突破策略

主运行入口是 `python -m aitrade`。程序会加载 `./config.yaml`，构建交易系统，获取市场数据，根据配置选择策略生成信号，经过风控后执行交易，再按 `trade.timeframe` 的分钟数休眠。

## 常用命令

### 环境准备

默认优先使用仓库提供的四个脚本入口：

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

前台运行：

```bash
uv run python -m aitrade
```

后台运行：

```bash
bash start.sh
bash status.sh
bash stop.sh
```

后台脚本会自动切到仓库根目录执行，因为 `aitrade/__main__.py` 固定读取 `./config.yaml`，而 `aitrade/config/log_config.py` 会把日志写到当前工作目录下的 `logs/`。

### 源码打包

`bash package.sh` 会在 `dist/` 下生成带时间戳的 `tar.gz` 源码包，默认排除 `.venv`、日志文件和本地 `config.yaml`。

```bash
bash package.sh
```

### 测试与 lint

当前仓库中没有测试套件、lint 命令、格式化配置或正式的构建系统。文档里不要虚构这些命令。如果需要验证改动，优先做和改动相关的定向冒烟验证，并明确说明哪些内容已验证、哪些没有验证。

## 配置模型

运行时配置通过 `aitrade/config/config_file.py` 从 `config.yaml` 加载。

必需的顶层结构包括：
- `app.gpt`：模型提供方、API Key、模型名
- `app.exchange`：交易所类型、凭证，以及可选的 OKX 密码
- `app.http_client`：代理开关与代理地址
- `app.trade`：沙盒模式、交易对、时间周期、K 线数量
- `app.trade.strategy`：策略类型与各策略参数

配置切换示例：

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

新环境初始化时，以 `config.example.yaml` 作为配置结构的权威示例。

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

- 持仓状态保存在 `trade_executor.py` 的内存对象中；进程重启后，本地持仓状态会丢失。
- 配置路径写死为 `./config.yaml`，因此脚本必须先切到仓库根目录执行，除非相关代码被调整。
- 后台运行态保存在 `.aitrade/`；主应用日志、交易日志和启动辅助日志保存在 `logs/`。
- 当前缺少测试，验证方式以手工和定向检查为主。
- 15 分钟 BTC 突破策略已做过滤，但仍可能受噪音影响，优先建议沙盒联调。
- 修改脚本或文档时，要确保命令与仓库里实际存在的脚本和入口保持一致。
- **网络错误日志清晰**：代码中涉及网络调用（交易所连接、API 请求等）的地方，如遇连接失败、超时等网络问题，日志输出必须清晰明确，包含具体的错误信息、失败位置和上下文，便于问题排查。

## 文档协作规则

- 每次有意义的仓库改动，都要同步更新 `CHANGELOG.md`，简要记录本次变更。
- 当对话中沉淀出对后续贡献者有帮助的长期流程知识、操作约束或非显而易见的项目使用经验时，要把这些内容写入项目文档，不要只保留在聊天记录里。
- 优先更新现有文档，例如 `README.md`、`CLAUDE.md` 或其他聚焦型项目文档，避免创建重复说明。
- 注释、文档、说明性文字默认使用中文，除非用户明确要求使用其他语言。
