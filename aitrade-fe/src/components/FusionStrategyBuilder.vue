<template>
  <a-space direction="vertical" size="middle" style="width: 100%">
    <a-card size="small" title="技术面节点">
      <a-space direction="vertical" size="middle" style="width: 100%">
        <a-alert type="info" show-icon message="可选择已有 K 线策略配置作为融合节点。" description="第一阶段支持 BTC 现货突破策略、BTC 现货趋势突破策略，以及内建技术面节点。" />
        <div v-for="(node, index) in localValue.klineNodes" :key="`kline-${index}`" class="builder-item">
          <div class="builder-item-row">
            <a-switch :checked="node.enabled" @change="updateKlineNode(index, 'enabled', $event)" />
            <a-select
              class="builder-select"
              :value="node.nodeType === 'builtin_technical' ? '__builtin_technical__' : node.strategyProfileId ?? undefined"
              placeholder="选择 K 线策略节点"
              @change="handleKlineProfileChange(index, $event)"
            >
              <a-select-option value="__builtin_technical__">内建技术面节点</a-select-option>
              <a-select-option v-for="item in klineProfiles" :key="item.id" :value="item.id">
                {{ item.name }}
              </a-select-option>
            </a-select>
            <a-input-number :value="node.weight" :min="0.01" :max="1" :step="0.01" @change="updateKlineNode(index, 'weight', Number($event || 0))" />
            <a-button danger @click="removeKlineNode(index)">删除</a-button>
          </div>
          <div class="builder-item-meta">
            <span v-if="node.requires_1h_timeframe" class="constraint-text">固定 1h / 依赖 4h 上下文</span>
            <span v-else>{{ node.strategyType || '未选择节点' }}</span>
          </div>
        </div>
        <a-button type="dashed" block @click="appendKlineNode">新增 K 线节点</a-button>
      </a-space>
    </a-card>

    <a-card size="small" title="信号源节点">
      <a-space direction="vertical" size="middle" style="width: 100%">
        <a-alert
          type="info"
          show-icon
          message="可选择已有信号源配置参与融合。"
          description="当前已接入运行时的信号源包括 trade_flow 与 indicator；其中 indicator 第一阶段支持 rsi / macd，每个融合策略最多启用一个 indicator 节点，且交易任务周期必须与 indicator 的主周期一致。"
        />
        <a-alert
          v-if="enabledIndicatorCount > 1"
          type="warning"
          show-icon
          message="当前已启用多个 indicator 节点"
          description="第一阶段每个融合策略最多只能启用一个 indicator 信号源节点；如果继续保留多个，启动交易任务时会被拒绝。"
        />
        <div v-for="(node, index) in localValue.signalSourceNodes" :key="`signal-${index}`" class="builder-item">
          <div class="builder-item-row signal-row">
            <a-switch :checked="node.enabled" @change="updateSignalNode(index, 'enabled', $event)" />
            <a-select class="builder-select" :value="node.signalSourceProfileId ?? undefined" placeholder="选择信号源" @change="handleSignalProfileChange(index, $event)">
              <a-select-option v-for="item in signalSourceProfiles" :key="item.id" :value="item.id">
                {{ item.name }}
              </a-select-option>
            </a-select>
            <a-input-number :value="node.weight" :min="0.01" :max="1" :step="0.01" @change="updateSignalNode(index, 'weight', Number($event || 0))" />
            <a-switch :checked="node.required" checked-children="必需" un-checked-children="可选" @change="updateSignalNode(index, 'required', $event)" />
            <a-button danger @click="removeSignalNode(index)">删除</a-button>
          </div>
          <div v-if="node.sourceType === 'trade_flow'" class="threshold-grid">
            <a-form-item label="买盘占比阈值">
              <a-input-number :value="node.thresholds.buy_ratio_threshold" :min="0.01" :max="1" :step="0.01" style="width: 100%" @change="updateSignalThreshold(index, 'buy_ratio_threshold', Number($event || 0))" />
            </a-form-item>
            <a-form-item label="卖盘占比阈值">
              <a-input-number :value="node.thresholds.sell_ratio_threshold" :min="0.01" :max="1" :step="0.01" style="width: 100%" @change="updateSignalThreshold(index, 'sell_ratio_threshold', Number($event || 0))" />
            </a-form-item>
            <a-form-item label="失衡阈值">
              <a-input-number :value="node.thresholds.imbalance_threshold" :min="0.01" :max="1" :step="0.01" style="width: 100%" @change="updateSignalThreshold(index, 'imbalance_threshold', Number($event || 0))" />
            </a-form-item>
          </div>
          <div class="builder-item-meta">{{ signalNodeSummary(node) }}</div>
        </div>
        <a-button type="dashed" block @click="appendSignalNode">新增信号源节点</a-button>
      </a-space>
    </a-card>

    <a-card size="small" title="过滤器与阈值">
      <div class="threshold-grid">
        <a-form-item label="最少可用节点数">
          <a-input-number :value="localValue.filters.min_available_nodes" :min="1" :step="1" style="width: 100%" @change="updateFilter('min_available_nodes', Number($event || 1))" />
        </a-form-item>
        <a-form-item label="允许降级运行">
          <a-switch :checked="localValue.filters.allow_degraded" @change="updateFilter('allow_degraded', $event)" />
        </a-form-item>
        <a-form-item label="最低综合置信度">
          <a-input-number :value="localValue.filters.min_confidence" :min="0.01" :max="1" :step="0.01" style="width: 100%" @change="updateFilter('min_confidence', Number($event || 0))" />
        </a-form-item>
        <a-form-item label="买入阈值">
          <a-input-number :value="localValue.filters.buy_threshold" :min="0.01" :max="1" :step="0.01" style="width: 100%" @change="updateFilter('buy_threshold', Number($event || 0))" />
        </a-form-item>
        <a-form-item label="卖出阈值">
          <a-input-number :value="localValue.filters.sell_threshold" :min="0.01" :max="1" :step="0.01" style="width: 100%" @change="updateFilter('sell_threshold', Number($event || 0))" />
        </a-form-item>
        <a-form-item label="单笔风险比例">
          <a-input-number :value="localValue.riskControls.default_risk_per_trade" :min="0.0001" :max="1" :step="0.0001" style="width: 100%" @change="updateRisk('default_risk_per_trade', Number($event || 0))" />
        </a-form-item>
      </div>
    </a-card>

    <a-card size="small" title="摘要预览">
      <a-descriptions :column="1" size="small" bordered>
        <a-descriptions-item label="K 线节点数">{{ enabledKlineCount }}</a-descriptions-item>
        <a-descriptions-item label="信号源节点数">{{ enabledSignalCount }}</a-descriptions-item>
        <a-descriptions-item label="indicator 节点数">{{ enabledIndicatorCount }}</a-descriptions-item>
        <a-descriptions-item label="最少可用节点数">{{ localValue.filters.min_available_nodes }}</a-descriptions-item>
        <a-descriptions-item label="固定周期约束">{{ requires1h ? '包含固定 1h 节点' : '无' }}</a-descriptions-item>
      </a-descriptions>
    </a-card>
  </a-space>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { SignalSourceProfile } from '@/types/signalSource'
