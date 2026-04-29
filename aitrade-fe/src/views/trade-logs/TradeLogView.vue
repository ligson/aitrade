<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="这里展示的是交易结果日志，可按条件筛选具体成交、跳过、风控拒绝和失败记录。"
        :description="activeRunTip"
      />

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
          <a-form-item label="运行实例 ID" class="filter-item">
            <a-input-number v-model:value="filters.runId" placeholder="全部实例" :min="1" :precision="0" style="width: 100%" />
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

      <a-table :data-source="rows" :columns="columns" row-key="id" :loading="loading" :pagination="pagination" :scroll="{ x: 'max-content' }" @change="handleTableChange">
        <template #bodyCell="{ column, record, text }">
          <template v-if="column.key === 'created_at'">
            {{ formatDateTime(text) }}
          </template>
          <template v-else-if="column.key === 'side'">
            <a-tag :color="sideTagColor(record.side)">{{ sideLabel(record.side) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'trade_mode'">
            <a-tag :color="tradeModeTagColor(resolveTradeMode(record))">{{ tradeModeLabel(resolveTradeMode(record)) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'result'">
            <a-tag :color="resultTagColor(record.result)">{{ resultLabel(record.result) }}</a-tag>
          </template>
          <template
            v-else-if="[
              'market_price',
              'requested_amount',
              'estimated_fill_price',
              'estimated_fee',
              'realized_pnl_net',
            ].includes(String(column.key))"
          >
            {{ formatNumber(text) }}
          </template>
          <template v-else-if="column.key === 'symbol'">
            {{ formatSymbol(text) }}
          </template>
          <template v-else-if="column.key === 'run_id'">
            {{ record.run_id ?? '-' }}
          </template>
          <template v-else-if="column.key === 'trigger_source'">
            <div class="cell-text">{{ triggerSourceLabel(record.trigger_source) }}</div>
          </template>
          <template v-else-if="column.key === 'error_message' || column.key === 'result_reason'">
            <div class="cell-text">{{ displayText(text) }}</div>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-button type="link" @click="openDetail(record)">查看</a-button>
          </template>
          <template v-else>
            {{ displayText(text) }}
          </template>
        </template>
      </a-table>
    </a-space>

    <a-drawer v-model:open="detailOpen" title="交易日志详情" width="960">
      <template v-if="detailRecord">
        <a-space direction="vertical" size="middle" style="width: 100%">
          <a-descriptions :column="2" bordered size="small">
            <a-descriptions-item label="日志 ID">{{ detailRecord.id }}</a-descriptions-item>
            <a-descriptions-item label="运行实例 ID">{{ detailRecord.run_id ?? '-' }}</a-descriptions-item>
            <a-descriptions-item label="任务配置 ID">{{ detailRecord.trade_task_profile_id ?? '-' }}</a-descriptions-item>
            <a-descriptions-item label="交易对">{{ formatSymbol(detailRecord.symbol) }}</a-descriptions-item>
            <a-descriptions-item label="策略">{{ displayText(detailRecord.strategy) }}</a-descriptions-item>
            <a-descriptions-item label="方向">{{ sideLabel(detailRecord.side) }}</a-descriptions-item>
            <a-descriptions-item label="结果">
              <a-tag :color="resultTagColor(detailRecord.result)">{{ resultLabel(detailRecord.result) }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="触发来源">{{ triggerSourceLabel(detailRecord.trigger_source) }}</a-descriptions-item>
            <a-descriptions-item label="时间">{{ formatDateTime(detailRecord.created_at) }}</a-descriptions-item>
            <a-descriptions-item label="交易方式">{{ tradeModeLabel(resolveTradeMode(detailRecord)) }}</a-descriptions-item>
            <a-descriptions-item label="结果原因" :span="2">{{ displayText(detailRecord.result_reason) }}</a-descriptions-item>
            <a-descriptions-item label="错误信息" :span="2">{{ displayText(detailRecord.error_message) }}</a-descriptions-item>
          </a-descriptions>

          <a-card size="small" title="价格与数量">
            <a-descriptions :column="2" bordered size="small">
              <a-descriptions-item label="市场价格">{{ formatNumber(detailRecord.market_price) }}</a-descriptions-item>
              <a-descriptions-item label="请求数量">{{ formatNumber(detailRecord.requested_amount) }}</a-descriptions-item>
              <a-descriptions-item label="订单 ID">{{ displayText(detailRecord.order_id) }}</a-descriptions-item>
              <a-descriptions-item label="订单状态">{{ displayText(detailRecord.order_status) }}</a-descriptions-item>
              <a-descriptions-item label="订单类型">{{ displayText(detailRecord.order_type) }}</a-descriptions-item>
              <a-descriptions-item label="订单价格">{{ formatNumber(detailRecord.order_price) }}</a-descriptions-item>
              <a-descriptions-item label="订单数量">{{ formatNumber(detailRecord.order_amount) }}</a-descriptions-item>
              <a-descriptions-item label="订单金额">{{ formatNumber(detailRecord.order_cost) }}</a-descriptions-item>
              <a-descriptions-item label="估算成交价">{{ formatNumber(detailRecord.estimated_fill_price) }}</a-descriptions-item>
              <a-descriptions-item label="估算手续费">{{ formatNumber(detailRecord.estimated_fee) }}</a-descriptions-item>
              <a-descriptions-item label="手续费率">{{ formatRate(detailRecord.fee_rate) }}</a-descriptions-item>
              <a-descriptions-item label="滑点率">{{ formatRate(detailRecord.slippage_rate) }}</a-descriptions-item>
              <a-descriptions-item label="已实现盈亏">{{ formatNumber(detailRecord.realized_pnl) }}</a-descriptions-item>
              <a-descriptions-item label="已实现净盈亏">{{ formatNumber(detailRecord.realized_pnl_net) }}</a-descriptions-item>
              <a-descriptions-item label="止损价">{{ formatNumber(detailRecord.stop_loss_price) }}</a-descriptions-item>
              <a-descriptions-item label="追踪止损价">{{ formatNumber(detailRecord.trailing_stop_price) }}</a-descriptions-item>
            </a-descriptions>
          </a-card>

          <a-card size="small" title="风控与信号上下文">
            <a-descriptions :column="2" bordered size="small">
              <a-descriptions-item label="信号置信度">{{ formatNumber(detailRecord.signal_confidence) }}</a-descriptions-item>
              <a-descriptions-item label="单笔风险">{{ formatNumber(detailRecord.risk_per_trade) }}</a-descriptions-item>
              <a-descriptions-item label="交易所">{{ displayText(detailRecord.exchange_type) }}</a-descriptions-item>
              <a-descriptions-item label="信号原因">{{ displayText(detailRecord.signal_reason) }}</a-descriptions-item>
            </a-descriptions>
          </a-card>

          <a-card size="small" title="扩展详情">
            <a-descriptions :column="1" bordered size="small">
              <a-descriptions-item v-if="detailSignalSummaryVisible" label="融合信号概览">
                <a-descriptions :column="2" bordered size="small">
                  <a-descriptions-item label="信号分数">{{ formatNumber(detailSignalSummary.signalScore) }}</a-descriptions-item>
                  <a-descriptions-item label="是否降级">{{ detailSignalSummary.degraded }}</a-descriptions-item>
                  <a-descriptions-item label="启用节点数">{{ detailSignalSummary.enabledNodeCount }}</a-descriptions-item>
                  <a-descriptions-item label="可用节点数">{{ detailSignalSummary.availableNodeCount }}</a-descriptions-item>
                  <a-descriptions-item label="归一化偏多分数">{{ formatNumber(detailSignalSummary.normalizedBuyScore) }}</a-descriptions-item>
                  <a-descriptions-item label="归一化偏空分数">{{ formatNumber(detailSignalSummary.normalizedSellScore) }}</a-descriptions-item>
                  <a-descriptions-item label="偏多活跃节点" :span="2">{{ detailSignalSummary.activeBuyNodes }}</a-descriptions-item>
                  <a-descriptions-item label="偏空活跃节点" :span="2">{{ detailSignalSummary.activeSellNodes }}</a-descriptions-item>
                </a-descriptions>
              </a-descriptions-item>
              <a-descriptions-item v-if="detailNodeSignals.length" label="融合节点结果">
                <a-table :data-source="detailNodeSignals" :columns="detailNodeSignalColumns" :pagination="false" size="small" :scroll="{ x: 'max-content' }" row-key="name">
                  <template #bodyCell="{ column, record }">
                    <template v-if="column.key === 'available'">
                      <a-tag :color="record.available ? 'green' : 'default'">{{ record.available ? '可用' : '不可用' }}</a-tag>
                    </template>
                    <template v-else-if="column.key === 'bias'">
                      <a-tag :color="signalBiasTagColor(record.bias)">{{ signalBiasLabel(record.bias) }}</a-tag>
                    </template>
                    <template v-else-if="['weight', 'score', 'confidence'].includes(String(column.key))">
                      {{ formatNumber(record[column.key]) }}
                    </template>
                    <template v-else-if="column.key === 'reason'">
                      <div class="cell-text">{{ displayText(record.reason) }}</div>
                    </template>
                    <template v-else>
                      {{ displayText(record[column.key]) }}
                    </template>
                  </template>
                </a-table>
              </a-descriptions-item>
              <a-descriptions-item label="信号元数据原文">
                <pre class="detail-json">{{ formatJson(detailRecord.signal_meta) }}</pre>
              </a-descriptions-item>
              <a-descriptions-item label="风控快照">
                <pre class="detail-json">{{ formatJson(detailRecord.risk_snapshot) }}</pre>
              </a-descriptions-item>
              <a-descriptions-item label="交易前持仓">
                <pre class="detail-json">{{ formatJson(detailRecord.position_before) }}</pre>
              </a-descriptions-item>
              <a-descriptions-item label="交易后持仓">
                <pre class="detail-json">{{ formatJson(detailRecord.position_after) }}</pre>
              </a-descriptions-item>
              <a-descriptions-item label="单日亏损快照">
                <pre class="detail-json">{{ formatJson(detailRecord.daily_loss_snapshot) }}</pre>
              </a-descriptions-item>
              <a-descriptions-item label="订单原始响应">
                <pre class="detail-json">{{ formatJson(detailRecord.order_raw) }}</pre>
              </a-descriptions-item>
            </a-descriptions>
          </a-card>
        </a-space>
      </template>
    </a-drawer>

    <a-drawer v-model:open="drawerOpen" title="当前持仓" width="900">
      <a-table :data-source="positions" :columns="positionColumns" row-key="symbol" :pagination="false" :scroll="{ x: 'max-content' }">
        <template #bodyCell="{ column, text }">
          <template v-if="column.key === 'updated_at' || column.key === 'entry_time'">
            {{ formatDateTime(text) }}
          </template>
          <template
            v-else-if="[
              'entry_price',
              'amount',
              'stop_loss',
              'initial_stop_loss',
              'trailing_stop_price',
              'highest_price',
              'highest_close',
            ].includes(String(column.key))"
          >
            {{ formatNumber(text as number | null | undefined) }}
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
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { fetchStrategyDefinitions } from '@/api/strategies'
import { fetchSystemSettings } from '@/api/system'
import { fetchPositions, pageTradeLogs } from '@/api/tradeLogs'
import type { StrategyDefinition } from '@/types/strategy'
import type { PositionItem, TradeLogItem } from '@/types/tradeLog'
import type { TradeMode } from '@/types/system'

dayjs.locale('zh-cn')

type SignalNodeItem = {
  name: string
  available: boolean
  bias: string
  weight: number | null
  score: number | null
  confidence: number | null
  reason: string
}

const route = useRoute()
const loading = ref(false)
const drawerOpen = ref(false)
const detailOpen = ref(false)
const rows = ref<TradeLogItem[]>([])
const positions = ref<PositionItem[]>([])
const detailRecord = ref<TradeLogItem | null>(null)
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

const filters = reactive<{ strategy?: string; side?: string; result?: string; symbol?: string; runId?: number; createdRange: [Dayjs, Dayjs] | [] }>({
  strategy: undefined,
  side: undefined,
  result: undefined,
  symbol: undefined,
  runId: undefined,
  createdRange: [],
})

const strategyOptions = computed(() => definitions.value.map((item) => ({ label: item.displayName, value: item.strategyType })))
const activeRunTip = computed(() => {
  if (!filters.runId) {
    return '可结合策略、结果、交易对、运行实例和时间范围排查一次任务运行中的具体交易结果。'
  }
  return `当前已按运行实例 ID ${filters.runId} 聚焦查看交易结果。`
})
const detailNodeSignalColumns = [
  { title: '节点名称', dataIndex: 'name', key: 'name', width: 180 },
  { title: '可用性', dataIndex: 'available', key: 'available', width: 100 },
  { title: '偏向', dataIndex: 'bias', key: 'bias', width: 100 },
  { title: '权重', dataIndex: 'weight', key: 'weight', width: 100 },
  { title: '评分', dataIndex: 'score', key: 'score', width: 100 },
  { title: '置信度', dataIndex: 'confidence', key: 'confidence', width: 120 },
  { title: '原因', dataIndex: 'reason', key: 'reason', width: 320 },
]
const detailSignalMeta = computed<Record<string, unknown>>(() => {
  const value = detailRecord.value?.signal_meta
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {}
})
const detailNodeSignals = computed<SignalNodeItem[]>(() => {
  const rawNodes = Array.isArray(detailSignalMeta.value.node_signals)
    ? detailSignalMeta.value.node_signals
    : Array.isArray(detailSignalMeta.value.signal_sources)
      ? detailSignalMeta.value.signal_sources
      : []
  return rawNodes.map((item) => normalizeSignalNode(item)).filter((item): item is SignalNodeItem => item !== null)
})
const detailSignalSummary = computed(() => ({
  signalScore: toOptionalNumber(detailSignalMeta.value.signal_score),
  degraded: typeof detailSignalMeta.value.degraded === 'boolean' ? (detailSignalMeta.value.degraded ? '是' : '否') : '-',
  enabledNodeCount: toDisplayCount(detailSignalMeta.value.enabled_node_count),
  availableNodeCount: toDisplayCount(detailSignalMeta.value.available_node_count),
  normalizedBuyScore: toOptionalNumber(detailSignalMeta.value.normalized_buy_score),
  normalizedSellScore: toOptionalNumber(detailSignalMeta.value.normalized_sell_score),
  activeBuyNodes: formatNameList(detailSignalMeta.value.active_buy_nodes),
  activeSellNodes: formatNameList(detailSignalMeta.value.active_sell_nodes),
}))
const detailSignalSummaryVisible = computed(() => {
  return [
    detailSignalSummary.value.signalScore,
    detailSignalSummary.value.normalizedBuyScore,
    detailSignalSummary.value.normalizedSellScore,
  ].some((item) => item !== null)
    || detailSignalSummary.value.degraded !== '-'
    || detailSignalSummary.value.enabledNodeCount !== '-'
    || detailSignalSummary.value.availableNodeCount !== '-'
    || detailSignalSummary.value.activeBuyNodes !== '-'
    || detailSignalSummary.value.activeSellNodes !== '-'
})

const columns = [
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 200 },
  { title: '运行实例 ID', dataIndex: 'run_id', key: 'run_id', width: 120 },
  { title: '策略', dataIndex: 'strategy', key: 'strategy', width: 140 },
  { title: '交易对', dataIndex: 'symbol', key: 'symbol', width: 140 },
  { title: '交易方式', dataIndex: 'trade_mode', key: 'trade_mode', width: 120 },
  { title: '方向', dataIndex: 'side', key: 'side', width: 100 },
  { title: '价格', dataIndex: 'market_price', key: 'market_price', width: 120 },
  { title: '数量', dataIndex: 'requested_amount', key: 'requested_amount', width: 120 },
  { title: '成交价', dataIndex: 'estimated_fill_price', key: 'estimated_fill_price', width: 120 },
  { title: '手续费', dataIndex: 'estimated_fee', key: 'estimated_fee', width: 120 },
  { title: '净盈亏', dataIndex: 'realized_pnl_net', key: 'realized_pnl_net', width: 140 },
  { title: '结果', dataIndex: 'result', key: 'result', width: 120 },
  { title: '触发来源', dataIndex: 'trigger_source', key: 'trigger_source', width: 160 },
  { title: '订单 ID', dataIndex: 'order_id', key: 'order_id', width: 220 },
  { title: '原因', dataIndex: 'result_reason', key: 'result_reason', width: 280 },
  { title: '错误信息', dataIndex: 'error_message', key: 'error_message', width: 300 },
  { title: '操作', key: 'actions', width: 100, fixed: 'right' },
]

const positionColumns = [
  { title: '交易对', dataIndex: 'symbol', key: 'symbol', width: 140 },
  { title: '策略', dataIndex: 'strategy', key: 'strategy', width: 140 },
  { title: '入场时间', dataIndex: 'entry_time', key: 'entry_time', width: 180 },
  { title: '入场价', dataIndex: 'entry_price', key: 'entry_price', width: 120 },
  { title: '数量', dataIndex: 'amount', key: 'amount', width: 120 },
  { title: '止损', dataIndex: 'stop_loss', key: 'stop_loss', width: 120 },
  { title: '初始止损', dataIndex: 'initial_stop_loss', key: 'initial_stop_loss', width: 120 },
  { title: '追踪止损', dataIndex: 'trailing_stop_price', key: 'trailing_stop_price', width: 120 },
  { title: '最高价', dataIndex: 'highest_price', key: 'highest_price', width: 120 },
  { title: '最高收盘价', dataIndex: 'highest_close', key: 'highest_close', width: 140 },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 180 },
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

function syncRunIdFromRoute() {
  const rawRunId = route.query.runId
  const nextRunId = typeof rawRunId === 'string' ? Number(rawRunId) : Number(rawRunId?.[0])
  filters.runId = Number.isInteger(nextRunId) && nextRunId > 0 ? nextRunId : undefined
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
    runId: filters.runId,
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

function formatRate(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }
  return `${(Number(value) * 100).toLocaleString('zh-CN', { maximumFractionDigits: 4 })}%`
}

function formatJson(value: unknown) {
  if (value === null || value === undefined) {
    return '-'
  }
  if (typeof value === 'string') {
    return value.trim() || '-'
  }
  if (Array.isArray(value)) {
    return value.length ? JSON.stringify(value, null, 2) : '[]'
  }
  if (typeof value === 'object') {
    return Object.keys(value as Record<string, unknown>).length ? JSON.stringify(value, null, 2) : '{}'
  }
  return String(value)
}

function toOptionalNumber(value: unknown) {
  return typeof value === 'number' ? value : null
}

function toDisplayCount(value: unknown) {
  return typeof value === 'number' ? String(value) : '-'
}

function formatNameList(value: unknown) {
  if (!Array.isArray(value)) {
    return '-'
  }
  const items = value.map((item) => String(item || '').trim()).filter(Boolean)
  return items.length ? items.join('、') : '-'
}

function normalizeSignalNode(value: unknown): SignalNodeItem | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }
  const item = value as Record<string, unknown>
  return {
    name: String(item.name || '-'),
    available: Boolean(item.available),
    bias: String(item.bias || 'hold'),
    weight: typeof item.weight === 'number' ? item.weight : null,
    score: typeof item.score === 'number' ? item.score : null,
    confidence: typeof item.confidence === 'number' ? item.confidence : null,
    reason: String(item.reason || ''),
  }
}

