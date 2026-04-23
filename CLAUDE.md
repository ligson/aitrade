# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库概览

当前仓库采用前后端并存布局：

- `aitrade-be/`：Python 后端项目
- `aitrade-fe/`：前端管理台项目

如果任务只涉及自动交易、策略、配置、脚本、日志、持久化或打包，默认工作目标是 `aitrade-be/`。

## 常用命令

仓库根目录保留了兼容入口：

```bash
bash init-env.sh
bash start.sh
bash status.sh
bash stop.sh
bash query-trades.sh latest 20
bash package.sh
```

这些脚本会转发到 `aitrade-be/` 内执行。

如需后端的详细初始化、运行、配置和实现说明，优先查看 `aitrade-be/README.md` 与 `aitrade-be/CLAUDE.md`。

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

## 重要提醒

- 当前前端已落地在 `aitrade-fe/`，默认本地开发入口是 `pnpm --dir aitrade-fe dev`。
- 修改根目录兼容脚本时，要确保它们仍然只做薄转发，不重复承载后端核心逻辑。
- 如果修改网络相关后端代码，日志必须清晰包含错误信息、失败位置和上下文。
