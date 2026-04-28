import type { PageData } from './api'

export type TradeMode = 'live' | 'sandbox' | 'paper'

// 仍由部署期文件或运行环境维护、页面只读展示的系统信息。
export interface SystemSettingsReadonly {
  backtestDataDir: string
  freqtradeUserDataDir: string
  appLogDir: string
}

// 页面保存接口要求整份 editable 一起提交，即使当前页面只编辑其中一部分字段。
export interface SystemSettingsEditable {
  gptProvider: string
  gptModel: string
  gptApiKey: string
  gptBaseUrl: string
  hasGptApiKey: boolean
  // 读取设置时这里是掩码回显，不保证是明文 key。
  gptApiKeyMasked: string
  persistPosition: boolean
  restorePositionOnStartup: boolean
  tradeTaskDefaultFeeRate: number
  tradeTaskDefaultSlippageRate: number
  tradeTaskDefaultDailyLossStopEnabled: boolean
  tradeTaskDefaultDailyLossStopThreshold: number
  tradeFlowFeedEnabled: boolean
  tradeFlowFeedFreshnessSeconds: number
  tradeFlowFeedLookbackTrades: number
  supportedSymbols: string[]
  supportedTimeframes: string[]
  defaultSymbol: string
  defaultTimeframe: string
  downloadTimerange: string
  dataFormatOhlcv: string
  exportArchiveFormat: string
}

export interface SystemSettingsMeta {
  id: number
  name: string
  description: string
  schemaVersion: number
  updatedAt: string
}

export interface SystemSettings {
  readonly: SystemSettingsReadonly
  editable: SystemSettingsEditable
  meta: SystemSettingsMeta
}

export interface SystemSettingsSavePayload {
  editable: SystemSettingsEditable
  name?: string
  description?: string
}

export interface TradeTaskLogItem {
  id: number
  runId: number | null
  profileName: string
  runnerName: string
  eventType: string
  status: string
  message: string
  detail: Record<string, unknown>
  createdAt: string | null
}

export interface TradeTaskRunItem {
  // snapshot 是启动瞬间固化下来的运行快照，用于排障和审计，不会随着 profile 更新而回写变化。
  id: number
  runnerName: string
  tradeTaskProfileId: number | null
  profileName: string
  strategyProfileId: number | null
  strategyType: string
  strategySchemaVersion: number
  symbol: string
  timeframe: string
  tradeMode?: TradeMode
  sandboxTrade?: boolean
  tradeLimit: number
  feeRate: number
  slippageRate: number
  dailyLossStopEnabled: boolean
  dailyLossStopThreshold: number
  strategyParams: Record<string, unknown>
  snapshot: Record<string, unknown>
  status: string
  createdBy: string
  createdAt: string
  startedAt: string | null
  finishedAt: string | null
  stopRequestedAt: string | null
  errorMessage: string
}

// 这是当前 runner 的运行时状态视图，不等同于某一次 run 的最终历史记录。
export interface TradeTaskStatus {
  runnerName: string
  runId: number | null
  tradeTaskProfileId: number | null
  profileName: string
  status: string
  isRunning: boolean
  canStart: boolean
  canStop: boolean
  startedAt: string | null
  stoppedAt: string | null
  stopRequestedAt: string | null
  lastHeartbeatAt: string | null
  lastCycleStartedAt: string | null
  lastCycleFinishedAt: string | null
  nextRunAt: string | null
  lastError: string
  startedBy: string
  symbol: string
  timeframe: string
  timeframeMinutes: number | null
  strategyType: string
  updatedAt: string | null
  recentLogs: TradeTaskLogItem[]
  currentRun: TradeTaskRunItem | null
}

export interface TradeTaskProfile {
  id: number
  name: string
  description: string
  enabled: boolean
  strategyProfileId: number
  strategyProfileName: string
  strategyType: string
  symbol: string
  timeframe: string
  tradeMode?: TradeMode
  sandboxTrade?: boolean
  tradeLimit: number
  feeRate: number
  slippageRate: number
  dailyLossStopEnabled: boolean
  dailyLossStopThreshold: number
  runnerName: string
  createdAt: string
  updatedAt: string
}

export interface TradeTaskProfileSavePayload {
  id?: number
  name: string
  description: string
  enabled: boolean
  strategyProfileId: number
  symbol: string
  timeframe: string
  tradeMode?: TradeMode
  sandboxTrade?: boolean
  tradeLimit: number
  feeRate: number
  slippageRate: number
  dailyLossStopEnabled: boolean
  dailyLossStopThreshold: number
  runnerName: string
}

export interface TradeTaskStartPayload {
  tradeTaskProfileId: number
}

export interface TradeTaskLogQuery {
  offset: number
  size: number
  runnerName?: string
  runId?: number
  eventType?: string
  status?: string
  keyword?: string
  createdFrom?: string
  createdTo?: string
}

export type TradeTaskLogPage = PageData<TradeTaskLogItem>

export interface SystemLogFileItem {
  filename: string
  path: string
  type: string
  size: number
  modifiedAt: number
}

export interface SystemLogContent extends SystemLogFileItem {
  tailLines: number
  content: string
  truncated: boolean
}

export type SystemLogFilePage = PageData<SystemLogFileItem>
