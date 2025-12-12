import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 300000, // 5 minutes for long-running analysis
  headers: {
    'Content-Type': 'application/json',
  },
})

export default apiClient
