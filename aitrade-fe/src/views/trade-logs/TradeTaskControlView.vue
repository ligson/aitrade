<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="这里统一管理交易任务的配置、运行和排障。"
        description="每条任务配置都会绑定独立 runner；任务启动时会冻结本次运行快照，之后再改配置不会影响已运行任务。当前支持不同交易对并发运行，同一交易对仍不支持并发。"
      />
      <a-alert
        v-if="invalidStrategyProfileCount > 0 || invalidReferenceProfiles.length > 0"
        type="warning"
        show-icon
        :message="strategyWarningMessage"
        :description="strategyWarningDescription"
      >
        <template #action>
          <a-button size="small" @click="goToStrategies">去策略配置清理</a-button>
        </template>
      </a-alert>

      <div class="overview-grid">
        <a-card v-for="item in overviewCards" :key="item.key" size="small" class="overview-card">
          <div class="overview-label">{{ item.label }}</div>
          <div class="overview-value">{{ item.value }}</div>
          <div class="overview-help">{{ item.help }}</div>
        </a-card>
      </div>

      <a-card size="small" title="任务中心">
        <a-space direction="vertical" size="middle" style="width: 100%">
          <div class="action-bar">
            <div class="action-tip">列表里同时展示配置态与运行态；点击概览、配置、运行可以在同一个任务上下文里继续操作。</div>
            <a-space wrap>
              <a-button type="primary" @click="openCreate">新增任务配置</a-button>
              <a-button :loading="tradeTaskLoading" @click="reloadAll">刷新状态</a-button>
              <a-button @click="goToTaskLogs()">查看任务日志</a-button>
            </a-space>
          </div>

          <a-table :data-source="runnerRows" :columns="columns" row-key="runnerName" :loading="tradeTaskLoading" :pagination="false" :scroll="{ x: 'max-content' }">
            <template #bodyCell="{ column, record, text }">
              <template v-if="column.key === 'name'">
                <div>{{ record.profile?.name || record.profileName || '-' }}</div>
                <div v-if="record.profile?.description" class="cell-meta">{{ record.profile.description }}</div>
                <div v-if="record.isOrphan" class="cell-meta cell-meta-warning">这是一条没有对应任务配置的运行态残留记录。</div>
              </template>
              <template v-else-if="column.key === 'ownerUserId'">
                {{ formatOwnerUserId(record.ownerUserId) }}
              </template>
              <template v-else-if="column.key === 'strategyProfileName'">
                <div>{{ record.missingStrategyProfile ? '关联策略异常或已删除' : (record.profile?.strategyProfileName || '-') }}</div>
                <div v-if="record.missingStrategyProfile" class="cell-meta cell-meta-warning">请先修复策略引用，再启动或更新这条任务配置。</div>
                <div v-else-if="record.strategyProfile?.fusionSummary" class="cell-meta">{{ formatFusionSummary(record.strategyProfile.fusionSummary) }}</div>
              </template>
              <template v-else-if="column.key === 'tradeMode'">
                <a-tag :color="tradeModeTagColor(resolveRowTradeMode(record))">{{ tradeModeLabel(resolveRowTradeMode(record)) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'enabled'">
                <a-tag :color="record.profile?.enabled ? 'green' : 'default'">{{ record.profile?.enabled ? '启用' : '停用' }}</a-tag>
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'runId'">
                {{ record.runId ?? '-' }}
              </template>
              <template v-else-if="column.key === 'lastHeartbeatAt' || column.key === 'nextRunAt' || column.key === 'updatedAt'">
                {{ formatDateTime(text) }}
              </template>
              <template v-else-if="column.key === 'lastError'">
                <div class="cell-text">{{ text || '-' }}</div>
              </template>
              <template v-else-if="column.key === 'actions'">
                <a-space size="small" wrap>
                  <a-button type="link" @click="openOverview(record)">概览</a-button>
                  <a-button type="link" :disabled="!record.profile" @click="openConfig(record)">配置</a-button>
                  <a-button type="link" @click="openRuntime(record)">运行</a-button>
                  <a-popconfirm :title="startConfirmTitle(record)" ok-text="启动" cancel-text="取消" @confirm="handleStartTradeTask(record)">
                    <a-button type="link" :disabled="!canStartRecord(record)" :loading="startLoadingRunner === record.runnerName">开始运行</a-button>
                  </a-popconfirm>
                  <a-popconfirm title="确认停止这个交易任务吗？" ok-text="停止" cancel-text="取消" @confirm="handleStopTradeTask(record)">
                    <a-button
                      type="link"
                      danger
                      :disabled="!record.canStop || record.status === 'stop_requested'"
                      :loading="stopLoadingRunner === record.runnerName"
                    >
                      停止运行
                    </a-button>
                  </a-popconfirm>
                </a-space>
              </template>
              <template v-else>
                {{ displayText(text) }}
              </template>
            </template>
          </a-table>
        </a-space>
      </a-card>
    </a-space>

    <a-drawer v-model:open="detailOpen" :title="detailDrawerTitle" width="960" destroy-on-close>
      <template #extra>
        <a-space v-if="detailMode === 'detail' && detailRow">
          <a-button size="small" @click="goToTaskLogs(detailRow)">任务日志</a-button>
          <a-button size="small" :disabled="!detailRow.runId" @click="goToTradeLogs(detailRow)">交易日志</a-button>
        </a-space>
      </template>

      <template v-if="detailMode === 'create'">
        <a-space direction="vertical" size="middle" style="width: 100%">
          <a-alert
            type="info"
            show-icon
            message="新增后即可在同一个任务中心里继续查看运行状态和日志。"
            description="这里保存的是任务级配置；系统级密钥、代理和持久化配置仍由后端配置与系统设置维护。"
          />
          <div class="tab-action-bar">
            <div class="action-tip">保存后系统会自动分配独立 runner，并在列表中显示这条新任务。</div>
            <a-space wrap>
              <a-button @click="closeDetail">取消</a-button>
              <a-button type="primary" :loading="saveLoading" @click="submitForm">保存配置</a-button>
            </a-space>
          </div>
          <div class="detail-section">
            <a-form layout="vertical">
              <a-form-item label="配置名称">
                <a-input v-model:value="form.name" />
              </a-form-item>
              <a-form-item label="描述">
                <a-input v-model:value="form.description" />
              </a-form-item>
              <a-form-item label="策略配置">
                <a-select v-model:value="form.strategyProfileId" show-search :filter-option="filterSelectOption">
                  <a-select-option v-for="item in enabledStrategyProfiles" :key="item.id" :value="item.id">
                    {{ item.name }}
                  </a-select-option>
                </a-select>
                <div v-if="selectedStrategyProfile?.fusionSummary" class="field-help">
                  {{ formatFusionSummary(selectedStrategyProfile.fusionSummary) }}
                </div>
              </a-form-item>
              <div class="form-grid">
                <a-form-item label="交易对">
                  <a-input v-model:value="form.symbol" placeholder="如 BTC/USDT" />
                </a-form-item>
                <a-form-item label="周期">
                  <a-select v-model:value="form.timeframe">
                    <a-select-option v-for="item in supportedTimeframes" :key="item" :value="item">
                      {{ item }}
                    </a-select-option>
                  </a-select>
                </a-form-item>
                <a-form-item label="K线数量">
                  <a-input-number v-model:value="form.tradeLimit" :min="1" style="width: 100%" />
                </a-form-item>
              </div>
              <a-form-item label="启用">
                <a-switch v-model:checked="form.enabled" />
              </a-form-item>
              <a-form-item label="交易方式">
                <a-select v-model:value="form.tradeMode">
                  <a-select-option value="live">真实交易</a-select-option>
                  <a-select-option value="sandbox">沙盒交易</a-select-option>
                  <a-select-option value="paper">纸上交易</a-select-option>
                </a-select>
                <div class="mode-help">真实交易：真实行情，真实下单；沙盒交易：沙盒行情，沙盒下单；纸上交易：真实行情，不真实下单。</div>
              </a-form-item>
              <div class="form-grid">
                <a-form-item label="手续费率">
                  <a-input-number v-model:value="form.feeRate" :min="0" :step="0.0001" style="width: 100%" />
                </a-form-item>
                <a-form-item label="滑点率">
                  <a-input-number v-model:value="form.slippageRate" :min="0" :step="0.0001" style="width: 100%" />
                </a-form-item>
                <a-form-item label="启用单日亏损停机">
                  <a-switch v-model:checked="form.dailyLossStopEnabled" />
                </a-form-item>
                <a-form-item label="单日亏损停机阈值">
                  <a-input-number
                    v-model:value="form.dailyLossStopThreshold"
                    :min="0"
                    :step="1"
                    :disabled="!form.dailyLossStopEnabled"
                    style="width: 100%"
                  />
                </a-form-item>
              </div>
            </a-form>
          </div>
        </a-space>
      </template>

      <template v-else-if="detailRow">
        <a-tabs v-model:activeKey="detailTab">
          <a-tab-pane key="overview" tab="概览">
            <a-space direction="vertical" size="middle" style="width: 100%">
              <a-descriptions :column="2" bordered size="small">
                <a-descriptions-item label="配置名称">{{ detailRow.profile?.name || detailRow.profileName || '-' }}</a-descriptions-item>
                <a-descriptions-item v-if="auth.isAdmin" label="所属用户">{{ formatOwnerUserId(detailRow.ownerUserId) }}</a-descriptions-item>
                <a-descriptions-item label="Runner">{{ detailRow.runnerName }}</a-descriptions-item>
                <a-descriptions-item label="状态">
                  <a-tag :color="statusColor(detailRow.status)">{{ statusLabel(detailRow.status) }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="是否运行中">{{ detailRow.isRunning ? '是' : '否' }}</a-descriptions-item>
                <a-descriptions-item label="任务配置状态">{{ detailRow.profile?.enabled ? '启用' : (detailRow.profile ? '停用' : '无对应配置') }}</a-descriptions-item>
                <a-descriptions-item label="策略配置">{{ detailRow.missingStrategyProfile ? '关联策略异常或已删除' : (detailRow.profile?.strategyProfileName || '-') }}</a-descriptions-item>
                <a-descriptions-item label="策略类型">{{ strategyTypeLabel(detailRow.strategyType || detailRow.profile?.strategyType || '') }}</a-descriptions-item>
                <a-descriptions-item label="交易对">{{ detailRow.symbol || detailRow.profile?.symbol || '-' }}</a-descriptions-item>
                <a-descriptions-item label="周期">{{ detailRow.timeframe || detailRow.profile?.timeframe || '-' }}</a-descriptions-item>
                <a-descriptions-item label="模式">{{ tradeModeLabel(resolveRowTradeMode(detailRow)) }}</a-descriptions-item>
                <a-descriptions-item label="运行实例 ID">{{ detailRow.runId ?? '-' }}</a-descriptions-item>
                <a-descriptions-item label="启动人">{{ detailRow.startedBy || '-' }}</a-descriptions-item>
                <a-descriptions-item label="启动时间">{{ formatDateTime(detailRow.startedAt) }}</a-descriptions-item>
                <a-descriptions-item label="停止时间">{{ formatDateTime(detailRow.stoppedAt) }}</a-descriptions-item>
                <a-descriptions-item label="停止请求时间">{{ formatDateTime(detailRow.stopRequestedAt) }}</a-descriptions-item>
                <a-descriptions-item label="最近心跳">{{ formatDateTime(detailRow.lastHeartbeatAt) }}</a-descriptions-item>
                <a-descriptions-item label="最近周期开始">{{ formatDateTime(detailRow.lastCycleStartedAt) }}</a-descriptions-item>
                <a-descriptions-item label="最近周期完成">{{ formatDateTime(detailRow.lastCycleFinishedAt) }}</a-descriptions-item>
                <a-descriptions-item label="下次运行时间">{{ formatDateTime(detailRow.nextRunAt) }}</a-descriptions-item>
                <a-descriptions-item label="配置更新时间">{{ formatDateTime(detailRow.profile?.updatedAt || detailRow.updatedAt) }}</a-descriptions-item>
                <a-descriptions-item v-if="detailRow.profile" label="配置描述" :span="2">{{ detailRow.profile.description || '-' }}</a-descriptions-item>
              </a-descriptions>

              <a-alert v-if="detailRow.lastError" type="error" show-icon :message="detailRow.lastError" />
              <a-alert v-if="detailRow.isOrphan" type="warning" show-icon message="当前运行态没有对应任务配置，无法进入配置编辑。" />
              <a-alert
                v-else-if="detailRow.missingStrategyProfile"
                type="warning"
                show-icon
                message="这条任务配置引用了异常或已删除的策略，已自动禁止启动。"
                description="请先前往策略配置页修复，再回到任务中心更新这条任务配置。"
              />

              <a-card v-if="detailRow.strategyProfile?.fusionSummary" size="small" title="融合策略摘要">
                <a-descriptions :column="2" bordered size="small">
                  <a-descriptions-item label="摘要" :span="2">{{ formatFusionSummary(detailRow.strategyProfile.fusionSummary) }}</a-descriptions-item>
                  <a-descriptions-item label="K 线节点数">{{ detailRow.strategyProfile.fusionSummary.klineNodeCount }}</a-descriptions-item>
                  <a-descriptions-item label="信号源节点数">{{ detailRow.strategyProfile.fusionSummary.signalSourceNodeCount }}</a-descriptions-item>
                  <a-descriptions-item label="最少可用节点数">{{ detailRow.strategyProfile.fusionSummary.minAvailableNodes }}</a-descriptions-item>
                  <a-descriptions-item label="允许降级运行">{{ detailRow.strategyProfile.fusionSummary.allowDegraded ? '是' : '否' }}</a-descriptions-item>
                  <a-descriptions-item label="固定周期约束" :span="2">{{ detailRow.strategyProfile.fusionSummary.requires1hTimeframe ? '包含固定 1h 节点' : '无' }}</a-descriptions-item>
                </a-descriptions>
              </a-card>
            </a-space>
          </a-tab-pane>

          <a-tab-pane key="config" tab="配置" :disabled="!detailRow.profile">
            <template v-if="detailRow.profile">
              <a-space direction="vertical" size="middle" style="width: 100%">
                <a-alert
                  v-if="detailRow.missingStrategyProfile"
                  type="warning"
                  show-icon
                  message="当前配置引用的策略异常或已删除，请先重新选择可用策略后再保存。"
                />
                <div class="tab-action-bar">
                  <div class="action-tip">这里修改的是任务级配置；保存后会影响后续启动，但不会回写当前已运行任务的快照。</div>
                  <a-space wrap>
                    <a-button @click="openOverview(detailRow)">返回概览</a-button>
                    <a-popconfirm
                      title="确认删除这套交易任务配置吗？"
                      ok-text="删除"
                      cancel-text="取消"
                      @confirm="removeProfile(detailRow.profile.id)"
                    >
                      <a-button danger :disabled="!canDeleteCurrentProfile">删除配置</a-button>
                    </a-popconfirm>
                    <a-button type="primary" :loading="saveLoading" @click="submitForm">保存配置</a-button>
                  </a-space>
                </div>
                <div v-if="!canDeleteCurrentProfile" class="action-tip">任务处于启动中、运行中或停止中时，需先停止运行后再删除配置。</div>
                <div class="detail-section">
                  <a-form layout="vertical">
                    <a-form-item label="配置名称">
                      <a-input v-model:value="form.name" />
                    </a-form-item>
                    <a-form-item label="描述">
                      <a-input v-model:value="form.description" />
                    </a-form-item>
                    <a-form-item label="策略配置">
                      <a-select v-model:value="form.strategyProfileId" show-search :filter-option="filterSelectOption">
                        <a-select-option v-for="item in enabledStrategyProfiles" :key="item.id" :value="item.id">
                          {{ item.name }}
                        </a-select-option>
                      </a-select>
                      <div v-if="selectedStrategyProfile?.fusionSummary" class="field-help">
                        {{ formatFusionSummary(selectedStrategyProfile.fusionSummary) }}
                      </div>
                    </a-form-item>
                    <div class="form-grid">
                      <a-form-item label="交易对">
                        <a-input v-model:value="form.symbol" placeholder="如 BTC/USDT" />
                      </a-form-item>
                      <a-form-item label="周期">
                        <a-select v-model:value="form.timeframe">
                          <a-select-option v-for="item in supportedTimeframes" :key="item" :value="item">
                            {{ item }}
                          </a-select-option>
                        </a-select>
                      </a-form-item>
                      <a-form-item label="K线数量">
                        <a-input-number v-model:value="form.tradeLimit" :min="1" style="width: 100%" />
                      </a-form-item>
                    </div>
                    <a-form-item label="启用">
                      <a-switch v-model:checked="form.enabled" />
                    </a-form-item>
                    <a-form-item label="交易方式">
                      <a-select v-model:value="form.tradeMode">
                        <a-select-option value="live">真实交易</a-select-option>
                        <a-select-option value="sandbox">沙盒交易</a-select-option>
                        <a-select-option value="paper">纸上交易</a-select-option>
                      </a-select>
                      <div class="mode-help">真实交易：真实行情，真实下单；沙盒交易：沙盒行情，沙盒下单；纸上交易：真实行情，不真实下单。</div>
                    </a-form-item>
                    <div class="form-grid">
                      <a-form-item label="手续费率">
                        <a-input-number v-model:value="form.feeRate" :min="0" :step="0.0001" style="width: 100%" />
                      </a-form-item>
                      <a-form-item label="滑点率">
                        <a-input-number v-model:value="form.slippageRate" :min="0" :step="0.0001" style="width: 100%" />
                      </a-form-item>
                      <a-form-item label="启用单日亏损停机">
                        <a-switch v-model:checked="form.dailyLossStopEnabled" />
                      </a-form-item>
                      <a-form-item label="单日亏损停机阈值">
                        <a-input-number
                          v-model:value="form.dailyLossStopThreshold"
                          :min="0"
                          :step="1"
                          :disabled="!form.dailyLossStopEnabled"
                          style="width: 100%"
                        />
                      </a-form-item>
                    </div>
                  </a-form>
                </div>
              </a-space>
            </template>
            <a-empty v-else description="当前运行态没有对应任务配置" />
          </a-tab-pane>

          <a-tab-pane key="runtime" tab="运行">
            <a-space direction="vertical" size="middle" style="width: 100%">
              <div class="tab-action-bar">
                <div class="action-tip">这里展示的是当前 runner 的实时运行态和最近事件；历史事件与成交结果请通过右侧按钮跳转查看。</div>
                <a-space wrap>
                  <a-popconfirm :title="startConfirmTitle(detailRow)" ok-text="启动" cancel-text="取消" @confirm="handleStartTradeTask(detailRow)">
                    <a-button type="primary" :disabled="!canStartRecord(detailRow)" :loading="startLoadingRunner === detailRow.runnerName">开始运行</a-button>
                  </a-popconfirm>
                  <a-popconfirm title="确认停止这个交易任务吗？" ok-text="停止" cancel-text="取消" @confirm="handleStopTradeTask(detailRow)">
                    <a-button
                      danger
                      :disabled="!detailRow.canStop || detailRow.status === 'stop_requested'"
                      :loading="stopLoadingRunner === detailRow.runnerName"
                    >
                      停止运行
                    </a-button>
                  </a-popconfirm>
                  <a-button @click="goToTaskLogs(detailRow)">查看任务日志</a-button>
                  <a-button :disabled="!detailRow.runId" @click="goToTradeLogs(detailRow)">查看交易日志</a-button>
                </a-space>
              </div>

              <a-descriptions :column="2" bordered size="small">
                <a-descriptions-item label="Runner">{{ detailRow.runnerName }}</a-descriptions-item>
                <a-descriptions-item label="运行实例 ID">{{ detailRow.runId ?? '-' }}</a-descriptions-item>
                <a-descriptions-item label="当前状态">
                  <a-tag :color="statusColor(detailRow.status)">{{ statusLabel(detailRow.status) }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="启动人">{{ detailRow.startedBy || '-' }}</a-descriptions-item>
                <a-descriptions-item label="最近心跳">{{ formatDateTime(detailRow.lastHeartbeatAt) }}</a-descriptions-item>
                <a-descriptions-item label="下次运行时间">{{ formatDateTime(detailRow.nextRunAt) }}</a-descriptions-item>
                <a-descriptions-item label="最近周期开始">{{ formatDateTime(detailRow.lastCycleStartedAt) }}</a-descriptions-item>
                <a-descriptions-item label="最近周期完成">{{ formatDateTime(detailRow.lastCycleFinishedAt) }}</a-descriptions-item>
              </a-descriptions>

              <a-alert v-if="detailRow.lastError" type="error" show-icon :message="detailRow.lastError" />

              <a-card v-if="detailRow.currentRun" size="small" title="当前运行快照">
                <a-space direction="vertical" size="middle" style="width: 100%">
                  <a-descriptions :column="2" bordered size="small">
                    <a-descriptions-item label="配置名称">{{ detailRow.currentRun.profileName }}</a-descriptions-item>
                    <a-descriptions-item v-if="auth.isAdmin" label="所属用户">{{ formatOwnerUserId(detailRow.currentRun.ownerUserId) }}</a-descriptions-item>
                    <a-descriptions-item label="策略配置 ID">{{ detailRow.currentRun.strategyProfileId ?? '-' }}</a-descriptions-item>
                    <a-descriptions-item label="交易对">{{ detailRow.currentRun.symbol }}</a-descriptions-item>
                    <a-descriptions-item label="周期">{{ detailRow.currentRun.timeframe }}</a-descriptions-item>
                    <a-descriptions-item label="模式">{{ tradeModeLabel(resolveTradeMode(detailRow.currentRun)) }}</a-descriptions-item>
                    <a-descriptions-item label="K 线数量">{{ detailRow.currentRun.tradeLimit }}</a-descriptions-item>
                    <a-descriptions-item label="手续费率">{{ formatRate(detailRow.currentRun.feeRate) }}</a-descriptions-item>
                    <a-descriptions-item label="滑点率">{{ formatRate(detailRow.currentRun.slippageRate) }}</a-descriptions-item>
                    <a-descriptions-item label="单日亏损停机">{{ detailRow.currentRun.dailyLossStopEnabled ? '已启用' : '关闭' }}</a-descriptions-item>
                    <a-descriptions-item label="单日亏损阈值">{{ formatNumber(detailRow.currentRun.dailyLossStopThreshold) }}</a-descriptions-item>
                    <a-descriptions-item label="策略类型">{{ strategyTypeLabel(detailRow.currentRun.strategyType) }}</a-descriptions-item>
                    <a-descriptions-item label="创建人">{{ detailRow.currentRun.createdBy }}</a-descriptions-item>
                  </a-descriptions>

                  <a-alert
                    v-if="currentRunSignalSourceSnapshots.length"
                    type="info"
                    show-icon
                    message="这里展示启动时冻结的信号源快照。"
                    description="当前运行中的任务会持续使用这些参数；后续再改信号源配置或融合策略，不会自动影响本次运行。"
                  />
                  <a-table
                    v-if="currentRunSignalSourceSnapshots.length"
                    :data-source="currentRunSignalSourceSnapshots"
                    :columns="signalSourceSnapshotColumns"
                    :row-key="signalSourceSnapshotRowKey"
                    :pagination="false"
                    size="small"
                    :scroll="{ x: 'max-content' }"
                  >
                    <template #bodyCell="{ column, record }">
                      <template v-if="column.key === 'sourceType'">
                        {{ signalSourceTypeLabel(record.sourceType) }}
                      </template>
                      <template v-else-if="column.key === 'runtimeSupported'">
                        <a-tag :color="record.sourceType === 'indicator' || record.sourceType === 'trade_flow' ? 'blue' : 'default'">
                          {{ record.sourceType === 'indicator' || record.sourceType === 'trade_flow' ? '已接入运行时' : '预留' }}
                        </a-tag>
                      </template>
                      <template v-else-if="column.key === 'required'">
                        <a-tag :color="record.required ? 'orange' : 'default'">{{ record.required ? '必需' : '可选' }}</a-tag>
                      </template>
                      <template v-else-if="column.key === 'weight'">
                        {{ formatNumber(record.weight) }}
                      </template>
                      <template v-else-if="column.key === 'description'">
                        <div class="cell-text">{{ record.description || '-' }}</div>
                      </template>
                      <template v-else-if="column.key === 'thresholds' || column.key === 'params'">
                        <pre class="snapshot-json">{{ formatJsonLike(record[column.key]) }}</pre>
                      </template>
                    </template>
                  </a-table>
                </a-space>
              </a-card>
              <a-empty v-else description="当前还没有运行快照，可先启动任务后再查看。" />

              <a-card v-if="detailRow.recentLogs.length" size="small" title="最近事件日志">
                <a-table :data-source="detailRow.recentLogs" :columns="recentLogColumns" :pagination="false" row-key="id" size="small" :scroll="{ x: 'max-content' }">
                  <template #bodyCell="{ column, record, text }">
                    <template v-if="column.key === 'createdAt'">
                      {{ formatDateTime(text) }}
                    </template>
                    <template v-else-if="column.key === 'eventType'">
                      <a-tag :color="eventTypeColor(record.eventType)">{{ eventTypeLabel(record.eventType) }}</a-tag>
                    </template>
                    <template v-else-if="column.key === 'status'">
                      <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
                    </template>
                    <template v-else-if="column.key === 'message'">
                      <div class="cell-text">{{ record.message || '-' }}</div>
                    </template>
                    <template v-else>
                      {{ displayText(text) }}
                    </template>
                  </template>
                </a-table>
              </a-card>
              <a-empty v-else description="最近暂无事件日志" />
            </a-space>
          </a-tab-pane>
        </a-tabs>
      </template>
    </a-drawer>
  </a-card>
</template>

<script setup lang="ts">
import dayjs from 'dayjs'
import { message } from 'ant-design-vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchStrategyProfiles } from '@/api/strategies'
import { useAuthStore } from '@/stores/auth'
import {
  deleteTradeTaskProfile,
  fetchSystemSettings,
  fetchTradeTaskProfiles,
  fetchTradeTaskStatuses,
  saveTradeTaskProfile,
  startTradeTask,
  stopTradeTask,
} from '@/api/system'
import type { StrategyProfile } from '@/types/strategy'
import type { TradeMode, TradeTaskProfile, TradeTaskProfileSavePayload, TradeTaskStatus } from '@/types/system'

type SignalSourceSnapshotItem = {
  signalSourceProfileId: number | null
  sourceType: string
  name: string
  required: boolean
  weight: number | null
  thresholds: Record<string, unknown>
  params: Record<string, unknown>
  description: string
}

type TradeTaskControlRow = TradeTaskStatus & {
  profile: TradeTaskProfile | null
  strategyProfile: StrategyProfile | null
  missingStrategyProfile: boolean
  isOrphan: boolean
}

type DetailTabKey = 'overview' | 'config' | 'runtime'

type TaskProfileFormState = {
  id?: number
  name: string
  description: string
  enabled: boolean
  strategyProfileId?: number
  symbol: string
  timeframe: string
  tradeMode: TradeMode
  tradeLimit: number
  feeRate: number
  slippageRate: number
  dailyLossStopEnabled: boolean
  dailyLossStopThreshold: number
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const tradeTaskLoading = ref(false)
const saveLoading = ref(false)
const startLoadingRunner = ref<string | null>(null)
const stopLoadingRunner = ref<string | null>(null)
const detailOpen = ref(false)
const detailMode = ref<'create' | 'detail'>('detail')
const detailRunnerName = ref<string | null>(null)
const detailTab = ref<DetailTabKey>('overview')
const pollTimer = ref<number | null>(null)
const profiles = ref<TradeTaskProfile[]>([])
const statuses = ref<TradeTaskStatus[]>([])
const strategyProfiles = ref<StrategyProfile[]>([])
const invalidStrategyProfileCount = ref(0)
const supportedTimeframes = ref<string[]>([])

const form = reactive<TaskProfileFormState>({
  name: '',
  description: '',
  enabled: true,
  strategyProfileId: undefined,
  symbol: 'BTC/USDT',
  timeframe: '15m',
  tradeMode: 'sandbox',
  tradeLimit: 100,
  feeRate: 0,
  slippageRate: 0,
  dailyLossStopEnabled: false,
  dailyLossStopThreshold: 100,
})

const activeStatuses = new Set(['starting', 'running', 'stop_requested'])
const errorStatuses = new Set(['failed', 'config_error', 'stale'])
const columns = computed(() => {
  const ownerColumn = auth.isAdmin ? [{ title: '所属用户', dataIndex: 'ownerUserId', key: 'ownerUserId', width: 120 }] : []
  return [
    { title: '配置名称', key: 'name', width: 220 },
    ...ownerColumn,
    { title: '策略配置', key: 'strategyProfileName', width: 260 },
    { title: '交易对', dataIndex: 'symbol', key: 'symbol', width: 140 },
    { title: '周期', dataIndex: 'timeframe', key: 'timeframe', width: 100 },
    { title: '模式', key: 'tradeMode', width: 120 },
    { title: '配置状态', key: 'enabled', width: 100 },
    { title: '运行状态', dataIndex: 'status', key: 'status', width: 120 },
    { title: '运行实例 ID', dataIndex: 'runId', key: 'runId', width: 120 },
    { title: '最近心跳', dataIndex: 'lastHeartbeatAt', key: 'lastHeartbeatAt', width: 180 },
    { title: '下次运行', dataIndex: 'nextRunAt', key: 'nextRunAt', width: 180 },
    { title: '最近错误', dataIndex: 'lastError', key: 'lastError', width: 260 },
    { title: '操作', key: 'actions', width: 340 },
  ]
})
const signalSourceSnapshotColumns = [
  { title: '名称', dataIndex: 'name', key: 'name', width: 180 },
  { title: '类型', dataIndex: 'sourceType', key: 'sourceType', width: 140 },
  { title: '运行时', key: 'runtimeSupported', width: 120 },
  { title: '必需性', dataIndex: 'required', key: 'required', width: 100 },
  { title: '权重', dataIndex: 'weight', key: 'weight', width: 100 },
  { title: '节点阈值', dataIndex: 'thresholds', key: 'thresholds', width: 260 },
  { title: '冻结参数', dataIndex: 'params', key: 'params', width: 340 },
  { title: '描述', dataIndex: 'description', key: 'description', width: 260 },
]
const recentLogColumns = [
  { title: '时间', dataIndex: 'createdAt', key: 'createdAt', width: 180 },
  { title: '事件', dataIndex: 'eventType', key: 'eventType', width: 140 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 120 },
  { title: '说明', dataIndex: 'message', key: 'message', width: 360 },
]

const statusMap = computed(() => new Map(statuses.value.map((item) => [item.runnerName, item] as const)))
const profileMap = computed(() => new Map(profiles.value.map((item) => [item.runnerName, item] as const)))
const validStrategyProfileIdSet = computed(() => new Set(strategyProfiles.value.map((item) => item.id)))
const invalidReferenceProfiles = computed(() => profiles.value.filter((item) => item.enabled && !validStrategyProfileIdSet.value.has(item.strategyProfileId)))
const enabledStrategyProfiles = computed(() => strategyProfiles.value.filter((item) => item.enabled))
const runnerRows = computed<TradeTaskControlRow[]>(() => {
  const rows = profiles.value.map((profile) => {
    const status = statusMap.value.get(profile.runnerName) || buildDefaultStatus(profile)
    const strategyProfile = strategyProfiles.value.find((item) => item.id === profile.strategyProfileId) || null
    return {
      ...status,
      profile,
      strategyProfile,
      missingStrategyProfile: profile.enabled && !validStrategyProfileIdSet.value.has(profile.strategyProfileId),
      isOrphan: false,
    }
  })
  const orphanRows = statuses.value
    .filter((item) => !profileMap.value.has(item.runnerName))
    .map((item) => ({
      ...item,
      profile: null,
      strategyProfile: null,
      missingStrategyProfile: false,
      isOrphan: true,
    }))
  return [...rows, ...orphanRows]
})
const detailRow = computed(() => {
  if (detailMode.value !== 'detail') {
    return null
  }
  return runnerRows.value.find((item) => item.runnerName === detailRunnerName.value) || null
})
const selectedStrategyProfile = computed(() => enabledStrategyProfiles.value.find((item) => item.id === form.strategyProfileId))
const canDeleteCurrentProfile = computed(() => Boolean(detailRow.value?.profile) && !activeStatuses.has(detailRow.value?.status || ''))
const detailDrawerTitle = computed(() => {
  if (detailMode.value === 'create') {
    return '新增任务配置'
  }
  const name = detailRow.value?.profile?.name || detailRow.value?.profileName || '任务详情'
  return `任务中心 / ${name}`
})
const strategyWarningMessage = computed(() => {
  if (invalidStrategyProfileCount.value > 0 && invalidReferenceProfiles.value.length > 0) {
    return `检测到 ${invalidStrategyProfileCount.value} 条异常策略配置，且有 ${invalidReferenceProfiles.value.length} 条任务配置引用了异常或已删除的策略。`
  }
  if (invalidStrategyProfileCount.value > 0) {
    return `检测到 ${invalidStrategyProfileCount.value} 条异常策略配置，已自动跳过，不影响当前页面可用配置加载。`
  }
  return `有 ${invalidReferenceProfiles.value.length} 条任务配置引用了异常或已删除的策略，已从启动候选中自动排除。`
})
const strategyWarningDescription = computed(() => {
  if (invalidReferenceProfiles.value.length > 0) {
    return '请先前往策略配置页清理异常策略，再回到任务中心修正相关任务配置。'
  }
  return '请前往策略配置页删除或修复异常策略。'
})
const currentRunSignalSourceSnapshots = computed<SignalSourceSnapshotItem[]>(() => {
  const snapshot = detailRow.value?.currentRun?.snapshot
  const rawItems = Array.isArray(snapshot?.signalSourceSnapshots) ? snapshot.signalSourceSnapshots : []
  return rawItems.map((item) => normalizeSignalSourceSnapshot(item)).filter((item): item is SignalSourceSnapshotItem => item !== null)
})
const overviewCards = computed(() => {
  const total = profiles.value.length
  const running = runnerRows.value.filter((item) => item.status === 'running').length
  const stopped = profiles.value.filter((profile) => (statusMap.value.get(profile.runnerName) || buildDefaultStatus(profile)).status === 'stopped').length
  const abnormal = runnerRows.value.filter((item) => item.isOrphan || item.missingStrategyProfile || errorStatuses.has(item.status)).length
  return [
    { key: 'total', label: '任务总数', value: total, help: '当前已入库的交易任务配置数量' },
    { key: 'running', label: '运行中', value: running, help: '状态为运行中的任务数' },
    { key: 'stopped', label: '已停止', value: stopped, help: '已加载配置且当前未运行的任务数' },
    { key: 'abnormal', label: '异常 / 残留', value: abnormal, help: `包含失败、配置错误、状态残留与异常引用，共 ${invalidReferenceProfiles.value.length} 条异常策略引用` },
  ]
})

function buildDefaultStatus(profile: TradeTaskProfile): TradeTaskStatus {
  return {
    runnerName: profile.runnerName,
    ownerUserId: profile.ownerUserId,
    runId: null,
    tradeTaskProfileId: profile.id,
    profileName: profile.name,
    status: 'stopped',
    isRunning: false,
    canStart: true,
    canStop: false,
    startedAt: null,
    stoppedAt: null,
    stopRequestedAt: null,
    lastHeartbeatAt: null,
    lastCycleStartedAt: null,
    lastCycleFinishedAt: null,
    nextRunAt: null,
    lastError: '',
    startedBy: '',
    symbol: profile.symbol,
    timeframe: profile.timeframe,
    timeframeMinutes: null,
    strategyType: profile.strategyType,
    updatedAt: profile.updatedAt,
    recentLogs: [],
    currentRun: null,
  }
}

function firstQueryValue(value: unknown) {
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0] : undefined
  }
  return undefined
}

function normalizeDetailTab(value?: string): DetailTabKey {
  if (value === 'config' || value === 'runtime') {
    return value
  }
  return 'overview'
}

function displayText(value: unknown) {
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed || '-'
  }
  if (value === null || value === undefined) {
    return '-'
  }
  return String(value)
}

function filterSelectOption(input: string, option?: { children?: unknown; value?: unknown }) {
  const label = typeof option?.children === 'string' ? option.children : String(option?.value || '')
  return label.toLowerCase().includes(input.toLowerCase())
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return '-'
  }
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm:ss') : value
}

function formatOwnerUserId(value: number | null | undefined) {
  if (!value) {
    return '-'
  }
  return value === auth.currentUser?.id ? `${value}（我）` : String(value)
}

function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }
  return Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 8 })
}

