<template>
  <el-container class="h-screen">
    <el-header class="bg-blue-600 text-white flex items-center shadow-md">
      <h1 class="text-2xl font-bold">A股投资分析系统</h1>
    </el-header>
    <el-container>
      <el-aside width="200px" class="bg-gray-50 border-r">
        <el-menu
          :default-active="activeMenu"
          router
          class="h-full"
        >
          <el-menu-item index="/">
            <el-icon><Document /></el-icon>
            <span>股票分析</span>
          </el-menu-item>
          <el-menu-item index="/history">
            <el-icon><Clock /></el-icon>
            <span>历史报告</span>
          </el-menu-item>
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main class="p-6">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Document, Clock, Setting } from '@element-plus/icons-vue'

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>
