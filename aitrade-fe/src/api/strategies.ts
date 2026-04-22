import { post } from './http'
import type { StrategyDefinition, StrategyProfile } from '@/types/strategy'

export function fetchStrategyDefinitions() {
  return post<StrategyDefinition[]>('/api/strategies/definitions')
}

export function fetchStrategyProfiles() {
  return post<StrategyProfile[]>('/api/strategies/list')
}

export function saveStrategyProfile(payload: {
  id?: number
  strategyType: string
  name: string
  description: string
  enabled: boolean
  params: Record<string, unknown>
}) {
  return post<StrategyProfile>('/api/strategies/save', payload)
}

export function deleteStrategyProfile(id: number) {
  return post<{ deleted: boolean; id: number }>('/api/strategies/delete', { id })
}