function formatRate(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }
  return `${(Number(value) * 100).toLocaleString('zh-CN', { maximumFractionDigits: 4 })}%`
}

function formatJsonLike(value: unknown) {
  if (value === null || value === undefined) {
    return '-'
  }
  if (typeof value === 'string') {
    return value.trim() || '-'
  }
  if (Array.isArray(value)) {
    return value.length ? JSON.stringify(value, null, 2) : '[]'
  }
  if (typeof value === 'object') {
    return Object.keys(value as Record<string, unknown>).length ? JSON.stringify(value, null, 2) : '{}'
  }
  return String(value)
}

function formatFusionSummary(summary?: StrategyProfile['fusionSummary'] | null) {
  if (!summary) {
    return '-'
  }
  const parts = [
    `${summary.klineNodeCount} 个 K 线节点`,
    `${summary.signalSourceNodeCount} 个信号源`,
    `最少 ${summary.minAvailableNodes} 个可用节点`,
  ]
  if (summary.requires1hTimeframe) {
    parts.push('包含固定 1h 节点')
  }
  if (!summary.allowDegraded) {
    parts.push('不允许降级')
  }
  return parts.join(' / ')
}

function signalSourceTypeLabel(value: string) {
  if (value === 'trade_flow') {
    return 'trade_flow'
  }
  if (value === 'indicator') {
    return 'indicator'
  }
  return value || '-'
}

