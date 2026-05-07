import { post } from './http'
import type {
  SystemDeploymentSettings,
  SystemDeploymentSettingsSavePayload,
  SystemDeploymentSettingsSaveResult,
  SystemLogContent,
  SystemLogFilePage,
  SystemSettings,
  SystemSettingsSavePayload,
  TradeTaskLogPage,
  TradeTaskLogQuery,
  TradeTaskProfile,
  TradeTaskProfileSavePayload,
  TradeTaskStartPayload,
  TradeTaskStatus,
} from '@/types/system'

export function fetchSystemSettings() {
  return post<SystemSettings>('/api/system/settings')
}

export function saveSystemSettings(payload: SystemSettingsSavePayload) {
  return post<SystemSettings>('/api/system/settings/save', payload)
}

export function fetchSystemDeploymentSettings() {
  return post<SystemDeploymentSettings>('/api/system/deployment-settings')
}

export function saveSystemDeploymentSettings(payload: SystemDeploymentSettingsSavePayload) {
  return post<SystemDeploymentSettingsSaveResult>('/api/system/deployment-settings/save', payload)
}

export function pageSystemLogFiles(payload: {
  offset: number
  size: number
  keyword?: string
  type?: string
}) {
  return post<SystemLogFilePage>('/api/system/logs/files', payload)
}

export function fetchSystemLogContent(payload: {
  filename: string
  tailLines?: number
}) {
  return post<SystemLogContent>('/api/system/logs/content', payload)
}

export function fetchTradeTaskProfiles() {
  return post<TradeTaskProfile[]>('/api/system/trade-task/profiles/list')
}

export function saveTradeTaskProfile(payload: TradeTaskProfileSavePayload) {
  return post<TradeTaskProfile>('/api/system/trade-task/profiles/save', payload)
}

export function deleteTradeTaskProfile(id: number) {
  return post<{ deleted: boolean; id: number }>('/api/system/trade-task/profiles/delete', { id })
}

export function fetchTradeTaskStatus() {
  return post<TradeTaskStatus>('/api/system/trade-task/status')
}

export function pageTradeTaskLogs(payload: TradeTaskLogQuery) {
  return post<TradeTaskLogPage>('/api/system/trade-task/logs/page', payload)
}

export function startTradeTask(payload: TradeTaskStartPayload) {
  return post<TradeTaskStatus>('/api/system/trade-task/start', payload)
}

export function stopTradeTask() {
  return post<TradeTaskStatus>('/api/system/trade-task/stop')
}
