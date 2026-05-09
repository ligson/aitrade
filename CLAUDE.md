# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库概览

当前仓库采用前后端并存布局：

- `aitrade-be/`：Python 后端项目
- `aitrade-fe/`：前端管理台项目

如果任务只涉及自动交易、策略、配置、脚本、日志、持久化或打包，默认工作目标是 `aitrade-be/`。

## 当前运行模式

仓库已经收敛为 **Web-only**：

- 唯一后端运行入口是 `python -m aitrade.web_runner`
- 后台脚本只保留 `aitrade-be/start-web.sh`、`status-web.sh`、`stop-web.sh`
- 交易任务由管理台页面启动、停止和查看状态
- 不要再恢复或新增独立 Bot/CLI 直跑入口、`python -m aitrade`、`start.sh / status.sh / stop.sh`

## 常用命令

仓库根目录保留的兼容入口：

```bash
bash init-env.sh
bash package.sh
bash query-trades.sh latest 20
bash deploy.sh chenws-japan
bash deploy.sh chenws-japan --mode frontend
bash deploy.sh chenws-japan --mode backend
```

说明：
- 这些脚本会转发到 `aitrade-be/` 内执行
- Web 服务控制脚本位于 `aitrade-be/`，不是仓库根目录
- `deploy.sh` 默认执行全量部署（前端 + 后端），也支持 `--mode frontend` 与 `--mode backend`
- 在 macOS 上执行后端源码打包时，必须优先使用 GNU tar；若缺少 `gtar`，请先执行 `brew install gnu-tar`
- 如需后端详细初始化、运行、配置和实现说明，优先查看 `aitrade-be/README.md` 与 `aitrade-be/CLAUDE.md`

## 目录边界

后端运行态统一位于 `aitrade-be/`：

- `config.yaml`
- `.venv/`
- `.aitrade/`
- `logs/`
- `dist/`

不要再把新的后端运行文件放回仓库根目录。

## 文档协作规则

- 每次有意义的仓库改动，都要同步更新 `CHANGELOG.md`。
- 仓库级说明优先放根目录 `README.md` / `CLAUDE.md`。
- 架构、模块、接口和运维类长文档优先收敛到根目录 `docs/`。
- 后端实现、运行和约束说明优先放 `aitrade-be/README.md` / `aitrade-be/CLAUDE.md`。
- 当一次会话形成对后续仍有价值的长期信息时，项目级知识写入仓库文档，个人协作偏好写入 Claude auto-memory，不要只保留在聊天记录里。
- 注释、文档、说明性文字默认使用中文，除非用户明确要求使用其他语言。
- 生成或修改代码时，要为关键逻辑补充合理注释，并补足有助于排障的分级日志；不要只给出裸代码，但也避免堆砌噪音型注释和日志。

## 重要提醒

- 当前前端已落地在 `aitrade-fe/`，默认本地开发入口是 `pnpm --dir aitrade-fe dev`。
- 本地联调默认固定复用既有端口：前端优先复用 `127.0.0.1:5173`，后端 Web 优先复用 `127.0.0.1:18081`；启动前先检查是否已有进程在跑，能复用就不要重复启动，除非用户明确要求隔离验证，否则不要擅自切换临时端口。
- 如需按 IDE 约定启动，优先复用项目内 `.idea/runConfigurations/fe_dev.xml` 与 `.idea/runConfigurations/be_web.xml` 对应命令和工作目录，不要在同一会话里反复新起多个前后端开发进程。
- 修改根目录兼容脚本时，要确保它们仍然只做薄转发，不重复承载后端核心逻辑；部署模式解析与真实发布逻辑统一维护在 `aitrade-be/deploy.sh`。
- 修改仓库内 Shell 脚本时，默认必须同时兼容 macOS 与 Linux，优先使用两边都支持的命令与参数，避免随手引入 GNU 专属写法；但后端源码打包在 macOS 上是例外，必须优先使用 GNU tar（`gtar` 或 PATH 中的 GNU tar）。
- 如果修改网络相关后端代码，日志必须清晰包含错误信息、失败位置和上下文。
- 新增或调整前端表格页时，统一遵循以下展示规则：表头文字不换行，表体内容允许换行；列宽需要按表头与关键信息设置合理最小宽度；当内容区宽度不足时，优先提供表格横向滚动，不要挤压表头或把内容顶出内容区。