function sideLabel(value: string | null | undefined) {
  return sideOptions.find((item) => item.value === value)?.label || value || '-'
}

function resultLabel(value: string | null | undefined) {
  return resultOptions.find((item) => item.value === value)?.label || value || '-'
}

function resolveTradeMode(record: Pick<TradeLogItem, 'trade_mode' | 'sandbox'> | null | undefined): TradeMode {
  if (record?.trade_mode) {
    return record.trade_mode
  }
  return record?.sandbox ? 'sandbox' : 'live'
}

function tradeModeLabel(value: TradeMode | null | undefined) {
  if (value === 'live') {
    return '真实交易'
  }
  if (value === 'sandbox') {
    return '沙盒交易'
  }
  if (value === 'paper') {
    return '纸上交易'
  }
  return value || '-'
}

function triggerSourceLabel(value: string | null | undefined) {
  if (value === 'strategy_signal') {
    return '策略信号'
  }
  if (value === 'stop_loss_trigger') {
    return '止损触发'
  }
  return value || '-'
}

function signalBiasLabel(value: string | null | undefined) {
  if (value === 'buy') {
    return '偏多'
  }
  if (value === 'sell') {
    return '偏空'
  }
  if (value === 'hold') {
    return '中性'
  }
  return value || '-'
}

