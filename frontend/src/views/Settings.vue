<template>
  <div class="max-w-2xl mx-auto">
    <el-card>
      <template #header>
        <div class="flex items-center">
          <el-icon class="mr-2"><Setting /></el-icon>
          <span class="text-xl font-bold">系统设置</span>
        </div>
      </template>

      <el-form :model="form" label-width="200px" class="mt-4">
        <el-form-item label="API Key" required>
          <el-input
            v-model="form.apiKey"
            type="password"
            show-password
            placeholder="请输入 OPENAI_COMPATIBLE_API_KEY"
            clearable
          />
        </el-form-item>

        <el-form-item label="Base URL" required>
          <el-input
            v-model="form.baseUrl"
            placeholder="请输入 OPENAI_COMPATIBLE_BASE_URL"
            clearable
          />
          <div class="text-sm text-gray-500 mt-1">
            例如: https://api.openai.com/v1
          </div>
        </el-form-item>

        <el-form-item label="Model" required>
          <el-input
            v-model="form.model"
            placeholder="请输入 OPENAI_COMPATIBLE_MODEL"
            clearable
          />
          <div class="text-sm text-gray-500 mt-1">
            例如: gpt-4, gpt-3.5-turbo
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSave" :loading="saving">
            保存设置
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <el-alert
        v-if="saveSuccess"
        title="设置已保存"
        type="success"
        :closable="false"
        class="mt-4"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { Setting } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { setConfig, getConfig } from '../api/config'

const settingsStore = useSettingsStore()

const form = ref({
  apiKey: '',
  baseUrl: '',
  model: '',
})

const saving = ref(false)
const saveSuccess = ref(false)

onMounted(async () => {
  // 先从本地存储加载
  form.value = {
    apiKey: settingsStore.apiKey,
    baseUrl: settingsStore.baseUrl,
    model: settingsStore.model,
  }

  // 尝试从后端获取当前配置
  try {
    const response = await getConfig()
    if (response.success && response.data) {
      // 如果后端有配置但本地没有，使用后端的配置
      if (response.data.api_key_set && !form.value.apiKey) {
        // API Key 不显示完整值，所以不更新
      }
      if (response.data.base_url_set && !form.value.baseUrl) {
        form.value.baseUrl = response.data.base_url || ''
      }
      if (response.data.model_set && !form.value.model) {
        form.value.model = response.data.model || ''
      }
    }
  } catch (error) {
    // 忽略错误，使用本地存储的值
    console.warn('Failed to load config from backend:', error)
  }
})

const handleSave = async () => {
  if (!form.value.apiKey || !form.value.baseUrl || !form.value.model) {
    ElMessage.warning('请填写所有必填项')
    return
  }

  saving.value = true
  saveSuccess.value = false

  try {
    // 保存到本地存储
    settingsStore.updateSettings(
      form.value.apiKey,
      form.value.baseUrl,
      form.value.model
    )

    // 调用后端 API 设置配置
    const response = await setConfig({
      api_key: form.value.apiKey,
      base_url: form.value.baseUrl,
      model: form.value.model,
    })

    if (response.success) {
      saveSuccess.value = true
      ElMessage.success('设置已保存并应用到后端')
      
      setTimeout(() => {
        saveSuccess.value = false
      }, 3000)
    } else {
      ElMessage.error(response.message || '保存失败')
    }
  } catch (error: any) {
    ElMessage.error('保存失败: ' + (error.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

const handleReset = () => {
  form.value = {
    apiKey: settingsStore.apiKey,
    baseUrl: settingsStore.baseUrl,
    model: settingsStore.model,
  }
}
</script>
