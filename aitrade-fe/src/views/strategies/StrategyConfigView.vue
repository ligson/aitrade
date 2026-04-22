<template>
  <a-row :gutter="16">
    <a-col :span="10">
      <a-card title="策略配置列表" extra="">
        <template #extra>
          <a-button type="primary" @click="openCreate">新增配置</a-button>
        </template>
        <a-list :data-source="profiles" bordered>
          <template #renderItem="{ item }">
            <a-list-item>
              <a-space direction="vertical" style="width: 100%">
                <a-space style="justify-content: space-between; width: 100%">
                  <div>
                    <div><strong>{{ item.name }}</strong></div>
                    <div>{{ item.definition?.displayName || item.strategyType }}</div>
                  </div>
                  <a-tag :color="item.enabled ? 'green' : 'default'">{{ item.enabled ? '启用' : '停用' }}</a-tag>
                </a-space>
                <div>{{ item.description }}</div>
                <a-space>
                  <a-button type="link" @click="openEdit(item)">编辑</a-button>
                  <a-button type="link" danger @click="removeProfile(item.id)">删除</a-button>
                </a-space>
              </a-space>
            </a-list-item>
          </template>
        </a-list>
      </a-card>
    </a-col>
    <a-col :span="14">
      <a-card :title="form.id ? '编辑策略配置' : '新增策略配置'">
        <a-form layout="vertical">
          <a-form-item label="策略类型">
            <a-select v-model:value="form.strategyType" @change="handleStrategyTypeChange">
              <a-select-option v-for="item in definitions" :key="item.strategyType" :value="item.strategyType">
                {{ item.displayName }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="配置名称"><a-input v-model:value="form.name" /></a-form-item>
          <a-form-item label="描述"><a-input v-model:value="form.description" /></a-form-item>
          <a-form-item label="启用"><a-switch v-model:checked="form.enabled" /></a-form-item>
          <a-alert v-if="currentDefinition" :message="currentDefinition.displayName" :description="currentDefinition.description" type="info" show-icon style="margin-bottom: 16px" />
          <StrategyParamForm v-if="currentDefinition" v-model:model-value="form.params" :schema="currentDefinition.paramSchema" />
          <a-space>
            <a-button type="primary" @click="submitForm">保存</a-button>
            <a-button @click="openCreate">重置</a-button>
          </a-space>
        </a-form>
      </a-card>
    </a-col>
  </a-row>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'

import StrategyParamForm from '@/components/StrategyParamForm.vue'
import { deleteStrategyProfile, fetchStrategyDefinitions, fetchStrategyProfiles, saveStrategyProfile } from '@/api/strategies'
import type { StrategyDefinition, StrategyProfile } from '@/types/strategy'

const definitions = ref<StrategyDefinition[]>([])
const profiles = ref<StrategyProfile[]>([])

const form = reactive<{ id?: number; strategyType: string; name: string; description: string; enabled: boolean; params: Record<string, unknown> }>({
  strategyType: '',
  name: '',
  description: '',
  enabled: true,
  params: {},
})

const currentDefinition = computed(() => definitions.value.find((item) => item.strategyType === form.strategyType))

async function loadDefinitions() {
  definitions.value = await fetchStrategyDefinitions()
  if (!form.strategyType && definitions.value.length > 0) {
    form.strategyType = definitions.value[0].strategyType
    form.params = { ...definitions.value[0].defaultParams }
  }
}

async function loadProfiles() {
  profiles.value = await fetchStrategyProfiles()
}

function handleStrategyTypeChange(value: string) {
  const definition = definitions.value.find((item) => item.strategyType === value)
  form.params = definition ? { ...definition.defaultParams } : {}
}

function openCreate() {
  const definition = definitions.value[0]
  form.id = undefined
  form.strategyType = definition?.strategyType || ''
  form.name = ''
  form.description = ''
  form.enabled = true
  form.params = definition ? { ...definition.defaultParams } : {}
}

function openEdit(profile: StrategyProfile) {
  form.id = profile.id
  form.strategyType = profile.strategyType
  form.name = profile.name
  form.description = profile.description
  form.enabled = profile.enabled
  form.params = { ...profile.params }
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
  await loadProfiles()
  openCreate()
}

async function removeProfile(id: number) {
  await deleteStrategyProfile(id)
  message.success('策略配置已删除')
  await loadProfiles()
  if (form.id === id) {
    openCreate()
  }
}

onMounted(async () => {
  await loadDefinitions()
  await loadProfiles()
  openCreate()
})
</script>
