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
  runnerName: string
  eventType: string
  status: string
  message: string
  detail: Record<string, unknown>
  createdAt: string | null
}

export interface TradeTaskStatus {
  runnerName: string
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
  timeframeMinutes: number | null
  strategyType: string
  updatedAt: string | null
  recentLogs: TradeTaskLogItem[]
}

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
