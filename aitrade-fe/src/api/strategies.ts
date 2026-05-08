import { post } from './http'
import type { SignalSourceDefinition, SignalSourceProfile } from '@/types/signalSource'
import type { StrategyDefinition, StrategyProfile, StrategyProfileListResult } from '@/types/strategy'

export function fetchStrategyDefinitions() {
  return post<StrategyDefinition[]>('/api/strategies/definitions')
}

export function fetchStrategyProfiles() {
  return post<StrategyProfileListResult>('/api/strategies/list')
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

export function fetchSignalSourceDefinitions() {
  return post<SignalSourceDefinition[]>('/api/signal-sources/definitions')
}

export function fetchSignalSourceProfiles() {
  return post<SignalSourceProfile[]>('/api/signal-sources/list')
}

export function saveSignalSourceProfile(payload: {
  id?: number
  sourceType: string
  name: string
  description: string
  enabled: boolean
  params: Record<string, unknown>
}) {
  return post<SignalSourceProfile>('/api/signal-sources/save', payload)
}

export function deleteSignalSourceProfile(id: number) {
  return post<{ deleted: boolean; id: number }>('/api/signal-sources/delete', { id })
}
