# 运行与运维说明

## 常用入口

仓库根目录保留的兼容脚本：

```bash
bash init-env.sh
bash package.sh
bash query-trades.sh latest 20
bash deploy.sh chenws-japan
```

Web 服务控制脚本位于 `aitrade-be/`：

```bash
cd aitrade-be
bash start-web.sh
bash status-web.sh
bash stop-web.sh
```

当前仓库为 Web-only，不再提供 `start.sh / status.sh / stop.sh`。

## 初始化

推荐：

```bash
bash init-env.sh
```

或：

```bash
cd aitrade-be
bash init-env.sh
```

初始化后先检查并补全 `aitrade-be/config.yaml`，再启动 Web 服务。

## 启动

### 后端 Web API 调试

```bash
cd aitrade-be
uv run python -m aitrade.web_runner
```

### 后端 Web 后台脚本

```bash
cd aitrade-be
bash start-web.sh
bash status-web.sh
bash stop-web.sh
```

如果需要在 IDE 里调试断点，建议：

- 模块名：`aitrade.web_runner`
- 工作目录：`aitrade-be/`
- Python 解释器：`aitrade-be/.venv/bin/python`

### 前端

```bash
pnpm --dir aitrade-fe dev
```

## 本地联调

默认本地联调关系：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:18081`

开发环境中前端通过 Vite 代理访问后端，因此修改前端 `.env`、后端监听配置或路由后，通常需要分别重启前端或后端进程。

这里的 `18081` 仅用于本地开发协作约定；远端正式部署当前默认仍使用 `18080`。

## 交易任务运维

当前真实交易任务通过管理台维护和控制：

- 在“任务中心”页维护多套任务配置、查看运行状态并执行开始/停止
- 在“任务日志”页查看运行事件，并可返回任务中心继续处理对应任务
- 在“交易日志”页查看实际成交与执行结果

重要约束：

- Web 服务启动后不会自动运行交易任务
- 任务启动时会生成 run snapshot，运行中不会回读页面后续修改
- 当前允许不同交易对并发运行；同一交易对仍不支持并发启动

## 常见排障

### 1. Web 服务起不来

优先检查：

- `bash status-web.sh`
- `aitrade-be/config.yaml` 是否缺少最小必留项
- `aitrade-be/logs/web-launcher.log`
- `app.web.port` 是否被其他进程占用

### 2. 浏览器报 CORS

优先检查：

- 前端开发环境是否走 Vite `/api` 代理
- `VITE_API_BASE_URL` 是否被写成了直连地址
- 后端 `app.web.cors_allow_origins` 是否包含前端地址

### 3. 页面可以打开，但任务无法启动

优先检查：

- 系统设置里的 AI 参数是否完整
- 任务配置里的交易对、周期、策略配置是否有效
- 任务日志是否出现 `config_error`、`failed` 或风控停机日志
- 交易所连接、代理和 API Key 是否可用

### 4. 部署后接口仍 404

排查顺序：

1. `ssh <server> "cd /data/aitrade/current/aitrade-be && bash status-web.sh"`
2. 确认 `status-web.sh` 里的 `PID` 与 `监听 PID` 一致
3. 确认 `readlink /data/aitrade/current` 已指向本次 release
4. `curl http://127.0.0.1:18080/health`
5. `curl http://127.0.0.1:18080/openapi.json`

要牢记：`/health` 正常只说明“有进程在响应”，不等于当前 release 已真正接管端口。

## 打包

```bash
bash package.sh
```

会在 `aitrade-be/dist/` 下生成带时间戳的源码包，并默认排除本地虚拟环境、日志与 `config.yaml`。

如果是在 macOS 上执行打包或部署，后端源码归档必须优先使用 GNU tar；若缺少 `gtar`，请先执行：

```bash
brew install gnu-tar
```

## 远端部署

```bash
bash deploy.sh chenws-japan
bash deploy.sh chenws-japan --mode frontend
bash deploy.sh chenws-japan --mode backend
```

当前正式部署约定：

- 后端版本目录通过 `/data/aitrade/releases/<release>` 管理
- 当前后端入口固定使用 `/data/aitrade/current/aitrade-be`
- 共享配置固定为 `/data/aitrade/shared/config.yaml`
- 前端静态目录固定为 `/data/aitrade/shared/public`

部署脚本默认使用 `--mode all`，会自动完成：

- 本地前端构建与后端打包
- 远端上传、解压新 release，并准备共享 `config.yaml`
- 先停止当前 `current` 版本的 Web 服务，再切换 `current`
- 前端静态资源全量更新到 `/data/aitrade/shared/public`
- 远端执行 `init-env.sh`、`start-web.sh`、`status-web.sh`
- 校验共享静态目录、本机 `http://127.0.0.1:18080/health`、`current` 软链目标，以及 `openapi.json` 是否包含关键路由

分量部署说明：

- `--mode frontend`：只构建并上传前端静态资源到 `/data/aitrade/shared/public`，不会打后端源码包、切换 `current` 或重启 Web。
- `--mode backend`：只打包并发布后端 release、切换 `current`、重启 Web，并校验 `/health` 与关键 OpenAPI 路由；不会重新构建或覆盖前端静态目录。
- 兼容简写：`bash deploy.sh chenws-japan frontend|backend|all` 也可使用，但推荐统一写成 `--mode ...`。

Nginx 静态站点根目录应固定指向 `/data/aitrade/shared/public`，不要指向具体 release 目录；`/api` 再反代到后端 Web 服务。

## 运行态目录

后端程序控制运行态位于 `aitrade-be/`：

- `config.yaml`
- `.venv/`
- `.aitrade/`
- `logs/`
- `dist/`

默认业务数据位于 `app.data_root_dir`（默认 `~/.aitrade`）下，不要把这些运行文件重新散落回仓库根目录。
