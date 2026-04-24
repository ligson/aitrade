# 运行与运维说明

## 常用入口

仓库根目录保留了兼容脚本：

```bash
bash init-env.sh
bash start.sh
bash status.sh
bash stop.sh
bash query-trades.sh latest 20
bash package.sh
```

这些脚本会转发到 `aitrade-be/`，适合继续从仓库根目录操作。

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

## 启动

### 后端 Bot

```bash
bash start.sh
bash status.sh
bash stop.sh
```

### 后端 Web API 调试

```bash
cd aitrade-be
uv run python -m aitrade.web_runner
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
- 后端：`http://127.0.0.1:18080`

开发环境中前端通过 Vite 代理访问后端，因此修改 `.env.development` 或后端路由后，通常需要分别重启前端或后端进程。

## 常见排障

### 1. 登录按钮没有反应

优先检查：

- 前端登录表单是否正确绑定 `:model`
- 浏览器 Network 中是否发出了 `/api/auth/login`

### 2. 浏览器报 CORS

优先检查：

- 前端开发环境是否走 Vite `/api` 代理
- `VITE_API_BASE_URL` 是否被写成了直连 `http://127.0.0.1:18080`
- 后端 `web.cors_allow_origins` 是否包含前端地址

### 3. 新增后端接口后前端报 404

如果前端页面已经更新，但新接口返回 404，通常是后端进程还没重启。当前 Web 入口默认不带自动热重载。

### 4. 登录出现 traceback

业务异常应返回统一响应结构。如果页面直接看到 traceback，说明某个错误没有被转成 `ApiError` 体系，优先检查认证、验证码与参数校验链路。

### 5. 交易日志筛选不准确

优先检查：

- 时间范围是否被正确转成 ISO 字符串
- 策略值是否使用策略类型而不是策略配置名称

## 打包

```bash
bash package.sh
```

会在 `aitrade-be/dist/` 下生成带时间戳的源码包，并默认排除本地虚拟环境、日志与 `config.yaml`。

## 远端部署

```bash
bash deploy.sh chenws-japan
```

当前正式部署约定：

- 后端版本目录通过 `/data/aitrade/releases/<release>` 管理
- 当前后端入口固定使用 `/data/aitrade/current/aitrade-be`
- 共享配置固定为 `/data/aitrade/shared/config.yaml`
- 前端静态目录固定为 `/data/aitrade/shared/public`

部署脚本默认会自动完成：

- 本地前端构建与后端打包
- 远端上传、解压、切换 `current`
- 前端静态资源全量更新到 `/data/aitrade/shared/public`
- 远端执行 `init-env.sh`、`stop-web.sh`、`start-web.sh`、`status-web.sh`
- 校验共享静态目录与本机 `http://127.0.0.1:18080/health`

Nginx 静态站点根目录应固定指向 `/data/aitrade/shared/public`，不要指向具体 release 目录；`/api` 再反代到后端 Web 服务。

如果服务器启用了 SELinux，还需要保证 `/data/aitrade/shared/public` 使用 `httpd_sys_content_t` 上下文；当前部署脚本会自动尝试执行 `semanage fcontext` 与 `restorecon`。

## 运行态目录

后端运行态统一位于 `aitrade-be/`：

- `config.yaml`
- `.venv/`
- `.aitrade/`
- `logs/`
- `dist/`

不要把这些运行文件重新散落回仓库根目录。
