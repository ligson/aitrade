<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-form layout="vertical" class="filter-form">
        <div class="filter-grid">
          <a-form-item label="交易对" class="filter-item">
            <a-select v-model:value="downloadForm.symbol" placeholder="请选择交易对">
              <a-select-option v-for="item in options.supportedSymbols" :key="item" :value="item">
                {{ item }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="周期" class="filter-item">
            <a-input v-model:value="downloadForm.timeframe" disabled />
          </a-form-item>
        </div>
        <a-space wrap>
          <a-button type="primary" :loading="downloadLoading" :disabled="!downloadForm.symbol" @click="handleDownloadData">下载历史数据</a-button>
          <a-upload :show-upload-list="false" accept=".zip" :before-upload="handleSelectArchive">
            <a-button :loading="importLoading">导入压缩包</a-button>
          </a-upload>
          <a-button :disabled="selectedRowKeys.length === 0" @click="handleExportSelected">导出选中</a-button>
          <a-button @click="loadFiles">刷新列表</a-button>
        </a-space>
        <a-alert
          style="margin-top: 12px"
          type="info"
          show-icon
          message="历史数据下载将从系统配置的最早范围下载到当前时点"
          :description="downloadHint"
        />
      </a-form>

      <a-form layout="inline">
        <a-form-item>
          <a-select v-model:value="filters.symbol" allow-clear placeholder="全部交易对" style="width: 180px">
            <a-select-option v-for="item in options.supportedSymbols" :key="item" :value="item">
              {{ item }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-input v-model:value="filters.keyword" allow-clear placeholder="搜索文件名 / 交易对 / 周期" style="width: 280px" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch">查询</a-button>
        </a-form-item>
        <a-form-item>
          <a-button @click="resetFilters">重置</a-button>
        </a-form-item>
      </a-form>

      <a-table
        :data-source="rows"
        :columns="columns"
        row-key="filename"
        :loading="loading"
        :pagination="pagination"
        :row-selection="rowSelection"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record, text }">
          <template v-if="column.key === 'size'">
            {{ formatFileSize(record.size) }}
          </template>
          <template v-else-if="column.key === 'modifiedAt' || column.key === 'timerangeFrom' || column.key === 'timerangeTo'">
            {{ formatDateTime(text) }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space size="small" wrap>
              <a-button type="link" @click="handleUseForBacktest(record)">用于回测</a-button>
              <a-button type="link" @click="handleExportSingle(record)">导出</a-button>
              <a-popconfirm title="确认删除这个历史数据文件吗？" ok-text="删除" cancel-text="取消" @confirm="handleDelete(record)">
                <a-button type="link" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
          <template v-else>
            {{ text || '-' }}
          </template>
        </template>
      </a-table>
    </a-space>
  </a-card>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  deleteBacktestDataFile,
  downloadBacktestData,
  exportBacktestDataArchive,
  fetchBacktestDataOptions,
  fetchBacktestDataStatus,
  importBacktestDataArchive,
  pageBacktestDataFiles,
} from '@/api/backtests'
import type { BacktestDataFileItem, BacktestDataOptions, BacktestDataStatus } from '@/types/backtest'

const router = useRouter()
const loading = ref(false)
const downloadLoading = ref(false)
const importLoading = ref(false)
const rows = ref<BacktestDataFileItem[]>([])
const selectedRowKeys = ref<string[]>([])
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: false,
})

const options = reactive<BacktestDataOptions>({
  supportedSymbols: [],
  defaultSymbol: 'BTC/USDT',
  defaultTimeframe: '15m',
  dataFormatOhlcv: 'jsongz',
  downloadMode: 'full',
  archiveFormat: 'zip',
})

const currentStatus = reactive<BacktestDataStatus>({
  available: false,
  pair: '',
  timeframe: '',
  timerange: '',
  path: '',
  format: 'jsongz',
})

const downloadForm = reactive({
  symbol: '',
  timeframe: '15m',
})

const filters = reactive({
  symbol: undefined as string | undefined,
  keyword: '',
})

const columns = [
  { title: '文件名', dataIndex: 'filename', key: 'filename', width: 280 },
  { title: '交易对', dataIndex: 'symbol', key: 'symbol', width: 140 },
  { title: '周期', dataIndex: 'timeframe', key: 'timeframe', width: 100 },
  { title: '格式', dataIndex: 'format', key: 'format', width: 100 },
  { title: '大小', dataIndex: 'size', key: 'size', width: 120 },
  { title: '起始时间', dataIndex: 'timerangeFrom', key: 'timerangeFrom', width: 180 },
  { title: '结束时间', dataIndex: 'timerangeTo', key: 'timerangeTo', width: 180 },
  { title: '更新时间', dataIndex: 'modifiedAt', key: 'modifiedAt', width: 180 },
  { title: '操作', key: 'actions', width: 180, fixed: 'right' },
]

