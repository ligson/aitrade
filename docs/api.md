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

## 历史数据与回测接口

### `POST /api/backtests/data/options`

返回历史数据管理与回测页所需的基础配置，包括：

- `supportedSymbols`
- `supportedTimeframes`
- `defaultSymbol`
- `defaultTimeframe`
- `dataFormatOhlcv`
- `downloadMode`
- `archiveFormat`

### `POST /api/backtests/data/catalog`

请求体：

```json
{
  "symbol": "BTC/USDT",
  "timeframe": "15m",
  "keyword": "BTC",
  "offset": 0,
  "size": 20
}
```

分页返回历史数据文件列表，当前每项至少包含：

- `filename`
- `symbol`
- `timeframe`
- `format`
- `path`
- `size`
- `modifiedAt`
- `timerangeFrom`
- `timerangeTo`

### `POST /api/backtests/data/download`

请求体：

```json
{
  "symbol": "BTC/USDT",
  "timeframe": "15m"
}
```

当前不再让前端传下载时间范围，后端会统一按配置里的最早时间范围下载到当前时点。

### `POST /api/backtests/data/export`

请求体：

```json
{
  "files": ["BTC_USDT-15m.json.gz"]
}
```

返回 zip 二进制流，压缩包内会附带 `manifest.json`。

### `POST /api/backtests/data/import`

- `multipart/form-data`
- 字段：
  - `file`：zip 压缩包
  - `overwrite`：是否覆盖同名文件

### `POST /api/backtests/data/delete`

请求体：

```json
{
  "filename": "BTC_USDT-15m.json.gz"
}
```

### `POST /api/backtests/run`

请求体：

```json
{
  "strategyProfileId": 1,
  "dataFile": "BTC_USDT-15m.json.gz",
  "initialBalance": 10000,
  "feeRate": 0.001
}
```

当前回测优先按历史文件发起，不再要求前端手工传 `timerange`。前端点击“开始回测”后会先展示确认弹窗，用户确认后才真正调用该接口。

### `POST /api/backtests/stop`

请求体：

```json
{
  "id": 4
}
```

用于对运行中的回测任务发起协作式停止。接口成功后任务会先进入 `stop_requested`，随后由回测线程主动收敛为 `stopped`。

### `POST /api/backtests/page`

分页查询回测任务列表。当前任务项会额外返回：

- `stopRequestedAt`
- `progressCurrent`
- `progressTotal`
- `progressPercent`
- `estimatedFinishAt`
- `canStop`

状态枚举当前至少包含：

- `pending`
- `running`
- `stop_requested`
- `stopped`
- `success`
- `failed`
- `unsupported`

### `POST /api/backtests/detail`

根据任务 ID 查询回测详情，返回字段与任务列表一致，并包含任务参数、数据来源、错误信息与成交明细查询所需主键。

### `POST /api/backtests/trades`

分页查询回测成交明细。

## 系统设置与系统日志接口

### `POST /api/system/settings`

返回系统级只读信息，当前至少包含：

- `backtestDataDir`
- `freqtradeUserDataDir`
- `appLogDir`
- `defaultTimeframe`
- `dataFormatOhlcv`
- `exportArchiveFormat`
- `downloadTimerange`

其中目录字段会尽量返回绝对路径，便于直接在管理台展示。

### `POST /api/system/logs/files`

请求体：

```json
{
  "offset": 0,
  "size": 20,
  "keyword": "trade",
  "type": "trade"
}
```

分页返回日志文件列表，当前每项至少包含：

- `filename`
- `path`
- `type`
- `size`
- `modifiedAt`

其中 `type` 当前区分为：

- `app`
- `trade`

### `POST /api/system/logs/content`

请求体：

```json
{
  "filename": "trade_2026-04-24-08.log",
  "tailLines": 200
}
```

返回指定日志文件最后若干行内容，当前至少包含：

- `filename`
- `path`
- `type`
- `size`
- `modifiedAt`
- `tailLines`
- `content`
- `truncated`

日志内容读取会限制在系统日志目录内，拒绝路径穿越与非 `.log` 文件读取。

## 当前鉴权约束

- 登录后，前端通过 Bearer Token 调业务接口。
- 用户管理接口要求管理员权限。
- 未登录或 token 失效时，前端会清理 token 并跳回登录页。
