export interface TradeLogItem {
  id: number
  created_at: string
  strategy: string
  trigger_source: string | null
  symbol: string
  side: string
  market_price: number | null
  requested_amount: number | null
  result: string
  result_reason: string | null
  order_id: string | null
  error_message: string | null
}

export interface PositionItem {
  symbol: string
  strategy: string
  entry_time: string | null
  entry_price: number | null
  amount: number | null
  stop_loss: number | null
  initial_stop_loss: number | null
  trailing_stop_price: number | null
  highest_price: number | null
  highest_close: number | null
  updated_at: string | null
}

export interface TradeLogFilterOptions {
  symbols: string[]
}
