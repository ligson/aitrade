import type { PageData } from './api'

export interface BacktestSummary {
  symbol: string
  timeframe: string
  initialBalance: number
  finalEquity: number
  totalReturn: number
  maxDrawdown: number
  tradeCount: number
  completedTradeCount: number
  winRate: number
  requiredHistory: number
  slippageRate: number
}

export interface BacktestDataStatus {
  available: boolean
  pair: string
  timeframe: string
  timerange: string
  path: string
  format: string
  size?: number | null
  modifiedAt?: string | null
  dataDir?: string
  userDataDir?: string
}

export interface BacktestDataOptions {
  supportedSymbols: string[]
  supportedTimeframes: string[]
  defaultSymbol: string
  defaultTimeframe: string
  dataFormatOhlcv: string
  downloadMode: string
  archiveFormat: string
}

export interface BacktestDataFileItem {
  filename: string
  symbol: string
  timeframe: string
  format: string
  path: string
  size: number
  modifiedAt: string
  timerangeFrom: string
  timerangeTo: string
  timerangeLabel: string
  available: boolean
  sourceType: string
}

export interface BacktestDataImportResult {
  imported: BacktestDataFileItem[]
  skipped: Array<{
    filename: string
    reason: string
  }>
  failed: Array<{
    filename: string
    reason: string
  }>
}

export interface BacktestJobDataSource {
  sourceType?: string
  filename?: string
  path?: string
  symbol?: string
  timeframe?: string
  format?: string
  size?: number
  timerange?: string
  timerangeFrom?: string
  timerangeTo?: string
  modifiedAt?: string
  available?: boolean
}

export interface BacktestJobItem {
  id: number
  strategyType: string
  strategyProfileId: number | null
  profileName: string
  symbol: string
  timeframe: string
  timerangeFrom: string
  timerangeTo: string
  status: string
  initialBalance: number
  feeRate: number
  slippageRate: number
  summary: Partial<BacktestSummary>
  params: Record<string, unknown>
  dataSource: BacktestJobDataSource
  errorMessage: string
  createdBy: string
  createdAt: string
  startedAt?: string | null
  finishedAt?: string | null
  stopRequestedAt?: string | null
  progressCurrent?: number | null
  progressTotal?: number | null
  progressPercent?: number | null
  estimatedFinishAt?: string | null
  canStop?: boolean
}

export interface BacktestTradeItem {
  id: number
  jobId: number
  barTime: string
  side: string
  price: number
  quantity: number
  fee: number
  pnl: number | null
  reason: string
  signal: Record<string, unknown>
  position: Record<string, unknown>
  createdAt: string
}

export type BacktestDataCatalogPage = PageData<BacktestDataFileItem>
export type BacktestPageData = PageData<BacktestJobItem>
export type BacktestTradePageData = PageData<BacktestTradeItem>
