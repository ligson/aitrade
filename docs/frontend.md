# 前端说明

## 技术栈

前端位于：

- `aitrade-fe/`

当前技术栈：

- Vue 3
- TypeScript
- Vite
- Pinia
- Vue Router
- ant-design-vue

## 启动方式

```bash
pnpm --dir aitrade-fe dev
```

默认本地开发地址：

- `http://127.0.0.1:5173`

构建命令：

```bash
pnpm --dir aitrade-fe build
```

## 页面结构

当前管理台包含以下页面：

- 登录页：`/login`
- 交易日志：`/trade-logs`
- 策略配置：`/strategies`
- 用户维护：`/users`

默认登录后首页会跳转到：

- `/trade-logs`

## 路由与登录态

路由定义位于：

- `aitrade-fe/src/router/index.ts`

登录态由 Pinia 管理：

- `aitrade-fe/src/stores/auth.ts`

关键行为：

- 访问非登录页前会尝试恢复 token 对应的当前用户
- 未登录访问业务页时会跳转到 `/login`
- 已登录访问 `/login` 会重定向到 `/trade-logs`

## HTTP 与代理

Axios 封装位于：

- `aitrade-fe/src/api/http.ts`

开发环境中，`VITE_API_BASE_URL` 默认为空，前端统一请求相对路径 `/api/...`，再通过 Vite 代理转发到后端。

Vite 代理配置位于：

- `aitrade-fe/vite.config.ts`

当前会代理：

- `/api`
- `/health`

目标地址默认为：

- `http://127.0.0.1:18080`

## 页面能力

### 登录页

- 用户名、密码、图形验证码登录
- 前端包含字段级必填校验
- 图形验证码通过后端 `POST /api/auth/captcha` 获取

### 交易日志页

- 支持交易日志分页查询
- 当前筛选项为：策略、方向、结果、交易对、交易时间范围
- 筛选项尽量使用固定选项，减少手工输入
- 支持查看当前持仓抽屉
- 表格中的方向和结果已做标签化展示

### 策略配置页

- 展示策略定义和策略配置列表
- 支持创建、编辑、删除策略配置
- 表单参数根据后端返回的 schema 动态渲染

### 用户维护页

- 管理员可分页查询用户
- 支持新增用户、编辑用户、重置密码、切换状态

## 开发约束

- 页面交互调整后，应优先在浏览器里实际点一遍，而不只看构建是否通过。
- 需要新增固定选项的筛选器时，优先使用 `Select`、`DatePicker`、`RangePicker` 等组件，不要让用户承担无谓的自由输入成本。
- 与后端联调时，优先保持接口值与后端真实枚举一致，例如交易日志中的 `strategy` 当前对应策略类型，而不是策略配置名称。
