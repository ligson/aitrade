import { post } from './http'
import type { CaptchaPayload, CurrentUser, LoginPayload } from '@/types/auth'

export function fetchCaptcha() {
  return post<CaptchaPayload>('/api/auth/captcha')
}

export function login(payload: { username: string; password: string; captchaKey: string; captchaCode: string }) {
  return post<LoginPayload>('/api/auth/login', payload)
}

export function fetchCurrentUser() {
  return post<CurrentUser>('/api/auth/me')
}

export function logout() {
  return post<{ loggedOut: boolean }>('/api/auth/logout')
}
