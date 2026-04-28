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

          <a-divider orientation="left">交易任务默认参数</a-divider>
          <div class="switch-grid">
            <a-form-item label="默认手续费率">
              <a-input-number v-model:value="form.tradeTaskDefaultFeeRate" :min="0" :step="0.0001" style="width: 100%" />
            </a-form-item>
            <a-form-item label="默认滑点率">
              <a-input-number v-model:value="form.tradeTaskDefaultSlippageRate" :min="0" :step="0.0001" style="width: 100%" />
            </a-form-item>
            <a-form-item label="默认启用单日亏损停机">
              <a-switch v-model:checked="form.tradeTaskDefaultDailyLossStopEnabled" />
            </a-form-item>
            <a-form-item label="默认单日亏损停机阈值">
              <a-input-number
                v-model:value="form.tradeTaskDefaultDailyLossStopThreshold"
                :min="0"
                :step="1"
                :disabled="!form.tradeTaskDefaultDailyLossStopEnabled"
                style="width: 100%"
              />
            </a-form-item>
          </div>

          <a-divider orientation="left">成交流 feed 默认参数</a-divider>
          <div class="switch-grid">
            <a-form-item label="启用成交流 feed">
              <a-switch v-model:checked="form.tradeFlowFeedEnabled" />
            </a-form-item>
            <a-form-item label="feed 新鲜度秒数">
              <a-input-number v-model:value="form.tradeFlowFeedFreshnessSeconds" :min="1" :step="1" style="width: 100%" />
            </a-form-item>
            <a-form-item label="回看成交数">
              <a-input-number v-model:value="form.tradeFlowFeedLookbackTrades" :min="1" :step="10" style="width: 100%" />
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
  tradeTaskDefaultFeeRate: 0,
  tradeTaskDefaultSlippageRate: 0,
  tradeTaskDefaultDailyLossStopEnabled: false,
  tradeTaskDefaultDailyLossStopThreshold: 100,
  tradeFlowFeedEnabled: true,
  tradeFlowFeedFreshnessSeconds: 120,
  tradeFlowFeedLookbackTrades: 200,
})

function syncForm() {
  form.persistPosition = settings.editable.persistPosition
  form.restorePositionOnStartup = settings.editable.restorePositionOnStartup
  form.tradeTaskDefaultFeeRate = settings.editable.tradeTaskDefaultFeeRate
  form.tradeTaskDefaultSlippageRate = settings.editable.tradeTaskDefaultSlippageRate
  form.tradeTaskDefaultDailyLossStopEnabled = settings.editable.tradeTaskDefaultDailyLossStopEnabled
  form.tradeTaskDefaultDailyLossStopThreshold = settings.editable.tradeTaskDefaultDailyLossStopThreshold
  form.tradeFlowFeedEnabled = settings.editable.tradeFlowFeedEnabled
  form.tradeFlowFeedFreshnessSeconds = settings.editable.tradeFlowFeedFreshnessSeconds
  form.tradeFlowFeedLookbackTrades = settings.editable.tradeFlowFeedLookbackTrades
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
    tradeTaskDefaultFeeRate: form.tradeTaskDefaultFeeRate,
    tradeTaskDefaultSlippageRate: form.tradeTaskDefaultSlippageRate,
    tradeTaskDefaultDailyLossStopEnabled: form.tradeTaskDefaultDailyLossStopEnabled,
    tradeTaskDefaultDailyLossStopThreshold: form.tradeTaskDefaultDailyLossStopThreshold,
    tradeFlowFeedEnabled: form.tradeFlowFeedEnabled,
    tradeFlowFeedFreshnessSeconds: form.tradeFlowFeedFreshnessSeconds,
    tradeFlowFeedLookbackTrades: form.tradeFlowFeedLookbackTrades,
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
