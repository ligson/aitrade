# CHANGELOG

所有有意义的仓库变更都应记录在这里。

## 2026-04-28

- 修复交易日志记录 `symbol` 落库不稳定的问题：交易执行链路改为显式使用当前执行交易对写入 `trade_records`，避免页面出现“交易对”为空。
- 为交易日志补齐最小任务运行关联：`trade_records` 新增 `run_id / trade_task_profile_id`，旧库启动时会自动补列并补索引，交易日志接口也支持按 `runId` 过滤，便于按一次任务运行排查成交、跳过、风控拒绝与失败记录。
- 增强“交易中心 / 交易日志”页面：新增运行实例 ID、触发来源、订单 ID、错误信息与详情抽屉，并补充当前持仓的初始止损、追踪止损、最高价、最高收盘价展示，提升排障可读性。
- 打通任务运行到交易日志的页面联动：`交易任务控制` 与 `任务日志` 页面新增跳转入口，可直接带 `runId` 打开对应交易结果日志。
- 调整交易日志页“交易对”下拉框数据源：改为直接读取系统设置里的 `supportedSymbols`，不再依赖历史 `trade_records` 去重结果，避免交易记录为空时筛选项也为空。
- 重构交易方式为三态模型：后端配置、任务配置快照、运行时状态、交易执行器与交易日志统一支持 `live / sandbox / paper`，其中 `paper` 使用真实行情但不会调用真实下单。
- 管理台交易任务配置、任务控制与交易日志页面同步升级为三态展示：统一显示“真实交易 / 沙盒交易 / 纸上交易”，并在启动确认中明确提示真实交易会真实下单。
- 为历史数据库补齐交易方式兼容：`trade_task_profiles`、`trade_task_runs`、`trade_records` 以及旧 SQLite store 会自动补 `trade_mode` 字段，旧 `sandbox_trade / sandboxTrade / sandbox` 仍可兼容映射。
- 新增独立策略 `btc_spot_trend_breakout`：采用固定 `1h` 执行 + `4h` 趋势过滤的 BTC 现货趋势突破规则，并保持旧 `btc_spot_breakout` 行为不变。
- 打通多周期 live / paper / sandbox 执行链路：`TradingBot` 可按策略声明同时装配主周期与上下文周期数据，并按主周期决定运行节奏，避免把 `4h` 过滤策略错误地按页面任务周期驱动。
- 扩展离线回测支持 `btc_spot_trend_breakout` 与固定比例滑点：回测任务、历史数据库与前端表单统一支持 `slippageRate`，并在缺少 `4h` 历史数据时返回明确错误。
- 为交易任务补齐任务级执行现实参数与运行风控：系统设置新增交易任务默认 `feeRate / slippageRate / dailyLossStop*`，任务配置保存真实生效值，启动时固化到 run snapshot，运行中修改配置不会回溯影响当前实例。
- 交易执行链路新增手续费、滑点与已实现净盈亏建模：`paper` 模式按配置估算成交价与双边手续费，`live / sandbox` 统一抽取成交摘要并在缺少交易所手续费回包时按配置估算，交易日志新增成交价、手续费、净盈亏与单日亏损快照展示。
- 新增任务级“单日亏损停机”能力：按当前 `run_id + UTC 当日 + 卖出已实现净亏损` 聚合，达到阈值后写入 `risk_halt_triggered` 任务日志并把运行状态收敛为 `stopped`，不再误记为执行失败。
- 整理仓库本地运行产物边界：清理仓库根目录历史残留的 `.aitrade/`、`logs/` 以及后端/前端构建产物、日志和 Python 缓存，并同步更新仓库级说明，明确后端运行态统一收敛在 `aitrade-be/` 下。

## 2026-04-25

- 新增交易任务页面控制链路：后端补齐 `/api/system/trade-task/status`、`/api/system/trade-task/start`、`/api/system/trade-task/stop` 接口，支持在 Web 进程内以单实例方式查看、启动、停止交易任务，并把运行状态持久化到数据库，避免管理台重复启动。
- 重构 `TradingBot` 主循环为“单次周期执行 + 可中断等待”模式，既支持管理台控制开始/停止，也保持 `python -m aitrade` 与现有 Bot 脚本链路兼容。
- 管理台新增“交易中心 / 交易任务”独立页面，承载交易任务控制与状态展示；系统设置页恢复为纯系统配置展示，避免把实时运行控制混入静态配置页面。
- 明确 Web 启动后默认不自动运行交易任务；交易任务运行参数仍以 `aitrade-be/config.yaml` 为准，修改配置后需重新开始任务才会生效。
- 为交易任务补齐数据库事件日志：开始请求、启动成功、周期开始/完成、停止请求、停止完成、失败与残留状态都会写入 `trade_task_logs`，并提供最近日志概览与独立任务日志查询能力，便于追踪每次运行过程。

