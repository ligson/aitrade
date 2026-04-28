export interface SignalSourceFieldSchema {
  field: string
  label: string
  type: 'number' | 'integer' | 'boolean' | 'string'
  required: boolean
  min?: number
  max?: number
  step?: number
  description?: string
}

export interface SignalSourceDefinition {
  sourceType: string
  displayName: string
  description: string
  defaultParams: Record<string, unknown>
  paramSchema: SignalSourceFieldSchema[]
  schemaVersion: number
  runtimeSupported: boolean
}

export interface SignalSourceProfile {
  id: number
  sourceType: string
  name: string
  description: string
  enabled: boolean
  params: Record<string, unknown>
  schemaVersion: number
  createdAt: string
  updatedAt: string
  definition?: SignalSourceDefinition
}
