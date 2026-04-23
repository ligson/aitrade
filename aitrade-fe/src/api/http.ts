import axios from 'axios'
import { message } from 'ant-design-vue'

import { router } from '@/router'
import type { ApiEnvelope } from '@/types/api'
import { clearToken, getToken } from '@/utils/token'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 15000,
})

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => {
    const payload = response.data as ApiEnvelope<unknown>
    if (!payload.success) {
      message.error(payload.message || '请求失败')
      return Promise.reject(new Error(payload.message || '请求失败'))
    }
    return response
  },
  (error) => {
    const status = error.response?.status
    const apiMessage = error.response?.data?.message as string | undefined
    if (status === 401) {
      clearToken()
      if (router.currentRoute.value.path !== '/login') {
        router.replace('/login')
      }
    }
    message.error(apiMessage || error.message || '请求失败')
    return Promise.reject(error)
  },
)

export async function post<T>(url: string, data?: unknown): Promise<T> {
  const response = await http.post<ApiEnvelope<T>>(url, data)
  return response.data.data
}

export async function get<T>(url: string): Promise<T> {
  const response = await http.get<ApiEnvelope<T>>(url)
  return response.data.data
}

export default http