function signalSourceSnapshotRowKey(record: SignalSourceSnapshotItem) {
  return `${record.signalSourceProfileId || record.name}-${record.sourceType}`
}

function normalizeSignalSourceSnapshot(value: unknown): SignalSourceSnapshotItem | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }
  const item = value as Record<string, unknown>
  return {
    signalSourceProfileId: typeof item.signalSourceProfileId === 'number' ? item.signalSourceProfileId : null,
    sourceType: String(item.sourceType || ''),
    name: String(item.name || '-'),
    required: Boolean(item.required),
    weight: typeof item.weight === 'number' ? item.weight : null,
    thresholds: item.thresholds && typeof item.thresholds === 'object' && !Array.isArray(item.thresholds) ? (item.thresholds as Record<string, unknown>) : {},
    params: item.params && typeof item.params === 'object' && !Array.isArray(item.params) ? (item.params as Record<string, unknown>) : {},
    description: String(item.description || ''),
  }
}

function statusLabel(value: string) {
  if (value === 'starting') {
    return '启动中'
  }
  if (value === 'running') {
    return '运行中'
  }
  if (value === 'stop_requested') {
    return '停止中'
  }
  if (value === 'stopped') {
    return '已停止'
  }
  if (value === 'failed') {
    return '失败'
  }
  if (value === 'config_error') {
    return '配置错误'
  }
  if (value === 'stale') {
    return '状态残留'
  }
  return value || '-'
}

