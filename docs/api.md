# Web API 说明

## 统一响应结构

当前 Web API 统一返回如下结构：

```json
{
  "success": true,
  "message": "",
  "trace": "",
  "httpCode": 200,
  "data": {}
}
```

- `success`：是否成功
- `message`：业务提示信息
- `trace`：调试堆栈，仅在允许显示时返回
- `httpCode`：HTTP 状态码镜像
- `data`：业务数据

## 健康检查

- `GET /health`
- `POST /health`

返回：

```json
{
  "success": true,
  "data": {
    "status": "ok"
  }
}
```

## 认证接口

### `POST /api/auth/captcha`

生成图形验证码，返回：

- `captchaKey`
- `captchaSvg`
- `expireSeconds`

### `POST /api/auth/login`

请求体：

```json
{
  "username": "admin",
  "password": "admin123456",
  "captchaKey": "...",
  "captchaCode": "..."
}
```

成功后返回：

- `token`
- `user`

失败时会返回统一业务错误，例如：

- `请输入用户名`
- `请输入密码`
- `请输入验证码`
- `验证码已失效，请刷新后重试`
- `验证码错误`
- `用户名或密码错误`

### `GET /api/auth/me` / `POST /api/auth/me`

返回当前登录用户。

### `POST /api/auth/logout`

返回：

```json
{
  "loggedOut": true
}
```

## 用户接口

### `POST /api/users/page`

请求体：

```json
{
  "offset": 0,
  "size": 20,
  "keyword": ""
}
```

分页返回统一放在：

- `data.total`
- `data.size`
- `data.offset`
- `data.data`

### `POST /api/users/create`

创建用户。

### `POST /api/users/update`

更新用户基本信息。

### `POST /api/users/reset-password`

重置用户密码。

### `POST /api/users/change-status`

切换用户状态。

## 交易日志接口

### `POST /api/trade-logs/page`

请求体支持：

```json
{
  "offset": 0,
  "size": 20,
  "strategy": "gpt",
  "side": "buy",
  "result": "executed",
  "symbol": "BTC/USDT",
  "createdFrom": "2026-04-23T00:00:00+00:00",
  "createdTo": "2026-04-23T23:59:59+00:00"
}
```

### `POST /api/trade-logs/positions`

返回当前持仓快照列表。

### `POST /api/trade-logs/filter-options`

返回交易日志页筛选项所需的可选值，当前至少包含：

```json
{
  "symbols": ["BTC/USDT"]
}
```

## 策略接口

### `POST /api/strategies/definitions`

返回策略类型定义：

- `strategyType`
- `displayName`
- `description`
- `defaultParams`
- `paramSchema`
- `schemaVersion`

### `POST /api/strategies/list`

返回策略配置列表。

### `POST /api/strategies/save`

创建或更新策略配置。

### `POST /api/strategies/delete`

删除策略配置。

## 当前鉴权约束

- 登录后，前端通过 Bearer Token 调业务接口。
- 用户管理接口要求管理员权限。
- 未登录或 token 失效时，前端会清理 token 并跳回登录页。
