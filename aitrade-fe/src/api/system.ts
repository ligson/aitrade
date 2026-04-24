import { post } from './http'
import type { SystemLogContent, SystemLogFilePage, SystemSettings } from '@/types/system'

export function fetchSystemSettings() {
  return post<SystemSettings>('/api/system/settings')
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
