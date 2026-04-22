export interface CurrentUser {
  id: number
  username: string
  email: string
  nickname: string
  remark: string
  status: string
  isAdmin: boolean
}

export interface CaptchaPayload {
  captchaKey: string
  captchaSvg: string
  expireSeconds: number
}

export interface LoginPayload {
  token: string
  user: CurrentUser
}