function statusColor(value: string) {
  if (value === 'starting') {
    return 'gold'
  }
  if (value === 'running') {
    return 'blue'
  }
  if (value === 'stop_requested') {
    return 'orange'
  }
  if (value === 'stopped') {
    return 'default'
  }
  return 'red'
}

function eventTypeLabel(value: string | null | undefined) {
  if (value === 'start_requested') {
    return '开始请求'
  }
  if (value === 'started') {
    return '启动完成'
  }
  if (value === 'cycle_started') {
    return '周期开始'
  }
  if (value === 'cycle_finished') {
    return '周期完成'
  }
  if (value === 'stop_requested') {
    return '停止请求'
  }
  if (value === 'stopped') {
    return '停止完成'
  }
  if (value === 'failed') {
    return '失败'
  }
  if (value === 'stale') {
    return '状态残留'
  }
  if (value === 'risk_halt_triggered') {
    return '风控停机'
  }
  return value || '-'
}

function eventTypeColor(value: string | null | undefined) {
  if (value === 'start_requested' || value === 'started') {
    return 'blue'
  }
  if (value === 'cycle_started' || value === 'cycle_finished') {
    return 'cyan'
  }
  if (value === 'stop_requested' || value === 'stopped' || value === 'risk_halt_triggered') {
    return 'orange'
  }
  if (value === 'failed' || value === 'stale') {
    return 'red'
  }
  return 'default'
}

