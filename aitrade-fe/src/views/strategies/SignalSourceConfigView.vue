<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="middle" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="信号源配置用于沉淀可复用的融合节点输入。"
        description="当前已接入运行时的信号源包括 trade_flow 与 indicator；其中 indicator 第一阶段支持 rsi / macd，且每个融合策略最多启用一个 indicator 节点，主周期必须与交易任务周期一致。"
      />
      <div class="page-toolbar">
        <a-button type="primary" @click="openCreate">新增信号源</a-button>
      </div>
      <a-table :data-source="tableRows" :columns="columns" row-key="id" :pagination="false" :scroll="{ x: 'max-content' }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'sourceType'">
            {{ record.definition?.displayName || record.sourceType }}
          </template>
          <template v-else-if="column.key === 'enabled'">
            <a-tag :color="record.enabled ? 'green' : 'default'">{{ record.enabled ? '启用' : '停用' }}</a-tag>
          </template>
          <template v-else-if="column.key === 'runtimeSupported'">
            <a-tag :color="record.definition?.runtimeSupported ? 'blue' : 'default'">{{ record.definition?.runtimeSupported ? '已接入运行时' : '预留' }}</a-tag>
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
    </a-space>

    <a-drawer v-model:open="detailOpen" title="信号源详情" width="520">
      <template v-if="detailProfile">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="名称">{{ detailProfile.name }}</a-descriptions-item>
          <a-descriptions-item label="类型">{{ detailProfile.definition?.displayName || detailProfile.sourceType }}</a-descriptions-item>
          <a-descriptions-item label="描述">{{ detailProfile.description || '-' }}</a-descriptions-item>
          <a-descriptions-item label="状态">{{ detailProfile.enabled ? '启用' : '停用' }}</a-descriptions-item>
          <a-descriptions-item label="运行时状态">{{ detailProfile.definition?.runtimeSupported ? '已接入运行时' : '预留配置' }}</a-descriptions-item>
        </a-descriptions>
        <a-alert v-if="detailProfile.definition" :message="detailProfile.definition.displayName" :description="detailProfile.definition.description" type="info" show-icon style="margin-top: 16px" />
        <a-descriptions :column="1" bordered size="small" style="margin-top: 16px">
          <a-descriptions-item v-for="item in detailParamItems" :key="item.field" :label="item.label">
            {{ item.value }}
          </a-descriptions-item>
        </a-descriptions>
      </template>
    </a-drawer>

    <a-drawer v-model:open="editOpen" :title="form.id ? '编辑信号源' : '新增信号源'" width="560">
      <a-form layout="vertical">
        <a-form-item label="信号源类型">
          <a-select v-model:value="form.sourceType" @change="handleSourceTypeChange">
            <a-select-option v-for="item in definitions" :key="item.sourceType" :value="item.sourceType">
              {{ item.displayName }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="名称">
          <a-input v-model:value="form.name" />
        </a-form-item>
        <a-form-item label="描述">
          <a-input v-model:value="form.description" />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch v-model:checked="form.enabled" />
        </a-form-item>
        <a-alert v-if="currentDefinition" :message="currentDefinition.displayName" :description="currentDefinition.description" type="info" show-icon style="margin-bottom: 16px" />
        <StrategyParamForm v-if="currentDefinition" v-model:model-value="form.params" :schema="currentDefinition.paramSchema" />
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
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'

import StrategyParamForm from '@/components/StrategyParamForm.vue'
import { deleteSignalSourceProfile, fetchSignalSourceDefinitions, fetchSignalSourceProfiles, saveSignalSourceProfile } from '@/api/strategies'
import type { SignalSourceDefinition, SignalSourceFieldSchema, SignalSourceProfile } from '@/types/signalSource'

type SignalSourceTableRow = SignalSourceProfile & { definition?: SignalSourceDefinition }

const definitions = ref<SignalSourceDefinition[]>([])
const profiles = ref<SignalSourceProfile[]>([])
const detailOpen = ref(false)
const editOpen = ref(false)
const detailProfile = ref<SignalSourceTableRow | null>(null)

const form = reactive<{ id?: number; sourceType: string; name: string; description: string; enabled: boolean; params: Record<string, unknown> }>({
  sourceType: '',
  name: '',
  description: '',
  enabled: true,
  params: {},
})

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name', width: 220 },
  { title: '信号源类型', dataIndex: 'sourceType', key: 'sourceType', width: 180 },
  { title: '运行时', key: 'runtimeSupported', width: 140 },
  { title: '描述', dataIndex: 'description', key: 'description', width: 260 },
  { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 100 },
  { title: '更新时间', dataIndex: 'updatedAt', key: 'updatedAt', width: 180 },
  { title: '操作', key: 'actions', width: 180 },
]

const tableRows = computed<SignalSourceTableRow[]>(() =>
  profiles.value.map((profile) => ({
    ...profile,
    definition: definitions.value.find((item) => item.sourceType === profile.sourceType),
  })),
)

const currentDefinition = computed(() => definitions.value.find((item) => item.sourceType === form.sourceType))

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

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return '-'
  }
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm:ss') : value
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

function formatParamValue(field: SignalSourceFieldSchema, value: unknown) {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (field.type === 'boolean') {
    return Boolean(value) ? '是' : '否'
  }
  return String(value)
}

async function loadDefinitions() {
  definitions.value = await fetchSignalSourceDefinitions()
}

async function loadProfiles() {
  profiles.value = await fetchSignalSourceProfiles()
}

function handleSourceTypeChange(value: string) {
  const definition = definitions.value.find((item) => item.sourceType === value)
  form.params = definition ? { ...definition.defaultParams } : {}
}

function resetForm() {
  const definition = definitions.value[0]
  form.id = undefined
  form.sourceType = definition?.sourceType || ''
  form.name = ''
  form.description = ''
  form.enabled = true
  form.params = definition ? { ...definition.defaultParams } : {}
}

function openCreate() {
  resetForm()
  editOpen.value = true
}

function openEdit(profile: SignalSourceTableRow) {
  form.id = profile.id
  form.sourceType = profile.sourceType
  form.name = profile.name
  form.description = profile.description
  form.enabled = profile.enabled
  form.params = { ...profile.params }
  editOpen.value = true
}

function openDetail(profile: SignalSourceTableRow) {
  detailProfile.value = profile
  detailOpen.value = true
}

function closeEdit() {
  editOpen.value = false
}

async function submitForm() {
  await saveSignalSourceProfile({
    id: form.id,
    sourceType: form.sourceType,
    name: form.name,
    description: form.description,
    enabled: form.enabled,
    params: form.params,
  })
  message.success('信号源配置已保存')
  editOpen.value = false
  await loadProfiles()
}

async function removeProfile(id: number) {
  await deleteSignalSourceProfile(id)
  message.success('信号源配置已删除')
  profiles.value = profiles.value.filter((item) => item.id !== id)
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
</style>
