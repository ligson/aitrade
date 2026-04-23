<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-form layout="vertical" class="filter-form">
        <div class="filter-grid">
          <a-form-item label="策略" class="filter-item">
            <a-select v-model:value="filters.strategy" allow-clear placeholder="全部策略">
              <a-select-option v-for="item in strategyOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="方向" class="filter-item">
            <a-select v-model:value="filters.side" allow-clear placeholder="全部方向">
              <a-select-option v-for="item in sideOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="结果" class="filter-item">
            <a-select v-model:value="filters.result" allow-clear placeholder="全部结果">
              <a-select-option v-for="item in resultOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="交易对" class="filter-item">
            <a-select v-model:value="filters.symbol" allow-clear show-search placeholder="全部交易对" :filter-option="filterSelectOption">
              <a-select-option v-for="item in symbolOptions" :key="item" :value="item">
                {{ item }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="交易时间" class="filter-item filter-item-range">
            <a-config-provider :locale="zhCN">
              <a-range-picker v-model:value="filters.createdRange" show-time style="width: 100%" />
            </a-config-provider>
          </a-form-item>
        </div>
        <a-space wrap>
          <a-button type="primary" @click="handleSearch">查询</a-button>
          <a-button @click="resetFilters">重置</a-button>
          <a-button @click="loadPositions">查看当前持仓</a-button>
        </a-space>
      </a-form>
      <a-table :data-source="rows" :columns="columns" row-key="id" :loading="loading" :pagination="pagination" @change="handleTableChange">
        <template #bodyCell="{ column, text }">
          <template v-if="column.key === 'created_at'">
            {{ formatDateTime(text) }}
          </template>
          <template v-else-if="column.key === 'side'">
            <a-tag :color="sideTagColor(text)">{{ sideLabel(text) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'result'">
            <a-tag :color="resultTagColor(text)">{{ resultLabel(text) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'market_price' || column.key === 'requested_amount'">
            {{ formatNumber(text) }}
          </template>
          <template v-else-if="column.key === 'symbol'">
            {{ formatSymbol(text) }}
          </template>
          <template v-else>
            {{ displayText(text) }}
          </template>
        </template>
      </a-table>
    </a-space>
    <a-drawer v-model:open="drawerOpen" title="当前持仓" width="720">
      <a-table :data-source="positions" :columns="positionColumns" row-key="symbol" :pagination="false">
        <template #bodyCell="{ column, text }">
          <template v-if="column.key === 'updated_at' || column.key === 'entry_time'">
            {{ formatDateTime(text) }}
          </template>
          <template v-else-if="column.key === 'entry_price' || column.key === 'amount' || column.key === 'stop_loss'">
            {{ formatNumber(text) }}
          </template>
          <template v-else-if="column.key === 'symbol'">
            {{ formatSymbol(text) }}
          </template>
          <template v-else>
            {{ displayText(text) }}
          </template>
        </template>
      </a-table>
    </a-drawer>
  </a-card>
</template>

<script setup lang="ts">
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import dayjs, { type Dayjs } from 'dayjs'
import 'dayjs/locale/zh-cn'
import { computed, onMounted, reactive, ref } from 'vue'

import { fetchStrategyDefinitions } from '@/api/strategies'
import { fetchPositions, fetchTradeLogFilterOptions, pageTradeLogs } from '@/api/tradeLogs'
import type { StrategyDefinition } from '@/types/strategy'
import type { PositionItem, TradeLogItem } from '@/types/tradeLog'

dayjs.locale('zh-cn')

const loading = ref(false)
const drawerOpen = ref(false)
const rows = ref<TradeLogItem[]>([])
const positions = ref<PositionItem[]>([])
const total = ref(0)
const offset = ref(0)
const size = ref(10)
const definitions = ref<StrategyDefinition[]>([])
const symbolOptions = ref<string[]>([])

const sideOptions = [
  { label: '买入', value: 'buy' },
  { label: '卖出', value: 'sell' },
]

const resultOptions = [
  { label: '已执行', value: 'executed' },
  { label: '已跳过', value: 'skipped' },
  { label: '风控拒绝', value: 'risk_rejected' },
  { label: '执行失败', value: 'failed' },
]

const filters = reactive<{ strategy?: string; side?: string; result?: string; symbol?: string; createdRange: [Dayjs, Dayjs] | [] }>({
  strategy: undefined,
  side: undefined,
  result: undefined,
  symbol: undefined,
  createdRange: [],
})

const strategyOptions = computed(() => definitions.value.map((item) => ({ label: item.displayName, value: item.strategyType })))

const columns = [
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 200 },
  { title: '策略', dataIndex: 'strategy', key: 'strategy', width: 140 },
  { title: '交易对', dataIndex: 'symbol', key: 'symbol', width: 140 },
  { title: '方向', dataIndex: 'side', key: 'side', width: 100 },
  { title: '价格', dataIndex: 'market_price', key: 'market_price', width: 120 },
  { title: '数量', dataIndex: 'requested_amount', key: 'requested_amount', width: 120 },
  { title: '结果', dataIndex: 'result', key: 'result', width: 120 },
  { title: '原因', dataIndex: 'result_reason', key: 'result_reason' },
]

const positionColumns = [
  { title: '交易对', dataIndex: 'symbol', key: 'symbol' },
  { title: '策略', dataIndex: 'strategy', key: 'strategy' },
  { title: '入场时间', dataIndex: 'entry_time', key: 'entry_time' },
  { title: '入场价', dataIndex: 'entry_price', key: 'entry_price' },
  { title: '数量', dataIndex: 'amount', key: 'amount' },
  { title: '止损', dataIndex: 'stop_loss', key: 'stop_loss' },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at' },
]

const pagination = reactive({
  current: 1,
  pageSize: size.value,
  total: total.value,
  showSizeChanger: false,
})

function filterSelectOption(input: string, option?: { children?: unknown; value?: unknown }) {
  const label = typeof option?.children === 'string' ? option.children : String(option?.value || '')
  return label.toLowerCase().includes(input.toLowerCase())
}

function buildPayload() {
  const [createdFrom, createdTo] = filters.createdRange
  return {
    offset: offset.value,
    size: size.value,
    strategy: filters.strategy,
    side: filters.side,
    result: filters.result,
    symbol: filters.symbol,
    createdFrom: createdFrom ? createdFrom.toISOString() : undefined,
    createdTo: createdTo ? createdTo.toISOString() : undefined,
  }
}

function displayText(value: unknown) {
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed || '-'
  }
  if (value === null || value === undefined) {
    return '-'
  }
  return String(value)
}

function formatSymbol(value: unknown) {
  return displayText(value)
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return '-'
  }
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm:ss') : value
}

function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }
  return Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 8 })
}

