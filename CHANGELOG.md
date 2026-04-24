# CHANGELOG

所有有意义的仓库变更都应记录在这里。

## 2026-04-23

- 修复前端登录页 `a-form` 未绑定 `:model` 导致的提交链路异常，避免点击登录按钮后无明显响应。
- 调整前端开发环境 `VITE_API_BASE_URL` 默认值为空，改为通过 Vite `/api` 代理转发本地后端请求，避免浏览器直连 `127.0.0.1:18080` 触发 CORS。
- 修复登录验证码校验异常直接透出 traceback 的问题，改为返回统一业务错误响应格式。
- 优化登录页校验交互：前端补充用户名、密码、验证码必填校验与字段级错误展示，后端缺参提示改为更具体的错误信息。
- 增强图形验证码复杂度：改为易区分的数字字母混合验证码，并增加随机颜色与干扰线，降低被简单识别的概率。
- 重构交易日志页筛选区：将策略、方向、结果、交易对改为选择式筛选，时间改为范围选择，并补充交易对筛选选项接口与表格标签化展示；同时收紧前四个筛选框宽度并将交易时间日历切换为中文。
- 重建仓库级 `docs/` 文档目录，补充架构、后端、前端、API 与运维说明，并在根 `README.md` 与 `CLAUDE.md` 中补充文档入口。
- 为 FastAPI 框架级 `HTTPException`（如 404）补充统一错误响应处理，避免直接返回默认的 `{"detail":"Not Found"}` 结构。
- 改造后台主布局：新增公共 breadcrumb、右侧内容区独立滚动、可收缩左侧菜单与统一滚动条样式，提升登录后的整体管理台体验。
- 继续优化后台管理台：为侧栏补齐图标与内置收起按钮，移除页面重复标题，并将策略配置页重构为表格 + 详情/编辑抽屉交互。
- 修复交易日志页筛选区在中等宽度下的布局溢出问题，并收紧交易对选项与展示逻辑，避免空白 symbol 干扰筛选和表格显示。
- 将前端路由页面改为按需懒加载，并新增全局顶部页面进度条，让首屏登录恢复和页面切换过程具备统一加载反馈。
- 继续优化前端导航体验：增强顶部进度条的渐变高光与收尾动画，并将 401 未授权跳转改为走 Vue Router 导航，避免整页硬刷新打断页面切换体验。
- 收口后端持久化配置示例：移除 `app.trade.persistence.sqlite_path` 的模板用法，仅保留 `database_url` 作为推荐配置，同时在运行时代码中继续保留对旧字段的兼容解析。
- 新增策略回测能力：补齐回测数据配置、回测任务与成交明细落库、`btc_spot_breakout` 离线回测接口与管理台页面，并支持通过 freqtrade CLI 下载 `BTC/USDT` 历史现货数据；同时明确 `gpt` 策略暂不支持离线回测。
- 修复回测历史数据下载链路：freqtrade `user_data` 与最小配置改为由后端自动初始化，并复用 `app.http_client` 代理配置访问 Binance；下载失败时同步收口为统一业务错误提示，避免把底层 traceback 直接返回前端。
- 新增远端部署基础能力：补齐 `deploy.sh`、`start-web.sh`、`status-web.sh`、`stop-web.sh`，支持通过 SSH 别名把前后端产物发布到远端 `/data/aitrade`，并在远端以共享 `config.yaml` 启动 Web 服务；前端构建时也支持覆盖 `VITE_API_BASE_URL` 指向远端后端地址。
- 修复远端 Web 环境下回测历史数据下载找不到 `freqtrade` 命令的问题：优先复用当前 Python 所在 `.venv/bin` 下的 CLI，并在 `start-web.sh` 启动时补齐 `.venv/bin` 到 PATH，避免 `bash init-env.sh` 已安装依赖但运行时因 PATH 缺失导致下载失败。
- 修复策略回测页日期选择器显示英文的问题，统一补齐 Ant Design 与 dayjs 中文 locale，并在前端文档中明确“无特殊要求默认显示中文”的界面规则。
- 新增独立“历史数据管理”菜单与页面，历史数据下载统一按配置里的最早范围执行到当前时点，支持按配置白名单展示交易对，并提供 zip 压缩包导入、导出和文件列表管理。
- 改造策略回测链路为“按历史文件回测”：前端改为选择历史文件，后端新增历史文件 catalog / import / export / delete / options 接口，并把回测任务数据来源升级为文件元信息结构，兼容旧任务详情展示。
- 后端新增 `python-multipart` 依赖，支持历史数据 zip 压缩包上传导入；同时补充前后端文档，明确历史数据管理与按文件回测约束。
- 统一清理仓库内旧文档描述：补齐架构文档中的历史数据管理/策略回测页面、修正 Web 入口说明，更新后端/API 文档中的 backtests 接口与 Web 专用脚本说明，并收口前端 README 的本地联调口径为“相对路径 + Vite 代理”。

