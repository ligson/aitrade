import type { PageData } from './api'

export interface SystemSettings {
  backtestDataDir: string
  freqtradeUserDataDir: string
  appLogDir: string
  supportedTimeframes: string[]
  defaultTimeframe: string
  dataFormatOhlcv: string
  exportArchiveFormat: string
  downloadTimerange: string
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
  id: number
  runnerName: string
  tradeTaskProfileId: number | null
  profileName: string
  strategyProfileId: number | null
  strategyType: string
  strategySchemaVersion: number
  symbol: string
  timeframe: string
  sandboxTrade: boolean
  tradeLimit: number
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
  sandboxTrade: boolean
  tradeLimit: number
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
  sandboxTrade: boolean
  tradeLimit: number
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
