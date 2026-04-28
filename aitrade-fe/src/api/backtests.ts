import { post, postBlob, postFormData } from './http'
import type {
  BacktestDataCatalogPage,
  BacktestDataImportResult,
  BacktestDataOptions,
  BacktestDataStatus,
  BacktestJobItem,
  BacktestPageData,
  BacktestTradePageData,
} from '@/types/backtest'

export function fetchBacktestDataOptions() {
  return post<BacktestDataOptions>('/api/backtests/data/options')
}

export function fetchBacktestDataStatus(payload?: {
  symbol?: string
  timeframe?: string
}) {
  return post<BacktestDataStatus>('/api/backtests/data/status', payload)
}

export function pageBacktestDataFiles(payload: {
  symbol?: string
  timeframe?: string
  keyword?: string
  offset: number
  size: number
}) {
  return post<BacktestDataCatalogPage>('/api/backtests/data/catalog', payload)
}

export function downloadBacktestData(payload?: {
  symbol?: string
  timeframe?: string
}) {
  return post<{
    command: string[]
    stdout: string
    stderr: string
    status: BacktestDataStatus
  }>('/api/backtests/data/download', payload)
}

export function exportBacktestDataArchive(files: string[]) {
  return postBlob('/api/backtests/data/export', { files })
}

export function importBacktestDataArchive(payload: { file: File; overwrite?: boolean }) {
  const formData = new FormData()
  formData.append('file', payload.file)
  formData.append('overwrite', String(Boolean(payload.overwrite)))
  return postFormData<BacktestDataImportResult>('/api/backtests/data/import', formData)
}

export function deleteBacktestDataFile(filename: string) {
  return post<{ deleted: boolean; filename: string }>('/api/backtests/data/delete', { filename })
}

export function runBacktest(payload: {
  strategyProfileId: number
  dataFile?: string
  initialBalance: number
  feeRate: number
  slippageRate: number
}) {
  return post<BacktestJobItem>('/api/backtests/run', payload)
}

export function stopBacktest(id: number) {
  return post<BacktestJobItem>('/api/backtests/stop', { id })
}

export function pageBacktests(payload: {
  offset: number
  size: number
  keyword?: string
  status?: string
}) {
  return post<BacktestPageData>('/api/backtests/page', payload)
}

export function fetchBacktestDetail(id: number) {
  return post<BacktestJobItem>('/api/backtests/detail', { id })
}

export function pageBacktestTrades(payload: {
  jobId: number
  offset: number
  size: number
}) {
  return post<BacktestTradePageData>('/api/backtests/trades', payload)
}
