<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="这里维护的是可通过网页管理的非敏感系统参数。"
        description="密钥、数据库连接、代理、监听地址、目录路径和外部命令等部署期配置仍需通过后端 config.yaml 维护。保存后会影响后续新发起的回测与新启动的交易任务，不会回溯修改已运行任务。"
      />

      <a-descriptions title="只读部署信息" :column="1" bordered :loading="loading">
        <a-descriptions-item label="历史数据目录">{{ settings.readonly.backtestDataDir || '-' }}</a-descriptions-item>
        <a-descriptions-item label="Freqtrade user_data 目录">{{ settings.readonly.freqtradeUserDataDir || '-' }}</a-descriptions-item>
        <a-descriptions-item label="系统日志目录">{{ settings.readonly.appLogDir || '-' }}</a-descriptions-item>
      </a-descriptions>

      <a-card title="可编辑系统设置" size="small" :loading="loading">
        <a-form layout="vertical">
          <div class="section-title">GPT 配置</div>
          <div class="form-grid two-column">
            <a-form-item label="提供方">
              <a-select v-model:value="form.gptProvider">
                <a-select-option value="deepseek">deepseek</a-select-option>
                <a-select-option value="openai">openai</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="模型名称">
              <a-input v-model:value="form.gptModel" placeholder="如 deepseek-chat" />
            </a-form-item>
          </div>

          <div class="section-title">交易持久化配置</div>
          <div class="switch-grid">
            <a-form-item label="持久化当前持仓">
              <a-switch v-model:checked="form.persistPosition" />
            </a-form-item>
            <a-form-item label="启动时恢复持仓">
              <a-switch v-model:checked="form.restorePositionOnStartup" />
            </a-form-item>
          </div>

          <div class="section-title">回测与历史数据配置</div>
          <div class="form-grid two-column">
            <a-form-item label="支持交易对">
              <a-select v-model:value="form.supportedSymbols" mode="tags" :token-separators="[',', '，', ' ']" placeholder="如 BTC/USDT, ETH/USDT" />
            </a-form-item>
            <a-form-item label="支持周期">
              <a-select v-model:value="form.supportedTimeframes" mode="tags" :token-separators="[',', '，', ' ']" placeholder="如 5m, 15m, 1h" />
            </a-form-item>
            <a-form-item label="默认交易对">
              <a-select v-model:value="form.defaultSymbol" show-search>
                <a-select-option v-for="item in normalizedSupportedSymbols" :key="item" :value="item">
                  {{ item }}
                </a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="默认周期">
              <a-select v-model:value="form.defaultTimeframe">
                <a-select-option v-for="item in normalizedSupportedTimeframes" :key="item" :value="item">
                  {{ item }}
                </a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="下载时间范围">
              <a-input v-model:value="form.downloadTimerange" placeholder="如 20180101-" />
            </a-form-item>
            <a-form-item label="历史数据格式">
              <a-select v-model:value="form.dataFormatOhlcv">
                <a-select-option value="json">json</a-select-option>
                <a-select-option value="jsongz">jsongz</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="导出压缩格式">
              <a-select v-model:value="form.exportArchiveFormat">
                <a-select-option value="zip">zip</a-select-option>
              </a-select>
            </a-form-item>
          </div>

          <a-space>
            <a-button @click="loadSettings">重置</a-button>
            <a-button type="primary" :loading="saving" @click="submitForm">保存系统设置</a-button>
          </a-space>
        </a-form>
      </a-card>
    </a-space>
  </a-card>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import { computed, onMounted, reactive, ref } from 'vue'

import { fetchSystemSettings, saveSystemSettings } from '@/api/system'
import type { SystemSettings } from '@/types/system'

const loading = ref(false)
const saving = ref(false)
const settings = reactive<SystemSettings>({
  readonly: {
    backtestDataDir: '',
    freqtradeUserDataDir: '',
    appLogDir: '',
  },
  editable: {
    gptProvider: 'deepseek',
    gptModel: '',
    persistPosition: true,
    restorePositionOnStartup: false,
    supportedSymbols: [],
    supportedTimeframes: [],
    defaultSymbol: '',
    defaultTimeframe: '',
    downloadTimerange: '',
    dataFormatOhlcv: 'jsongz',
    exportArchiveFormat: 'zip',
  },
  meta: {
    id: 0,
    name: '',
    description: '',
    schemaVersion: 1,
    updatedAt: '',
  },
})

