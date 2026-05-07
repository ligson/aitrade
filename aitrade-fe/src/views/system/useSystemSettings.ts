import { reactive, ref } from 'vue'

import { fetchSystemSettings, saveSystemSettings } from '@/api/system'
import type { SystemSettings, SystemSettingsEditable } from '@/types/system'

function createEmptySettings(): SystemSettings {
  // 这里只提供首屏渲染和响应式结构稳定所需的空骨架；
  // 真正的生效值始终以后端 loadSettings() 返回的数据为准。
  return {
    readonly: {
      dataRootDir: '',
      dataRootMode: 'managed',
      tradeDatabaseUrl: '',
      backtestDataDir: '',
      freqtradeUserDataDir: '',
      appLogDir: '',
    },
    editable: {
      gptProvider: 'deepseek',
      gptModel: '',
      gptApiKey: '',
      gptBaseUrl: '',
      hasGptApiKey: false,
      gptApiKeyMasked: '',
      persistPosition: true,
      restorePositionOnStartup: false,
      tradeTaskDefaultFeeRate: 0,
      tradeTaskDefaultSlippageRate: 0,
      tradeTaskDefaultDailyLossStopEnabled: false,
      tradeTaskDefaultDailyLossStopThreshold: 100,
      tradeFlowFeedEnabled: true,
      tradeFlowFeedFreshnessSeconds: 120,
      tradeFlowFeedLookbackTrades: 200,
      supportedSymbols: [],
      supportedTimeframes: [],
      defaultSymbol: '',
      defaultTimeframe: '',
      downloadTimerange: '',
      dataFormatOhlcv: 'jsongz',
      exportArchiveFormat: 'zip',
    },
    meta: {
      id: 0,
      name: '',
      description: '',
      schemaVersion: 1,
      updatedAt: '',
    },
  }
}

export function normalizeStringArray(values: string[]) {
  // 统一做 trim、去重和保序，避免 tags 输入在页面展示与后端保存时出现不一致。
  const result: string[] = []
  const seen = new Set<string>()
  for (const item of values) {
    const text = String(item || '').trim()
    if (!text || seen.has(text)) {
      continue
    }
    seen.add(text)
    result.push(text)
  }
  return result
}

export function useSystemSettings() {
  const loading = ref(false)
  const saving = ref(false)
  const settings = reactive<SystemSettings>(createEmptySettings())

  function applySettings(data: SystemSettings) {
    // 保持 reactive 对象引用稳定，避免各页面已经绑定的 settings 引用失效。
    Object.assign(settings.readonly, data.readonly)
    Object.assign(settings.editable, data.editable)
    Object.assign(settings.meta, data.meta)
  }

  async function loadSettings() {
    loading.value = true
    try {
      const data = await fetchSystemSettings()
      applySettings(data)
      return data
    } finally {
      loading.value = false
    }
  }

  async function saveEditable(editable: SystemSettingsEditable) {
    // 后端保存语义是整份 editable 覆盖，而不是局部 patch；
    // 因此各个子页面提交时都必须带上其他页面当前值，避免互相覆盖丢字段。
    saving.value = true
    try {
      const data = await saveSystemSettings({ editable })
      applySettings(data)
      return data
    } finally {
      saving.value = false
    }
  }

  return {
    loading,
    saving,
    settings,
    applySettings,
    loadSettings,
    saveEditable,
  }
}
