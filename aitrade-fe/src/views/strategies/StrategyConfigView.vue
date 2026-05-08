<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="middle" style="width: 100%">
      <div class="page-toolbar">
        <a-space wrap>
          <a-button @click="goToSignalSources">信号源配置</a-button>
          <a-button type="primary" @click="openCreate">新增配置</a-button>
        </a-space>
      </div>
      <a-alert
        v-if="hasInvalidProfiles"
        type="warning"
        show-icon
        :message="`检测到 ${invalidProfiles.length} 条异常策略配置，已从正常列表中自动跳过。`"
        description="这些异常配置不会再阻塞任务配置、任务控制和回测页面；请在下方清理或修复。"
      />
      <a-table :data-source="tableRows" :columns="columns" row-key="id" :pagination="false" :scroll="{ x: 'max-content' }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'ownerUserId'">
            {{ formatOwnerUserId(record.ownerUserId) }}
          </template>
          <template v-else-if="column.key === 'strategyType'">
            <div>{{ record.definition?.displayName || record.strategyType }}</div>
            <div v-if="record.definition?.fixedConstraints?.length" class="cell-meta">{{ formatFixedConstraints(record.definition) }}</div>
          </template>
          <template v-else-if="column.key === 'strategyCategory'">
            <a-tag :color="strategyCategoryColor(record.definition?.strategyCategory)">{{ strategyCategoryLabel(record.definition?.strategyCategory) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'fusionSummary'">
            <span class="summary-text">{{ formatFusionSummary(record.fusionSummary) }}</span>
          </template>
          <template v-else-if="column.key === 'enabled'">
            <a-tag :color="record.enabled ? 'green' : 'default'">{{ record.enabled ? '启用' : '停用' }}</a-tag>
          </template>
          <template v-else-if="column.key === 'createdAt' || column.key === 'updatedAt'">
            {{ formatDateTime(record[column.key]) }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space size="small" wrap>
              <a-button type="link" @click="openDetail(record)">详情</a-button>
              <a-button type="link" @click="openEdit(record)">编辑</a-button>
              <a-button type="link" danger @click="removeProfile(record.id)">删除</a-button>
            </a-space>
          </template>
        </template>
      </a-table>
      <a-card v-if="hasInvalidProfiles" size="small" title="异常策略配置">
        <a-table :data-source="invalidProfiles" :columns="invalidColumns" row-key="id" :pagination="false" :scroll="{ x: 'max-content' }">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'strategyType'">
              <div>{{ strategyTypeDisplayLabel(record.strategyType) }}</div>
            </template>
            <template v-else-if="column.key === 'enabled'">
              <a-tag :color="record.enabled ? 'green' : 'default'">{{ record.enabled ? '启用' : '停用' }}</a-tag>
            </template>
            <template v-else-if="column.key === 'errorStage'">
              {{ errorStageLabel(record.errorStage) }}
            </template>
            <template v-else-if="column.key === 'errorMessage'">
              <span class="summary-text">{{ record.errorMessage }}</span>
            </template>
            <template v-else-if="column.key === 'updatedAt'">
              {{ formatDateTime(record.updatedAt) }}
            </template>
            <template v-else-if="column.key === 'actions'">
              <a-button type="link" danger @click="removeProfile(record.id)">删除</a-button>
            </template>
          </template>
        </a-table>
      </a-card>
    </a-space>

    <a-drawer v-model:open="detailOpen" title="策略详情" width="560">
      <template v-if="detailProfile">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="配置名称">{{ detailProfile.name }}</a-descriptions-item>
          <a-descriptions-item v-if="auth.isAdmin" label="所属用户">{{ formatOwnerUserId(detailProfile.ownerUserId) }}</a-descriptions-item>
          <a-descriptions-item label="策略类型">{{ detailProfile.definition?.displayName || detailProfile.strategyType }}</a-descriptions-item>
          <a-descriptions-item label="策略分类">{{ strategyCategoryLabel(detailProfile.definition?.strategyCategory) }}</a-descriptions-item>
          <a-descriptions-item label="配置模式">{{ configModeLabel(detailProfile.definition?.configMode) }}</a-descriptions-item>
          <a-descriptions-item label="固定约束">{{ formatFixedConstraints(detailProfile.definition) }}</a-descriptions-item>
          <a-descriptions-item label="描述">{{ detailProfile.description || '-' }}</a-descriptions-item>
          <a-descriptions-item label="状态">{{ detailProfile.enabled ? '启用' : '停用' }}</a-descriptions-item>
          <a-descriptions-item label="创建时间">{{ formatDateTime(detailProfile.createdAt) }}</a-descriptions-item>
          <a-descriptions-item label="更新时间">{{ formatDateTime(detailProfile.updatedAt) }}</a-descriptions-item>
        </a-descriptions>
        <a-alert v-if="detailProfile.definition" :message="detailProfile.definition.displayName" :description="detailProfile.definition.description" type="info" show-icon style="margin-top: 16px" />
        <a-descriptions v-if="detailFusionItems.length" :column="1" bordered size="small" style="margin-top: 16px">
          <a-descriptions-item v-for="item in detailFusionItems" :key="item.field" :label="item.label">
            {{ item.value }}
          </a-descriptions-item>
        </a-descriptions>
        <a-descriptions v-if="detailParamItems.length" :column="1" bordered size="small" style="margin-top: 16px">
          <a-descriptions-item v-for="item in detailParamItems" :key="item.field" :label="item.label">
            {{ item.value }}
          </a-descriptions-item>
        </a-descriptions>
      </template>
    </a-drawer>

    <a-drawer v-model:open="editOpen" :title="form.id ? '编辑策略配置' : '新增策略配置'" width="760">
      <a-form layout="vertical">
        <a-form-item label="策略类型">
          <a-select v-model:value="form.strategyType" @change="handleStrategyTypeChange">
            <a-select-option v-for="item in definitions" :key="item.strategyType" :value="item.strategyType">
              {{ item.displayName }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="配置名称">
          <a-input v-model:value="form.name" />
        </a-form-item>
        <a-form-item label="描述">
          <a-input v-model:value="form.description" />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch v-model:checked="form.enabled" />
        </a-form-item>
        <a-alert v-if="currentDefinition" :message="currentDefinition.displayName" :description="currentDefinition.description" type="info" show-icon style="margin-bottom: 16px" />
        <FusionStrategyBuilder
          v-if="currentDefinition?.configMode === 'structured' && form.strategyType === 'spot_multi_signal_fusion'"
          v-model:model-value="fusionFormParams"
          :kline-profiles="fusionKlineProfiles"
          :signal-source-profiles="availableSignalSourceProfiles"
        />
        <StrategyParamForm v-else-if="currentDefinition" v-model:model-value="form.params" :schema="currentDefinition.paramSchema" />
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

import { useAuthStore } from '@/stores/auth'

import FusionStrategyBuilder from '@/components/FusionStrategyBuilder.vue'
import StrategyParamForm from '@/components/StrategyParamForm.vue'
import { deleteStrategyProfile, fetchSignalSourceProfiles, fetchStrategyDefinitions, fetchStrategyProfiles, saveStrategyProfile } from '@/api/strategies'
import type { SignalSourceProfile } from '@/types/signalSource'
import type { FusionStrategyParams, FusionSummary, InvalidStrategyProfile, StrategyCategory, StrategyDefinition, StrategyFieldSchema, StrategyProfile } from '@/types/strategy'

type StrategyTableRow = StrategyProfile & { definition?: StrategyDefinition }

const router = useRouter()
const auth = useAuthStore()
const definitions = ref<StrategyDefinition[]>([])
const profiles = ref<StrategyProfile[]>([])
const invalidProfiles = ref<InvalidStrategyProfile[]>([])
const signalSourceProfiles = ref<SignalSourceProfile[]>([])
const detailOpen = ref(false)
const editOpen = ref(false)
const detailProfile = ref<StrategyTableRow | null>(null)

const form = reactive<{ id?: number; strategyType: string; name: string; description: string; enabled: boolean; params: Record<string, unknown> }>({
  strategyType: '',
  name: '',
  description: '',
  enabled: true,
  params: {},
})

const columns = computed(() => {
  const ownerColumn = auth.isAdmin ? [{ title: '所属用户', dataIndex: 'ownerUserId', key: 'ownerUserId', width: 120 }] : []
  return [
    { title: '配置名称', dataIndex: 'name', key: 'name', width: 220 },
    ...ownerColumn,
    { title: '策略类型', dataIndex: 'strategyType', key: 'strategyType', width: 220 },
    { title: '策略分类', key: 'strategyCategory', width: 120 },
    { title: '融合摘要', key: 'fusionSummary', width: 260 },
    { title: '描述', dataIndex: 'description', key: 'description', width: 260 },
    { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 100 },
    { title: '更新时间', dataIndex: 'updatedAt', key: 'updatedAt', width: 180 },
    { title: '操作', key: 'actions', width: 180 },
  ]
})

const invalidColumns = computed(() => {
  const ownerColumn = auth.isAdmin ? [{ title: '所属用户', dataIndex: 'ownerUserId', key: 'ownerUserId', width: 120 }] : []
  return [
    { title: '配置名称', dataIndex: 'name', key: 'name', width: 220 },
    ...ownerColumn,
    { title: '策略类型', dataIndex: 'strategyType', key: 'strategyType', width: 220 },
    { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 100 },
    { title: '错误阶段', dataIndex: 'errorStage', key: 'errorStage', width: 120 },
    { title: '错误原因', dataIndex: 'errorMessage', key: 'errorMessage', width: 360 },
    { title: '更新时间', dataIndex: 'updatedAt', key: 'updatedAt', width: 180 },
    { title: '操作', key: 'actions', width: 120 },
  ]
})

const tableRows = computed<StrategyTableRow[]>(() =>
  profiles.value.map((profile) => ({
    ...profile,
    definition: definitions.value.find((item) => item.strategyType === profile.strategyType),
  })),
)

const currentDefinition = computed(() => definitions.value.find((item) => item.strategyType === form.strategyType))
const hasInvalidProfiles = computed(() => invalidProfiles.value.length > 0)

const fusionKlineProfiles = computed(() =>
  profiles.value.filter((item) => item.enabled && definitions.value.find((definition) => definition.strategyType === item.strategyType)?.usableAsFusionNode),
)

const availableSignalSourceProfiles = computed(() => signalSourceProfiles.value.filter((item) => item.enabled))

const fusionFormParams = computed<FusionStrategyParams>({
  get() {
    return form.params as unknown as FusionStrategyParams
  },
  set(value) {
    form.params = value as unknown as Record<string, unknown>
  },
})

const detailFusionItems = computed(() => {
  const summary = detailProfile.value?.fusionSummary
  if (!summary) {
    return []
  }
  return [
    { field: 'klineNodeCount', label: 'K 线节点数', value: String(summary.klineNodeCount) },
    { field: 'signalSourceNodeCount', label: '信号源节点数', value: String(summary.signalSourceNodeCount) },
    { field: 'minAvailableNodes', label: '最少可用节点数', value: String(summary.minAvailableNodes) },
    { field: 'allowDegraded', label: '允许降级运行', value: summary.allowDegraded ? '是' : '否' },
    { field: 'decisionMode', label: '融合模式', value: summary.decisionMode },
    { field: 'requires1hTimeframe', label: '固定周期约束', value: summary.requires1hTimeframe ? '包含固定 1h 节点' : '无' },
  ]
})

const detailParamItems = computed(() => {
  if (!detailProfile.value) {
    return []
  }
  const schema = detailProfile.value.definition?.paramSchema || []
  if (schema.length > 0) {
    return schema.map((field) => ({
      field: field.field,
      label: field.label,
      value: formatParamValue(field, detailProfile.value?.params[field.field]),
    }))
  }
  return Object.entries(detailProfile.value.params).map(([field, value]) => ({
    field,
    label: field,
    value: formatFallbackValue(value),
  }))
})

function deepClone<T>(value: T): T {
  if (value == null) {
    return {} as T
  }
  return JSON.parse(JSON.stringify(value)) as T
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

function formatFallbackValue(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (typeof value === 'boolean') {
    return value ? '是' : '否'
  }
  if (Array.isArray(value) || typeof value === 'object') {
    return JSON.stringify(value)
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

function strategyCategoryLabel(value?: StrategyCategory) {
  if (value === 'kline') {
    return 'K 线策略'
  }
  if (value === 'gpt') {
    return 'GPT 策略'
  }
  if (value === 'ai') {
    return 'AI 策略'
  }
  if (value === 'fusion') {
    return '融合策略'
  }
  return '-'
}

function strategyCategoryColor(value?: StrategyCategory) {
  if (value === 'kline') {
    return 'blue'
  }
  if (value === 'gpt') {
    return 'purple'
  }
  if (value === 'ai') {
    return 'geekblue'
  }
  if (value === 'fusion') {
    return 'magenta'
  }
  return 'default'
}

function configModeLabel(value?: StrategyDefinition['configMode']) {
  if (value === 'structured') {
    return '结构化编排'
  }
  if (value === 'flat_params') {
    return '参数表单'
  }
  return '-'
}

function formatFixedConstraints(definition?: StrategyDefinition) {
  if (!definition?.fixedConstraints?.length) {
    return '-'
  }
  return definition.fixedConstraints.join(' / ')
}

function strategyTypeDisplayLabel(value: string) {
  return definitions.value.find((item) => item.strategyType === value)?.displayName || value || '-'
}

function errorStageLabel(value: string) {
  if (value === 'json_load') {
    return 'JSON 解析'
  }
  if (value === 'normalize') {
    return '参数归一'
  }
  if (value === 'summarize') {
    return '摘要生成'
  }
  return value || '-'
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

async function loadDefinitions() {
  definitions.value = await fetchStrategyDefinitions()
}

async function loadProfiles() {
  const data = await fetchStrategyProfiles()
  profiles.value = data.items
  invalidProfiles.value = data.invalidItems
}

async function loadSignalSourceProfiles() {
  signalSourceProfiles.value = await fetchSignalSourceProfiles()
}

function goToSignalSources() {
  router.push('/signal-sources')
}

function handleStrategyTypeChange(value: string) {
  const definition = definitions.value.find((item) => item.strategyType === value)
  form.params = definition ? deepClone(definition.defaultParams) : {}
}

function resetForm() {
  const definition = definitions.value[0]
  form.id = undefined
  form.strategyType = definition?.strategyType || ''
  form.name = ''
  form.description = ''
  form.enabled = true
  form.params = definition ? deepClone(definition.defaultParams) : {}
}

function openCreate() {
  resetForm()
  editOpen.value = true
}

function openEdit(profile: StrategyTableRow) {
  form.id = profile.id
  form.strategyType = profile.strategyType
  form.name = profile.name
  form.description = profile.description
  form.enabled = profile.enabled
  form.params = deepClone(profile.params)
  editOpen.value = true
}

function openDetail(profile: StrategyTableRow) {
  detailProfile.value = profile
  detailOpen.value = true
}

function closeEdit() {
  editOpen.value = false
}

async function submitForm() {
  await saveStrategyProfile({
    id: form.id,
    strategyType: form.strategyType,
    name: form.name,
    description: form.description,
    enabled: form.enabled,
    params: form.params,
  })
  message.success('策略配置已保存')
  editOpen.value = false
  await loadProfiles()
}

async function removeProfile(id: number) {
  await deleteStrategyProfile(id)
  message.success('策略配置已删除')
  await loadProfiles()
  if (detailProfile.value?.id === id) {
    detailOpen.value = false
    detailProfile.value = null
  }
  if (form.id === id) {
    resetForm()
  }
}

onMounted(async () => {
  await loadDefinitions()
  await loadProfiles()
  await loadSignalSourceProfiles()
  resetForm()
})
</script>

<style scoped>
.page-card {
  min-height: 100%;
}

.page-toolbar {
  display: flex;
  justify-content: flex-end;
}

.cell-meta {
  margin-top: 4px;
  color: #8c8c8c;
  font-size: 12px;
  white-space: normal;
}

.summary-text {
  white-space: normal;
}

:deep(.ant-table-thead > tr > th) {
  white-space: nowrap;
}
</style>
