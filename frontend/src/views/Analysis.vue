<template>
  <div class="max-w-6xl mx-auto">
    <el-card class="mb-4">
      <template #header>
        <div class="flex items-center">
          <el-icon class="mr-2"><Document /></el-icon>
          <span class="text-xl font-bold">AI Agent 股票分析</span>
        </div>
      </template>

      <el-form :model="analysisForm" label-width="120px" class="mb-4">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="股票代码" required>
              <el-input
                v-model="analysisForm.ticker"
                placeholder="请输入股票代码，如：002848"
                clearable
                @keyup.enter="handleStartAnalysis"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="新闻数量">
              <el-input-number
                v-model="analysisForm.num_of_news"
                :min="1"
                :max="100"
                :step="1"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="初始资金">
              <el-input-number
                v-model="analysisForm.initial_capital"
                :min="0"
                :step="10000"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="初始持仓">
              <el-input-number
                v-model="analysisForm.initial_position"
                :min="0"
                :step="100"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <el-button
            type="primary"
            @click="handleStartAnalysis"
            :loading="analyzing"
            :disabled="!analysisForm.ticker"
          >
            开始分析
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 分析状态 -->
    <el-card v-if="currentRunId" class="mb-4">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-bold">分析状态</span>
          <el-tag :type="statusTagType">{{ analysisStatus }}</el-tag>
        </div>
      </template>

      <!-- 错误提示 -->
      <div v-if="errorMessage" class="mb-4">
        <el-alert
          :title="errorMessage"
          type="error"
          :closable="true"
          @close="errorMessage = ''"
          show-icon
        >
          <template #default>
            <div class="error-details">
              <p class="font-semibold">{{ errorMessage }}</p>
              <p v-if="errorDetails" class="mt-2 text-sm text-gray-600">{{ errorDetails }}</p>
            </div>
          </template>
        </el-alert>
      </div>

      <!-- 状态消息 -->
      <div v-if="statusMessage && !errorMessage" class="mb-2">
        <el-alert :title="statusMessage" :type="statusType" :closable="false" />
      </div>

      <el-progress
        v-if="analysisStatus === 'running'"
        :percentage="progressPercentage"
        :status="progressStatus"
        class="mb-4"
      />

      <div v-if="analysisStatus === 'running'" class="text-center mb-4">
        <el-icon class="is-loading text-2xl"><Loading /></el-icon>
        <p class="mt-2 text-gray-600">分析正在进行中，请稍候...</p>
      </div>

      <!-- 日志显示区域 -->
      <div v-if="logs.length > 0" class="mt-4">
        <div class="flex items-center justify-between mb-2">
          <h4 class="font-semibold">执行日志</h4>
          <el-button
            size="small"
            text
            @click="showLogs = !showLogs"
          >
            {{ showLogs ? '隐藏日志' : '显示日志' }}
          </el-button>
        </div>
        <el-collapse-transition>
          <div v-show="showLogs">
            <el-scrollbar height="400px" class="border rounded p-4 bg-gray-50">
              <template v-if="logs.length > 0">
                <div
                  v-for="(log, index) in logs"
                  :key="index"
                  class="mb-3 pb-3 border-b last:border-b-0"
                >
                  <div class="flex items-start justify-between mb-1">
                    <div class="flex items-center gap-2">
                      <el-tag size="small" type="info">{{ log.agent_name }}</el-tag>
                      <span class="text-xs text-gray-500">
                        {{ formatTimestamp(log.timestamp) }}
                      </span>
                    </div>
                  </div>
                  <div class="mt-2">
                    <div v-if="log.request_data" class="mb-2">
                      <span class="text-xs font-semibold text-blue-600">请求:</span>
                      <pre class="text-xs mt-1 p-2 bg-white rounded border overflow-x-auto">{{ formatLogData(log.request_data) }}</pre>
                    </div>
                    <div v-if="log.response_data">
                      <span class="text-xs font-semibold text-green-600">响应:</span>
                      <pre class="text-xs mt-1 p-2 bg-white rounded border overflow-x-auto">{{ formatLogData(log.response_data) }}</pre>
                    </div>
                  </div>
                </div>
              </template>
              <div v-else class="text-center text-gray-400 py-8">
                暂无日志
              </div>
            </el-scrollbar>
          </div>
        </el-collapse-transition>
      </div>
    </el-card>

    <!-- 分析结果 -->
    <el-card v-if="analysisResult" class="mb-4">
      <template #header>
        <div class="flex items-center">
          <el-icon class="mr-2"><Document /></el-icon>
          <span class="text-xl font-bold">分析结果</span>
        </div>
      </template>

      <div v-if="analysisResult.final_decision" class="mb-4">
        <h3 class="text-lg font-bold mb-2">最终决策</h3>
        <el-card class="bg-gray-50">
          <pre class="whitespace-pre-wrap">{{ JSON.stringify(analysisResult.final_decision, null, 2) }}</pre>
        </el-card>
      </div>

      <div v-if="analysisResult.agent_results && Object.keys(analysisResult.agent_results).length > 0">
        <h3 class="text-lg font-bold mb-2">Agent 分析结果</h3>
        <el-collapse>
          <el-collapse-item
            v-for="(result, agentName) in analysisResult.agent_results"
            :key="agentName"
            :title="agentName"
            :name="agentName"
          >
            <el-card class="bg-gray-50">
              <pre class="whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
            </el-card>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { Document, Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { startAnalysis, getAnalysisStatus, getAnalysisResult, getLogs } from '../api/analysis'
import type { AnalysisResult, LLMInteractionLog } from '../api/analysis'

const analysisForm = ref({
  ticker: '',
  show_reasoning: true,
  num_of_news: 5,
  initial_capital: 100000,
  initial_position: 0,
})

const analyzing = ref(false)
const currentRunId = ref<string | null>(null)
const analysisStatus = ref<string>('')
const statusMessage = ref<string>('')
const errorMessage = ref<string>('')
const errorDetails = ref<string>('')
const analysisResult = ref<AnalysisResult | null>(null)
const statusCheckInterval = ref<number | null>(null)
const logs = ref<LLMInteractionLog[]>([])
const showLogs = ref(true)
const logCheckInterval = ref<number | null>(null)

const statusTagType = computed(() => {
  if (analysisStatus.value === 'completed') return 'success'
  if (analysisStatus.value === 'error') return 'danger'
  if (analysisStatus.value === 'running') return 'warning'
  return 'info'
})

const statusType = computed(() => {
  if (analysisStatus.value === 'completed') return 'success'
  if (analysisStatus.value === 'error') return 'error'
  if (analysisStatus.value === 'running') return 'info'
  return 'info'
})

const progressPercentage = computed(() => {
  if (analysisStatus.value === 'completed') return 100
  if (analysisStatus.value === 'running') return 50
  return 0
})

const progressStatus = computed(() => {
  if (analysisStatus.value === 'completed') return 'success'
  if (analysisStatus.value === 'error') return 'exception'
  return undefined
})

const handleStartAnalysis = async () => {
  if (!analysisForm.value.ticker) {
    ElMessage.warning('请输入股票代码')
    return
  }

  analyzing.value = true
  analysisResult.value = null
  analysisStatus.value = ''
  statusMessage.value = ''
  errorMessage.value = ''
  errorDetails.value = ''
  logs.value = []

  try {
    const response = await startAnalysis({
      ticker: analysisForm.value.ticker,
      show_reasoning: analysisForm.value.show_reasoning,
      num_of_news: analysisForm.value.num_of_news,
      initial_capital: analysisForm.value.initial_capital,
      initial_position: analysisForm.value.initial_position,
    })

    if (response.success && response.data) {
      currentRunId.value = response.data.run_id
      analysisStatus.value = response.data.status
      statusMessage.value = response.data.message
      ElMessage.success('分析任务已启动')

      // 开始轮询状态和日志
      startStatusPolling()
      startLogPolling()
    } else {
      errorMessage.value = response.message || '启动分析失败'
      errorDetails.value = '请检查后端服务是否正常运行，或查看控制台获取更多信息'
      ElMessage.error(errorMessage.value)
    }
  } catch (error: any) {
    const errorMsg = error.response?.data?.detail || error.message || '未知错误'
    errorMessage.value = '启动分析失败'
    errorDetails.value = errorMsg
    
    // 检查是否是网络错误
    if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error')) {
      errorDetails.value = '无法连接到后端服务，请确保后端服务已启动（运行 poetry run python run_with_backend.py）'
    } else if (error.response?.status === 500) {
      errorDetails.value = `服务器内部错误: ${errorMsg}`
    } else if (error.response?.status === 404) {
      errorDetails.value = `API端点不存在: ${errorMsg}`
    }
    
    ElMessage.error(errorMessage.value + ': ' + errorDetails.value)
  } finally {
    analyzing.value = false
  }
}

