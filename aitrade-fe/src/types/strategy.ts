export interface StrategyFieldSchema {
  field: string
  label: string
  type: 'number' | 'integer' | 'boolean'
  required: boolean
  min?: number
  max?: number
  step?: number
  description?: string
}

export interface StrategyDefinition {
  strategyType: string
  displayName: string
  description: string
  defaultParams: Record<string, unknown>
  paramSchema: StrategyFieldSchema[]
  schemaVersion: number
}

export interface StrategyProfile {
  id: number
  strategyType: string
  name: string
  description: string
  enabled: boolean
  params: Record<string, unknown>
  schemaVersion: number
  createdAt: string
  updatedAt: string
  definition?: StrategyDefinition
}
