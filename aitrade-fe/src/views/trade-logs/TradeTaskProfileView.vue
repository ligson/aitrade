<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="这里维护的是可启动的交易任务配置。"
        description="任务级参数通过页面配置并入库保存；启动时会生成运行快照，后续修改不会影响已运行任务。"
      />

      <a-card size="small" title="交易任务配置">
        <a-space direction="vertical" size="middle" style="width: 100%">
          <div class="section-toolbar">
            <a-button type="primary" @click="openCreate">新增配置</a-button>
          </div>

          <a-table :data-source="profiles" :columns="profileColumns" row-key="id" :pagination="false" :scroll="{ x: 'max-content' }">
            <template #bodyCell="{ column, record, text }">
              <template v-if="column.key === 'enabled'">
                <a-tag :color="record.enabled ? 'green' : 'default'">{{ record.enabled ? '启用' : '停用' }}</a-tag>
              </template>
              <template v-else-if="column.key === 'sandboxTrade'">
                <a-tag :color="record.sandboxTrade ? 'gold' : 'blue'">{{ record.sandboxTrade ? '沙盒' : '实盘' }}</a-tag>
              </template>
              <template v-else-if="column.key === 'updatedAt'">
                {{ formatDateTime(text) }}
              </template>
              <template v-else-if="column.key === 'actions'">
                <a-space size="small" wrap>
                  <a-button type="link" @click="goToControl(record.id)">去控制页</a-button>
                  <a-button type="link" @click="openDetail(record)">详情</a-button>
                  <a-button type="link" @click="openEdit(record)">编辑</a-button>
                  <a-popconfirm title="确认删除这套交易任务配置吗？" ok-text="删除" cancel-text="取消" @confirm="removeProfile(record.id)">
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
    </a-space>

    <a-drawer v-model:open="detailOpen" title="交易任务配置详情" width="560">
      <template v-if="detailProfile">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="配置名称">{{ detailProfile.name }}</a-descriptions-item>
          <a-descriptions-item label="描述">{{ detailProfile.description || '-' }}</a-descriptions-item>
          <a-descriptions-item label="状态">{{ detailProfile.enabled ? '启用' : '停用' }}</a-descriptions-item>
          <a-descriptions-item label="策略配置">{{ detailProfile.strategyProfileName || '-' }}</a-descriptions-item>
          <a-descriptions-item label="策略类型">{{ strategyTypeLabel(detailProfile.strategyType) }}</a-descriptions-item>
          <a-descriptions-item label="交易对">{{ detailProfile.symbol }}</a-descriptions-item>
          <a-descriptions-item label="周期">{{ detailProfile.timeframe }}</a-descriptions-item>
          <a-descriptions-item label="模式">{{ detailProfile.sandboxTrade ? '沙盒' : '实盘' }}</a-descriptions-item>
          <a-descriptions-item label="K线数量">{{ detailProfile.tradeLimit }}</a-descriptions-item>
          <a-descriptions-item label="Runner">{{ detailProfile.runnerName }}</a-descriptions-item>
          <a-descriptions-item label="创建时间">{{ formatDateTime(detailProfile.createdAt) }}</a-descriptions-item>
          <a-descriptions-item label="更新时间">{{ formatDateTime(detailProfile.updatedAt) }}</a-descriptions-item>
        </a-descriptions>
      </template>
    </a-drawer>

    <a-drawer v-model:open="editOpen" :title="form.id ? '编辑交易任务配置' : '新增交易任务配置'" width="560">
      <a-form layout="vertical">
        <a-form-item label="配置名称">
          <a-input v-model:value="form.name" />
        </a-form-item>
        <a-form-item label="描述">
          <a-input v-model:value="form.description" />
        </a-form-item>
        <a-form-item label="策略配置">
          <a-select v-model:value="form.strategyProfileId" show-search :filter-option="filterSelectOption">
            <a-select-option v-for="item in enabledStrategyProfiles" :key="item.id" :value="item.id">
              {{ item.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <div class="form-grid">
          <a-form-item label="交易对">
            <a-input v-model:value="form.symbol" placeholder="如 BTC/USDT" />
          </a-form-item>
          <a-form-item label="周期">
            <a-select v-model:value="form.timeframe">
              <a-select-option v-for="item in supportedTimeframes" :key="item" :value="item">
                {{ item }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="K线数量">
            <a-input-number v-model:value="form.tradeLimit" :min="1" style="width: 100%" />
          </a-form-item>
          <a-form-item label="Runner">
            <a-input v-model:value="form.runnerName" />
          </a-form-item>
        </div>
        <a-form-item label="启用">
          <a-switch v-model:checked="form.enabled" />
        </a-form-item>
        <a-form-item label="沙盒交易">
          <a-switch v-model:checked="form.sandboxTrade" />
        </a-form-item>
      </a-form>
      <template #footer>
        <a-space>
          <a-button @click="closeEdit">取消</a-button>
          <a-button type="primary" @click="submitForm">保存</a-button>
        </a-space>
      </template>
    </a-drawer>
  </a-card>
</template>

<script setup lang="ts">
import dayjs from 'dayjs'
import { message } from 'ant-design-vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { fetchStrategyProfiles } from '@/api/strategies'
import { deleteTradeTaskProfile, fetchSystemSettings, fetchTradeTaskProfiles, saveTradeTaskProfile } from '@/api/system'
import type { StrategyProfile } from '@/types/strategy'
import type { TradeTaskProfile } from '@/types/system'

const router = useRouter()
const detailOpen = ref(false)
const editOpen = ref(false)
const profiles = ref<TradeTaskProfile[]>([])
const strategyProfiles = ref<StrategyProfile[]>([])
const supportedTimeframes = ref<string[]>([])
const detailProfile = ref<TradeTaskProfile | null>(null)

const form = reactive<{ id?: number; name: string; description: string; enabled: boolean; strategyProfileId?: number; symbol: string; timeframe: string; sandboxTrade: boolean; tradeLimit: number; runnerName: string }>({
  name: '',
  description: '',
  enabled: true,
  strategyProfileId: undefined,
  symbol: 'BTC/USDT',
  timeframe: '15m',
  sandboxTrade: true,
  tradeLimit: 100,
  runnerName: 'default',
})

const profileColumns = [
  { title: '配置名称', dataIndex: 'name', key: 'name', width: 220 },
  { title: '策略配置', dataIndex: 'strategyProfileName', key: 'strategyProfileName', width: 220 },
  { title: '交易对', dataIndex: 'symbol', key: 'symbol', width: 140 },
  { title: '周期', dataIndex: 'timeframe', key: 'timeframe', width: 100 },
  { title: 'K线数量', dataIndex: 'tradeLimit', key: 'tradeLimit', width: 120 },
  { title: '模式', dataIndex: 'sandboxTrade', key: 'sandboxTrade', width: 100 },
  { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 100 },
  { title: '更新时间', dataIndex: 'updatedAt', key: 'updatedAt', width: 180 },
  { title: '操作', key: 'actions', width: 260 },
]

const enabledStrategyProfiles = computed(() => strategyProfiles.value.filter((item) => item.enabled))

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

function strategyTypeLabel(value: string) {
  return strategyProfiles.value.find((item) => item.strategyType === value)?.definition?.displayName || value || '-'
}

function resetForm() {
  form.id = undefined
  form.name = ''
  form.description = ''
  form.enabled = true
  form.strategyProfileId = enabledStrategyProfiles.value[0]?.id
  form.symbol = 'BTC/USDT'
  form.timeframe = supportedTimeframes.value[0] || '15m'
  form.sandboxTrade = true
  form.tradeLimit = 100
  form.runnerName = 'default'
}

function openCreate() {
  resetForm()
  editOpen.value = true
}

function openEdit(profile: TradeTaskProfile) {
  form.id = profile.id
  form.name = profile.name
  form.description = profile.description
  form.enabled = profile.enabled
  form.strategyProfileId = profile.strategyProfileId
  form.symbol = profile.symbol
  form.timeframe = profile.timeframe
  form.sandboxTrade = profile.sandboxTrade
  form.tradeLimit = profile.tradeLimit
  form.runnerName = profile.runnerName
  editOpen.value = true
}

function openDetail(profile: TradeTaskProfile) {
  detailProfile.value = profile
  detailOpen.value = true
}

function closeEdit() {
  editOpen.value = false
}

function goToControl(profileId: number) {
  router.push({ path: '/trade-task-control', query: { profileId: String(profileId) } })
}

async function loadProfiles() {
  profiles.value = await fetchTradeTaskProfiles()
}

async function loadStrategyProfiles() {
  strategyProfiles.value = await fetchStrategyProfiles()
}

async function loadSettings() {
  const data = await fetchSystemSettings()
  supportedTimeframes.value = data.editable.supportedTimeframes
  if (!form.timeframe) {
    form.timeframe = supportedTimeframes.value[0] || '15m'
  }
}

async function submitForm() {
  await saveTradeTaskProfile({
    id: form.id,
    name: form.name,
    description: form.description,
    enabled: form.enabled,
    strategyProfileId: form.strategyProfileId!,
    symbol: form.symbol,
    timeframe: form.timeframe,
    sandboxTrade: form.sandboxTrade,
    tradeLimit: form.tradeLimit,
    runnerName: form.runnerName,
  })
  message.success('交易任务配置已保存')
  editOpen.value = false
  await loadProfiles()
}

async function removeProfile(id: number) {
  await deleteTradeTaskProfile(id)
  message.success('交易任务配置已删除')
  await loadProfiles()
  if (detailProfile.value?.id === id) {
    detailOpen.value = false
    detailProfile.value = null
  }
}

onMounted(async () => {
  await loadStrategyProfiles()
  await loadSettings()
  resetForm()
  await loadProfiles()
})
</script>

<style scoped>
.page-card {
  min-height: 100%;
}

.section-toolbar {
  display: flex;
  justify-content: flex-end;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0 16px;
}

:deep(.ant-table-thead > tr > th) {
  white-space: nowrap;
}
</style>
