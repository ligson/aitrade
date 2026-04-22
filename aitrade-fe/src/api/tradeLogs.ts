import { post } from './http'
import type { PageData } from '@/types/api'
import type { PositionItem, TradeLogItem } from '@/types/tradeLog'

export function pageTradeLogs(payload: {
  offset: number
  size: number
  strategy?: string
  side?: string
  result?: string
  symbol?: string
  createdFrom?: string
  createdTo?: string
}) {
  return post<PageData<TradeLogItem>>('/api/trade-logs/page', payload)
}

export function fetchPositions() {
  return post<PositionItem[]>('/api/trade-logs/positions')
}
