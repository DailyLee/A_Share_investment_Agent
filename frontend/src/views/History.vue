<template>
  <div class="max-w-6xl mx-auto">
    <el-card>
      <template #header>
        <div class="flex items-center justify-between">
          <div class="flex items-center">
            <el-icon class="mr-2"><Clock /></el-icon>
            <span class="text-xl font-bold">历史报告</span>
          </div>
          <el-button @click="handleRefresh" :loading="loading">
            <el-icon class="mr-1"><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <el-input
        v-model="searchText"
        placeholder="搜索股票代码或日期"
        class="mb-4"
        clearable
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <el-table
        v-loading="loading"
        :data="filteredReports"
        stripe
        style="width: 100%"
        @row-click="handleRowClick"
      >
        <el-table-column prop="ticker" label="股票代码" width="120" />
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column prop="filename" label="文件名" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              @click.stop="handleViewReport(row)"
            >
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && filteredReports.length === 0" description="暂无报告" />
    </el-card>

    <!-- 报告详情对话框 -->
    <el-dialog
      v-model="reportDialogVisible"
      :title="selectedReport?.filename"
      width="80%"
      fullscreen
    >
      <div v-loading="reportLoading" class="report-content">
        <div
          v-if="reportContent"
          class="markdown-body"
          v-html="renderedContent"
        />
        <el-empty v-else-if="!reportLoading" description="报告内容为空" />
      </div>
      <template #footer>
        <el-button @click="reportDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="handleDownloadReport">下载</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Clock, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getReportList, getReportContent } from '../api/reports'
import type { ReportInfo } from '../api/reports'
import { marked } from 'marked'

const loading = ref(false)
const reports = ref<ReportInfo[]>([])
const searchText = ref('')
const reportDialogVisible = ref(false)
const reportLoading = ref(false)
const reportContent = ref<string>('')
const selectedReport = ref<ReportInfo | null>(null)

const filteredReports = computed(() => {
  if (!searchText.value) {
    return reports.value
  }
  const search = searchText.value.toLowerCase()
  return reports.value.filter(
    (report) =>
      report.ticker.toLowerCase().includes(search) ||
      report.date.includes(search) ||
      report.filename.toLowerCase().includes(search)
  )
})

const renderedContent = computed(() => {
  if (!reportContent.value) return ''
  return marked(reportContent.value)
})

const fetchReports = async () => {
  loading.value = true
  try {
    const response = await getReportList()
    if (response.success && response.data) {
      // 解析文件名，提取 ticker 和 date
      reports.value = response.data.map((report) => {
        const match = report.filename.match(/^(\d+)_(\d{8})\.md$/)
        return {
          ...report,
          ticker: match ? match[1] : '',
          date: match
            ? `${match[2].substring(0, 4)}-${match[2].substring(4, 6)}-${match[2].substring(6, 8)}`
            : '',
        }
      })
      // 按日期倒序排序
      reports.value.sort((a, b) => b.date.localeCompare(a.date))
    } else {
      ElMessage.error(response.message || '获取报告列表失败')
    }
  } catch (error: any) {
    ElMessage.error('获取报告列表失败: ' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

const handleRefresh = () => {
  fetchReports()
}

const handleRowClick = (row: ReportInfo) => {
  handleViewReport(row)
}

const handleViewReport = async (report: ReportInfo) => {
  selectedReport.value = report
  reportDialogVisible.value = true
  reportLoading.value = true
  reportContent.value = ''

  try {
    const response = await getReportContent(report.filename)
    if (response.success && response.data) {
      reportContent.value = response.data.content
    } else {
      ElMessage.error(response.message || '获取报告内容失败')
    }
  } catch (error: any) {
    ElMessage.error('获取报告内容失败: ' + (error.message || '未知错误'))
  } finally {
    reportLoading.value = false
  }
}

const handleDownloadReport = () => {
  if (!selectedReport.value || !reportContent.value) return

  const blob = new Blob([reportContent.value], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = selectedReport.value.filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

onMounted(() => {
  fetchReports()
})
</script>

<style scoped>
.report-content {
  max-height: 70vh;
  overflow-y: auto;
  padding: 20px;
}

.markdown-body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  line-height: 1.6;
  color: #24292e;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  margin-top: 24px;
  margin-bottom: 16px;
  font-weight: 600;
  line-height: 1.25;
}

.markdown-body :deep(p) {
  margin-bottom: 16px;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin-bottom: 16px;
  padding-left: 2em;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  margin-bottom: 16px;
  width: 100%;
}

.markdown-body :deep(table th),
.markdown-body :deep(table td) {
  border: 1px solid #dfe2e5;
  padding: 6px 13px;
}

.markdown-body :deep(table th) {
  background-color: #f6f8fa;
  font-weight: 600;
}

.markdown-body :deep(code) {
  background-color: rgba(27, 31, 35, 0.05);
  border-radius: 3px;
  font-size: 85%;
  margin: 0;
  padding: 0.2em 0.4em;
}

.markdown-body :deep(pre) {
  background-color: #f6f8fa;
  border-radius: 3px;
  font-size: 85%;
  line-height: 1.45;
  overflow: auto;
  padding: 16px;
}

.markdown-body :deep(pre code) {
  background-color: transparent;
  border: 0;
  display: inline;
  line-height: inherit;
  margin: 0;
  overflow: visible;
  padding: 0;
  word-wrap: normal;
}
</style>
