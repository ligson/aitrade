<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="这里维护的是可启动的交易任务配置。"
        description="任务级参数通过页面配置并入库保存；启动时会生成运行快照，后续修改不会影响已运行任务。系统会为每条任务配置自动分配独立 runner，当前版本暂不支持同一交易对并发运行。"
      />
      <a-alert
        v-if="invalidStrategyProfileCount > 0"
        type="warning"
        show-icon
        :message="`检测到 ${invalidStrategyProfileCount} 条异常策略配置，已自动跳过，不影响当前页面可用配置加载。`"
        description="如需清理，请前往策略配置页删除或修复异常策略。"
      >
        <template #action>
          <a-button size="small" @click="goToStrategies">去策略配置清理</a-button>
        </template>
      </a-alert>

      <a-card size="small" title="交易任务配置">
        <a-space direction="vertical" size="middle" style="width: 100%">
          <div class="section-toolbar">
            <a-button type="primary" @click="openCreate">新增配置</a-button>
          </div>

          <a-table :data-source="profiles" :columns="profileColumns" row-key="id" :pagination="false" :scroll="{ x: 'max-content' }">
            <template #bodyCell="{ column, record, text }">
              <template v-if="column.key === 'strategyProfileName'">
                <div>{{ record.missingStrategyProfile ? '关联策略异常或已删除' : (record.strategyProfileName || '-') }}</div>
                <div v-if="record.missingStrategyProfile" class="cell-meta cell-meta-warning">请前往策略配置页清理异常策略后，再更新这条任务配置。</div>
                <div v-else-if="record.strategyProfile?.fusionSummary" class="cell-meta">{{ formatFusionSummary(record.strategyProfile.fusionSummary) }}</div>
              </template>
              <template v-else-if="column.key === 'enabled'">
                <a-tag :color="record.enabled ? 'green' : 'default'">{{ record.enabled ? '启用' : '停用' }}</a-tag>
              </template>
              <template v-else-if="column.key === 'tradeMode'">
                <a-tag :color="tradeModeTagColor(resolveProfileTradeMode(record))">{{ tradeModeLabel(resolveProfileTradeMode(record)) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'updatedAt'">
                {{ formatDateTime(text) }}
              </template>
              <template v-else-if="column.key === 'feeRate' || column.key === 'slippageRate'">
                {{ formatRate(text) }}
              </template>
              <template v-else-if="column.key === 'dailyLossStopEnabled'">
                <a-tag :color="record.dailyLossStopEnabled ? 'orange' : 'default'">{{ record.dailyLossStopEnabled ? `已启用 / ${formatNumber(record.dailyLossStopThreshold)}` : '关闭' }}</a-tag>
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
                {{ displayText(text) }}
              </template>
            </template>
          </a-table>
        </a-space>
      </a-card>
    </a-space>

    <a-drawer v-model:open="detailOpen" title="交易任务配置详情" width="620">
      <template v-if="detailProfile">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="配置名称">{{ detailProfile.name }}</a-descriptions-item>
          <a-descriptions-item label="描述">{{ detailProfile.description || '-' }}</a-descriptions-item>
          <a-descriptions-item label="状态">{{ detailProfile.enabled ? '启用' : '停用' }}</a-descriptions-item>
          <a-descriptions-item label="策略配置">{{ detailProfile.missingStrategyProfile ? '关联策略异常或已删除' : (detailProfile.strategyProfileName || '-') }}</a-descriptions-item>
          <a-descriptions-item label="策略类型">{{ strategyTypeLabel(detailProfile.strategyType) }}</a-descriptions-item>
          <a-descriptions-item label="交易对">{{ detailProfile.symbol }}</a-descriptions-item>
          <a-descriptions-item label="周期">{{ detailProfile.timeframe }}</a-descriptions-item>
          <a-descriptions-item label="模式">{{ tradeModeLabel(resolveProfileTradeMode(detailProfile)) }}</a-descriptions-item>
          <a-descriptions-item label="K线数量">{{ detailProfile.tradeLimit }}</a-descriptions-item>
          <a-descriptions-item label="手续费率">{{ formatRate(detailProfile.feeRate) }}</a-descriptions-item>
          <a-descriptions-item label="滑点率">{{ formatRate(detailProfile.slippageRate) }}</a-descriptions-item>
          <a-descriptions-item label="单日亏损停机">{{ detailProfile.dailyLossStopEnabled ? '已启用' : '关闭' }}</a-descriptions-item>
          <a-descriptions-item label="单日亏损阈值">{{ formatNumber(detailProfile.dailyLossStopThreshold) }}</a-descriptions-item>
          <a-descriptions-item label="Runner">{{ detailProfile.runnerName }}</a-descriptions-item>
          <a-descriptions-item label="创建时间">{{ formatDateTime(detailProfile.createdAt) }}</a-descriptions-item>
          <a-descriptions-item label="更新时间">{{ formatDateTime(detailProfile.updatedAt) }}</a-descriptions-item>
        </a-descriptions>
        <a-descriptions v-if="detailProfile.strategyProfile?.fusionSummary" :column="1" bordered size="small" style="margin-top: 16px">
          <a-descriptions-item label="融合摘要">{{ formatFusionSummary(detailProfile.strategyProfile.fusionSummary) }}</a-descriptions-item>
          <a-descriptions-item label="K 线节点数">{{ detailProfile.strategyProfile.fusionSummary.klineNodeCount }}</a-descriptions-item>
          <a-descriptions-item label="信号源节点数">{{ detailProfile.strategyProfile.fusionSummary.signalSourceNodeCount }}</a-descriptions-item>
          <a-descriptions-item label="最少可用节点数">{{ detailProfile.strategyProfile.fusionSummary.minAvailableNodes }}</a-descriptions-item>
          <a-descriptions-item label="允许降级运行">{{ detailProfile.strategyProfile.fusionSummary.allowDegraded ? '是' : '否' }}</a-descriptions-item>
          <a-descriptions-item label="固定周期约束">{{ detailProfile.strategyProfile.fusionSummary.requires1hTimeframe ? '包含固定 1h 节点' : '无' }}</a-descriptions-item>
        </a-descriptions>
      </template>
    </a-drawer>

    <a-drawer v-model:open="editOpen" :title="form.id ? '编辑交易任务配置' : '新增交易任务配置'" width="620">
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
          <div v-if="selectedStrategyProfile?.fusionSummary" class="field-help">
            {{ formatFusionSummary(selectedStrategyProfile.fusionSummary) }}
          </div>
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
        </div>
        <a-form-item label="启用">
          <a-switch v-model:checked="form.enabled" />
        </a-form-item>
        <a-form-item label="交易方式">
          <a-select v-model:value="form.tradeMode">
            <a-select-option value="live">真实交易</a-select-option>
            <a-select-option value="sandbox">沙盒交易</a-select-option>
            <a-select-option value="paper">纸上交易</a-select-option>
          </a-select>
          <div class="mode-help">真实交易：真实行情，真实下单；沙盒交易：沙盒行情，沙盒下单；纸上交易：真实行情，不真实下单。</div>
        </a-form-item>
        <div class="form-grid">
          <a-form-item label="手续费率">
            <a-input-number v-model:value="form.feeRate" :min="0" :step="0.0001" style="width: 100%" />
          </a-form-item>
          <a-form-item label="滑点率">
            <a-input-number v-model:value="form.slippageRate" :min="0" :step="0.0001" style="width: 100%" />
          </a-form-item>
          <a-form-item label="启用单日亏损停机">
            <a-switch v-model:checked="form.dailyLossStopEnabled" />
          </a-form-item>
          <a-form-item label="单日亏损停机阈值">
            <a-input-number
              v-model:value="form.dailyLossStopThreshold"
              :min="0"
              :step="1"
              :disabled="!form.dailyLossStopEnabled"
              style="width: 100%"
            />
          </a-form-item>
        </div>
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
import type { FusionSummary, StrategyProfile } from '@/types/strategy'
import type { TradeMode, TradeTaskProfile } from '@/types/system'

type TradeTaskProfileRow = TradeTaskProfile & {
  strategyProfile?: StrategyProfile
  missingStrategyProfile?: boolean
}

const router = useRouter()
const detailOpen = ref(false)
const editOpen = ref(false)
const profiles = ref<TradeTaskProfileRow[]>([])
const strategyProfiles = ref<StrategyProfile[]>([])
const invalidStrategyProfileCount = ref(0)
const supportedTimeframes = ref<string[]>([])
const detailProfile = ref<TradeTaskProfileRow | null>(null)

const form = reactive<{
  id?: number
  name: string
  description: string
  enabled: boolean
  strategyProfileId?: number
  symbol: string
  timeframe: string
  tradeMode: TradeMode
  tradeLimit: number
  feeRate: number
  slippageRate: number
  dailyLossStopEnabled: boolean
  dailyLossStopThreshold: number
}>({
  name: '',
  description: '',
  enabled: true,
  strategyProfileId: undefined,
  symbol: 'BTC/USDT',
  timeframe: '15m',
  tradeMode: 'sandbox',
  tradeLimit: 100,
  feeRate: 0,
  slippageRate: 0,
  dailyLossStopEnabled: false,
  dailyLossStopThreshold: 100,
})

const profileColumns = [
  { title: '配置名称', dataIndex: 'name', key: 'name', width: 220 },
  { title: '策略配置', dataIndex: 'strategyProfileName', key: 'strategyProfileName', width: 260 },
  { title: '交易对', dataIndex: 'symbol', key: 'symbol', width: 140 },
  { title: '周期', dataIndex: 'timeframe', key: 'timeframe', width: 100 },
  { title: 'K线数量', dataIndex: 'tradeLimit', key: 'tradeLimit', width: 120 },
  { title: '手续费率', dataIndex: 'feeRate', key: 'feeRate', width: 120 },
  { title: '滑点率', dataIndex: 'slippageRate', key: 'slippageRate', width: 120 },
  { title: '单日亏损停机', dataIndex: 'dailyLossStopEnabled', key: 'dailyLossStopEnabled', width: 140 },
  { title: '模式', dataIndex: 'tradeMode', key: 'tradeMode', width: 120 },
  { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 100 },
  { title: '更新时间', dataIndex: 'updatedAt', key: 'updatedAt', width: 180 },
  { title: '操作', key: 'actions', width: 260 },
]

const enabledStrategyProfiles = computed(() => strategyProfiles.value.filter((item) => item.enabled))

const selectedStrategyProfile = computed(() => enabledStrategyProfiles.value.find((item) => item.id === form.strategyProfileId))

function filterSelectOption(input: string, option?: { children?: unknown; value?: unknown }) {
  const label = typeof option?.children === 'string' ? option.children : String(option?.value || '')
  return label.toLowerCase().includes(input.toLowerCase())
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

function formatFusionSummary(summary?: FusionSummary | null) {
  if (!summary) {
    return '-'
  }
  const parts = [
    `${summary.klineNodeCount} 个 K 线节点`,
    `${summary.signalSourceNodeCount} 个信号源`,
    `最少 ${summary.minAvailableNodes} 个可用节点`,
  ]
  if (summary.requires1hTimeframe) {
    parts.push('包含固定 1h 节点')
  }
  if (!summary.allowDegraded) {
    parts.push('不允许降级')
  }
  return parts.join(' / ')
}

function strategyTypeLabel(value: string) {
  return strategyProfiles.value.find((item) => item.strategyType === value)?.definition?.displayName || value || '-'
}

function resolveProfileTradeMode(profile: Pick<TradeTaskProfile, 'tradeMode' | 'sandboxTrade'> | null | undefined): TradeMode {
  if (profile?.tradeMode) {
    return profile.tradeMode
  }
  return profile?.sandboxTrade === false ? 'live' : 'sandbox'
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

function tradeModeTagColor(value: TradeMode) {
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

async function resetForm() {
  form.id = undefined
  form.name = ''
  form.description = ''
  form.enabled = true
  form.strategyProfileId = enabledStrategyProfiles.value[0]?.id
  form.symbol = 'BTC/USDT'
  form.timeframe = supportedTimeframes.value[0] || '15m'
  form.tradeMode = 'sandbox'
  form.tradeLimit = 100
  form.feeRate = 0
  form.slippageRate = 0
  form.dailyLossStopEnabled = false
  form.dailyLossStopThreshold = 100
  await loadSettings()
}

async function openCreate() {
  await resetForm()
  editOpen.value = true
}

function openEdit(profile: TradeTaskProfileRow) {
  form.id = profile.id
  form.name = profile.name
  form.description = profile.description
  form.enabled = profile.enabled
  form.strategyProfileId = profile.strategyProfileId
  form.symbol = profile.symbol
  form.timeframe = profile.timeframe
  form.tradeMode = resolveProfileTradeMode(profile)
  form.tradeLimit = profile.tradeLimit
  form.feeRate = profile.feeRate
  form.slippageRate = profile.slippageRate
  form.dailyLossStopEnabled = profile.dailyLossStopEnabled
  form.dailyLossStopThreshold = profile.dailyLossStopThreshold
  editOpen.value = true
}

function openDetail(profile: TradeTaskProfileRow) {
  detailProfile.value = profile
  detailOpen.value = true
}

function closeEdit() {
  editOpen.value = false
}

function goToControl(profileId: number) {
  router.push({ path: '/trade-task-control', query: { profileId: String(profileId) } })
}

function goToStrategies() {
  router.push('/strategies')
}

async function loadProfiles() {
  const profileList = await fetchTradeTaskProfiles()
  profiles.value = profileList.map((profile) => {
    const strategyProfile = strategyProfiles.value.find((item) => item.id === profile.strategyProfileId)
    return {
      ...profile,
      strategyProfile,
      missingStrategyProfile: Boolean(profile.strategyProfileId) && strategyProfile == null,
    }
  })
}

async function loadStrategyProfiles() {
  const data = await fetchStrategyProfiles()
  strategyProfiles.value = data.items
  invalidStrategyProfileCount.value = data.invalidItems.length
}

async function loadSettings() {
  const data = await fetchSystemSettings()
  supportedTimeframes.value = data.editable.supportedTimeframes
  if (!form.timeframe) {
    form.timeframe = supportedTimeframes.value[0] || '15m'
  }
  if (!form.id) {
    form.feeRate = data.editable.tradeTaskDefaultFeeRate
    form.slippageRate = data.editable.tradeTaskDefaultSlippageRate
    form.dailyLossStopEnabled = data.editable.tradeTaskDefaultDailyLossStopEnabled
    form.dailyLossStopThreshold = data.editable.tradeTaskDefaultDailyLossStopThreshold
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
    tradeMode: form.tradeMode,
    tradeLimit: form.tradeLimit,
    feeRate: form.feeRate,
    slippageRate: form.slippageRate,
    dailyLossStopEnabled: form.dailyLossStopEnabled,
    dailyLossStopThreshold: form.dailyLossStopThreshold,
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
  await resetForm()
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

.mode-help,
.field-help,
.cell-meta {
  margin-top: 4px;
  color: #8c8c8c;
  font-size: 12px;
  white-space: normal;
}

.cell-meta-warning {
  color: #d46b08;
}

:deep(.ant-table-thead > tr > th) {
  white-space: nowrap;
}
</style>