function strategyTypeLabel(value: string) {
  return strategyProfiles.value.find((item) => item.strategyType === value)?.definition?.displayName || value || '-'
}

function resolveTradeMode(
  payload: Pick<TradeTaskProfile, 'tradeMode' | 'sandboxTrade'> | Pick<NonNullable<TradeTaskStatus['currentRun']>, 'tradeMode' | 'sandboxTrade'> | null | undefined,
): TradeMode {
  if (payload?.tradeMode) {
    return payload.tradeMode
  }
  return payload?.sandboxTrade === false ? 'live' : 'sandbox'
}

function resolveRowTradeMode(record: TradeTaskControlRow): TradeMode {
  if (record.currentRun) {
    return resolveTradeMode(record.currentRun)
  }
  return resolveTradeMode(record.profile)
}

function tradeModeLabel(value: TradeMode) {
  if (value === 'live') {
    return '真实交易'
  }
  if (value === 'sandbox') {
    return '沙盒交易'
  }
  if (value === 'paper') {
    return '纸上交易'
  }
  return value || '-'
}

function tradeModeTagColor(value: TradeMode) {
  if (value === 'live') {
    return 'red'
  }
  if (value === 'sandbox') {
    return 'gold'
  }
  if (value === 'paper') {
    return 'blue'
  }
  return 'default'
}

