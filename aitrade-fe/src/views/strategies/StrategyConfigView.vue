<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="middle" style="width: 100%">
      <div class="page-toolbar">
        <a-button type="primary" @click="openCreate">新增配置</a-button>
      </div>
      <a-table :data-source="tableRows" :columns="columns" row-key="id" :pagination="false">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'strategyType'">
            {{ record.definition?.displayName || record.strategyType }}
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
    </a-space>

    <a-drawer v-model:open="detailOpen" title="策略详情" width="520">
      <template v-if="detailProfile">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="配置名称">{{ detailProfile.name }}</a-descriptions-item>
          <a-descriptions-item label="策略类型">{{ detailProfile.definition?.displayName || detailProfile.strategyType }}</a-descriptions-item>
          <a-descriptions-item label="描述">{{ detailProfile.description || '-' }}</a-descriptions-item>
          <a-descriptions-item label="状态">{{ detailProfile.enabled ? '启用' : '停用' }}</a-descriptions-item>
          <a-descriptions-item label="创建时间">{{ formatDateTime(detailProfile.createdAt) }}</a-descriptions-item>
          <a-descriptions-item label="更新时间">{{ formatDateTime(detailProfile.updatedAt) }}</a-descriptions-item>
        </a-descriptions>
        <a-alert v-if="detailProfile.definition" :message="detailProfile.definition.displayName" :description="detailProfile.definition.description" type="info" show-icon style="margin-top: 16px" />
        <a-descriptions :column="1" bordered size="small" style="margin-top: 16px">
          <a-descriptions-item v-for="item in detailParamItems" :key="item.field" :label="item.label">
            {{ item.value }}
          </a-descriptions-item>
        </a-descriptions>
      </template>
    </a-drawer>

    <a-drawer v-model:open="editOpen" :title="form.id ? '编辑策略配置' : '新增策略配置'" width="560">
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
import { deleteStrategyProfile, fetchStrategyDefinitions, fetchStrategyProfiles, saveStrategyProfile } from '@/api/strategies'
import type { StrategyDefinition, StrategyFieldSchema, StrategyProfile } from '@/types/strategy'

type StrategyTableRow = StrategyProfile & { definition?: StrategyDefinition }

const definitions = ref<StrategyDefinition[]>([])
const profiles = ref<StrategyProfile[]>([])
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

const columns = [
  { title: '配置名称', dataIndex: 'name', key: 'name' },
  { title: '策略类型', dataIndex: 'strategyType', key: 'strategyType', width: 180 },
  { title: '描述', dataIndex: 'description', key: 'description' },
  { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 100 },
  { title: '更新时间', dataIndex: 'updatedAt', key: 'updatedAt', width: 180 },
  { title: '操作', key: 'actions', width: 180 },
]

const tableRows = computed<StrategyTableRow[]>(() =>
  profiles.value.map((profile) => ({
    ...profile,
    definition: definitions.value.find((item) => item.strategyType === profile.strategyType),
  })),
)

const currentDefinition = computed(() => definitions.value.find((item) => item.strategyType === form.strategyType))

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

function formatParamValue(field: StrategyFieldSchema, value: unknown) {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (field.type === 'boolean') {
    return Boolean(value) ? '是' : '否'
  }
  return String(value)
}

async function loadDefinitions() {
  definitions.value = await fetchStrategyDefinitions()
}

async function loadProfiles() {
  profiles.value = await fetchStrategyProfiles()
}

function handleStrategyTypeChange(value: string) {
  const definition = definitions.value.find((item) => item.strategyType === value)
  form.params = definition ? { ...definition.defaultParams } : {}
}

function resetForm() {
  const definition = definitions.value[0]
  form.id = undefined
  form.strategyType = definition?.strategyType || ''
  form.name = ''
  form.description = ''
  form.enabled = true
  form.params = definition ? { ...definition.defaultParams } : {}
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
  form.params = { ...profile.params }
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
