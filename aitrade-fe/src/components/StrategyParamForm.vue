<template>
  <a-form layout="vertical">
    <template v-for="field in schema" :key="field.field">
      <a-form-item :label="field.label" :extra="field.description">
        <a-switch
          v-if="field.type === 'boolean'"
          :checked="Boolean(modelValue[field.field])"
          @change="updateBooleanField(field.field, $event)"
        />
        <a-input
          v-else-if="field.type === 'string'"
          :value="stringValue(field.field)"
          @update:value="updateStringField(field.field, $event)"
        />
        <a-input-number
          v-else
          :value="numberValue(field.field)"
          :precision="field.type === 'integer' ? 0 : undefined"
          :step="field.step ?? (field.type === 'integer' ? 1 : 0.01)"
          :min="field.min"
          :max="field.max"
          style="width: 100%"
          @change="updateNumberField(field.field, field.type, $event)"
        />
      </a-form-item>
    </template>
  </a-form>
</template>

<script setup lang="ts">
import type { StrategyFieldSchema } from '@/types/strategy'

const props = defineProps<{
  schema: StrategyFieldSchema[]
  modelValue: Record<string, unknown>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown>]
}>()

function updateField(field: string, value: unknown) {
  emit('update:modelValue', {
    ...props.modelValue,
    [field]: value,
  })
}

function updateBooleanField(field: string, checked: boolean) {
  updateField(field, checked)
}

function updateStringField(field: string, value: string) {
  updateField(field, value)
}

function updateNumberField(field: string, type: 'number' | 'integer' | 'boolean' | 'string', value: number | string | null) {
  updateField(field, normalizeNumber(type, value))
}

function numberValue(field: string) {
  const value = props.modelValue[field]
  return typeof value === 'number' ? value : undefined
}

function stringValue(field: string) {
  const value = props.modelValue[field]
  return typeof value === 'string' ? value : ''
}

function normalizeNumber(type: 'number' | 'integer' | 'boolean' | 'string', value: number | string | null) {
  if (value == null || value === '') {
    return undefined
  }
  const normalized = Number(value)
  return type === 'integer' ? Math.trunc(normalized) : normalized
}
</script>