const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: Array<string | number>) => {
    selectedRowKeys.value = keys.map((item) => String(item))
  },
}))

const downloadHint = computed(() => {
  const parts = [
    `默认周期：${downloadForm.timeframe || options.defaultTimeframe || '-'}`,
    `落盘格式：${options.dataFormatOhlcv || '-'}`,
    `下载目录：${currentStatus.dataDir || '-'}`,
  ]
  return parts.join('；')
})

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return '-'
  }
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm:ss') : value
}

function formatFileSize(value: number | null | undefined) {
  if (!value || value <= 0) {
    return '-'
  }
  if (value < 1024) {
    return `${value} B`
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(2)} KB`
  }
  if (value < 1024 * 1024 * 1024) {
    return `${(value / 1024 / 1024).toFixed(2)} MB`
  }
  return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function saveBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.URL.revokeObjectURL(url)
}

async function loadOptions() {
  const data = await fetchBacktestDataOptions()
  Object.assign(options, data)
  if (!downloadForm.symbol) {
    downloadForm.symbol = data.defaultSymbol
  }
  if (!downloadForm.timeframe) {
    downloadForm.timeframe = data.defaultTimeframe
  }
}

async function loadStatus() {
  const status = await fetchBacktestDataStatus({
    symbol: downloadForm.symbol || options.defaultSymbol,
    timeframe: downloadForm.timeframe || options.defaultTimeframe,
  })
  Object.assign(currentStatus, status)
}

async function loadFiles() {
  loading.value = true
  try {
    const data = await pageBacktestDataFiles({
      symbol: filters.symbol,
      keyword: filters.keyword,
      offset: (pagination.current - 1) * pagination.pageSize,
      size: pagination.pageSize,
    })
    rows.value = data.data
    pagination.total = data.total
  } finally {
    loading.value = false
  }
}

async function handleDownloadData() {
  if (!downloadForm.symbol) {
    message.warning('请先选择交易对')
    return
  }
  downloadLoading.value = true
  try {
    const data = await downloadBacktestData({
      symbol: downloadForm.symbol,
      timeframe: downloadForm.timeframe,
    })
    Object.assign(currentStatus, data.status)
    message.success('历史数据下载完成')
    pagination.current = 1
    await loadFiles()
  } finally {
    downloadLoading.value = false
  }
}

async function handleExport(files: string[]) {
  const blob = await exportBacktestDataArchive(files)
  const timestamp = dayjs().format('YYYYMMDD_HHmmss')
  saveBlob(blob, `backtest-data-export-${timestamp}.zip`)
  message.success('历史数据压缩包已开始下载')
}

async function handleExportSelected() {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请至少选择一个历史数据文件')
    return
  }
  await handleExport(selectedRowKeys.value)
}

async function handleExportSingle(record: BacktestDataFileItem) {
  await handleExport([record.filename])
}

async function handleDelete(record: BacktestDataFileItem) {
  await deleteBacktestDataFile(record.filename)
  message.success('历史数据文件已删除')
  selectedRowKeys.value = selectedRowKeys.value.filter((item) => item !== record.filename)
  if (rows.value.length === 1 && pagination.current > 1) {
    pagination.current -= 1
  }
  await loadFiles()
}

async function handleSelectArchive(file: File) {
  importLoading.value = true
  try {
    const result = await importBacktestDataArchive({ file })
    const importedCount = result.imported.length
    const skippedCount = result.skipped.length
    if (importedCount === 0 && skippedCount > 0) {
      message.warning(`导入完成，${skippedCount} 个文件已跳过`)
    } else {
      message.success(`导入完成，成功导入 ${importedCount} 个文件`)
    }
    pagination.current = 1
    await loadFiles()
  } finally {
    importLoading.value = false
  }
  return false
}

function handleUseForBacktest(record: BacktestDataFileItem) {
  router.push({
    name: 'backtests',
    query: {
      dataFile: record.filename,
    },
  })
}

function handleSearch() {
  pagination.current = 1
  loadFiles()
}

function resetFilters() {
  filters.symbol = undefined
  filters.keyword = ''
  pagination.current = 1
  loadFiles()
}

function handleTableChange(page: { current?: number }) {
  pagination.current = page.current || 1
  loadFiles()
}

onMounted(async () => {
  await loadOptions()
  await loadStatus()
  await loadFiles()
})
</script>

<style scoped>
.page-card {
  height: 100%;
}

.filter-form {
  width: 100%;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0 16px;
  margin-bottom: 8px;
}

.filter-item {
  min-width: 0;
  margin-bottom: 12px;
}
</style>
