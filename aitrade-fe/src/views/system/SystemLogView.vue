<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-space wrap>
        <a-input v-model:value="filters.keyword" allow-clear placeholder="搜索日志文件名" style="width: 280px" />
        <a-select v-model:value="filters.type" allow-clear placeholder="全部日志类型" style="width: 180px">
          <a-select-option v-for="item in typeOptions" :key="item.value" :value="item.value">
            {{ item.label }}
          </a-select-option>
        </a-select>
        <a-button type="primary" @click="handleSearch">查询</a-button>
        <a-button @click="resetFilters">重置</a-button>
      </a-space>

      <a-table :data-source="rows" :columns="columns" row-key="filename" :loading="loading" :pagination="pagination" @change="handleTableChange">
        <template #bodyCell="{ column, record, text }">
          <template v-if="column.key === 'type'">
            <a-tag :color="record.type === 'trade' ? 'blue' : 'green'">{{ record.type === 'trade' ? '交易日志' : '应用日志' }}</a-tag>
          </template>
          <template v-else-if="column.key === 'size'">
            {{ formatFileSize(record.size) }}
          </template>
          <template v-else-if="column.key === 'modifiedAt'">
            {{ formatDateTime(record.modifiedAt) }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-button type="link" @click="openDetail(record.filename)">查看</a-button>
          </template>
          <template v-else>
            {{ text || '-' }}
          </template>
        </template>
      </a-table>
    </a-space>

    <a-drawer v-model:open="detailOpen" title="日志内容" width="960">
      <a-space direction="vertical" size="middle" style="width: 100%">
        <a-descriptions :column="1" bordered size="small" v-if="detail">
          <a-descriptions-item label="文件名">{{ detail.filename }}</a-descriptions-item>
          <a-descriptions-item label="日志类型">{{ detail.type === 'trade' ? '交易日志' : '应用日志' }}</a-descriptions-item>
          <a-descriptions-item label="文件路径">{{ detail.path }}</a-descriptions-item>
          <a-descriptions-item label="文件大小">{{ formatFileSize(detail.size) }}</a-descriptions-item>
          <a-descriptions-item label="最后修改时间">{{ formatDateTime(detail.modifiedAt) }}</a-descriptions-item>
        </a-descriptions>
        <a-alert
          v-if="detail?.truncated"
          type="info"
          show-icon
          message="当前仅展示日志文件最后部分内容"
          :description="`本次已加载最后 ${detail.tailLines} 行。`"
        />
        <pre class="log-content app-scrollbar">{{ detail?.content || '' }}</pre>
      </a-space>
    </a-drawer>
  </a-card>
</template>

<script setup lang="ts">
import dayjs from 'dayjs'
import { onMounted, reactive, ref } from 'vue'

import { fetchSystemLogContent, pageSystemLogFiles } from '@/api/system'
import type { SystemLogContent, SystemLogFileItem } from '@/types/system'

const loading = ref(false)
const detailOpen = ref(false)
const rows = ref<SystemLogFileItem[]>([])
const detail = ref<SystemLogContent | null>(null)

const filters = reactive({
  keyword: '',
  type: undefined as string | undefined,
})

const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: false,
})

const typeOptions = [
  { label: '应用日志', value: 'app' },
  { label: '交易日志', value: 'trade' },
]

const columns = [
  { title: '文件名', dataIndex: 'filename', key: 'filename' },
  { title: '日志类型', dataIndex: 'type', key: 'type', width: 120 },
  { title: '文件大小', dataIndex: 'size', key: 'size', width: 120 },
  { title: '最后修改时间', dataIndex: 'modifiedAt', key: 'modifiedAt', width: 180 },
  { title: '操作', key: 'actions', width: 100 },
]

function formatDateTime(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  const parsed = dayjs(typeof value === 'number' ? value * 1000 : value)
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm:ss') : String(value)
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

async function loadFiles() {
  loading.value = true
  try {
    const data = await pageSystemLogFiles({
      offset: (pagination.current - 1) * pagination.pageSize,
      size: pagination.pageSize,
      keyword: filters.keyword,
      type: filters.type,
    })
    rows.value = data.data
    pagination.total = data.total
  } finally {
    loading.value = false
  }
}

async function openDetail(filename: string) {
  detail.value = await fetchSystemLogContent({ filename, tailLines: 200 })
  detailOpen.value = true
}

function handleSearch() {
  pagination.current = 1
  loadFiles()
}

function resetFilters() {
  filters.keyword = ''
  filters.type = undefined
  pagination.current = 1
  loadFiles()
}

function handleTableChange(page: { current?: number }) {
  pagination.current = page.current || 1
  loadFiles()
}

onMounted(loadFiles)
</script>

<style scoped>
.page-card {
  min-height: 100%;
}

.log-content {
  min-height: 320px;
  max-height: calc(100vh - 320px);
  margin: 0;
  padding: 16px;
  overflow: auto;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