import type { FusionKlineNode, FusionSignalSourceNode, FusionStrategyParams, StrategyProfile } from '@/types/strategy'

const props = defineProps<{
  modelValue: FusionStrategyParams
  klineProfiles: StrategyProfile[]
  signalSourceProfiles: SignalSourceProfile[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: FusionStrategyParams]
}>()

const localValue = computed(() => props.modelValue)
const enabledKlineCount = computed(() => localValue.value.klineNodes.filter((item) => item.enabled).length)
const enabledSignalCount = computed(() => localValue.value.signalSourceNodes.filter((item) => item.enabled).length)
const enabledIndicatorCount = computed(() => localValue.value.signalSourceNodes.filter((item) => item.enabled && item.sourceType === 'indicator').length)
const requires1h = computed(() => localValue.value.klineNodes.some((item) => item.enabled && item.requires_1h_timeframe))

function updateValue(nextValue: FusionStrategyParams) {
  emit('update:modelValue', nextValue)
}

function signalNodeSummary(node: FusionSignalSourceNode) {
  if (!node.sourceType) {
    return '未选择信号源。'
  }
  if (node.sourceType === 'trade_flow') {
    return 'trade_flow 已接入运行时；下方阈值用于解释买卖盘占比与成交额失衡结果。'
  }
  if (node.sourceType === 'indicator') {
    const indicatorKey = String(node.params?.indicator_key || '').trim().toUpperCase() || '未设置指标'
    const timeframe = String(node.params?.primary_timeframe || '').trim() || '未设置主周期'
    return `indicator 已接入运行时；当前指标 ${indicatorKey}，主周期 ${timeframe}；第一阶段每个融合策略最多启用一个 indicator 节点，且交易任务周期必须与这里的主周期一致。`
  }
  return `${node.sourceType} 当前仍建议先确认运行时支持情况。`
}