## 2026-04-22

- 为项目根目录 `.idea/runConfigurations/` 补充 `be-web` 与 `fe-dev` 共享运行配置；其中 `be-web` 调整为以 `aitrade-be/` 为工作目录执行 `uv run python -m aitrade.web_runner`，避免 IDEA 的 uv 运行项把仓库根目录当作项目根导致后端模块无法导入。
- 在 `aitrade-fe/` 初始化 `pnpm + TypeScript + Vue 3 + Vite + ant-design-vue` 前端工程，并落地登录、用户维护、交易日志查询、策略配置四个管理台页面。
- 补齐前端路由、Pinia 登录态、统一 Axios 封装与 Bearer Token 恢复逻辑，改为通过 `POST /api/auth/me` 恢复当前用户信息。
- 修复前端 TypeScript / Vue 构建配置，补充 `src/env.d.ts`，恢复 `pnpm build` 成功。
- 修复前端通用 HTTP 解包错误，避免分页接口把整个响应包误传给表格组件，恢复交易日志页和管理员态渲染。
- 为后端 FastAPI Web API 补齐 CORS、健康检查、当前用户与退出登录接口，并保持统一响应结构。
- 为策略配置接口补齐参数校验与删除能力，支持按策略 schema 动态渲染和保存参数。
- 更新仓库根文档、后端文档与新增前端文档，补充前后端联调方式、页面能力与 Web API 说明。
- 补充协作约定：项目级长期信息写入仓库文档，个人协作偏好写入 Claude auto-memory，避免知识只留在对话里。

## 2026-04-21

- 修复 `aitrade-be/uv.lock` 与 `aitrade-be/pyproject.toml` 漂移导致的 `bash init-env.sh` 初始化失败问题，恢复迁移后的 uv 锁定环境同步流程。
- 收敛 `aitrade-be/query-trades.sh` 的环境前置条件，统一要求先完成 `bash init-env.sh` 并使用 `aitrade-be/.venv/bin/python` 执行。
- 收口根目录与后端文档边界：根文档保留仓库导航与兼容入口说明，后端文档继续承载运行细节，并补充 Web 入口说明。
- 调整仓库结构为前后端并存布局：当前 Python 后端整体迁移到 `aitrade-be/`，并预留 `aitrade-fe/` 目录承载未来前端界面。
- 在仓库根保留 `init-env.sh`、`start.sh`、`status.sh`、`stop.sh`、`query-trades.sh`、`package.sh` 兼容入口，内部统一转发到 `aitrade-be/`。
- 将 `config.yaml`、`.venv/`、`.aitrade/`、`logs/`、`dist/` 等后端运行态收拢到 `aitrade-be/`，避免继续污染仓库根目录。
- 重写根 `README.md` 与根 `CLAUDE.md` 为仓库级说明，并把后端详细运行说明下沉到 `aitrade-be/README.md` 与 `aitrade-be/CLAUDE.md`。
- 引入 SQLAlchemy 2.x 同步 ORM，并新增通用 `TradeStore` 抽象与工厂，让交易持久化不再直接绑定 SQLite 实现。
- 将 `app.trade.persistence` 主配置项从 `sqlite_path` 演进为 `database_url`，同时保留 `sqlite_path` 兼容旧配置。
- 改造 `query-trades.sh`：改为读取 `config.yaml` 中的持久化配置，并通过通用存储层查询交易记录和当前持仓。
- 更新 `README.md` 与 `CLAUDE.md`，同步说明新的持久化配置、默认 SQLite URL 和未来 MySQL 兼容方向。
- 新增 `aitrade/trade/trading_system/sqlite_trade_store.py`，把交易执行结果写入 `./.aitrade/trades.sqlite3`，并持久化本地持仓快照。
- 改造 `RiskManager`、`TradeExecutor`、`TradingBot` 和运行入口：记录风控拒绝、跳过执行、下单成功/失败等结构化交易明细，支持按配置恢复本地持仓。
- 新增 `app.trade.persistence` 配置与 `query-trades.sh` 查询脚本，支持直接查看最近交易记录、失败记录和当前持仓。
- 更新 `README.md` 与 `CLAUDE.md`，补充 SQLite 交易记录、持仓恢复和查询脚本说明。

