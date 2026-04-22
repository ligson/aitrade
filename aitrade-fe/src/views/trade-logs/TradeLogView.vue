<template>
  <a-card title="交易日志查询">
    <a-space direction="vertical" style="width: 100%">
      <a-form layout="inline">
        <a-form-item label="策略"><a-input v-model:value="filters.strategy" /></a-form-item>
        <a-form-item label="方向"><a-input v-model:value="filters.side" /></a-form-item>
        <a-form-item label="结果"><a-input v-model:value="filters.result" /></a-form-item>
        <a-form-item label="交易对"><a-input v-model:value="filters.symbol" /></a-form-item>
        <a-form-item label="开始时间"><a-input v-model:value="filters.createdFrom" placeholder="ISO 时间" /></a-form-item>
        <a-form-item label="结束时间"><a-input v-model:value="filters.createdTo" placeholder="ISO 时间" /></a-form-item>
        <a-form-item><a-button type="primary" @click="loadLogs">查询</a-button></a-form-item>
        <a-form-item><a-button @click="loadPositions">查看当前持仓</a-button></a-form-item>
      </a-form>
      <a-table :data-source="rows" :columns="columns" row-key="id" :loading="loading" :pagination="pagination" @change="handleTableChange" />
    </a-space>
    <a-drawer v-model:open="drawerOpen" title="当前持仓" width="720">
      <a-table :data-source="positions" :columns="positionColumns" row-key="symbol" :pagination="false" />
    </a-drawer>
  </a-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { fetchPositions, pageTradeLogs } from '@/api/tradeLogs'
import type { PositionItem, TradeLogItem } from '@/types/tradeLog'

const loading = ref(false)
const drawerOpen = ref(false)
const rows = ref<TradeLogItem[]>([])
const positions = ref<PositionItem[]>([])
const total = ref(0)
const offset = ref(0)
const size = ref(10)

const filters = reactive({
  strategy: '',
  side: '',
  result: '',
  symbol: '',
  createdFrom: '',
  createdTo: '',
})

const columns = [
  { title: '时间', dataIndex: 'created_at', key: 'created_at' },
  { title: '策略', dataIndex: 'strategy', key: 'strategy' },
  { title: '交易对', dataIndex: 'symbol', key: 'symbol' },
  { title: '方向', dataIndex: 'side', key: 'side' },
  { title: '价格', dataIndex: 'market_price', key: 'market_price' },
  { title: '数量', dataIndex: 'requested_amount', key: 'requested_amount' },
  { title: '结果', dataIndex: 'result', key: 'result' },
  { title: '原因', dataIndex: 'result_reason', key: 'result_reason' },
]

const positionColumns = [
  { title: '交易对', dataIndex: 'symbol', key: 'symbol' },
  { title: '策略', dataIndex: 'strategy', key: 'strategy' },
  { title: '入场价', dataIndex: 'entry_price', key: 'entry_price' },
  { title: '数量', dataIndex: 'amount', key: 'amount' },
  { title: '止损', dataIndex: 'stop_loss', key: 'stop_loss' },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at' },
]

const pagination = {
  current: 1,
  pageSize: size.value,
  total: total.value,
  showSizeChanger: false,
}

async function loadLogs() {
  loading.value = true
  try {
    const data = await pageTradeLogs({ offset: offset.value, size: size.value, ...filters })
    rows.value = data.data
    total.value = data.total
    pagination.total = data.total
    pagination.current = Math.floor(offset.value / size.value) + 1
  } finally {
    loading.value = false
  }
}

async function loadPositions() {
  positions.value = await fetchPositions()
  drawerOpen.value = true
}

function handleTableChange(page: { current?: number }) {
  offset.value = ((page.current || 1) - 1) * size.value
  loadLogs()
}

onMounted(loadLogs)
</script>