const startStatusPolling = () => {
  if (statusCheckInterval.value) {
    clearInterval(statusCheckInterval.value)
  }

  statusCheckInterval.value = window.setInterval(async () => {
    if (!currentRunId.value) return

    try {
      const statusResponse = await getAnalysisStatus(currentRunId.value)
      if (statusResponse.success && statusResponse.data) {
        analysisStatus.value = statusResponse.data.status

        if (statusResponse.data.status === 'completed') {
          // 获取结果
          await fetchAnalysisResult()
          stopStatusPolling()
          stopLogPolling()
        } else if (statusResponse.data.status === 'error') {
          errorMessage.value = statusResponse.data.error || '分析失败'
          errorDetails.value = '分析过程中发生错误，请查看日志了解详细信息'
          statusMessage.value = ''
          stopStatusPolling()
          stopLogPolling()
        }
      } else {
        errorMessage.value = statusResponse.message || '获取状态失败'
        errorDetails.value = '无法获取分析状态，请检查后端服务'
      }
    } catch (error: any) {
      console.error('获取状态失败:', error)
      const errorMsg = error.response?.data?.detail || error.message || '未知错误'
      errorMessage.value = '获取分析状态失败'
      errorDetails.value = errorMsg
      
      if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error')) {
        errorDetails.value = '无法连接到后端服务，请确保后端服务已启动'
      }
    }
  }, 2000) // 每2秒检查一次
}

