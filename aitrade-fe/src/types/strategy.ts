export interface StrategyFieldSchema {
  field: string
  label: string
  type: 'number' | 'integer' | 'boolean' | 'string'
  required: boolean
  min?: number
  max?: number
  step?: number
  description?: string
}

export type StrategyCategory = 'kline' | 'gpt' | 'ai' | 'fusion'

export interface FusionKlineNode {
  nodeType: 'strategy_profile' | 'builtin_technical'
  strategyProfileId: number | null
  strategyType: string
  name: string
  enabled: boolean
  weight: number
  params: Record<string, unknown>
  requires_1h_timeframe?: boolean
}

export interface FusionSignalSourceNode {
  signalSourceProfileId: number | null
  sourceType: string
  name: string
  enabled: boolean
  required: boolean
  weight: number
  thresholds: {
    buy_ratio_threshold: number
    sell_ratio_threshold: number
    imbalance_threshold: number
  }
  params: Record<string, unknown>
}

export interface FusionStrategyParams {
  klineNodes: FusionKlineNode[]
  signalSourceNodes: FusionSignalSourceNode[]
  filters: {
    min_available_nodes: number
    allow_degraded: boolean
    min_confidence: number
    buy_threshold: number
    sell_threshold: number
  }
  riskControls: {
    default_risk_per_trade: number
    shared_atr_period: number
    shared_atr_stop_mult: number
    shared_atr_trail_mult: number
  }
  decisionPolicy: {
    mode: 'weighted_score'
  }
}

export interface StrategyDefinition {
  strategyType: string
  displayName: string
  description: string
  defaultParams: Record<string, unknown>
  paramSchema: StrategyFieldSchema[]
  schemaVersion: number
  backtestSupported: boolean
  strategyCategory: StrategyCategory
  configMode: 'flat_params' | 'structured'
  usableAsFusionNode: boolean
  supportsSpot: boolean
  supportsPaper: boolean
  supportsBacktest: boolean
  fixedConstraints: string[]
}

export interface FusionSummary {
  klineNodeCount: number
  signalSourceNodeCount: number
  minAvailableNodes: number
  allowDegraded: boolean
  decisionMode: string
  requires1hTimeframe: boolean
}

export interface StrategyProfile {
  id: number
  ownerUserId: number | null
  strategyType: string
  name: string
  description: string
  enabled: boolean
  params: Record<string, unknown>
  schemaVersion: number
  createdAt: string
  updatedAt: string
  definition?: StrategyDefinition
  fusionSummary?: FusionSummary | null
}

export interface InvalidStrategyProfile {
  id: number
  ownerUserId: number | null
  strategyType: string
  name: string
  enabled: boolean
  createdAt: string
  updatedAt: string
  errorStage: 'json_load' | 'normalize' | 'summarize' | string
  errorMessage: string
}

export interface StrategyProfileListSummary {
  total: number
  validCount: number
  invalidCount: number
}

export interface StrategyProfileListResult {
  items: StrategyProfile[]
  invalidItems: InvalidStrategyProfile[]
  summary: StrategyProfileListSummary
}
