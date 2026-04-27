<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="这里维护的是可通过网页管理的 AI 参数。"
        description="保存后会影响后续新发起的回测与新启动的交易任务，不会回溯修改已运行任务。"
      />

      <a-card title="AI 设置" size="small" :loading="loading">
        <a-form layout="vertical">
          <div class="form-grid two-column">
            <a-form-item label="提供方">
              <a-select v-model:value="form.gptProvider">
                <a-select-option value="deepseek">deepseek</a-select-option>
                <a-select-option value="openai">openai</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="模型名称">
              <a-input v-model:value="form.gptModel" placeholder="如 deepseek-chat" />
            </a-form-item>
            <a-form-item label="API Key">
              <a-input-password v-model:value="form.gptApiKey" placeholder="未修改则保留当前密钥" />
            </a-form-item>
            <a-form-item label="Base URL（可选）">
              <a-input v-model:value="form.gptBaseUrl" placeholder="留空时按 provider 自动选择默认端点" />
            </a-form-item>
          </div>

          <a-space>
            <a-button @click="loadForm">重置</a-button>
            <a-button type="primary" :loading="saving" @click="submitForm">保存 AI 设置</a-button>
          </a-space>
        </a-form>
      </a-card>
    </a-space>
  </a-card>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import { onMounted, reactive } from 'vue'

import { useSystemSettings } from './useSystemSettings'

const { loading, saving, settings, loadSettings, saveEditable } = useSystemSettings()

const form = reactive({
  gptProvider: 'deepseek',
  gptModel: '',
  gptApiKey: '',
  gptBaseUrl: '',
})

function syncForm() {
  form.gptProvider = settings.editable.gptProvider
  form.gptModel = settings.editable.gptModel
  // 后端不会回传明文 key，这里只把掩码态回填到输入框，用来提示“系统已保存过密钥”。
  form.gptApiKey = settings.editable.gptApiKeyMasked || ''
  form.gptBaseUrl = settings.editable.gptBaseUrl || ''
}

async function loadForm() {
  await loadSettings()
  syncForm()
}

async function submitForm() {
  if (!form.gptModel.trim()) {
    message.warning('请填写 GPT 模型名称')
    return
  }
  // 首次保存时必须输入真实 key；
  // 如果后端已标记存在 key，则空值或掩码值都表示“保留旧密钥”。
  if (!form.gptApiKey.trim() && !settings.editable.hasGptApiKey) {
    message.warning('请填写 GPT API Key')
    return
  }
  await saveEditable({
    // 保存接口按整份 editable 覆盖，AI 页面也需要带上交易/数据页当前值。
    ...settings.editable,
    gptProvider: form.gptProvider,
    gptModel: form.gptModel.trim(),
    gptApiKey: form.gptApiKey.trim(),
    gptBaseUrl: form.gptBaseUrl.trim(),
  })
  // 保存后以后端回写的掩码态和标准化结果为准，避免继续显示本地临时输入态。
  syncForm()
  message.success('AI 设置已保存')
}

onMounted(loadForm)
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
