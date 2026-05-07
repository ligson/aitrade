<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="warning"
        show-icon
        message="这里维护的是部署级数据根目录。"
        description="页面只维护一个 dataRootDir，并由系统自动规划数据库、日志、历史数据和 Freqtrade user_data 的子目录。保存后通常需要重启后端，新的数据库连接和目录配置才会完全生效。"
      />

      <a-alert
        v-if="settings.compatibilityStatus !== 'managed'"
        type="info"
        show-icon
        :message="compatibilityTitle"
        :description="settings.compatibilityMessage"
      />

      <a-card title="部署设置" size="small" :loading="loading">
        <a-form layout="vertical">
          <a-form-item label="配置文件路径">
            <a-input :value="settings.configFilePath" readonly />
          </a-form-item>

          <a-form-item label="数据根目录">
            <a-input v-model:value="form.dataRootDir" placeholder="如 ~/.aitrade" />
          </a-form-item>

          <a-space>
            <a-button @click="loadForm">重置</a-button>
            <a-button type="primary" :loading="saving" @click="submitForm">保存部署设置</a-button>
          </a-space>
        </a-form>
      </a-card>

      <a-card title="当前配置文件下的目录规划" size="small" :loading="loading">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="数据根目录">{{ settings.derivedPaths.dataRootDir || '-' }}</a-descriptions-item>
          <a-descriptions-item label="数据库连接地址">{{ settings.derivedPaths.databaseUrl || '-' }}</a-descriptions-item>
          <a-descriptions-item label="系统日志目录">{{ settings.derivedPaths.appLogDir || '-' }}</a-descriptions-item>
          <a-descriptions-item label="历史数据目录">{{ settings.derivedPaths.backtestDataDir || '-' }}</a-descriptions-item>
          <a-descriptions-item label="Freqtrade user_data 目录">{{ settings.derivedPaths.freqtradeUserDataDir || '-' }}</a-descriptions-item>
        </a-descriptions>
      </a-card>

      <a-card title="当前运行中的生效值" size="small" :loading="loading">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="数据根目录">{{ settings.runtime.dataRootDir || '-' }}</a-descriptions-item>
          <a-descriptions-item label="数据库连接地址">{{ settings.runtime.databaseUrl || '-' }}</a-descriptions-item>
          <a-descriptions-item label="系统日志目录">{{ settings.runtime.appLogDir || '-' }}</a-descriptions-item>
          <a-descriptions-item label="历史数据目录">{{ settings.runtime.backtestDataDir || '-' }}</a-descriptions-item>
          <a-descriptions-item label="Freqtrade user_data 目录">{{ settings.runtime.freqtradeUserDataDir || '-' }}</a-descriptions-item>
        </a-descriptions>
      </a-card>

      <a-alert
        v-if="settings.restartRequired"
        type="info"
        show-icon
        message="检测到配置文件值与当前运行值不一致。"
        description="请在方便的窗口重启后端，让新的数据库连接和目录配置完全生效。"
      />
    </a-space>
  </a-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'

import { fetchSystemDeploymentSettings, saveSystemDeploymentSettings } from '@/api/system'
import type { SystemDeploymentSettings } from '@/types/system'

function createEmptySettings(): SystemDeploymentSettings {
  return {
    configFilePath: '',
    editable: {
      dataRootDir: '',
    },
    derivedPaths: {
      dataRootDir: '',
      databaseUrl: '',
      backtestDataDir: '',
      freqtradeUserDataDir: '',
      appLogDir: '',
    },
    runtime: {
      dataRootDir: '',
      databaseUrl: '',
      backtestDataDir: '',
      freqtradeUserDataDir: '',
      appLogDir: '',
    },
    compatibilityStatus: 'managed',
    compatibilityMessage: '',
    restartRequired: false,
  }
}

const loading = ref(false)
const saving = ref(false)
const settings = reactive<SystemDeploymentSettings>(createEmptySettings())
const form = reactive({
  dataRootDir: '',
})

const compatibilityTitle = computed(() => {
  const titleMap = {
    managed: '当前配置已使用单根目录。',
    legacy_inferred: '当前配置仍在兼容读取旧字段。',
    legacy_split: '当前配置仍是旧版分散路径。',
    external_database: '当前数据库仍在使用外部连接地址。',
  } satisfies Record<SystemDeploymentSettings['compatibilityStatus'], string>
  return titleMap[settings.compatibilityStatus]
})

function applySettings(data: SystemDeploymentSettings) {
  settings.configFilePath = data.configFilePath
  settings.restartRequired = data.restartRequired
  settings.compatibilityStatus = data.compatibilityStatus
  settings.compatibilityMessage = data.compatibilityMessage
  Object.assign(settings.editable, data.editable)
  Object.assign(settings.derivedPaths, data.derivedPaths)
  Object.assign(settings.runtime, data.runtime)
}

function syncForm() {
  form.dataRootDir = settings.editable.dataRootDir
}

function validateForm() {
  form.dataRootDir = form.dataRootDir.trim()
  if (!form.dataRootDir) {
    message.warning('请填写数据根目录')
    return false
  }
  return true
}

async function loadForm() {
  loading.value = true
  try {
    const data = await fetchSystemDeploymentSettings()
    applySettings(data)
    syncForm()
  } finally {
    loading.value = false
  }
}

async function submitForm() {
  if (!validateForm()) {
    return
  }
  saving.value = true
  try {
    const data = await saveSystemDeploymentSettings({
      editable: {
        dataRootDir: form.dataRootDir,
      },
    })
    applySettings(data)
    syncForm()
    message.success(data.message || '部署设置已保存，请重启后端使其完全生效')
  } finally {
    saving.value = false
  }
}

onMounted(loadForm)
</script>

<style scoped>
.page-card {
  min-height: 100%;
}
</style>
