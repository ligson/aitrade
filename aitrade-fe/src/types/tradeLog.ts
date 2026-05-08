import type { TradeMode } from './system'

export interface TradeLogItem {
  id: number
  owner_user_id: number | null
  created_at: string
  run_id: number | null
  trade_task_profile_id: number | null
  strategy: string
  trigger_source: string | null
  symbol: string
  side: string
  signal_confidence: number | null
  signal_reason: string | null
  market_price: number | null
  requested_amount: number | null
  stop_loss_price: number | null
  trailing_stop_price: number | null
  risk_per_trade: number | null
  exchange_type: string
  sandbox: boolean
  trade_mode?: TradeMode
  result: string
  result_reason: string | null
  order_id: string | null
  order_status: string | null
  order_type: string | null
  order_price: number | null
  order_amount: number | null
  order_cost: number | null
  fee_rate: number | null
  slippage_rate: number | null
  estimated_fill_price: number | null
  estimated_fee: number | null
  realized_pnl: number | null
  realized_pnl_net: number | null
  daily_loss_snapshot: Record<string, unknown> | null
  error_message: string | null
  signal_meta: Record<string, unknown>
  risk_snapshot: Record<string, unknown>
  position_before: Record<string, unknown> | null
  position_after: Record<string, unknown> | null
  order_raw: Record<string, unknown>
}

export interface PositionItem {
  owner_user_id: number | null
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
