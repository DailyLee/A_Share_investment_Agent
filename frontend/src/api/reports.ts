import axios from 'axios'

export interface ReportInfo {
  filename: string
  ticker: string
  date: string
}

export interface ReportListResponse {
  success: boolean
  message: string
  data: ReportInfo[]
  timestamp: string
}

export interface ReportContentResponse {
  success: boolean
  message: string
  data: {
    filename: string
    content: string
  }
  timestamp: string
}

const reportsClient = axios.create({
  baseURL: '/agent/reports',
  timeout: 10000,
})

export async function getReportList(): Promise<ReportListResponse> {
  const response = await reportsClient.get<ReportListResponse>('/')
  return response.data
}

export async function getReportContent(filename: string): Promise<ReportContentResponse> {
  const response = await reportsClient.get<ReportContentResponse>(`/${filename}`)
  return response.data
}
