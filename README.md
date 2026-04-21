aitrade
=================================
A simple trading system for AI.

## 配置

1. 复制 `config.example.yaml` 为 `config.yaml`
2. 根据文件注释填写 GPT、交易所、代理和交易参数
3. 默认配置里包含沙盒模式开关，联调时优先确认该项
4. `app.trade.strategy.type` 可切换交易策略：
   - `gpt`：保留原有 AI 信号策略
   - `btc_spot_breakout`：BTC 现货 long-only 规则策略
5. 默认会把结构化交易记录写入 `./.aitrade/trades.sqlite3`

## 初始化与运行

推荐按下面四个命令完成初始化、启动、查看状态和停止：

```bash
bash init-env.sh
bash start.sh
bash status.sh
bash stop.sh
```

如需前台运行，可在仓库根目录执行：

```bash
uv run python -m aitrade
```

### `bash init-env.sh`

- 使用 `uv` 按 `.python-version` 固定的 Python `3.14` 创建并同步 `.venv/`
- 依赖来源为 `pyproject.toml` 与 `uv.lock`
- 如果不存在 `config.yaml`，会从 `config.example.yaml` 自动生成
- 执行结束后会提示下一步编辑配置再启动

如果本机缺少 `uv`：
- macOS / Linux：按脚本提示先安装 `uv`，再重新执行初始化

### `bash start.sh`

- 自动切到仓库根目录启动，避免 `./config.yaml` 路径错误
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

### SQLite 交易记录

- 默认会把交易执行结果写入 `./.aitrade/trades.sqlite3`
- 默认会持久化当前本地持仓、止损和追踪止损状态到 `position_state` 表
- `app.trade.persistence.restore_position_on_startup` 默认是 `false`，避免本地快照与真实交易所状态不一致时自动恢复
- `trade_records` 会记录策略、时间、方向、价格、数量、原因、止损/追踪止损、订单结果、失败原因等字段

常见查询方式：

```bash
bash query-trades.sh latest 20
bash query-trades.sh strategy gpt 20
bash query-trades.sh side buy 20
bash query-trades.sh failed 20
bash query-trades.sh position
```

## 项目流程

程序启动后会按如下顺序循环执行：

1. 从交易所拉取 K 线和基础市场数据
2. 根据配置选择策略生成交易信号
3. 经过风控判断后执行下单
4. 持仓时动态更新止损位
5. 检查止损条件
6. 等待下一个交易周期

## 核心结构

- `aitrade/__main__.py`：程序入口，负责日志初始化和加载 `config.yaml`
- `aitrade/trade/trading_system/trading_bot.py`：主循环调度与策略切换入口
- `aitrade/trade/strategies/`：策略抽象层，包含 GPT 策略和 BTC 现货突破策略
- `aitrade/trade/trading_system/market_data_fetcher.py`：行情获取与指标整理
- `aitrade/trade/gpt_signal/`：GPT 信号分析、提示词构建、响应解析
- `aitrade/trade/trading_system/risk_manager.py`：风控检查与仓位计算
- `aitrade/trade/trading_system/trade_executor.py`：下单、持仓状态、止损信息管理，以及 SQLite 交易记录落库
- `aitrade/trade/trading_system/sqlite_trade_store.py`：SQLite 建表、交易记录查询与持仓快照持久化

## 当前限制

- 持仓状态会同时保存在进程内存和 `./.aitrade/trades.sqlite3` 中，但默认不会在启动时自动恢复；如需恢复，需要显式打开 `app.trade.persistence.restore_position_on_startup`
- 当前仓库未内置测试套件，本次主要做了脚本语法检查与定向验证
- `start.sh` / `status.sh` / `stop.sh` 依赖仓库根目录下的 `.aitrade/` 运行态目录
- 主应用日志、交易日志和启动辅助日志默认写入 `logs/`
- 如果本地配置指向真实交易环境，运行脚本前请先确认 `config.yaml` 中的沙盒与凭证配置

## 打包

执行后会在 `dist/` 目录下生成一个带时间戳的 `tar.gz` 源码包，并排除本地 `.venv`、日志和 `config.yaml`：

```bash
bash package.sh
```

## 协作文档约定

- 每次有意义的仓库改动都同步更新 `CHANGELOG.md`
- 如果对话中沉淀出对后续使用者有帮助的流程、约束或经验，优先写入项目文档，而不是只留在聊天记录里
- 注释、文档、说明性文字默认使用中文，除非用户明确要求使用其他语言
- 机器人运行依赖仓库根目录下的 `config.yaml`，脚本会自动切到项目根目录执行
- `.aitrade/` 是本地运行态目录，不需要手工提交
