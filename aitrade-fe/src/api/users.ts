import { post } from './http'
import type { PageData } from '@/types/api'
import type { UserItem } from '@/types/user'

export function pageUsers(payload: { offset: number; size: number; keyword: string }) {
  return post<PageData<UserItem>>('/api/users/page', payload)
}

export function createUser(payload: {
  username: string
  email: string
  nickname: string
  password: string
  remark: string
  isAdmin: boolean
}) {
  return post<UserItem>('/api/users/create', payload)
}

export function updateUser(payload: { id: number; email: string; nickname: string; remark: string }) {
  return post<UserItem>('/api/users/update', payload)
}

export function resetPassword(payload: { id: number; password: string }) {
  return post<Record<string, never>>('/api/users/reset-password', payload)
}

export function changeUserStatus(payload: { id: number; status: string }) {
  return post<Record<string, never>>('/api/users/change-status', payload)
}