## 2026-04-27

- 系统设置页升级为可编辑模式：后端新增 `system_setting_profiles` 聚合配置表与 `/api/system/settings/save` 接口，前端“系统设置”页支持维护 GPT provider/model、持仓持久化开关、回测支持交易对/周期、默认周期、下载时间范围和历史数据格式等非敏感系统参数。
- 拆分系统设置页面信息架构：将原单页“系统设置”收口为“系统概览”，并新增“AI 设置 / 交易设置 / 数据设置”三个独立菜单页，沿用现有系统设置接口完成分类保存，降低单页复杂度。
- AI 设置页接管 `provider / model / api_key / base_url`：Web 场景下的 AI 密钥与可选自定义端点改由系统设置数据库维护，页面使用掩码回显 API Key，留空 Base URL 时继续按 provider 自动选择默认端点。
- 按新的系统设置边界精简 `aitrade-be/config.example.yaml`：移除 Web 场景下可由数据库维护的示例项，只保留密钥、数据库连接、代理、监听地址、目录路径和外部命令等部署期必需配置；被省略字段在 Web 首次初始化时会回落到文件当前值或运行时默认值。
- Web 运行时新增“文件配置 + 数据库覆盖”机制：`config.yaml` 继续承载密钥、数据库连接、代理、监听地址、目录路径和外部命令等敏感或部署期配置；系统设置页保存的非敏感参数会覆盖 Web 场景下的 `gpt`、`trade.persistence` 与 `backtest` 对应字段，并作用于后续新发起的回测任务与新启动的交易任务。
- 交易任务运行配置改为三层合并：启动任务时在 `config.yaml` 基础上先应用数据库系统设置，再叠加任务运行快照，确保新任务继承最新网页系统设置，而已运行任务仍保持启动时快照语义。
- 拆分“交易中心”下的任务控制与运行日志展示：`交易任务` 页收口为纯控制与状态页，新增独立 `任务日志` 页面承载交易任务运行事件的筛选、分页与详情查看，保留现有 `交易日志` 页面继续表示交易结果日志，避免两类日志混在同一页面。
- 后端新增 `POST /api/system/trade-task/logs/page` 接口，在 `system` 模块内复用 `trade_task_logs` 表提供任务运行日志分页查询，首版支持按事件、状态、关键词与时间范围筛选。
- 交易任务改造为页面配置与数据库驱动：新增交易任务配置与运行快照模型，支持在管理台维护多套任务配置，并在启动时固化 `策略 / 交易对 / 周期 / K线数量 / 沙盒模式` 等任务级参数，避免后续页面修改影响已运行实例。
- `POST /api/system/trade-task/start` 改为按所选任务配置启动，运行状态与任务日志新增 `runId / profileName / timeframe` 等关联字段；交易任务页同步升级为“配置区 + 控制区 + 当前运行快照”，并在任务日志页展示快照关联后的运行事件。
- 为交易任务启动链路修复后端锁重入死锁问题：`start/stop` 返回状态时不再在持锁状态下再次调用 `get_status()`，恢复页面点击“开始运行”后的及时响应。
- 将原单页 `交易任务` 继续拆成两个独立菜单页：新增 `交易任务配置` 与 `交易任务控制` 路由，旧 `/trade-tasks` 地址自动跳转到配置页；配置维护与运行控制职责分离，并支持从配置页携带 `profileId` 跳到控制页直接启动。
- 收口 Web 对 `config.yaml` 任务级配置的依赖：`python -m aitrade.web_runner` 与 `bash start-web.sh` 不再要求保留 `sandbox_trade / symbol / timeframe / limit / strategy.*` 等任务级 YAML 占位，真实任务参数统一以数据库配置与启动快照为准；CLI/Bot 直跑链路仍保持原有文件配置语义。
- 为系统设置、交易任务状态机与 AI 信号链路补充关键中文注释和分级日志，重点说明 Web/Bot 配置边界、整份 editable 保存语义、API Key 掩码保留旧值规则、run snapshot 固化语义与 stale/failed 等运行状态，便于后续维护和排障。
- 补充本地联调协作规则：默认固定复用 `127.0.0.1:5173` 前端端口与 `127.0.0.1:18081` 后端 Web 端口，启动前优先复用已运行进程，并优先遵循 `.idea/runConfigurations/fe_dev.xml` 与 `.idea/runConfigurations/be_web.xml` 的启动命令和工作目录，避免在同一会话里反复切换端口或新起多个开发进程。
- 增强远端部署稳态：`deploy.sh` 改为先停止当前 `current` 版本的 Web 服务，再切换新 release；同时补充 `current` 软链、运行态 PID 与实际监听 PID、一条关键 OpenAPI 路由和 `/health` 的联合校验，避免出现“源码已更新但旧进程仍占端口、线上继续提供旧路由表”的情况。
- 增强 Web 运维脚本排障能力：`start-web.sh` 新增端口监听者识别与启动后监听归属校验，`status-web.sh` 新增监听 PID/命令展示，并同步把这次旧进程占用 `18080` 导致新版本未生效的经验写入运维文档与后端 README。
- 补充脚本协作约束：仓库内 `*.sh` 脚本默认需要兼容 macOS 与 Linux，后续新增或修改脚本时应优先使用双平台都支持的命令与参数，避免引入 GNU 专属写法。