function appendKlineNode() {
  updateValue({
    ...localValue.value,
    klineNodes: [
      ...localValue.value.klineNodes,
      {
        nodeType: 'strategy_profile',
        strategyProfileId: null,
        strategyType: '',
        name: '',
        enabled: true,
        weight: 0.5,
        params: {},
        requires_1h_timeframe: false,
      },
    ],
  })
}

function removeKlineNode(index: number) {
  updateValue({
    ...localValue.value,
    klineNodes: localValue.value.klineNodes.filter((_, currentIndex) => currentIndex !== index),
  })
}

function handleKlineProfileChange(index: number, value: string | number) {
  const nextNodes = [...localValue.value.klineNodes]
  if (value === '__builtin_technical__') {
    nextNodes[index] = {
      ...nextNodes[index],
      nodeType: 'builtin_technical',
      strategyProfileId: null,
      strategyType: 'builtin_technical',
      name: '内建技术面节点',
      params: {},
      requires_1h_timeframe: false,
    }
  } else {
    const profile = props.klineProfiles.find((item) => item.id === Number(value))
    nextNodes[index] = {
      ...nextNodes[index],
      nodeType: 'strategy_profile',
      strategyProfileId: Number(value),
      strategyType: profile?.strategyType || '',
      name: profile?.name || '',
      params: profile?.params || {},
      requires_1h_timeframe: profile?.strategyType === 'btc_spot_trend_breakout',
    }
  }
  updateValue({ ...localValue.value, klineNodes: nextNodes })
}

function updateKlineNode(index: number, key: keyof FusionKlineNode, value: unknown) {
  const nextNodes = [...localValue.value.klineNodes]
  nextNodes[index] = {
    ...nextNodes[index],
    [key]: value,
  }
  updateValue({ ...localValue.value, klineNodes: nextNodes })
}

function appendSignalNode() {
  updateValue({
    ...localValue.value,
    signalSourceNodes: [
      ...localValue.value.signalSourceNodes,
      {
        signalSourceProfileId: null,
        sourceType: '',
        name: '',
        enabled: true,
        required: false,
        weight: 0.4,
        thresholds: {
          buy_ratio_threshold: 0.55,
          sell_ratio_threshold: 0.45,
          imbalance_threshold: 0.08,
        },
        params: {},
      },
    ],
  })
}

function removeSignalNode(index: number) {
  updateValue({
    ...localValue.value,
    signalSourceNodes: localValue.value.signalSourceNodes.filter((_, currentIndex) => currentIndex !== index),
  })
}

function handleSignalProfileChange(index: number, value: number) {
  const profile = props.signalSourceProfiles.find((item) => item.id === Number(value))
  const nextNodes = [...localValue.value.signalSourceNodes]
  nextNodes[index] = {
    ...nextNodes[index],
    signalSourceProfileId: Number(value),
    sourceType: profile?.sourceType || '',
    name: profile?.name || '',
    params: profile?.params || {},
  }
  updateValue({ ...localValue.value, signalSourceNodes: nextNodes })
}

function updateSignalNode(index: number, key: keyof FusionSignalSourceNode, value: unknown) {
  const nextNodes = [...localValue.value.signalSourceNodes]
  nextNodes[index] = {
    ...nextNodes[index],
    [key]: value,
  }
  updateValue({ ...localValue.value, signalSourceNodes: nextNodes })
}

function updateSignalThreshold(index: number, key: keyof FusionSignalSourceNode['thresholds'], value: number) {
  const nextNodes = [...localValue.value.signalSourceNodes]
  nextNodes[index] = {
    ...nextNodes[index],
    thresholds: {
      ...nextNodes[index].thresholds,
      [key]: value,
    },
  }
  updateValue({ ...localValue.value, signalSourceNodes: nextNodes })
}

function updateFilter(key: keyof FusionStrategyParams['filters'], value: boolean | number) {
  updateValue({
    ...localValue.value,
    filters: {
      ...localValue.value.filters,
      [key]: value,
    },
  })
}

function updateRisk(key: keyof FusionStrategyParams['riskControls'], value: number) {
  updateValue({
    ...localValue.value,
    riskControls: {
      ...localValue.value.riskControls,
      [key]: value,
    },
  })
}
</script>

<style scoped>
.builder-item {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 12px;
}

.builder-item-row {
  display: grid;
  grid-template-columns: auto minmax(220px, 1fr) 120px auto;
  gap: 12px;
  align-items: center;
}

.signal-row {
  grid-template-columns: auto minmax(220px, 1fr) 120px auto auto;
}

.builder-select {
  width: 100%;
}

.builder-item-meta {
  margin-top: 8px;
  color: #8c8c8c;
  font-size: 12px;
}

.constraint-text {
  color: #d46b08;
}

.threshold-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0 16px;
}
</style>
