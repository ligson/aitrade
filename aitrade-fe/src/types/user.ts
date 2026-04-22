export interface UserItem {
  id: number
  username: string
  email: string
  nickname: string
  remark: string
  status: string
  isAdmin: boolean
  createdAt: string
  updatedAt: string
  lastLoginAt: string | null
}