function signalBiasTagColor(value: string | null | undefined) {
  if (value === 'buy') {
    return 'green'
  }
  if (value === 'sell') {
    return 'volcano'
  }
  if (value === 'hold') {
    return 'default'
  }
  return 'default'
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

function tradeModeTagColor(value: TradeMode | null | undefined) {
  if (value === 'live') {
    return 'red'
  }
  if (value === 'sandbox') {
    return 'gold'
  }
  if (value === 'paper') {
    return 'blue'
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
  const [strategyDefinitions, settings] = await Promise.all([fetchStrategyDefinitions(), fetchSystemSettings()])
  definitions.value = strategyDefinitions
  symbolOptions.value = Array.from(new Set(settings.editable.supportedSymbols.map((item) => item.trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b))
}

async function loadPositions() {
  positions.value = await fetchPositions()
  drawerOpen.value = true
}

function openDetail(record: TradeLogItem) {
  detailRecord.value = record
  detailOpen.value = true
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
  filters.runId = undefined
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
  () => route.query.runId,
  () => {
    syncRunIdFromRoute()
    offset.value = 0
    pagination.current = 1
    loadLogs()
  },
)

onMounted(async () => {
  syncRunIdFromRoute()
  await loadFilterOptions()
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
.filter-item :deep(.ant-input-number) {
  width: 100%;
}

.cell-text {
  white-space: normal;
  word-break: break-word;
}

.detail-json {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
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