function sideLabel(value: string | null | undefined) {
  return sideOptions.find((item) => item.value === value)?.label || value || '-'
}

function resultLabel(value: string | null | undefined) {
  return resultOptions.find((item) => item.value === value)?.label || value || '-'
}

function sideTagColor(value: string | null | undefined) {
  if (value === 'buy') {
    return 'green'
  }
  if (value === 'sell') {
    return 'volcano'
  }
  return 'default'
}

function resultTagColor(value: string | null | undefined) {
  if (value === 'executed') {
    return 'green'
  }
  if (value === 'skipped') {
    return 'gold'
  }
  if (value === 'risk_rejected') {
    return 'orange'
  }
  if (value === 'failed') {
    return 'red'
  }
  return 'default'
}

async function loadLogs() {
  loading.value = true
  try {
    const data = await pageTradeLogs(buildPayload())
    rows.value = data.data
    total.value = data.total
    pagination.total = data.total
    pagination.current = Math.floor(offset.value / size.value) + 1
  } finally {
    loading.value = false
  }
}

async function loadFilterOptions() {
  const [strategyDefinitions, filterOptions] = await Promise.all([fetchStrategyDefinitions(), fetchTradeLogFilterOptions()])
  definitions.value = strategyDefinitions
  symbolOptions.value = Array.from(new Set(filterOptions.symbols.map((item) => item.trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b))
}

async function loadPositions() {
  positions.value = await fetchPositions()
  drawerOpen.value = true
}

function handleSearch() {
  offset.value = 0
  pagination.current = 1
  loadLogs()
}

function resetFilters() {
  filters.strategy = undefined
  filters.side = undefined
  filters.result = undefined
  filters.symbol = undefined
  filters.createdRange = []
  offset.value = 0
  pagination.current = 1
  loadLogs()
}

function handleTableChange(page: { current?: number }) {
  offset.value = ((page.current || 1) - 1) * size.value
  loadLogs()
}

onMounted(async () => {
  await loadFilterOptions()
  await loadLogs()
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

.filter-item-range {
  grid-column: span 2;
}

.filter-item :deep(.ant-select),
.filter-item :deep(.ant-picker) {
  width: 100%;
}

@media (max-width: 1200px) {
  .filter-item-range {
    grid-column: span 1;
  }
}
</style>