const startLogPolling = () => {
  if (logCheckInterval.value) {
    clearInterval(logCheckInterval.value)
  }

  logCheckInterval.value = window.setInterval(async () => {
    if (!currentRunId.value || analysisStatus.value === 'completed' || analysisStatus.value === 'error') {
      return
    }

    try {
      const logData = await getLogs(currentRunId.value, 100)
      logs.value = logData.sort((a, b) => 
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      )
    } catch (error: any) {
      // 日志获取失败不显示错误，因为可能是日志还未生成
      console.debug('获取日志失败:', error)
    }
  }, 3000) // 每3秒获取一次日志
}

const stopLogPolling = () => {
  if (logCheckInterval.value) {
    clearInterval(logCheckInterval.value)
    logCheckInterval.value = null
  }
}

const stopStatusPolling = () => {
  if (statusCheckInterval.value) {
    clearInterval(statusCheckInterval.value)
    statusCheckInterval.value = null
  }
}

const fetchAnalysisResult = async () => {
  if (!currentRunId.value) return

  try {
    // 最后一次获取日志
    try {
      const logData = await getLogs(currentRunId.value, 100)
      logs.value = logData.sort((a, b) => 
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      )
    } catch (error) {
      console.debug('获取最终日志失败:', error)
    }

    const response = await getAnalysisResult(currentRunId.value)
    if (response.success && response.data) {
      analysisResult.value = response.data
      statusMessage.value = '分析完成'
      errorMessage.value = ''
      errorDetails.value = ''
      ElMessage.success('分析完成')
    } else {
      errorMessage.value = response.message || '获取结果失败'
      errorDetails.value = '分析已完成，但无法获取结果数据'
      ElMessage.error(errorMessage.value)
    }
  } catch (error: any) {
    const errorMsg = error.response?.data?.detail || error.message || '未知错误'
    errorMessage.value = '获取结果失败'
    errorDetails.value = errorMsg
    
    if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error')) {
      errorDetails.value = '无法连接到后端服务，请确保后端服务已启动'
    }
    
    ElMessage.error(errorMessage.value + ': ' + errorDetails.value)
  }
}

const formatTimestamp = (timestamp: string) => {
  try {
    const date = new Date(timestamp)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return timestamp
  }
}

const formatLogData = (data: any): string => {
  try {
    if (typeof data === 'string') {
      return data
    }
    return JSON.stringify(data, null, 2)
  } catch {
    return String(data)
  }
}

const handleReset = () => {
  analysisForm.value = {
    ticker: '',
    show_reasoning: true,
    num_of_news: 5,
    initial_capital: 100000,
    initial_position: 0,
  }
  currentRunId.value = null
  analysisStatus.value = ''
  statusMessage.value = ''
  errorMessage.value = ''
  errorDetails.value = ''
  analysisResult.value = null
  logs.value = []
  stopStatusPolling()
  stopLogPolling()
}

onUnmounted(() => {
  stopStatusPolling()
  stopLogPolling()
})
</script>
