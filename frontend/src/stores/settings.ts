import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSettingsStore = defineStore('settings', () => {
  const apiKey = ref<string>(localStorage.getItem('OPENAI_COMPATIBLE_API_KEY') || '')
  const baseUrl = ref<string>(localStorage.getItem('OPENAI_COMPATIBLE_BASE_URL') || '')
  const model = ref<string>(localStorage.getItem('OPENAI_COMPATIBLE_MODEL') || '')

  function saveSettings() {
    localStorage.setItem('OPENAI_COMPATIBLE_API_KEY', apiKey.value)
    localStorage.setItem('OPENAI_COMPATIBLE_BASE_URL', baseUrl.value)
    localStorage.setItem('OPENAI_COMPATIBLE_MODEL', model.value)
  }

  function updateSettings(newApiKey: string, newBaseUrl: string, newModel: string) {
    apiKey.value = newApiKey
    baseUrl.value = newBaseUrl
    model.value = newModel
    saveSettings()
  }

  return {
    apiKey,
    baseUrl,
    model,
    saveSettings,
    updateSettings,
  }
})
