# aitrade-fe

这是 `aitrade` 的前端管理台，使用 `pnpm + TypeScript + Vue 3 + Vite + ant-design-vue`。

## 当前页面

- 登录：账户、密码、图形验证码
- 用户维护：用户名/邮箱/昵称/备注维护、密码重置、状态锁定
- 交易日志查询：交易日志分页查询、当前持仓抽屉
- 策略配置：策略介绍、动态参数表单、配置保存/删除
- 历史数据管理：按配置交易对白名单下载历史数据、zip 压缩包导入导出、文件列表管理
- 策略回测：按历史文件发起回测、查看任务详情与成交明细

## 开发命令

在 `aitrade-fe/` 目录下执行：

```bash
pnpm install
pnpm dev
pnpm build
```

也可以直接在仓库根目录执行：

```bash
pnpm --dir aitrade-fe install
pnpm --dir aitrade-fe dev
pnpm --dir aitrade-fe build
```

## 联调约定

开发环境默认 `VITE_API_BASE_URL` 为空，前端统一请求相对路径 `/api/...`，再通过 Vite 代理转发到后端。

Vite 开发服务默认监听：

- `http://127.0.0.1:5173`

开发时通过 Vite 代理转发：

- `/api`
- `/health`

代理目标默认是：

- `http://127.0.0.1:18080`

## 认证方式

- 登录成功后，把 Bearer Token 保存到 `localStorage`
- 页面刷新后会通过 `POST /api/auth/me` 恢复当前用户信息
- 收到 `401` 时前端会清理本地 token 并跳回 `/login`

## 构建说明

当前已验证 `pnpm build` 可成功产出 `dist/`。

如需在远端部署时指定前端请求的后端地址，可以在构建时覆盖：

```bash
VITE_API_BASE_URL=http://<remote-host>:18080 pnpm build
```
