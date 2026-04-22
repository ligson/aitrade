export interface ApiEnvelope<T> {
  success: boolean
  message: string
  trace: string
  httpCode: number
  data: T
}

export interface PageData<T> {
  total: number
  size: number
  offset: number
  data: T[]
}