const form = reactive({
  gptProvider: 'deepseek',
  gptModel: '',
  persistPosition: true,
  restorePositionOnStartup: false,
  supportedSymbols: [] as string[],
  supportedTimeframes: [] as string[],
  defaultSymbol: '',
  defaultTimeframe: '',
  downloadTimerange: '',
  dataFormatOhlcv: 'jsongz',
  exportArchiveFormat: 'zip',
})

const normalizedSupportedSymbols = computed(() => normalizeStringArray(form.supportedSymbols))
const normalizedSupportedTimeframes = computed(() => normalizeStringArray(form.supportedTimeframes))

function normalizeStringArray(values: string[]) {
  const result: string[] = []
  const seen = new Set<string>()
  for (const item of values) {
    const text = String(item || '').trim()
    if (!text || seen.has(text)) {
      continue
    }
    seen.add(text)
    result.push(text)
  }
  return result
}

function applySettings(data: SystemSettings) {
  Object.assign(settings.readonly, data.readonly)
  Object.assign(settings.editable, data.editable)
  Object.assign(settings.meta, data.meta)
  Object.assign(form, {
    gptProvider: data.editable.gptProvider,
    gptModel: data.editable.gptModel,
    persistPosition: data.editable.persistPosition,
    restorePositionOnStartup: data.editable.restorePositionOnStartup,
    supportedSymbols: [...data.editable.supportedSymbols],
    supportedTimeframes: [...data.editable.supportedTimeframes],
    defaultSymbol: data.editable.defaultSymbol,
    defaultTimeframe: data.editable.defaultTimeframe,
    downloadTimerange: data.editable.downloadTimerange,
    dataFormatOhlcv: data.editable.dataFormatOhlcv,
    exportArchiveFormat: data.editable.exportArchiveFormat,
  })
}

async function loadSettings() {
  loading.value = true
  try {
    const data = await fetchSystemSettings()
    applySettings(data)
  } finally {
    loading.value = false
  }
}

function validateForm() {
  form.supportedSymbols = normalizeStringArray(form.supportedSymbols)
  form.supportedTimeframes = normalizeStringArray(form.supportedTimeframes)
  if (!form.gptModel.trim()) {
    message.warning('请填写 GPT 模型名称')
    return false
  }
  if (form.supportedSymbols.length === 0) {
    message.warning('请至少填写一个支持交易对')
    return false
  }
  if (form.supportedTimeframes.length === 0) {
    message.warning('请至少填写一个支持周期')
    return false
  }
  if (!form.defaultSymbol || !form.supportedSymbols.includes(form.defaultSymbol)) {
    message.warning('默认交易对必须包含在支持交易对列表中')
    return false
  }
  if (!form.defaultTimeframe || !form.supportedTimeframes.includes(form.defaultTimeframe)) {
    message.warning('默认周期必须包含在支持周期列表中')
    return false
  }
  if (!form.downloadTimerange.trim()) {
    message.warning('请填写下载时间范围')
    return false
  }
  return true
}

async function submitForm() {
  if (!validateForm()) {
    return
  }
  saving.value = true
  try {
    const data = await saveSystemSettings({
      editable: {
        gptProvider: form.gptProvider,
        gptModel: form.gptModel.trim(),
        persistPosition: form.persistPosition,
        restorePositionOnStartup: form.restorePositionOnStartup,
        supportedSymbols: [...form.supportedSymbols],
        supportedTimeframes: [...form.supportedTimeframes],
        defaultSymbol: form.defaultSymbol,
        defaultTimeframe: form.defaultTimeframe,
        downloadTimerange: form.downloadTimerange.trim(),
        dataFormatOhlcv: form.dataFormatOhlcv,
        exportArchiveFormat: form.exportArchiveFormat,
      },
    })
    applySettings(data)
    message.success('系统设置已保存')
  } finally {
    saving.value = false
  }
}

onMounted(loadSettings)
</script>

<style scoped>
.page-card {
  min-height: 100%;
}

.form-grid {
  display: grid;
  gap: 0 16px;
}

.two-column {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.switch-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0 16px;
}

.section-title {
  margin-bottom: 12px;
  font-weight: 600;
}
</style>
