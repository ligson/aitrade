aitrade
=================================
A simple trading system for AI.

## 项目位置

当前后端已迁移到 `aitrade-be/` 子目录中。

本文档描述的是 **后端子项目**，默认工作目录就是 `aitrade-be/`。

## 配置

1. 复制 `config.example.yaml` 为 `config.yaml`
2. 先填写系统级配置：GPT、交易所、代理、Web、持久化与回测相关配置
3. 如果你只启动 Web 管理台，`config.yaml` 不再要求保留任务级交易参数；真实交易任务参数以数据库任务配置和启动快照为准
4. 如果你要直接运行 Bot（`uv run python -m aitrade` / `bash start.sh`），再额外补齐 `app.trade.sandbox_trade / symbol / timeframe / limit / strategy.*`
5. `app.trade.strategy.type` 仅在 Bot/CLI 直跑场景下用于切换交易策略：
   - `gpt`：保留原有 AI 信号策略
   - `btc_spot_breakout`：BTC 现货 long-only 规则策略
6. 默认会把结构化交易记录写入 `sqlite:///./.aitrade/trades.sqlite3`

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

其中现有 `start.sh` / `status.sh` / `stop.sh` 主要服务 Bot 运行链路，本次仓库迁移未新增 Web 专用运维脚本。

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
- Web 场景下，`config.yaml` 只要求保留系统级配置与 `app.trade.persistence`；不再要求保留任务级交易参数占位
- CLI/Bot 直跑场景下，仍需在 `config.yaml` 中提供 `sandbox_trade / symbol / timeframe / limit / strategy.*`
- 当前页面控制采用 Web 进程内单实例 Runner，只允许同一时刻有一个交易任务运行

当前 Web API 主要服务 `aitrade-fe/` 管理台，默认本地联调地址如下：

- 前端开发服务：`http://127.0.0.1:5173`
- 后端 Web API：`http://127.0.0.1:18080`
- 健康检查：`GET /health` 或 `POST /health`

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

### 交易记录持久化

- 默认通过 SQLAlchemy 同步 ORM 把交易执行结果写入 `sqlite:///./.aitrade/trades.sqlite3`
- 默认会持久化当前本地持仓、止损和追踪止损状态到 `position_state` 表
- 主配置项是 `app.trade.persistence.database_url`，将来可切到 MySQL 等数据库；`sqlite_path` 仅作为兼容旧配置的别名
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
- 如果开启了 `app.http_client.proxy_enable`，回测历史数据下载会自动复用同一代理配置访问 Binance
- 若仍出现证书校验失败，通常是本机代理链路或证书环境问题，不是回测目录路径问题

## 核心结构

- `aitrade/__main__.py`：程序入口，负责日志初始化和加载 `config.yaml`
- `aitrade/trade/trading_system/trading_bot.py`：主循环调度与策略切换入口
- `aitrade/trade/strategies/`：策略抽象层，包含 GPT 策略和 BTC 现货突破策略
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
- 如果本地配置指向真实交易环境，运行脚本前请先确认 `config.yaml` 中的沙盒与凭证配置

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
- 切换 `/data/aitrade/current` 到新版本
- 自动执行远端 `init-env.sh`、`stop-web.sh`、`start-web.sh`、`status-web.sh`
- 自动校验 `/data/aitrade/shared/public/index.html` 与 `http://127.0.0.1:18080/health`

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

Web 服务默认监听 `app.web.port`，默认端口为 `18080`。

## 协作文档约定

- 每次有意义的仓库改动都同步更新仓库根目录 `CHANGELOG.md`
- 如果对话中沉淀出对后续使用者有帮助的流程、约束或经验，优先写入项目文档，而不是只留在聊天记录里
- 注释、文档、说明性文字默认使用中文，除非用户明确要求使用其他语言
- 机器人运行依赖 `aitrade-be/` 目录下的 `config.yaml`
- `.aitrade/` 是本地运行态目录，不需要手工提交
