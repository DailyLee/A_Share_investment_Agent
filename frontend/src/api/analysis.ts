import apiClient from './client'
import axios from 'axios'

export interface StockAnalysisRequest {
  ticker: string
  show_reasoning?: boolean
  num_of_news?: number
  initial_capital?: number
  initial_position?: number
}

export interface StockAnalysisResponse {
  run_id: string
  ticker: string
  status: string
  message: string
  submitted_at: string
  completed_at?: string
}

export interface ApiResponse<T> {
  success: boolean
  message: string
  data: T
  timestamp: string
}

export interface AnalysisStatus {
  run_id: string
  status: string
  start_time: string
  end_time?: string
  is_complete?: boolean
  error?: string
}

export interface AnalysisResult {
  run_id: string
  ticker: string
  completion_time?: string
  final_decision?: any
  agent_results?: Record<string, any>
}

export async function startAnalysis(request: StockAnalysisRequest): Promise<ApiResponse<StockAnalysisResponse>> {
  const response = await apiClient.post<ApiResponse<StockAnalysisResponse>>('/analysis/start', request)
  return response.data
}

export async function getAnalysisStatus(runId: string): Promise<ApiResponse<AnalysisStatus>> {
  const response = await apiClient.get<ApiResponse<AnalysisStatus>>(`/analysis/${runId}/status`)
  return response.data
}

export async function getAnalysisResult(runId: string): Promise<ApiResponse<AnalysisResult>> {
  const response = await apiClient.get<ApiResponse<AnalysisResult>>(`/analysis/${runId}/result`)
  return response.data
}

export interface LLMInteractionLog {
  agent_name: string
  timestamp: string
  request_data: any
  response_data: any
  run_id?: string
}

export async function getLogs(runId: string, limit: number = 100): Promise<LLMInteractionLog[]> {
  // 日志接口不在 /api 前缀下，使用代理路径
  const response = await axios.get<LLMInteractionLog[]>(`/agent/logs/`, {
    params: {
      run_id: runId,
      limit: limit
    }
  })
  return response.data
}