function applyProfileToForm(profile: TradeTaskProfile) {
  form.id = profile.id
  form.name = profile.name
  form.description = profile.description
  form.enabled = profile.enabled
  form.strategyProfileId = profile.strategyProfileId
  form.symbol = profile.symbol
  form.timeframe = profile.timeframe
  form.tradeMode = resolveTradeMode(profile)
  form.tradeLimit = profile.tradeLimit
  form.feeRate = profile.feeRate
  form.slippageRate = profile.slippageRate
  form.dailyLossStopEnabled = profile.dailyLossStopEnabled
  form.dailyLossStopThreshold = profile.dailyLossStopThreshold
}

async function resetForm() {
  form.id = undefined
  form.name = ''
  form.description = ''
  form.enabled = true
  form.strategyProfileId = enabledStrategyProfiles.value[0]?.id
  form.symbol = 'BTC/USDT'
  form.timeframe = supportedTimeframes.value[0] || '15m'
  form.tradeMode = 'sandbox'
  form.tradeLimit = 100
  form.feeRate = 0
  form.slippageRate = 0
  form.dailyLossStopEnabled = false
  form.dailyLossStopThreshold = 100
  await loadSettings()
}

function canStartRecord(record: TradeTaskControlRow) {
  return Boolean(record.tradeTaskProfileId) && Boolean(record.profile?.enabled) && !record.missingStrategyProfile && record.canStart
}

