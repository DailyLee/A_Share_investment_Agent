import apiClient from './client'

export interface ConfigRequest {
  api_key?: string
  base_url?: string
  model?: string
}

export interface ConfigResponse {
  api_key?: string
  api_key_set: boolean
  base_url?: string
  base_url_set: boolean
  model?: string
  model_set: boolean
}

export interface ApiResponse<T> {
  success: boolean
  message: string
  data: T
  timestamp: string
}

export async function setConfig(request: ConfigRequest): Promise<ApiResponse<ConfigResponse>> {
  const response = await apiClient.post<ApiResponse<ConfigResponse>>('/config/set', request)
  return response.data
}

export async function getConfig(): Promise<ApiResponse<ConfigResponse>> {
  const response = await apiClient.get<ApiResponse<ConfigResponse>>('/config/get')
  return response.data
}
