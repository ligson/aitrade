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
              <a-popconfirm title="确认按当前所选页面配置启动交易任务吗？" ok-text="启动" cancel-text="取消" @confirm="handleStartTradeTask">
                <a-button type="primary" :loading="startLoading" :disabled="!tradeTask.canStart || !selectedProfileId">开始运行</a-button>
              </a-popconfirm>
              <a-popconfirm title="确认停止当前交易任务吗？" ok-text="停止" cancel-text="取消" @confirm="handleStopTradeTask">
                <a-button danger :loading="stopLoading" :disabled="!tradeTask.canStop || tradeTask.status === 'stop_requested'">停止运行</a-button>
              </a-popconfirm>
              <a-button :loading="tradeTaskLoading" @click="reloadAll">刷新状态</a-button>
              <a-button @click="goToProfiles">返回配置页</a-button>
              <a-button @click="goToTaskLogs">查看任务日志</a-button>
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
            <a-descriptions :column="2" bordered size="small">
              <a-descriptions-item label="配置名称">{{ tradeTask.currentRun.profileName }}</a-descriptions-item>
              <a-descriptions-item label="策略配置 ID">{{ tradeTask.currentRun.strategyProfileId ?? '-' }}</a-descriptions-item>
              <a-descriptions-item label="交易对">{{ tradeTask.currentRun.symbol }}</a-descriptions-item>
              <a-descriptions-item label="周期">{{ tradeTask.currentRun.timeframe }}</a-descriptions-item>
              <a-descriptions-item label="模式">{{ tradeTask.currentRun.sandboxTrade ? '沙盒' : '实盘' }}</a-descriptions-item>
              <a-descriptions-item label="K线数量">{{ tradeTask.currentRun.tradeLimit }}</a-descriptions-item>
              <a-descriptions-item label="策略类型">{{ strategyTypeLabel(tradeTask.currentRun.strategyType) }}</a-descriptions-item>
              <a-descriptions-item label="创建人">{{ tradeTask.currentRun.createdBy }}</a-descriptions-item>
            </a-descriptions>
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
import type { TradeTaskProfile, TradeTaskStatus } from '@/types/system'

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
const enabledProfiles = computed(() => profiles.value.filter((item) => item.enabled))

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

function goToProfiles() {
  router.push('/trade-task-profiles')
}

function goToTaskLogs() {
  router.push('/trade-task-logs')
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
</style>
