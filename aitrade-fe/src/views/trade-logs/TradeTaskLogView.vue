<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="这里展示的是交易任务运行过程事件日志，不是交易结果日志。"
        :description="activeContextTip"
      >
        <template #action>
          <a-button v-if="canGoBackToTaskCenter" size="small" @click="goToTaskCenter">返回任务中心</a-button>
        </template>
      </a-alert>

      <a-form layout="vertical" class="filter-form">
        <div class="filter-grid">
          <a-form-item label="任务配置 / Runner" class="filter-item">
            <a-select v-model:value="filters.runnerName" allow-clear show-search placeholder="全部任务配置" :filter-option="filterSelectOption">
              <a-select-option v-for="item in profileOptions" :key="item.runnerName" :value="item.runnerName">
                {{ item.name }} / {{ item.runnerName }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="运行实例 ID" class="filter-item">
            <a-input-number v-model:value="filters.runId" :min="1" :precision="0" placeholder="全部实例" style="width: 100%" />
          </a-form-item>
          <a-form-item label="事件" class="filter-item">
            <a-select v-model:value="filters.eventType" allow-clear placeholder="全部事件">
              <a-select-option v-for="item in eventTypeOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="状态" class="filter-item">
            <a-select v-model:value="filters.status" allow-clear placeholder="全部状态">
              <a-select-option v-for="item in statusOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="关键词" class="filter-item">
            <a-input v-model:value="filters.keyword" allow-clear placeholder="搜索说明或详情" />
          </a-form-item>
          <a-form-item label="时间范围" class="filter-item filter-item-range">
            <a-config-provider :locale="zhCN">
              <a-range-picker v-model:value="filters.createdRange" show-time style="width: 100%" />
            </a-config-provider>
          </a-form-item>
        </div>
        <a-space wrap>
          <a-button type="primary" @click="handleSearch">查询</a-button>
          <a-button @click="resetFilters">重置</a-button>
          <a-button v-if="canGoBackToTaskCenter" @click="goToTaskCenter">返回任务中心</a-button>
        </a-space>
      </a-form>

      <a-table :data-source="rows" :columns="columns" row-key="id" :loading="loading" :pagination="pagination" :scroll="{ x: 'max-content' }" @change="handleTableChange">
        <template #bodyCell="{ column, record, text }">
          <template v-if="column.key === 'createdAt'">
            {{ formatDateTime(text) }}
          </template>
          <template v-else-if="column.key === 'ownerUserId'">
            {{ formatOwnerUserId(record.ownerUserId) }}
          </template>
          <template v-else-if="column.key === 'eventType'">
            <a-tag :color="eventTypeColor(record.eventType)">{{ eventTypeLabel(record.eventType) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'runId'">
            {{ record.runId ?? '-' }}
          </template>
          <template v-else-if="column.key === 'profileName'">
            <div class="cell-text">{{ record.profileName || '-' }}</div>
          </template>
          <template v-else-if="column.key === 'message'">
            <div class="cell-text">{{ text || '-' }}</div>
          </template>
          <template v-else-if="column.key === 'detailPreview'">
            <div class="cell-text">{{ formatDetailPreview(record.detail) }}</div>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space size="small">
              <a-button type="link" @click="openDetail(record)">查看</a-button>
              <a-button type="link" :disabled="!record.runId" @click="goToTradeLogs(record)">查看交易日志</a-button>
            </a-space>
          </template>
          <template v-else>
            {{ text || '-' }}
          </template>
        </template>
      </a-table>
    </a-space>

    <a-drawer v-model:open="detailOpen" title="任务日志详情" width="880">
      <template v-if="detailRecord">
        <a-space direction="vertical" size="middle" style="width: 100%">
          <a-descriptions :column="2" bordered size="small">
            <a-descriptions-item label="日志 ID">{{ detailRecord.id }}</a-descriptions-item>
            <a-descriptions-item v-if="auth.isAdmin" label="所属用户">{{ formatOwnerUserId(detailRecord.ownerUserId) }}</a-descriptions-item>
            <a-descriptions-item label="运行实例 ID">{{ detailRecord.runId ?? '-' }}</a-descriptions-item>
            <a-descriptions-item label="配置名称">{{ detailRecord.profileName || '-' }}</a-descriptions-item>
            <a-descriptions-item label="Runner">{{ detailRecord.runnerName }}</a-descriptions-item>
            <a-descriptions-item label="时间">{{ formatDateTime(detailRecord.createdAt) }}</a-descriptions-item>
            <a-descriptions-item label="事件">
              <a-tag :color="eventTypeColor(detailRecord.eventType)">{{ eventTypeLabel(detailRecord.eventType) }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="状态">
              <a-tag :color="statusColor(detailRecord.status)">{{ statusLabel(detailRecord.status) }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="说明" :span="2">{{ detailRecord.message || '-' }}</a-descriptions-item>
          </a-descriptions>

          <a-card size="small" title="详情数据">
            <template v-if="detailEntries.length > 0">
              <a-descriptions :column="1" bordered size="small">
                <a-descriptions-item v-for="item in detailEntries" :key="item.key" :label="item.key">
                  <div class="cell-text">{{ item.value }}</div>
                </a-descriptions-item>
              </a-descriptions>
            </template>
            <a-empty v-else description="暂无详情数据" />
          </a-card>
        </a-space>
      </template>
    </a-drawer>
  </a-card>
</template>

<script setup lang="ts">
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import dayjs, { type Dayjs } from 'dayjs'
import 'dayjs/locale/zh-cn'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { fetchTradeTaskProfiles, pageTradeTaskLogs } from '@/api/system'
import type { TradeTaskLogItem, TradeTaskProfile } from '@/types/system'

dayjs.locale('zh-cn')

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const detailOpen = ref(false)
const rows = ref<TradeTaskLogItem[]>([])
const profiles = ref<TradeTaskProfile[]>([])
const detailRecord = ref<TradeTaskLogItem | null>(null)
const offset = ref(0)
const size = ref(10)

const filters = reactive<{
  runnerName?: string
  runId?: number
  eventType?: string
  status?: string
  keyword: string
  createdRange: [Dayjs, Dayjs] | []
}>({
  runnerName: undefined,
  runId: undefined,
  eventType: undefined,
  status: undefined,
  keyword: '',
  createdRange: [],
})

const pagination = reactive({
  current: 1,
  pageSize: size.value,
  total: 0,
  showSizeChanger: false,
})

const statusOptions = [
  { label: '启动中', value: 'starting' },
  { label: '运行中', value: 'running' },
  { label: '停止中', value: 'stop_requested' },
  { label: '已停止', value: 'stopped' },
  { label: '失败', value: 'failed' },
  { label: '配置错误', value: 'config_error' },
  { label: '状态残留', value: 'stale' },
]

const eventTypeOptions = [
  { label: '开始请求', value: 'start_requested' },
  { label: '启动完成', value: 'started' },
  { label: '周期开始', value: 'cycle_started' },
  { label: '周期完成', value: 'cycle_finished' },
  { label: '停止请求', value: 'stop_requested' },
  { label: '停止完成', value: 'stopped' },
  { label: '失败', value: 'failed' },
  { label: '状态残留', value: 'stale' },
]

const columns = computed(() => {
  const ownerColumn = auth.isAdmin ? [{ title: '所属用户', dataIndex: 'ownerUserId', key: 'ownerUserId', width: 120 }] : []
  return [
    { title: '时间', dataIndex: 'createdAt', key: 'createdAt', width: 180 },
    ...ownerColumn,
    { title: '运行实例 ID', dataIndex: 'runId', key: 'runId', width: 120 },
    { title: '配置名称', dataIndex: 'profileName', key: 'profileName', width: 200 },
    { title: '事件', dataIndex: 'eventType', key: 'eventType', width: 120 },
    { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
    { title: '说明', dataIndex: 'message', key: 'message', width: 240 },
    { title: '详情摘要', key: 'detailPreview', width: 420 },
    { title: '操作', key: 'actions', width: 180 },
  ]
})

const profileOptions = computed(() => profiles.value.slice().sort((a, b) => a.id - b.id))
const canGoBackToTaskCenter = computed(() => Boolean(firstQueryValue(route.query.runnerName) || firstQueryValue(route.query.profileId)))
const activeContextTip = computed(() => {
  if (filters.runnerName && filters.runId) {
    return `当前已按 Runner ${filters.runnerName} 和运行实例 ID ${filters.runId} 聚焦查看任务事件。`
  }
  if (filters.runnerName) {
    return `当前已按 Runner ${filters.runnerName} 聚焦查看任务事件；可继续按事件、状态、关键词和时间范围筛选。`
  }
  if (filters.runId) {
    return `当前已按运行实例 ID ${filters.runId} 聚焦查看任务事件。`
  }
  return '可按任务、运行实例、事件、状态、关键词和时间范围筛选；长详情会在表格内换行，并可在详情抽屉里查看完整信息。'
})
const detailEntries = computed(() => {
  if (!detailRecord.value) {
    return []
  }
  return Object.entries(detailRecord.value.detail ?? {}).map(([key, value]) => ({
    key,
    value: typeof value === 'string' ? value : JSON.stringify(value),
  }))
})

function firstQueryValue(value: unknown) {
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0] : undefined
  }
  return undefined
}

function buildPayload() {
  const [createdFrom, createdTo] = filters.createdRange
  return {
    offset: offset.value,
    size: size.value,
    runnerName: filters.runnerName,
    runId: filters.runId,
    eventType: filters.eventType,
    status: filters.status,
    keyword: filters.keyword.trim() || undefined,
    createdFrom: createdFrom ? createdFrom.toISOString() : undefined,
    createdTo: createdTo ? createdTo.toISOString() : undefined,
  }
}

function buildTaskCenterQuery() {
  const runnerName = filters.runnerName || firstQueryValue(route.query.runnerName)
  const matchedProfileId = runnerName ? profiles.value.find((item) => item.runnerName === runnerName)?.id : undefined
  const profileId = firstQueryValue(route.query.profileId) || (matchedProfileId ? String(matchedProfileId) : undefined)
  return {
    ...(runnerName ? { runnerName } : {}),
    ...(profileId ? { profileId } : {}),
    tab: firstQueryValue(route.query.tab) || 'runtime',
  }
}

function syncFiltersFromRoute() {
  const runnerName = firstQueryValue(route.query.runnerName)
  const rawRunId = firstQueryValue(route.query.runId)
  const nextRunId = rawRunId ? Number(rawRunId) : Number.NaN
  filters.runnerName = runnerName || undefined
  filters.runId = Number.isInteger(nextRunId) && nextRunId > 0 ? nextRunId : undefined
}

function filterSelectOption(input: string, option?: { children?: unknown; value?: unknown }) {
  const label = typeof option?.children === 'string' ? option.children : String(option?.value || '')
  return label.toLowerCase().includes(input.toLowerCase())
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return '-'
  }
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm:ss') : value
}

function formatOwnerUserId(value: number | null | undefined) {
  if (!value) {
    return '-'
  }
  return value === auth.currentUser?.id ? `${value}（我）` : String(value)
}

function statusLabel(value: string | null | undefined) {
  return statusOptions.find((item) => item.value === value)?.label || value || '-'
}

function statusColor(value: string | null | undefined) {
  if (value === 'starting') {
    return 'gold'
  }
  if (value === 'running') {
    return 'blue'
  }
  if (value === 'stop_requested') {
    return 'orange'
  }
  if (value === 'stopped') {
    return 'default'
  }
  return 'red'
}

function eventTypeLabel(value: string | null | undefined) {
  return eventTypeOptions.find((item) => item.value === value)?.label || value || '-'
}

function eventTypeColor(value: string | null | undefined) {
  if (value === 'start_requested' || value === 'started') {
    return 'blue'
  }
  if (value === 'cycle_started' || value === 'cycle_finished') {
    return 'cyan'
  }
  if (value === 'stop_requested' || value === 'stopped') {
    return 'orange'
  }
  if (value === 'failed' || value === 'stale') {
    return 'red'
  }
  return 'default'
}

function formatDetailPreview(detail: Record<string, unknown>) {
  const entries = Object.entries(detail ?? {})
  if (!entries.length) {
    return '-'
  }
  return entries
    .map(([key, value]) => `${key}=${typeof value === 'string' ? value : JSON.stringify(value)}`)
    .join('；')
}

async function loadProfiles() {
  profiles.value = await fetchTradeTaskProfiles()
}

async function loadLogs() {
  loading.value = true
  try {
    const data = await pageTradeTaskLogs(buildPayload())
    rows.value = data.data
    pagination.total = data.total
    pagination.current = Math.floor(offset.value / size.value) + 1
  } finally {
    loading.value = false
  }
}

function openDetail(record: TradeTaskLogItem) {
  detailRecord.value = record
  detailOpen.value = true
}

function goToTaskCenter() {
  router.push({ path: '/trade-tasks', query: buildTaskCenterQuery() })
}

function goToTradeLogs(record: TradeTaskLogItem) {
  if (!record.runId) {
    return
  }
  const matchedProfileId = profiles.value.find((item) => item.runnerName === record.runnerName)?.id
  router.push({
    path: '/trade-logs',
    query: {
      runId: String(record.runId),
      runnerName: record.runnerName,
      ...(matchedProfileId ? { profileId: String(matchedProfileId) } : {}),
      tab: firstQueryValue(route.query.tab) || 'runtime',
    },
  })
}

function handleSearch() {
  offset.value = 0
  pagination.current = 1
  loadLogs()
}

function resetFilters() {
  filters.runnerName = undefined
  filters.runId = undefined
  filters.eventType = undefined
  filters.status = undefined
  filters.keyword = ''
  filters.createdRange = []
  offset.value = 0
  pagination.current = 1
  loadLogs()
}

function handleTableChange(page: { current?: number }) {
  offset.value = ((page.current || 1) - 1) * size.value
  loadLogs()
}

watch(
  () => [route.query.runnerName, route.query.runId, route.query.profileId, route.query.tab],
  () => {
    syncFiltersFromRoute()
    offset.value = 0
    pagination.current = 1
    loadLogs()
  },
)

onMounted(async () => {
  await loadProfiles()
  syncFiltersFromRoute()
  await loadLogs()
})
</script>

<style scoped>
.page-card {
  min-height: 100%;
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

.filter-item-range {
  grid-column: span 2;
}

.filter-item :deep(.ant-select),
.filter-item :deep(.ant-picker),
.filter-item :deep(.ant-input),
.filter-item :deep(.ant-input-number) {
  width: 100%;
}

.cell-text {
  white-space: normal;
  word-break: break-word;
}

:deep(.ant-table-thead > tr > th) {
  white-space: nowrap;
}

@media (max-width: 1200px) {
  .filter-item-range {
    grid-column: span 1;
  }
}
</style>
