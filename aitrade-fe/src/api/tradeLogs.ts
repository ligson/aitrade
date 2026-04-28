import { post } from './http'
import type { PageData } from '@/types/api'
import type { PositionItem, TradeLogFilterOptions, TradeLogItem } from '@/types/tradeLog'

export function pageTradeLogs(payload: {
  offset: number
  size: number
  strategy?: string
  side?: string
  result?: string
  symbol?: string
  runId?: number
  createdFrom?: string
  createdTo?: string
}) {
  return post<PageData<TradeLogItem>>('/api/trade-logs/page', payload)
}

export function fetchPositions() {
  return post<PositionItem[]>('/api/trade-logs/positions')
}

export function fetchTradeLogFilterOptions() {
  return post<TradeLogFilterOptions>('/api/trade-logs/filter-options')
}