function startConfirmTitle(record: TradeTaskControlRow) {
  const tradeMode = resolveRowTradeMode(record)
  const modeLabel = tradeModeLabel(tradeMode)
  const profileName = record.profile?.name || record.profileName || '当前配置'
  if (tradeMode === 'live') {
    return `确认启动“${profileName}”吗？当前为${modeLabel}，会使用真实行情并真实下单。`
  }
  if (tradeMode === 'paper') {
    return `确认启动“${profileName}”吗？当前为${modeLabel}，会使用真实行情但不会真实下单。`
  }
  return `确认启动“${profileName}”吗？当前为${modeLabel}，会使用沙盒行情并在沙盒环境下单。`
}

function buildTaskCenterQuery(record: TradeTaskControlRow, tab: DetailTabKey) {
  const query: Record<string, string> = { tab, runnerName: record.runnerName }
  if (record.tradeTaskProfileId) {
    query.profileId = String(record.tradeTaskProfileId)
  }
  return query
}

function clearTaskCenterQuery() {
  const nextQuery = { ...route.query }
  delete nextQuery.profileId
  delete nextQuery.runnerName
  delete nextQuery.tab
  delete nextQuery.create
  router.replace({ path: '/trade-tasks', query: nextQuery })
}

function openDetail(record: TradeTaskControlRow, tab: DetailTabKey) {
  detailMode.value = 'detail'
  detailRunnerName.value = record.runnerName
  detailTab.value = record.profile ? tab : 'runtime'
  detailOpen.value = true
  if (record.profile) {
    applyProfileToForm(record.profile)
  }
  router.replace({ path: '/trade-tasks', query: { ...route.query, ...buildTaskCenterQuery(record, detailTab.value) } })
}

function openOverview(record: TradeTaskControlRow) {
  openDetail(record, 'overview')
}

function openConfig(record: TradeTaskControlRow) {
  if (!record.profile) {
    return
  }
  openDetail(record, 'config')
}

function openRuntime(record: TradeTaskControlRow) {
  openDetail(record, 'runtime')
}

async function openCreate() {
  detailMode.value = 'create'
  detailRunnerName.value = null
  detailTab.value = 'config'
  clearTaskCenterQuery()
  await resetForm()
  detailOpen.value = true
}

function closeDetail() {
  detailOpen.value = false
}

function goToStrategies() {
  router.push('/strategies')
}

function goToTaskLogs(record?: TradeTaskControlRow) {
  if (!record) {
    router.push('/trade-task-logs')
    return
  }
  router.push({
    path: '/trade-task-logs',
    query: {
      runnerName: record.runnerName,
      ...(record.tradeTaskProfileId ? { profileId: String(record.tradeTaskProfileId) } : {}),
      ...(record.runId ? { runId: String(record.runId) } : {}),
      tab: 'runtime',
    },
  })
}

function goToTradeLogs(record: TradeTaskControlRow) {
  if (!record.runId) {
    return
  }
  router.push({
    path: '/trade-logs',
    query: {
      runId: String(record.runId),
      runnerName: record.runnerName,
      ...(record.tradeTaskProfileId ? { profileId: String(record.tradeTaskProfileId) } : {}),
      tab: 'runtime',
    },
  })
}

function ensurePolling() {
  if (!statuses.value.some((item) => activeStatuses.has(item.status))) {
    stopPolling()
    return
  }
  if (pollTimer.value !== null) {
    return
  }
  pollTimer.value = window.setInterval(async () => {
    await loadTradeTaskStatuses()
  }, 4000)
}

