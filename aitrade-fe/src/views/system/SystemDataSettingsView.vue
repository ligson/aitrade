<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="这里维护的是回测与历史数据的默认参数。"
        description="保存后会影响后续新发起的历史数据下载、回测任务与新启动的交易任务。"
      />

      <a-card title="数据设置" size="small" :loading="loading">
        <a-form layout="vertical">
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
            <a-button @click="loadForm">重置</a-button>
            <a-button type="primary" :loading="saving" @click="submitForm">保存数据设置</a-button>
          </a-space>
        </a-form>
      </a-card>
    </a-space>
  </a-card>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import { computed, onMounted, reactive } from 'vue'

import { normalizeStringArray, useSystemSettings } from './useSystemSettings'

const { loading, saving, settings, loadSettings, saveEditable } = useSystemSettings()

const form = reactive({
  supportedSymbols: [] as string[],
  supportedTimeframes: [] as string[],
  defaultSymbol: '',
  defaultTimeframe: '',
  downloadTimerange: '',
  dataFormatOhlcv: 'jsongz',
  exportArchiveFormat: 'zip',
})

// 默认值下拉需要基于规范化后的候选集生成，否则 tags 输入里的空白/重复项会让展示和保存结果不一致。
const normalizedSupportedSymbols = computed(() => normalizeStringArray(form.supportedSymbols))
const normalizedSupportedTimeframes = computed(() => normalizeStringArray(form.supportedTimeframes))

function syncForm() {
  // 页面表单使用的是 settings.editable 的本地编辑副本，保存或重置后再统一从服务端结果同步回来。
  form.supportedSymbols = [...settings.editable.supportedSymbols]
  form.supportedTimeframes = [...settings.editable.supportedTimeframes]
  form.defaultSymbol = settings.editable.defaultSymbol
  form.defaultTimeframe = settings.editable.defaultTimeframe
  form.downloadTimerange = settings.editable.downloadTimerange
  form.dataFormatOhlcv = settings.editable.dataFormatOhlcv
  form.exportArchiveFormat = settings.editable.exportArchiveFormat
}

async function loadForm() {
  await loadSettings()
  syncForm()
}

function validateForm() {
  // 先归一化，再检查默认值是否仍属于支持列表；
  // 这个顺序需要与后端保存时的归一化约束保持一致。
  form.supportedSymbols = normalizeStringArray(form.supportedSymbols)
  form.supportedTimeframes = normalizeStringArray(form.supportedTimeframes)
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
  await saveEditable({
    // 数据页只改自己负责的字段，但提交时仍要保留整份 editable，避免覆盖掉 AI/交易页设置。
    ...settings.editable,
    supportedSymbols: [...form.supportedSymbols],
    supportedTimeframes: [...form.supportedTimeframes],
    defaultSymbol: form.defaultSymbol,
    defaultTimeframe: form.defaultTimeframe,
    downloadTimerange: form.downloadTimerange.trim(),
    dataFormatOhlcv: form.dataFormatOhlcv,
    exportArchiveFormat: form.exportArchiveFormat,
  })
  syncForm()
  message.success('数据设置已保存')
}

onMounted(loadForm)
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
</style>
