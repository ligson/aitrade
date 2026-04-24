<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-form layout="vertical" class="run-form">
        <div class="filter-grid">
          <a-form-item label="策略配置" class="filter-item">
            <a-select v-model:value="runForm.strategyProfileId" placeholder="请选择策略配置" show-search :filter-option="filterSelectOption">
              <a-select-option v-for="item in supportedProfiles" :key="item.id" :value="item.id">
                {{ item.name }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="历史文件" class="filter-item filter-item-wide">
            <a-select
              v-model:value="runForm.dataFile"
              placeholder="请选择历史数据文件"
              show-search
              :filter-option="filterSelectOption"
              @change="handleDataFileChange"
            >
              <a-select-option v-for="item in dataFiles" :key="item.filename" :value="item.filename">
                {{ item.filename }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="交易对" class="filter-item">
            <a-input :value="selectedDataFile?.symbol || '-'" disabled />
          </a-form-item>
          <a-form-item label="周期" class="filter-item">
            <a-input :value="selectedDataFile?.timeframe || '-'" disabled />
          </a-form-item>
          <a-form-item label="文件时间范围" class="filter-item filter-item-wide">
            <a-input :value="selectedTimerangeLabel" disabled />
          </a-form-item>
          <a-form-item label="初始资金" class="filter-item">
            <a-input-number v-model:value="runForm.initialBalance" :min="1" style="width: 100%" />
          </a-form-item>
          <a-form-item label="手续费率" class="filter-item">
            <a-input-number v-model:value="runForm.feeRate" :min="0" :step="0.0001" :precision="4" style="width: 100%" />
          </a-form-item>
        </div>
        <a-space wrap>
          <a-button type="primary" :loading="runLoading" :disabled="!runForm.strategyProfileId || !runForm.dataFile" @click="openRunConfirm">开始回测</a-button>
          <a-button @click="goToHistoryData">管理历史数据</a-button>
          <a-button @click="loadJobs">刷新任务</a-button>
        </a-space>
        <a-alert
          v-if="unsupportedProfiles.length > 0"
          style="margin-top: 12px"
          type="warning"
          show-icon
          :message="'以下策略暂不支持离线回测：' + unsupportedProfiles.map((item) => item.name).join('、')"
        />
      </a-form>

      <a-form layout="inline">
        <a-form-item>
          <a-input v-model:value="filters.keyword" allow-clear placeholder="搜索配置名称 / 策略 / 交易对" style="width: 280px" />
        </a-form-item>
        <a-form-item>
          <a-select v-model:value="filters.status" allow-clear placeholder="全部状态" style="width: 180px">
            <a-select-option v-for="item in statusOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch">查询</a-button>
        </a-form-item>
        <a-form-item>
          <a-button @click="resetFilters">重置</a-button>
        </a-form-item>
      </a-form>

      <a-table :data-source="rows" :columns="columns" row-key="id" :loading="loading" :pagination="pagination" @change="handleTableChange">
        <template #bodyCell="{ column, record, text }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'dataSource'">
            {{ backtestDataSourceLabel(record) }}
          </template>
          <template v-else-if="column.key === 'totalReturn'">
            {{ formatPercent(record.summary.totalReturn) }}
          </template>
          <template v-else-if="column.key === 'maxDrawdown'">
            {{ formatPercent(record.summary.maxDrawdown) }}
          </template>
          <template v-else-if="column.key === 'tradeCount'">
            {{ record.summary.tradeCount ?? '-' }}
          </template>
          <template v-else-if="column.key === 'estimatedFinishAt'">
            {{ formatDateTime(record.estimatedFinishAt) }}
          </template>
          <template v-else-if="column.key === 'createdAt' || column.key === 'finishedAt'">
            {{ formatDateTime(text) }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space size="small" wrap>
              <a-button type="link" @click="openDetail(record)">详情</a-button>
              <a-popconfirm
                v-if="record.canStop"
                title="确认停止这个回测任务吗？"
                ok-text="停止"
                cancel-text="取消"
                @confirm="handleStopJob(record)"
              >
                <a-button type="link" danger>停止</a-button>
              </a-popconfirm>
              <a-button v-else-if="record.status === 'stop_requested'" type="link" disabled>停止中</a-button>
            </a-space>
          </template>
          <template v-else>
            {{ text || '-' }}
          </template>
        </template>
      </a-table>
    </a-space>

    <a-modal v-model:open="runConfirmOpen" title="确认开始回测" ok-text="确认开始" cancel-text="取消" :confirm-loading="runLoading" @ok="confirmRunBacktest">
      <a-descriptions :column="1" bordered size="small">
        <a-descriptions-item label="策略配置">{{ selectedProfile?.name || '-' }}</a-descriptions-item>
        <a-descriptions-item label="策略类型">{{ selectedProfile?.strategyType || '-' }}</a-descriptions-item>
        <a-descriptions-item label="历史文件">{{ selectedDataFile?.filename || '-' }}</a-descriptions-item>
        <a-descriptions-item label="交易对">{{ selectedDataFile?.symbol || '-' }}</a-descriptions-item>
        <a-descriptions-item label="周期">{{ selectedDataFile?.timeframe || '-' }}</a-descriptions-item>
        <a-descriptions-item label="文件时间范围">{{ selectedTimerangeLabel }}</a-descriptions-item>
        <a-descriptions-item label="初始资金">{{ formatNumber(runForm.initialBalance) }}</a-descriptions-item>
        <a-descriptions-item label="手续费率">{{ formatPercent(runForm.feeRate) }}</a-descriptions-item>
      </a-descriptions>
    </a-modal>

    <a-drawer v-model:open="detailOpen" title="回测详情" width="980">
      <template v-if="detailJob">
        <a-space style="margin-bottom: 16px" v-if="detailJob.canStop || detailJob.status === 'stop_requested'">
          <a-popconfirm
            v-if="detailJob.canStop"
            title="确认停止这个回测任务吗？"
            ok-text="停止"
            cancel-text="取消"
            @confirm="handleStopJob(detailJob)"
          >
            <a-button danger>停止任务</a-button>
          </a-popconfirm>
          <a-button v-else type="default" disabled>停止中</a-button>
        </a-space>

        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="策略配置">{{ detailJob.profileName }}</a-descriptions-item>
          <a-descriptions-item label="策略类型">{{ detailJob.strategyType }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="statusColor(detailJob.status)">{{ statusLabel(detailJob.status) }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="发起人">{{ detailJob.createdBy }}</a-descriptions-item>
          <a-descriptions-item label="交易对">{{ detailJob.symbol }}</a-descriptions-item>
          <a-descriptions-item label="周期">{{ detailJob.timeframe }}</a-descriptions-item>
          <a-descriptions-item label="开始时间">{{ formatDateTime(detailJob.timerangeFrom) }}</a-descriptions-item>
          <a-descriptions-item label="结束时间">{{ formatDateTime(detailJob.timerangeTo) }}</a-descriptions-item>
          <a-descriptions-item label="初始资金">{{ formatNumber(detailJob.initialBalance) }}</a-descriptions-item>
          <a-descriptions-item label="手续费率">{{ formatPercent(detailJob.feeRate) }}</a-descriptions-item>
          <a-descriptions-item label="任务创建时间">{{ formatDateTime(detailJob.createdAt) }}</a-descriptions-item>
          <a-descriptions-item label="任务完成时间">{{ formatDateTime(detailJob.finishedAt) }}</a-descriptions-item>
          <a-descriptions-item label="预计完成时间">{{ formatDateTime(detailJob.estimatedFinishAt) }}</a-descriptions-item>
          <a-descriptions-item label="停止请求时间">{{ formatDateTime(detailJob.stopRequestedAt) }}</a-descriptions-item>
          <a-descriptions-item label="当前进度">{{ progressLabel(detailJob) }}</a-descriptions-item>
          <a-descriptions-item label="进度百分比">{{ progressPercentLabel(detailJob) }}</a-descriptions-item>
        </a-descriptions>

        <a-alert v-if="detailJob.errorMessage" style="margin-top: 16px" type="error" show-icon :message="detailJob.errorMessage" />

        <a-descriptions :column="2" bordered size="small" style="margin-top: 16px">
          <a-descriptions-item label="历史文件">{{ detailJob.dataSource.filename || '-' }}</a-descriptions-item>
          <a-descriptions-item label="来源类型">{{ detailJob.dataSource.sourceType || '-' }}</a-descriptions-item>
          <a-descriptions-item label="数据格式">{{ detailJob.dataSource.format || '-' }}</a-descriptions-item>
          <a-descriptions-item label="文件大小">{{ formatFileSize(detailJob.dataSource.size) }}</a-descriptions-item>
          <a-descriptions-item label="数据开始时间">{{ formatDateTime(detailJob.dataSource.timerangeFrom || detailJob.timerangeFrom) }}</a-descriptions-item>
          <a-descriptions-item label="数据结束时间">{{ formatDateTime(detailJob.dataSource.timerangeTo || detailJob.timerangeTo) }}</a-descriptions-item>
          <a-descriptions-item label="文件路径" :span="2">{{ detailJob.dataSource.path || '-' }}</a-descriptions-item>
        </a-descriptions>

        <a-descriptions :column="2" bordered size="small" style="margin-top: 16px">
          <a-descriptions-item label="最终权益">{{ formatNumber(detailJob.summary.finalEquity) }}</a-descriptions-item>
          <a-descriptions-item label="总收益率">{{ formatPercent(detailJob.summary.totalReturn) }}</a-descriptions-item>
          <a-descriptions-item label="最大回撤">{{ formatPercent(detailJob.summary.maxDrawdown) }}</a-descriptions-item>
          <a-descriptions-item label="已完成交易数">{{ detailJob.summary.completedTradeCount ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="总成交记录数">{{ detailJob.summary.tradeCount ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="胜率">{{ formatPercent(detailJob.summary.winRate) }}</a-descriptions-item>
        </a-descriptions>

        <a-alert v-if="detailDefinition" style="margin-top: 16px" type="info" show-icon :message="detailDefinition.displayName" :description="detailDefinition.description" />

        <a-descriptions v-if="detailParamItems.length > 0" :column="2" bordered size="small" style="margin-top: 16px">
          <a-descriptions-item v-for="item in detailParamItems" :key="item.field" :label="item.label">
            {{ item.value }}
          </a-descriptions-item>
        </a-descriptions>

        <a-typography-title :level="5" style="margin-top: 16px; margin-bottom: 12px">成交明细</a-typography-title>
        <a-alert
          v-if="!detailTradesLoading && detailTradePagination.total === 0"
          type="info"
          show-icon
          message="当前暂无成交记录"
        />
        <a-table
          v-else
          :data-source="detailTrades"
          :columns="tradeColumns"
          row-key="id"
          :loading="detailTradesLoading"
          :pagination="detailTradePagination"
          @change="handleTradeTableChange"
        >
          <template #bodyCell="{ column, text, record }">
            <template v-if="column.key === 'barTime'">
              {{ formatDateTime(text) }}
            </template>
            <template v-else-if="column.key === 'price' || column.key === 'quantity' || column.key === 'fee' || column.key === 'pnl'">
              {{ formatNumber(text) }}
            </template>
            <template v-else-if="column.key === 'side'">
              <a-tag :color="record.side === 'buy' ? 'green' : 'volcano'">{{ record.side === 'buy' ? '买入' : '卖出' }}</a-tag>
            </template>
            <template v-else>
              {{ text || '-' }}
            </template>
          </template>
        </a-table>
      </template>
    </a-drawer>
  </a-card>
</template>

<script setup lang="ts">
import dayjs from 'dayjs'
import { message } from 'ant-design-vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchBacktestDataOptions, fetchBacktestDetail, pageBacktestDataFiles, pageBacktests, pageBacktestTrades, runBacktest, stopBacktest } from '@/api/backtests'
import { fetchStrategyDefinitions, fetchStrategyProfiles } from '@/api/strategies'
import type { BacktestDataFileItem, BacktestDataOptions, BacktestJobItem, BacktestTradeItem } from '@/types/backtest'
import type { StrategyDefinition, StrategyFieldSchema, StrategyProfile } from '@/types/strategy'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const runLoading = ref(false)
const detailOpen = ref(false)
const detailTradesLoading = ref(false)
const runConfirmOpen = ref(false)
const rows = ref<BacktestJobItem[]>([])
const definitions = ref<StrategyDefinition[]>([])
const profiles = ref<StrategyProfile[]>([])
const dataFiles = ref<BacktestDataFileItem[]>([])
const detailJob = ref<BacktestJobItem | null>(null)
const detailTrades = ref<BacktestTradeItem[]>([])
const pollTimer = ref<number | null>(null)

const options = reactive<BacktestDataOptions>({
  supportedSymbols: [],
  supportedTimeframes: [],
  defaultSymbol: 'BTC/USDT',
  defaultTimeframe: '15m',
  dataFormatOhlcv: 'jsongz',
  downloadMode: 'full',
  archiveFormat: 'zip',
})

const runForm = reactive({
  strategyProfileId: undefined as number | undefined,
  dataFile: '',
  initialBalance: 10000,
  feeRate: 0.001,
})

const filters = reactive({
  keyword: '',
  status: undefined as string | undefined,
})

const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: false,
})

const detailTradePagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: false,
})

const statusOptions = [
  { label: '待执行', value: 'pending' },
  { label: '运行中', value: 'running' },
  { label: '停止中', value: 'stop_requested' },
  { label: '已停止', value: 'stopped' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
  { label: '不支持', value: 'unsupported' },
]

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: '策略配置', dataIndex: 'profileName', key: 'profileName', width: 180 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 120 },
  { title: '数据来源', key: 'dataSource', width: 240 },
  { title: '预计完成时间', dataIndex: 'estimatedFinishAt', key: 'estimatedFinishAt', width: 180 },
  { title: '收益率', key: 'totalReturn', width: 120 },
  { title: '最大回撤', key: 'maxDrawdown', width: 120 },
  { title: '交易数', key: 'tradeCount', width: 120 },
  { title: '创建时间', dataIndex: 'createdAt', key: 'createdAt', width: 180 },
  { title: '完成时间', dataIndex: 'finishedAt', key: 'finishedAt', width: 180 },
  { title: '操作', key: 'actions', width: 180 },
]

const tradeColumns = [
  { title: '时间', dataIndex: 'barTime', key: 'barTime', width: 180 },
  { title: '方向', dataIndex: 'side', key: 'side', width: 100 },
  { title: '价格', dataIndex: 'price', key: 'price', width: 120 },
  { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 120 },
  { title: '手续费', dataIndex: 'fee', key: 'fee', width: 120 },
  { title: '盈亏', dataIndex: 'pnl', key: 'pnl', width: 120 },
  { title: '原因', dataIndex: 'reason', key: 'reason' },
]

const supportedProfiles = computed(() => profiles.value.filter((item) => item.definition?.backtestSupported))
const unsupportedProfiles = computed(() => profiles.value.filter((item) => item.definition && !item.definition.backtestSupported))
const detailDefinition = computed(() => definitions.value.find((item) => item.strategyType === detailJob.value?.strategyType))
const selectedDataFile = computed(() => dataFiles.value.find((item) => item.filename === runForm.dataFile) || null)
const selectedProfile = computed(() => profiles.value.find((item) => item.id === runForm.strategyProfileId) || null)
const selectedTimerangeLabel = computed(() => {
  if (!selectedDataFile.value) {
    return '-'
  }
  return `${formatDateTime(selectedDataFile.value.timerangeFrom)} ~ ${formatDateTime(selectedDataFile.value.timerangeTo)}`
})
const detailParamItems = computed(() => {
  if (!detailJob.value) {
    return []
  }
  const schema = detailDefinition.value?.paramSchema || []
  if (schema.length > 0) {
    return schema.map((field) => ({
      field: field.field,
      label: field.label,
      value: formatParamValue(field, detailJob.value?.params[field.field]),
    }))
  }
  return Object.entries(detailJob.value.params).map(([field, value]) => ({
    field,
    label: field,
    value: formatFallbackValue(value),
  }))
})

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

function formatNumber(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  const normalized = Number(value)
  if (Number.isNaN(normalized)) {
    return '-'
  }
  return normalized.toLocaleString('zh-CN', { maximumFractionDigits: 8 })
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }
  return `${(Number(value) * 100).toFixed(2)}%`
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

function formatFallbackValue(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (typeof value === 'boolean') {
    return value ? '是' : '否'
  }
  return String(value)
}

function formatParamValue(field: StrategyFieldSchema, value: unknown) {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (field.type === 'boolean') {
    return Boolean(value) ? '是' : '否'
  }
  return String(value)
}

function statusLabel(value: string) {
  return statusOptions.find((item) => item.value === value)?.label || value
}

function statusColor(value: string) {
  if (value === 'success') {
    return 'green'
  }
  if (value === 'running') {
    return 'blue'
  }
  if (value === 'pending') {
    return 'gold'
  }
  if (value === 'stop_requested') {
    return 'orange'
  }
  if (value === 'stopped') {
    return 'default'
  }
  if (value === 'failed') {
    return 'red'
  }
  return 'default'
}

function backtestDataSourceLabel(job: BacktestJobItem) {
  if (job.dataSource.filename) {
    return job.dataSource.filename
  }
  if (job.dataSource.symbol || job.dataSource.timeframe || job.dataSource.timerange) {
    return [job.dataSource.symbol, job.dataSource.timeframe, job.dataSource.timerange].filter(Boolean).join(' / ') || '-'
  }
  return '-'
}

function progressLabel(job: BacktestJobItem | null) {
  if (!job || job.progressCurrent === null || job.progressCurrent === undefined || job.progressTotal === null || job.progressTotal === undefined) {
    return '-'
  }
  return `${job.progressCurrent} / ${job.progressTotal}`
}

function progressPercentLabel(job: BacktestJobItem | null) {
  if (!job || job.progressPercent === null || job.progressPercent === undefined) {
    return '-'
  }
  return `${job.progressPercent.toFixed(2)}%`
}

async function loadDefinitionsAndProfiles() {
  const [definitionRows, profileRows] = await Promise.all([fetchStrategyDefinitions(), fetchStrategyProfiles()])
  definitions.value = definitionRows
  profiles.value = profileRows.map((item) => ({
    ...item,
    definition: definitionRows.find((definition) => definition.strategyType === item.strategyType),
  }))
  if (!runForm.strategyProfileId) {
    runForm.strategyProfileId = supportedProfiles.value[0]?.id
  }
}

async function loadDataOptions() {
  const data = await fetchBacktestDataOptions()
  Object.assign(options, data)
}

async function loadDataFiles() {
  const data = await pageBacktestDataFiles({
    offset: 0,
    size: 200,
  })
  dataFiles.value = data.data
  const queryDataFile = typeof route.query.dataFile === 'string' ? route.query.dataFile : ''
  if (queryDataFile && dataFiles.value.some((item) => item.filename === queryDataFile)) {
    runForm.dataFile = queryDataFile
  }
  if (!runForm.dataFile) {
    runForm.dataFile = dataFiles.value[0]?.filename || ''
  }
}

async function loadJobs() {
  loading.value = true
  try {
    const data = await pageBacktests({
      offset: (pagination.current - 1) * pagination.pageSize,
      size: pagination.pageSize,
      keyword: filters.keyword,
      status: filters.status,
    })
    rows.value = data.data
    pagination.total = data.total
    ensurePolling()
  } finally {
    loading.value = false
  }
}

async function loadDetailTrades() {
  if (!detailJob.value) {
    return
  }
  detailTradesLoading.value = true
  try {
    const data = await pageBacktestTrades({
      jobId: detailJob.value.id,
      offset: (detailTradePagination.current - 1) * detailTradePagination.pageSize,
      size: detailTradePagination.pageSize,
    })
    detailTrades.value = data.data
    detailTradePagination.total = data.total
  } finally {
    detailTradesLoading.value = false
  }
}

function handleDataFileChange() {
  if (route.query.dataFile) {
    router.replace({ name: 'backtests' })
  }
}

function validateRunForm() {
  if (!runForm.strategyProfileId) {
    message.warning('请先选择策略配置')
    return false
  }
  if (!runForm.dataFile) {
    message.warning('请先选择历史文件')
    return false
  }
  return true
}

function openRunConfirm() {
  if (!validateRunForm()) {
    return
  }
  runConfirmOpen.value = true
}

async function confirmRunBacktest() {
  if (!validateRunForm()) {
    return
  }
  runLoading.value = true
  try {
    const job = await runBacktest({
      strategyProfileId: runForm.strategyProfileId!,
      dataFile: runForm.dataFile,
      initialBalance: runForm.initialBalance,
      feeRate: runForm.feeRate,
    })
    runConfirmOpen.value = false
    message.success(job.status === 'unsupported' ? '该策略暂不支持离线回测' : '回测任务已创建')
    await loadJobs()
    if (job.status !== 'unsupported') {
      await openDetail(job)
    }
  } finally {
    runLoading.value = false
  }
}

async function handleStopJob(record: BacktestJobItem) {
  const job = await stopBacktest(record.id)
  message.success(job.status === 'stop_requested' ? '停止请求已发送' : '任务已更新')
  await loadJobs()
  if (detailJob.value?.id === record.id) {
    detailJob.value = await fetchBacktestDetail(record.id)
    await loadDetailTrades()
  }
}

function goToHistoryData() {
  router.push({ name: 'backtest-data' })
}

function handleSearch() {
  pagination.current = 1
  loadJobs()
}

function resetFilters() {
  filters.keyword = ''
  filters.status = undefined
  pagination.current = 1
  loadJobs()
}

function handleTableChange(page: { current?: number }) {
  pagination.current = page.current || 1
  loadJobs()
}

function handleTradeTableChange(page: { current?: number }) {
  detailTradePagination.current = page.current || 1
  loadDetailTrades()
}

async function openDetail(record: BacktestJobItem) {
  detailJob.value = await fetchBacktestDetail(record.id)
  detailOpen.value = true
  detailTradePagination.current = 1
  await loadDetailTrades()
}

function ensurePolling() {
  const hasRunning = rows.value.some((item) => item.status === 'pending' || item.status === 'running' || item.status === 'stop_requested')
  if (!hasRunning) {
    stopPolling()
    return
  }
  if (pollTimer.value !== null) {
    return
  }
  pollTimer.value = window.setInterval(async () => {
    await loadJobs()
    if (detailJob.value && (detailJob.value.status === 'pending' || detailJob.value.status === 'running' || detailJob.value.status === 'stop_requested')) {
      detailJob.value = await fetchBacktestDetail(detailJob.value.id)
      await loadDetailTrades()
    }
  }, 4000)
}

function stopPolling() {
  if (pollTimer.value !== null) {
    window.clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

onMounted(async () => {
  await loadDefinitionsAndProfiles()
  await loadDataOptions()
  await loadDataFiles()
  await loadJobs()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped>
.page-card {
  min-height: 100%;
}

.run-form {
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

.filter-item-wide {
  grid-column: span 2;
}

@media (max-width: 1200px) {
  .filter-item-wide {
    grid-column: span 1;
  }
}
</style>
