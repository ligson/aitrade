<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-descriptions title="目录信息" :column="1" bordered :loading="loading">
        <a-descriptions-item label="历史数据目录">{{ settings.backtestDataDir || '-' }}</a-descriptions-item>
        <a-descriptions-item label="Freqtrade user_data 目录">{{ settings.freqtradeUserDataDir || '-' }}</a-descriptions-item>
        <a-descriptions-item label="系统日志目录">{{ settings.appLogDir || '-' }}</a-descriptions-item>
      </a-descriptions>

      <a-descriptions title="历史数据配置" :column="2" bordered :loading="loading">
        <a-descriptions-item label="支持周期">{{ settings.supportedTimeframes?.join(' / ') || '-' }}</a-descriptions-item>
        <a-descriptions-item label="默认周期">{{ settings.defaultTimeframe || '-' }}</a-descriptions-item>
        <a-descriptions-item label="数据格式">{{ settings.dataFormatOhlcv || '-' }}</a-descriptions-item>
        <a-descriptions-item label="导出压缩格式">{{ settings.exportArchiveFormat || '-' }}</a-descriptions-item>
        <a-descriptions-item label="下载时间范围">{{ settings.downloadTimerange || '-' }}</a-descriptions-item>
      </a-descriptions>
    </a-space>
  </a-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { fetchSystemSettings } from '@/api/system'
import type { SystemSettings } from '@/types/system'

const loading = ref(false)
const settings = reactive<SystemSettings>({
  backtestDataDir: '',
  freqtradeUserDataDir: '',
  appLogDir: '',
  supportedTimeframes: [],
  defaultTimeframe: '',
  dataFormatOhlcv: '',
  exportArchiveFormat: '',
  downloadTimerange: '',
})

async function loadSettings() {
  loading.value = true
  try {
    const data = await fetchSystemSettings()
    Object.assign(settings, data)
  } finally {
    loading.value = false
  }
}

onMounted(loadSettings)
</script>

<style scoped>
.page-card {
  min-height: 100%;
}
</style>
