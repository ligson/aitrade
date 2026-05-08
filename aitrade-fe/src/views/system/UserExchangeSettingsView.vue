<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="这里维护当前用户自己的交易所接入凭证。"
        description="保存后会影响后续新启动的交易任务；已经运行中的任务会继续使用启动时冻结的交易所快照，不会被这里的后续修改回溯影响。"
      />

      <a-card title="交易所设置" size="small" :loading="loading">
        <a-form layout="vertical">
          <div class="form-grid two-column">
            <a-form-item label="当前用户">
              <a-input :value="targetUserLabel" disabled />
            </a-form-item>
            <a-form-item label="交易所类型">
              <a-select v-model:value="form.exchangeType">
                <a-select-option value="binance">binance</a-select-option>
                <a-select-option value="okx">okx</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="API Key">
              <a-input-password v-model:value="form.apiKey" placeholder="未修改则保留当前密钥" />
            </a-form-item>
            <a-form-item label="API Secret">
              <a-input-password v-model:value="form.apiSecret" placeholder="未修改则保留当前密钥" />
            </a-form-item>
            <a-form-item :label="requiresPassword ? 'Password（OKX 必填）' : 'Password（仅 OKX 需要）'">
              <a-input-password
                v-model:value="form.password"
                :disabled="!requiresPassword"
                :placeholder="requiresPassword ? '未修改则保留当前密码' : '当前交易所类型无需填写 Password'"
              />
            </a-form-item>
          </div>

          <a-space>
            <a-button @click="loadForm">重置</a-button>
            <a-button type="primary" :loading="saving" @click="submitForm">保存交易所设置</a-button>
          </a-space>
        </a-form>
      </a-card>
    </a-space>
  </a-card>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import { computed, onMounted, reactive, ref } from 'vue'

import { fetchUserExchangeSettings, saveUserExchangeSettings } from '@/api/system'
import type { UserExchangeSettings } from '@/types/system'

function createEmptySettings(): UserExchangeSettings {
  return {
    editable: {
      exchangeType: 'binance',
      apiKey: '',
      apiSecret: '',
      password: '',
      hasApiKey: false,
      hasApiSecret: false,
      hasPassword: false,
      apiKeyMasked: '',
      apiSecretMasked: '',
      passwordMasked: '',
    },
    meta: {
      userId: 0,
      username: '',
      nickname: '',
      isAdmin: false,
      updatedAt: null,
    },
  }
}

const loading = ref(false)
const saving = ref(false)
const settings = ref<UserExchangeSettings>(createEmptySettings())

const form = reactive({
  exchangeType: 'binance',
  apiKey: '',
  apiSecret: '',
  password: '',
})

const requiresPassword = computed(() => form.exchangeType === 'okx')
const targetUserLabel = computed(() => {
  const nickname = settings.value.meta.nickname?.trim()
  const username = settings.value.meta.username?.trim()
  if (nickname && username) {
    return `${nickname}（${username}）`
  }
  return nickname || username || '-'
})

function syncForm() {
  form.exchangeType = settings.value.editable.exchangeType || 'binance'
  form.apiKey = settings.value.editable.apiKeyMasked || ''
  form.apiSecret = settings.value.editable.apiSecretMasked || ''
  form.password = settings.value.editable.passwordMasked || ''
}

async function loadForm() {
  loading.value = true
  try {
    const data = await fetchUserExchangeSettings()
    settings.value = data
    syncForm()
  } finally {
    loading.value = false
  }
}

async function submitForm() {
  if (!form.exchangeType.trim()) {
    message.warning('请选择交易所类型')
    return
  }
  if (!form.apiKey.trim() && !settings.value.editable.hasApiKey) {
    message.warning('请填写 API Key')
    return
  }
  if (!form.apiSecret.trim() && !settings.value.editable.hasApiSecret) {
    message.warning('请填写 API Secret')
    return
  }
  if (requiresPassword.value && !form.password.trim() && !settings.value.editable.hasPassword) {
    message.warning('使用 OKX 时，请填写 Password')
    return
  }
  saving.value = true
  try {
    const data = await saveUserExchangeSettings({
      editable: {
        exchangeType: form.exchangeType.trim(),
        apiKey: form.apiKey.trim(),
        apiSecret: form.apiSecret.trim(),
        password: requiresPassword.value ? form.password.trim() : '',
      },
    })
    settings.value = data
    syncForm()
    message.success('交易所设置已保存')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadForm()
})
</script>

<style scoped>
.page-card {
  min-height: 100%;
}

.form-grid {
  display: grid;
  gap: 0 16px;
}

.two-column {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

</style>
