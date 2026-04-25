<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-card size="small" title="交易任务控制">
        <a-space direction="vertical" size="middle" style="width: 100%">
          <a-space wrap>
            <a-popconfirm title="确认按当前 config.yaml 配置启动交易任务吗？" ok-text="启动" cancel-text="取消" @confirm="handleStartTradeTask">
              <a-button type="primary" :loading="startLoading" :disabled="!tradeTask.canStart">开始运行</a-button>
            </a-popconfirm>
            <a-popconfirm title="确认停止当前交易任务吗？" ok-text="停止" cancel-text="取消" @confirm="handleStopTradeTask">
              <a-button danger :loading="stopLoading" :disabled="!tradeTask.canStop || tradeTask.status === 'stop_requested'">停止运行</a-button>
            </a-popconfirm>
            <a-button :loading="tradeTaskLoading" @click="loadTradeTaskStatus">刷新状态</a-button>
          </a-space>

          <a-descriptions :column="2" bordered size="small" :loading="tradeTaskLoading">
            <a-descriptions-item label="当前状态">
              <a-tag :color="statusColor(tradeTask.status)">{{ statusLabel(tradeTask.status) }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="运行中">{{ tradeTask.isRunning ? '是' : '否' }}</a-descriptions-item>
            <a-descriptions-item label="交易对">{{ tradeTask.symbol || '-' }}</a-descriptions-item>
            <a-descriptions-item label="策略类型">{{ tradeTask.strategyType || '-' }}</a-descriptions-item>
            <a-descriptions-item label="周期(分钟)">{{ tradeTask.timeframeMinutes ?? '-' }}</a-descriptions-item>
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

          <a-alert v-if="tradeTask.lastError" type="error" show-icon :message="tradeTask.lastError" />
          <a-alert
            type="info"
            show-icon
            message="交易任务运行参数来自后端 config.yaml；修改配置后需重新开始任务才会生效。Web 服务启动后不会自动运行交易任务。"
          />
        </a-space>
      </a-card>

      <a-card size="small" title="最近运行日志">
        <a-table
          size="small"
          :columns="logColumns"
          :data-source="tradeTask.recentLogs"
          :pagination="false"
          :scroll="{ x: 960 }"
          row-key="id"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
            </template>
            <template v-else-if="column.key === 'createdAt'">
              {{ formatDateTime(record.createdAt) }}
            </template>
            <template v-else-if="column.key === 'detail'">
              <span class="log-detail">{{ formatLogDetail(record.detail) }}</span>
            </template>
          </template>
          <template #emptyText>暂无运行日志</template>
        </a-table>
      </a-card>
    </a-space>
  </a-card>
</template>

<script setup lang="ts">
import dayjs from 'dayjs'
import { message } from 'ant-design-vue'
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import { fetchTradeTaskStatus, startTradeTask, stopTradeTask } from '@/api/system'
import type { TradeTaskLogItem, TradeTaskStatus } from '@/types/system'

const tradeTaskLoading = ref(false)
const startLoading = ref(false)
const stopLoading = ref(false)
const pollTimer = ref<number | null>(null)

const tradeTask = reactive<TradeTaskStatus>({
  runnerName: 'default',
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
  timeframeMinutes: null,
  strategyType: '',
  updatedAt: null,
  recentLogs: [],
})

const activeStatuses = new Set(['starting', 'running', 'stop_requested'])
const logColumns = [
  {
    title: '时间',
    dataIndex: 'createdAt',
    key: 'createdAt',
    width: 180,
  },
  {
    title: '事件',
    dataIndex: 'eventType',
    key: 'eventType',
    width: 140,
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    width: 120,
  },
  {
    title: '说明',
    dataIndex: 'message',
    key: 'message',
    width: 220,
  },
  {
    title: '详情',
    dataIndex: 'detail',
    key: 'detail',
  },
]

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

function formatLogDetail(detail: TradeTaskLogItem['detail']) {
  const entries = Object.entries(detail ?? {})
  if (!entries.length) {
    return '-'
  }
  return entries
    .map(([key, value]) => `${key}=${typeof value === 'string' ? value : JSON.stringify(value)}`)
    .join('；')
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
  startLoading.value = true
  try {
    const data = await startTradeTask()
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

onMounted(loadTradeTaskStatus)

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped>
.page-card {
  min-height: 100%;
}

.log-detail {
  white-space: normal;
  word-break: break-all;
}
</style>
