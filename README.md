# aitrade

这是一个前后端并存的 Web 化自动交易系统仓库。

## 目录结构

- `aitrade-be/`：Python 后端，提供 FastAPI Web API、交易任务运行内核、配置模板、运维脚本与打包脚本
- `aitrade-fe/`：Vue 3 管理台，提供登录、系统设置、交易任务、任务日志、交易日志、策略配置、历史数据与回测页面

## 当前运行模式

仓库现已收敛为 **Web-only**：

- 后端唯一运行入口：`python -m aitrade.web_runner`
- 后端后台脚本：`bash start-web.sh / status-web.sh / stop-web.sh`
- 真实交易任务由 Web 管理台发起、停止和查看状态
- 不再支持独立 `python -m aitrade` 或 `bash start.sh / status.sh / stop.sh` 的 Bot/CLI 直跑模式

## 常用命令

如果继续在仓库根目录操作，推荐：

```bash
bash init-env.sh
bash package.sh
bash query-trades.sh latest 20
bash deploy.sh chenws-japan
bash deploy.sh chenws-japan --mode frontend
bash deploy.sh chenws-japan --mode backend
```

说明：
- `init-env.sh` 会转发到 `aitrade-be/` 初始化后端环境
- Web 服务控制脚本位于 `aitrade-be/`：`start-web.sh / status-web.sh / stop-web.sh`
- `query-trades.sh` 仍可用于本地查询结构化交易记录
- `deploy.sh` 默认执行全量部署（前端 + 后端），也支持 `--mode frontend` 或 `--mode backend` 分量部署
- 在 macOS 上执行 `package.sh` / `deploy.sh` 打包后端源码时，必须优先使用 GNU tar；若缺少 `gtar`，请先执行 `brew install gnu-tar`

## 运行态目录边界

后端程序目录保持在 `aitrade-be/`：

- `config.yaml`
- `.venv/`
- `.aitrade/`（PID 等程序控制运行态）
- `logs/`（shell 启动辅助日志）
- `dist/`

后端业务数据默认按 `app.data_root_dir`（默认 `~/.aitrade`）自动派生：

- SQLite：`~/.aitrade/trades.sqlite3`
- Python 应用日志：`~/.aitrade/logs`
- 历史数据：`~/.aitrade/backtest-data`
- Freqtrade `user_data`：`~/.aitrade/freqtrade-user-data`

## 文档入口

- 后端运行与实现说明：`aitrade-be/README.md`
- 后端协作约束：`aitrade-be/CLAUDE.md`
- 架构说明：`docs/architecture.md`
- 后端说明：`docs/backend.md`
- 运维说明：`docs/operations.md`

## 当前状态

- 本地联调默认复用 `http://127.0.0.1:5173 -> http://127.0.0.1:18081`
- 远端正式部署当前默认仍使用后端 `18080`
- Web 服务启动后不会自动运行交易任务；任务需在管理台中显式开始
- 任务运行时会基于系统设置与所选任务配置生成运行快照，运行中不会回读页面后续修改
