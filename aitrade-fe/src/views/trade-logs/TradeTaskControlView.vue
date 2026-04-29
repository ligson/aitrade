<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="这里控制交易任务的启动、停止和运行状态。"
        description="启动时会固定当前所选任务配置生成数据库快照；如需改策略、交易对或周期，请先回到配置页维护。"
      />

      <a-card size="small" title="交易任务控制">
        <a-space direction="vertical" size="middle" style="width: 100%">
          <div class="action-bar">
            <a-space wrap>
              <a-select v-model:value="selectedProfileId" placeholder="请选择启动配置" style="width: 260px" show-search :filter-option="filterSelectOption">
                <a-select-option v-for="item in enabledProfiles" :key="item.id" :value="item.id">
                  {{ item.name }}
                </a-select-option>
              </a-select>
              <a-popconfirm :title="startConfirmTitle" ok-text="启动" cancel-text="取消" @confirm="handleStartTradeTask">
                <a-button type="primary" :loading="startLoading" :disabled="!tradeTask.canStart || !selectedProfileId">开始运行</a-button>
              </a-popconfirm>
              <a-popconfirm title="确认停止当前交易任务吗？" ok-text="停止" cancel-text="取消" @confirm="handleStopTradeTask">
                <a-button danger :loading="stopLoading" :disabled="!tradeTask.canStop || tradeTask.status === 'stop_requested'">停止运行</a-button>
              </a-popconfirm>
              <a-button :loading="tradeTaskLoading" @click="reloadAll">刷新状态</a-button>
              <a-button @click="goToProfiles">返回配置页</a-button>
              <a-button @click="goToTaskLogs">查看任务日志</a-button>
              <a-button :disabled="!tradeTask.runId" @click="goToTradeLogs">查看本次运行交易日志</a-button>
            </a-space>
            <div class="action-tip">任务级参数由页面配置和数据库快照驱动；系统级密钥、代理和持久化配置仍来自后端 config.yaml。</div>
          </div>

          <div class="summary-grid">
            <div class="summary-card">
              <div class="summary-label">当前状态</div>
              <div class="summary-value">
                <a-tag :color="statusColor(tradeTask.status)">{{ statusLabel(tradeTask.status) }}</a-tag>
              </div>
            </div>
            <div class="summary-card">
              <div class="summary-label">当前配置</div>
              <div class="summary-value summary-text">{{ tradeTask.profileName || '-' }}</div>
            </div>
            <div class="summary-card">
              <div class="summary-label">最近心跳</div>
              <div class="summary-value summary-text">{{ formatDateTime(tradeTask.lastHeartbeatAt) }}</div>
            </div>
            <div class="summary-card">
              <div class="summary-label">下次运行</div>
              <div class="summary-value summary-text">{{ formatDateTime(tradeTask.nextRunAt) }}</div>
            </div>
          </div>

          <a-descriptions :column="2" bordered size="small" :loading="tradeTaskLoading">
            <a-descriptions-item label="当前状态">
              <a-tag :color="statusColor(tradeTask.status)">{{ statusLabel(tradeTask.status) }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="运行中">{{ tradeTask.isRunning ? '是' : '否' }}</a-descriptions-item>
            <a-descriptions-item label="当前配置">{{ tradeTask.profileName || '-' }}</a-descriptions-item>
            <a-descriptions-item label="运行实例 ID">{{ tradeTask.runId ?? '-' }}</a-descriptions-item>
            <a-descriptions-item label="交易对">{{ tradeTask.symbol || '-' }}</a-descriptions-item>
            <a-descriptions-item label="策略类型">{{ strategyTypeLabel(tradeTask.strategyType) }}</a-descriptions-item>
            <a-descriptions-item label="周期">{{ tradeTask.timeframe || '-' }}</a-descriptions-item>
            <a-descriptions-item label="启动人">{{ tradeTask.startedBy || '-' }}</a-descriptions-item>
            <a-descriptions-item label="启动时间">{{ formatDateTime(tradeTask.startedAt) }}</a-descriptions-item>
            <a-descriptions-item label="停止时间">{{ formatDateTime(tradeTask.stoppedAt) }}</a-descriptions-item>
            <a-descriptions-item label="停止请求时间">{{ formatDateTime(tradeTask.stopRequestedAt) }}</a-descriptions-item>
            <a-descriptions-item label="最近心跳">{{ formatDateTime(tradeTask.lastHeartbeatAt) }}</a-descriptions-item>
            <a-descriptions-item label="最近周期开始">{{ formatDateTime(tradeTask.lastCycleStartedAt) }}</a-descriptions-item>
            <a-descriptions-item label="最近周期完成">{{ formatDateTime(tradeTask.lastCycleFinishedAt) }}</a-descriptions-item>
            <a-descriptions-item label="下次运行时间">{{ formatDateTime(tradeTask.nextRunAt) }}</a-descriptions-item>
            <a-descriptions-item label="状态更新时间">{{ formatDateTime(tradeTask.updatedAt) }}</a-descriptions-item>
          </a-descriptions>

          <a-card v-if="tradeTask.currentRun" size="small" title="当前运行快照">
            <a-space direction="vertical" size="middle" style="width: 100%">
              <a-descriptions :column="2" bordered size="small">
                <a-descriptions-item label="配置名称">{{ tradeTask.currentRun.profileName }}</a-descriptions-item>
                <a-descriptions-item label="策略配置 ID">{{ tradeTask.currentRun.strategyProfileId ?? '-' }}</a-descriptions-item>
                <a-descriptions-item label="交易对">{{ tradeTask.currentRun.symbol }}</a-descriptions-item>
                <a-descriptions-item label="周期">{{ tradeTask.currentRun.timeframe }}</a-descriptions-item>
                <a-descriptions-item label="模式">{{ tradeModeLabel(resolveTradeMode(tradeTask.currentRun)) }}</a-descriptions-item>
                <a-descriptions-item label="K线数量">{{ tradeTask.currentRun.tradeLimit }}</a-descriptions-item>
                <a-descriptions-item label="手续费率">{{ formatRate(tradeTask.currentRun.feeRate) }}</a-descriptions-item>
                <a-descriptions-item label="滑点率">{{ formatRate(tradeTask.currentRun.slippageRate) }}</a-descriptions-item>
                <a-descriptions-item label="单日亏损停机">{{ tradeTask.currentRun.dailyLossStopEnabled ? '已启用' : '关闭' }}</a-descriptions-item>
                <a-descriptions-item label="单日亏损阈值">{{ formatNumber(tradeTask.currentRun.dailyLossStopThreshold) }}</a-descriptions-item>
                <a-descriptions-item label="策略类型">{{ strategyTypeLabel(tradeTask.currentRun.strategyType) }}</a-descriptions-item>
                <a-descriptions-item label="创建人">{{ tradeTask.currentRun.createdBy }}</a-descriptions-item>
              </a-descriptions>

              <a-alert
                v-if="currentRunSignalSourceSnapshots.length"
                type="info"
                show-icon
                message="这里展示启动时冻结的信号源快照。"
                description="当前运行中的任务会持续使用这些参数；后续再改信号源配置或融合策略，不会自动影响本次运行。"
              />
              <a-table
                v-if="currentRunSignalSourceSnapshots.length"
                :data-source="currentRunSignalSourceSnapshots"
                :columns="signalSourceSnapshotColumns"
                :row-key="signalSourceSnapshotRowKey"
                :pagination="false"
                size="small"
                :scroll="{ x: 'max-content' }"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'sourceType'">
                    {{ signalSourceTypeLabel(record.sourceType) }}
                  </template>
                  <template v-else-if="column.key === 'runtimeSupported'">
                    <a-tag :color="record.sourceType === 'indicator' || record.sourceType === 'trade_flow' ? 'blue' : 'default'">
                      {{ record.sourceType === 'indicator' || record.sourceType === 'trade_flow' ? '已接入运行时' : '预留' }}
                    </a-tag>
                  </template>
                  <template v-else-if="column.key === 'required'">
                    <a-tag :color="record.required ? 'orange' : 'default'">{{ record.required ? '必需' : '可选' }}</a-tag>
                  </template>
                  <template v-else-if="column.key === 'weight'">
                    {{ formatNumber(record.weight) }}
                  </template>
                  <template v-else-if="column.key === 'description'">
                    <div class="cell-text">{{ record.description || '-' }}</div>
                  </template>
                  <template v-else-if="column.key === 'thresholds' || column.key === 'params'">
                    <pre class="snapshot-json">{{ formatJsonLike(record[column.key]) }}</pre>
                  </template>
                </template>
              </a-table>
            </a-space>
          </a-card>

          <a-alert v-if="tradeTask.lastError" type="error" show-icon :message="tradeTask.lastError" />
        </a-space>
      </a-card>
    </a-space>
  </a-card>
</template>

<script setup lang="ts">
import dayjs from 'dayjs'
import { message } from 'ant-design-vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchStrategyProfiles } from '@/api/strategies'
import { fetchTradeTaskProfiles, fetchTradeTaskStatus, startTradeTask, stopTradeTask } from '@/api/system'
import type { StrategyProfile } from '@/types/strategy'
import type { TradeMode, TradeTaskProfile, TradeTaskStatus } from '@/types/system'

type SignalSourceSnapshotItem = {
  signalSourceProfileId: number | null
  sourceType: string
  name: string
  required: boolean
  weight: number | null
  thresholds: Record<string, unknown>
  params: Record<string, unknown>
  description: string
}

const route = useRoute()
const router = useRouter()
const tradeTaskLoading = ref(false)
const startLoading = ref(false)
const stopLoading = ref(false)
const pollTimer = ref<number | null>(null)
const profiles = ref<TradeTaskProfile[]>([])
const strategyProfiles = ref<StrategyProfile[]>([])
const selectedProfileId = ref<number | undefined>()

const tradeTask = reactive<TradeTaskStatus>({
  runnerName: 'default',
  runId: null,
  tradeTaskProfileId: null,
  profileName: '',
  status: 'stopped',
  isRunning: false,
  canStart: true,
  canStop: false,
  startedAt: null,
  stoppedAt: null,
  stopRequestedAt: null,
  lastHeartbeatAt: null,
  lastCycleStartedAt: null,
  lastCycleFinishedAt: null,
  nextRunAt: null,
  lastError: '',
  startedBy: '',
  symbol: '',
  timeframe: '',
  timeframeMinutes: null,
  strategyType: '',
  updatedAt: null,
  recentLogs: [],
  currentRun: null,
})

const activeStatuses = new Set(['starting', 'running', 'stop_requested'])
const signalSourceSnapshotColumns = [
  { title: '名称', dataIndex: 'name', key: 'name', width: 180 },
  { title: '类型', dataIndex: 'sourceType', key: 'sourceType', width: 140 },
  { title: '运行时', key: 'runtimeSupported', width: 120 },
  { title: '必需性', dataIndex: 'required', key: 'required', width: 100 },
  { title: '权重', dataIndex: 'weight', key: 'weight', width: 100 },
  { title: '节点阈值', dataIndex: 'thresholds', key: 'thresholds', width: 260 },
  { title: '冻结参数', dataIndex: 'params', key: 'params', width: 340 },
  { title: '描述', dataIndex: 'description', key: 'description', width: 260 },
]
const enabledProfiles = computed(() => profiles.value.filter((item) => item.enabled))
const selectedProfile = computed(() => enabledProfiles.value.find((item) => item.id === selectedProfileId.value) || null)
const currentRunSignalSourceSnapshots = computed<SignalSourceSnapshotItem[]>(() => {
  const snapshot = tradeTask.currentRun?.snapshot
  const rawItems = Array.isArray(snapshot?.signalSourceSnapshots) ? snapshot.signalSourceSnapshots : []
  return rawItems
    .map((item) => normalizeSignalSourceSnapshot(item))
    .filter((item): item is SignalSourceSnapshotItem => item !== null)
})
const startConfirmTitle = computed(() => {
  const tradeMode = resolveTradeMode(selectedProfile.value)
  const modeLabel = tradeModeLabel(tradeMode)
  if (tradeMode === 'live') {
    return `确认启动“${selectedProfile.value?.name || '当前配置'}”吗？当前为${modeLabel}，会使用真实行情并真实下单。`
  }
  if (tradeMode === 'paper') {
    return `确认启动“${selectedProfile.value?.name || '当前配置'}”吗？当前为${modeLabel}，会使用真实行情但不会真实下单。`
  }
  return `确认启动“${selectedProfile.value?.name || '当前配置'}”吗？当前为${modeLabel}，会使用沙盒行情并在沙盒环境下单。`
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

function formatJsonLike(value: unknown) {
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

function signalSourceTypeLabel(value: string) {
  if (value === 'trade_flow') {
    return 'trade_flow'
  }
  if (value === 'indicator') {
    return 'indicator'
  }
  return value || '-'
}

function signalSourceSnapshotRowKey(record: SignalSourceSnapshotItem) {
  return `${record.signalSourceProfileId || record.name}-${record.sourceType}`
}

function normalizeSignalSourceSnapshot(value: unknown): SignalSourceSnapshotItem | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }
  const item = value as Record<string, unknown>
  return {
    signalSourceProfileId: typeof item.signalSourceProfileId === 'number' ? item.signalSourceProfileId : null,
    sourceType: String(item.sourceType || ''),
    name: String(item.name || '-'),
    required: Boolean(item.required),
    weight: typeof item.weight === 'number' ? item.weight : null,
    thresholds: item.thresholds && typeof item.thresholds === 'object' && !Array.isArray(item.thresholds) ? (item.thresholds as Record<string, unknown>) : {},
    params: item.params && typeof item.params === 'object' && !Array.isArray(item.params) ? (item.params as Record<string, unknown>) : {},
    description: String(item.description || ''),
  }
}

function statusLabel(value: string) {
  if (value === 'starting') {
    return '启动中'
  }
  if (value === 'running') {
    return '运行中'
  }
  if (value === 'stop_requested') {
    return '停止中'
  }
  if (value === 'stopped') {
    return '已停止'
  }
  if (value === 'failed') {
    return '失败'
  }
  if (value === 'config_error') {
    return '配置错误'
  }
  if (value === 'stale') {
    return '状态残留'
  }
  return value || '-'
}

function statusColor(value: string) {
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

function strategyTypeLabel(value: string) {
  return strategyProfiles.value.find((item) => item.strategyType === value)?.definition?.displayName || value || '-'
}

function resolveTradeMode(payload: Pick<TradeTaskProfile, 'tradeMode' | 'sandboxTrade'> | Pick<NonNullable<TradeTaskStatus['currentRun']>, 'tradeMode' | 'sandboxTrade'> | null | undefined): TradeMode {
  if (payload?.tradeMode) {
    return payload.tradeMode
  }
  return payload?.sandboxTrade === false ? 'live' : 'sandbox'
}

function tradeModeLabel(value: TradeMode) {
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

function goToProfiles() {
  router.push('/trade-task-profiles')
}

function goToTaskLogs() {
  router.push('/trade-task-logs')
}

function goToTradeLogs() {
  if (!tradeTask.runId) {
    return
  }
  router.push({ path: '/trade-logs', query: { runId: String(tradeTask.runId) } })
}

function ensurePolling() {
  if (!activeStatuses.has(tradeTask.status)) {
    stopPolling()
    return
  }
  if (pollTimer.value !== null) {
    return
  }
  pollTimer.value = window.setInterval(async () => {
    await loadTradeTaskStatus()
  }, 4000)
}

function stopPolling() {
  if (pollTimer.value !== null) {
    window.clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

function syncSelectedProfileFromRoute() {
  const rawProfileId = route.query.profileId
  const queryProfileId = typeof rawProfileId === 'string' ? Number(rawProfileId) : Number(rawProfileId?.[0])
  const matchedProfile = Number.isFinite(queryProfileId) ? enabledProfiles.value.find((item) => item.id === queryProfileId) : undefined
  if (matchedProfile) {
    selectedProfileId.value = matchedProfile.id
    return
  }
  if (!selectedProfileId.value || !enabledProfiles.value.some((item) => item.id === selectedProfileId.value)) {
    selectedProfileId.value = enabledProfiles.value[0]?.id
  }
}

async function loadProfiles() {
  profiles.value = await fetchTradeTaskProfiles()
  syncSelectedProfileFromRoute()
}

async function loadStrategyProfiles() {
  strategyProfiles.value = await fetchStrategyProfiles()
}

async function loadTradeTaskStatus() {
  tradeTaskLoading.value = true
  try {
    const data = await fetchTradeTaskStatus()
    Object.assign(tradeTask, data)
    ensurePolling()
  } finally {
    tradeTaskLoading.value = false
  }
}

async function handleStartTradeTask() {
  if (!selectedProfileId.value) {
    message.warning('请先选择一套启用中的交易任务配置')
    return
  }
  startLoading.value = true
  try {
    const data = await startTradeTask({ tradeTaskProfileId: selectedProfileId.value })
    Object.assign(tradeTask, data)
    message.success(data.status === 'running' ? '交易任务已启动' : '交易任务正在启动')
    ensurePolling()
  } finally {
    startLoading.value = false
  }
}

async function handleStopTradeTask() {
  stopLoading.value = true
  try {
    const data = await stopTradeTask()
    Object.assign(tradeTask, data)
    message.success(data.status === 'stop_requested' ? '停止请求已发送' : '交易任务已停止')
    ensurePolling()
  } finally {
    stopLoading.value = false
  }
}

async function reloadAll() {
  await Promise.all([loadProfiles(), loadTradeTaskStatus()])
}

watch(
  () => route.query.profileId,
  () => {
    syncSelectedProfileFromRoute()
  },
)

onMounted(async () => {
  await Promise.all([loadStrategyProfiles(), loadProfiles()])
  await loadTradeTaskStatus()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped>
.page-card {
  min-height: 100%;
}

.action-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  align-items: center;
  justify-content: space-between;
}

.action-tip {
  color: rgba(0, 0, 0, 0.45);
  font-size: 13px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.summary-card {
  padding: 16px;
  border: 1px solid #f0f0f0;
  border-radius: 10px;
  background: #fafcff;
}

.summary-label {
  margin-bottom: 8px;
  color: rgba(0, 0, 0, 0.45);
  font-size: 13px;
}

.summary-value {
  min-height: 24px;
  display: flex;
  align-items: center;
}

.summary-text {
  color: rgba(0, 0, 0, 0.88);
  font-weight: 500;
  word-break: break-word;
}

.cell-text {
  white-space: normal;
  word-break: break-word;
}

.snapshot-json {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
}

:deep(.ant-table-thead > tr > th) {
  white-space: nowrap;
}
</style>