## 2026-04-20

- 新增 `pyproject.toml` 与 `uv.lock`，将项目依赖切换为由 uv 管理，并固定 Python 版本为 `3.14`。
- 改造 `init-env.sh`、`start.sh`、`status.sh`、`stop.sh` 与 `package.sh`：本地环境改为 `.venv/`，初始化、运行与打包统一围绕 uv 工作流。
- 删除 `requirements.txt` 与 `create-deps.sh`，仓库只保留 `pyproject.toml` + `uv.lock` 作为依赖来源。
- 更新 `README.md` 与 `CLAUDE.md`，同步说明新的 uv 初始化、前台运行和打包方式。

- 更新 `.gitignore` 说明：明确 `uv.lock` 应提交到版本控制，继续忽略 `.venv`、日志文件和本地运行态产物。

## 2026-04-17

- 新增 `CLAUDE.md`，补充了面向后续 Claude Code 会话的仓库说明，包括常用命令、核心架构和文档协作规则。
- 更新 `README.md`，补充项目实际运行流程、主要入口和面向协作者的使用约定。
- 建立”有意义的仓库改动需同步更新 `CHANGELOG.md`”这一规则。
- 将”注释、文档、说明性文字默认使用中文”加入项目协作规则和持久记忆。
- 新增 `aitrade/trade/strategies/` 策略抽象层，支持通过配置切换 `gpt` 与 `btc_spot_breakout` 两种交易策略。
- 改造 `TradingBot`、`RiskManager`、`TradeExecutor` 和 `MarketDataFetcher`，使主链路支持策略化信号、价格止损与追踪止损更新。
- 更新 `config.example.yaml`、`README.md` 和 `CLAUDE.md`，补充双策略配置说明、BTC 现货突破策略参数，以及当前验证限制。
- 修复 `stop.sh` 文件内容异常的问题，恢复后台停止脚本，并同步更新运行文档。
- 改造 `init-env.sh` 为兼容 macOS 与 Linux 的跨平台初始化脚本，并同步更新初始化说明。
- 改造 `package.sh`，输出 `dist/` 下的时间戳 `tar.gz` 源码包，并排除本地环境与敏感配置。
- 重构 `init-env.sh`、`start.sh`、`status.sh` 与 `stop.sh`：统一 `.aitrade/` 运行态目录、`logs/` 日志提示、三态状态检查与幂等停止，并同步更新 `.gitignore`、`README.md` 和 `CLAUDE.md`。
- 增强 `start.sh` 和配置加载链路：启动前先校验 `config.yaml`，配置错误直接指出具体配置项；启动失败时输出最近日志，便于定位原因。
- 修复 Binance 沙盒模式下误加载 futures 市场的问题：在 `MarketDataFetcher` 和 `TradeExecutor` 中将 Binance 限制为 spot 市场，避免启动阶段访问 `binancefuture` 端点。
- 更新 `CLAUDE.md` “重要实现约束”部分：要求所有网络相关代码（交易所连接、API 请求）在遇到网络问题时，日志输出必须清晰，包含具体错误信息、失败位置和上下文，便于问题排查。