## 2026-04-24

- 将管理台左侧导航改为按业务域分组的二级菜单，当前按“交易中心 / 策略中心 / 数据中心 / 系统管理”分类展示，并同步调整页面面包屑为“分类 / 页面”结构，提升导航直观性与后续扩展性。
- 修复管理台右侧内容区在页面高度变小时的内容溢出问题：移除交易日志、策略配置、历史数据管理、策略回测页面卡片的固定高度，改为最小占满内容区，让超长内容统一走右侧内容区滚动条显示，避免表格把内容顶出可视区域。
- 新增“系统设置”与“系统日志”页面，并将系统级目录与只读配置从历史数据管理页迁移到系统设置页统一展示；历史数据管理页不再显示顶部目录提醒，只保留下载、导入导出、文件管理与用于回测等业务操作。
- 后端新增 `/api/system/settings`、`/api/system/logs/files`、`/api/system/logs/content` 接口，支持查看历史数据目录、Freqtrade `user_data` 目录、系统日志目录与关键只读配置，并支持在日志目录范围内安全分页查看日志文件和最后若干行内容。
- 优化策略回测页的历史文件展示：移除顶部提示条与额外的已选文件提示区，直接依赖表单里的交易对、周期、文件时间范围等字段承载所选历史文件信息，减少重复信息干扰。
- 策略回测页新增“开始前确认”交互：点击“开始回测”后先弹出确认窗口，展示策略配置、历史文件、交易对、周期、文件时间范围、初始资金与手续费率，只有确认后才真正创建回测任务。
- 回测任务新增协作式停止与 ETA 展示：后端新增 `/api/backtests/stop` 接口、`stop_requested / stopped` 状态、进度与预计完成时间字段，前端列表与详情页同步支持停止任务、显示停止中状态、展示进度与预计完成时间，并兼容旧 SQLite 表自动补列。
- 放开历史数据下载周期限制：后端新增 `app.backtest.supported_timeframes` 配置并通过接口返回，前端历史数据管理页改为可选周期下拉，当前默认支持 `5m / 15m / 30m / 1h / 4h / 1d`，系统设置页也同步展示支持周期。
- 收敛策略回测详情抽屉为只读信息展示：不再复用可编辑参数表单，改为纯描述项展示本次回测参数，并将下方表格明确命名为“成交明细”，无成交记录时显示只读提示，避免误解为可编辑页面。
- 收敛远端部署链路为可重复执行的“发布 + 更新”流程：后端继续使用 `/data/aitrade/releases` 与 `/data/aitrade/current` 管理版本，前端静态资源改为固定发布到 `/data/aitrade/shared/public`，部署脚本默认自动完成远端 Web 重启与健康检查，并自动处理共享静态目录的 SELinux 标签；文档也同步明确 Nginx 应固定指向共享静态目录。
- 补充前端表格统一展示规范：表头文字默认保持单行，表体内容允许换行，列宽按表头与关键信息设置最小宽度，内容区不足时通过表格横向滚动承载，后续新增表格页也需遵循这一规则。

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