function stopPolling() {
  if (pollTimer.value !== null) {
    window.clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

// 兼容旧书签和日志页返回链接：优先按 runnerName 深链，其次按 profileId 兜底。
function syncDetailFromRoute() {
  if (route.path !== '/trade-tasks') {
    return
  }
  const queryRunnerName = firstQueryValue(route.query.runnerName)
  const rawProfileId = firstQueryValue(route.query.profileId)
  const queryProfileId = rawProfileId ? Number(rawProfileId) : Number.NaN
  const nextTab = normalizeDetailTab(firstQueryValue(route.query.tab))
  const matchedRow = queryRunnerName
    ? runnerRows.value.find((item) => item.runnerName === queryRunnerName)
    : Number.isFinite(queryProfileId)
      ? runnerRows.value.find((item) => item.tradeTaskProfileId === queryProfileId)
      : undefined

  if (!matchedRow) {
    return
  }

  detailMode.value = 'detail'
  detailRunnerName.value = matchedRow.runnerName
  detailTab.value = matchedRow.profile ? nextTab : 'runtime'
  detailOpen.value = true
  if (matchedRow.profile) {
    applyProfileToForm(matchedRow.profile)
  }
}

async function loadProfiles() {
  profiles.value = await fetchTradeTaskProfiles()
}

async function loadStrategyProfiles() {
  const data = await fetchStrategyProfiles()
  strategyProfiles.value = data.items
  invalidStrategyProfileCount.value = data.invalidItems.length
}

async function loadSettings() {
  const data = await fetchSystemSettings()
  supportedTimeframes.value = data.editable.supportedTimeframes
  if (!form.timeframe) {
    form.timeframe = supportedTimeframes.value[0] || '15m'
  }
  if (!form.id) {
    form.feeRate = data.editable.tradeTaskDefaultFeeRate
    form.slippageRate = data.editable.tradeTaskDefaultSlippageRate
    form.dailyLossStopEnabled = data.editable.tradeTaskDefaultDailyLossStopEnabled
    form.dailyLossStopThreshold = data.editable.tradeTaskDefaultDailyLossStopThreshold
  }
}

async function loadTradeTaskStatuses() {
  tradeTaskLoading.value = true
  try {
    statuses.value = await fetchTradeTaskStatuses()
    ensurePolling()
  } finally {
    tradeTaskLoading.value = false
  }
}

async function submitForm() {
  if (!form.name.trim()) {
    message.warning('请填写配置名称')
    return
  }
  if (!form.symbol.trim()) {
    message.warning('请填写交易对')
    return
  }
  if (!form.strategyProfileId) {
    message.warning('请选择策略配置')
    return
  }

  saveLoading.value = true
  try {
    const payload: TradeTaskProfileSavePayload = {
      id: form.id,
      name: form.name.trim(),
      description: form.description.trim(),
      enabled: form.enabled,
      strategyProfileId: form.strategyProfileId,
      symbol: form.symbol.trim(),
      timeframe: form.timeframe,
      tradeMode: form.tradeMode,
      tradeLimit: form.tradeLimit,
      feeRate: form.feeRate,
      slippageRate: form.slippageRate,
      dailyLossStopEnabled: form.dailyLossStopEnabled,
      dailyLossStopThreshold: form.dailyLossStopThreshold,
    }
    const saved = await saveTradeTaskProfile(payload)
    message.success('交易任务配置已保存')
    await reloadAll()
    const matchedRow = runnerRows.value.find((item) => item.tradeTaskProfileId === saved.id || item.runnerName === saved.runnerName)
    if (matchedRow) {
      openConfig(matchedRow)
    } else {
      closeDetail()
    }
  } finally {
    saveLoading.value = false
  }
}

async function removeProfile(id: number) {
  await deleteTradeTaskProfile(id)
  message.success('交易任务配置已删除')
  await reloadAll()
  closeDetail()
}

async function handleStartTradeTask(record: TradeTaskControlRow) {
  if (!record.tradeTaskProfileId) {
    message.warning('当前记录没有对应的任务配置，不能启动')
    return
  }
  if (record.missingStrategyProfile) {
    message.warning('当前任务配置关联的策略异常或已删除，请先修复后再启动')
    return
  }
  startLoadingRunner.value = record.runnerName
  try {
    const data = await startTradeTask({ tradeTaskProfileId: record.tradeTaskProfileId })
    message.success(data.status === 'running' ? '交易任务已启动' : '交易任务正在启动')
    await loadTradeTaskStatuses()
  } finally {
    startLoadingRunner.value = null
  }
}

async function handleStopTradeTask(record: TradeTaskControlRow) {
  stopLoadingRunner.value = record.runnerName
  try {
    const data = await stopTradeTask({ runnerName: record.runnerName })
    message.success(data.status === 'stop_requested' ? '停止请求已发送' : '交易任务已停止')
    await loadTradeTaskStatuses()
  } finally {
    stopLoadingRunner.value = null
  }
}

async function reloadAll() {
  await Promise.all([loadSettings(), loadStrategyProfiles(), loadProfiles(), loadTradeTaskStatuses()])
  syncDetailFromRoute()
}

watch(
  () => [route.query.profileId, route.query.runnerName, route.query.tab],
  () => {
    syncDetailFromRoute()
  },
)

watch(detailTab, (value) => {
  if (detailMode.value === 'detail' && detailOpen.value && detailRow.value) {
    router.replace({ path: '/trade-tasks', query: { ...route.query, ...buildTaskCenterQuery(detailRow.value, value) } })
  }
})

watch(detailOpen, (value) => {
  if (!value) {
    detailMode.value = 'detail'
    detailRunnerName.value = null
    clearTaskCenterQuery()
  }
})

watch(detailRow, (value) => {
  if (detailMode.value === 'detail' && detailOpen.value && !value) {
    closeDetail()
  }
})

onMounted(async () => {
  await reloadAll()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped>
.page-card {
  min-height: 100%;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.overview-card {
  min-width: 0;
}

.overview-label {
  color: rgba(0, 0, 0, 0.45);
  font-size: 13px;
}

.overview-value {
  margin-top: 8px;
  color: rgba(0, 0, 0, 0.88);
  font-size: 28px;
  font-weight: 600;
  line-height: 1.2;
}

.overview-help {
  margin-top: 8px;
  color: rgba(0, 0, 0, 0.45);
  font-size: 12px;
  white-space: normal;
}

.action-bar,
.tab-action-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  align-items: center;
  justify-content: space-between;
}

.action-tip,
.cell-meta,
.mode-help,
.field-help {
  color: rgba(0, 0, 0, 0.45);
  font-size: 13px;
  white-space: normal;
}

.cell-meta,
.mode-help,
.field-help {
  margin-top: 4px;
  font-size: 12px;
}

.cell-meta-warning {
  color: #d46b08;
}

.detail-section {
  padding: 16px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  background: #fafafa;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0 16px;
}

.cell-text {
  white-space: normal;
  word-break: break-word;
}

.snapshot-json {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

:deep(.ant-table-thead > tr > th) {
  white-space: nowrap;
}
</style>
