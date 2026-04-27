<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="这里维护的是交易运行相关的持久化参数。"
        description="这些参数会作用于后续新启动的交易任务，不会回溯修改已运行任务。"
      />

      <a-card title="交易设置" size="small" :loading="loading">
        <a-form layout="vertical">
          <div class="switch-grid">
            <a-form-item label="持久化当前持仓">
              <a-switch v-model:checked="form.persistPosition" />
            </a-form-item>
            <a-form-item label="启动时恢复持仓">
              <a-switch v-model:checked="form.restorePositionOnStartup" />
            </a-form-item>
          </div>

          <a-space>
            <a-button @click="loadForm">重置</a-button>
            <a-button type="primary" :loading="saving" @click="submitForm">保存交易设置</a-button>
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
  persistPosition: true,
  restorePositionOnStartup: false,
})

function syncForm() {
  form.persistPosition = settings.editable.persistPosition
  form.restorePositionOnStartup = settings.editable.restorePositionOnStartup
}

async function loadForm() {
  await loadSettings()
  syncForm()
}

async function submitForm() {
  await saveEditable({
    // 这些开关只影响后续新启动任务，但保存接口仍然要求提交完整 editable。
    ...settings.editable,
    persistPosition: form.persistPosition,
    restorePositionOnStartup: form.restorePositionOnStartup,
  })
  syncForm()
  message.success('交易设置已保存')
}

onMounted(loadForm)
</script>

<style scoped>
.page-card {
  min-height: 100%;
}

.switch-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0 16px;
}
</style>
