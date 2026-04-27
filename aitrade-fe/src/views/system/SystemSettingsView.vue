<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="这里维护的是系统设置概览。"
        description="可网页维护的参数已拆分到 AI 设置、交易设置、数据设置三个独立页面。AI 的 provider、model、API Key 与可选 Base URL 改由 AI 设置页维护；交易所凭证、数据库连接、代理、监听地址、目录路径和外部命令等部署期配置仍需通过后端 config.yaml 维护。"
      />

      <a-descriptions title="只读部署信息" :column="1" bordered :loading="loading">
        <a-descriptions-item label="历史数据目录">{{ settings.readonly.backtestDataDir || '-' }}</a-descriptions-item>
        <a-descriptions-item label="Freqtrade user_data 目录">{{ settings.readonly.freqtradeUserDataDir || '-' }}</a-descriptions-item>
        <a-descriptions-item label="系统日志目录">{{ settings.readonly.appLogDir || '-' }}</a-descriptions-item>
      </a-descriptions>

      <a-card title="维护入口" size="small">
        <a-space wrap>
          <RouterLink to="/system-ai-settings"><a-button>AI 设置</a-button></RouterLink>
          <RouterLink to="/system-trade-settings"><a-button>交易设置</a-button></RouterLink>
          <RouterLink to="/system-data-settings"><a-button>数据设置</a-button></RouterLink>
        </a-space>
      </a-card>
    </a-space>
  </a-card>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

import { useSystemSettings } from './useSystemSettings'

const { loading, settings, loadSettings } = useSystemSettings()

// 系统概览页只负责展示部署期只读信息和拆分后的维护入口，不再承载大而全的设置表单。

onMounted(loadSettings)
</script>

<style scoped>
.page-card {
  min-height: 100%;
}
</style>
