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
