<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="这页帮助你按正确顺序使用系统。"
        description="对普通用户来说，最容易出错的不是某个字段怎么填，而是不清楚页面之间是什么关系。你可以把本系统理解为：先准备数据和策略，再创建任务，最后查看运行与交易日志。"
      />

      <a-card title="系统能做什么" size="small">
        <ul class="help-list">
          <li>维护多套策略配置，并为不同交易对或周期复用。</li>
          <li>创建交易任务配置，让某套策略按指定模式和参数运行。</li>
          <li>查看任务运行日志、交易结果日志和当前持仓。</li>
          <li>在回测或模拟环境中先验证思路，再决定是否进入更真实的运行环境。</li>
        </ul>
      </a-card>

      <a-card title="推荐上手流程" size="small">
        <ol class="help-list ordered">
          <li>先看“策略中心”，确认你要使用哪类策略或信号源。</li>
          <li>如果需要历史验证，再到“数据中心 / 历史数据管理”和“策略中心 / 策略回测”准备并验证数据。</li>
          <li>到“交易中心 / 交易任务配置”创建可启动的任务。</li>
          <li>到“交易中心 / 交易任务控制”启动、停止并观察当前运行状态。</li>
          <li>最后到“任务日志”和“交易日志”排查实际运行过程与成交结果。</li>
        </ol>
      </a-card>

      <a-card title="交易中心怎么用" size="small">
        <a-divider orientation="left">交易任务配置</a-divider>
        <p class="help-text">这里维护的是可以启动的任务模板。你需要在这里决定交易对、周期、策略配置、交易模式、手续费率、滑点率和单日亏损停机等参数。</p>
        <a-divider orientation="left">交易任务控制</a-divider>
        <p class="help-text">这里是运行入口。开始运行时，系统会把当时的任务配置冻结成快照，后面你再改配置，也不会反向影响已经启动的任务。</p>
        <a-divider orientation="left">任务日志与交易日志</a-divider>
        <p class="help-text">任务日志更偏“运行过程”，适合看启动、停止、失败和周期状态；交易日志更偏“成交结果”，适合看买卖、风控拒绝、执行失败和订单详情。</p>
      </a-card>

      <a-card title="策略中心怎么用" size="small">
        <ul class="help-list">
          <li><strong>策略配置</strong>：决定策略本身如何生成信号。</li>
          <li><strong>信号源配置</strong>：为融合策略提供可复用输入，比如 trade_flow 或 indicator。</li>
          <li><strong>策略回测</strong>：先用历史数据验证思路，减少直接上真实环境的风险。</li>
        </ul>
      </a-card>

      <a-card title="数据中心怎么用" size="small">
        <p class="help-text">如果你准备做回测，通常需要先到“历史数据管理”准备所需的交易对和周期数据。没有合适的数据，回测结论就不可靠。</p>
      </a-card>

      <a-card title="新手最容易忽略的几点" size="small">
        <ul class="help-list">
          <li>先理解交易模式差异：paper、sandbox、live 看到的风险和执行方式并不相同。</li>
          <li>不要只看策略信号，还要同时关注手续费、滑点和风控阈值。</li>
          <li>任务启动后的快照是独立的，改动配置后要重新启动新任务才会生效。</li>
          <li>先学会看日志，再学会调参数；很多问题不是策略错，而是运行参数不合适。</li>
        </ul>
      </a-card>
    </a-space>
  </a-card>
</template>

<script setup lang="ts">
</script>

<style scoped>
.page-card {
  min-height: 100%;
}

.help-list {
  margin: 0;
  padding-left: 20px;
  color: rgba(0, 0, 0, 0.88);
}

.help-list li + li {
  margin-top: 8px;
}

.ordered {
  padding-left: 22px;
}

.help-text {
  margin: 0;
  line-height: 1.8;
  color: rgba(0, 0, 0, 0.72);
}
</style>
