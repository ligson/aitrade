# aitrade

这是一个前后端并存的交易系统仓库。

当前目录结构：

- `aitrade-be/`：Python 后端，包含交易机器人、FastAPI Web API、配置模板、运行脚本与打包脚本
- `aitrade-fe/`：Vue 3 管理后台，包含登录、用户维护、交易日志查询与策略配置页面

## 仓库入口

如果你希望继续在仓库根目录操作，可以直接使用兼容入口：

```bash
bash init-env.sh
bash start.sh
bash status.sh
bash stop.sh
bash query-trades.sh latest 20
bash package.sh
```

这些脚本会自动转发到 `aitrade-be/`，因此后端运行态也会统一落在 `aitrade-be/` 下。

如果需要后端的详细初始化、运行、配置和架构说明，请查看：

- `aitrade-be/README.md`
- `aitrade-be/CLAUDE.md`

## 运行态目录

后端相关运行文件现在统一位于 `aitrade-be/`：

- 配置文件：`aitrade-be/config.yaml`
- 虚拟环境：`aitrade-be/.venv/`
- 运行态：`aitrade-be/.aitrade/`
- 日志：`aitrade-be/logs/`
- 数据库：`aitrade-be/.aitrade/trades.sqlite3`
- 打包产物：`aitrade-be/dist/`

## 文档分层

- 仓库级说明：当前 `README.md` 与根目录 `CLAUDE.md`
- 后端详细说明：`aitrade-be/README.md` 与 `aitrade-be/CLAUDE.md`

## 当前状态

- 后端已经迁移到 `aitrade-be/`
- 前端管理台已经落地在 `aitrade-fe/`，技术栈为 `pnpm + TypeScript + Vue 3 + Vite + ant-design-vue`
- Web 管理台当前覆盖登录（账户/密码/图形验证码）、用户维护、交易日志查询和策略配置
- 前后端本地联调默认通过 `http://127.0.0.1:5173 -> http://127.0.0.1:18080` 进行
