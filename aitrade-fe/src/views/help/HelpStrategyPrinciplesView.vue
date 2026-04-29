<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="warning"
        show-icon
        message="这页解释的是策略原理与风险边界，不是收益承诺。"
        description="策略说明能帮助你理解系统为什么这样设计，但不能保证未来收益。真正影响结果的，除了信号本身，还有数据质量、手续费、滑点、风险控制和执行环境。"
      />

      <a-card title="策略由什么组成" size="small">
        <div class="help-section">
          <h3>信号</h3>
          <p>信号负责回答“现在更适合买、卖，还是先观望”。它来自指标、K 线结构、成交流或多个节点的综合判断。</p>
        </div>
        <div class="help-section">
          <h3>执行</h3>
          <p>执行负责把信号变成订单。哪怕信号一样，不同的交易模式、手续费和滑点，也可能让最终结果不同。</p>
        </div>
        <div class="help-section">
          <h3>风控</h3>
          <p>风控负责限制错误时的损失，例如止损、追踪止损、单日亏损停机。很多时候，风控比“找到更多信号”更重要。</p>
        </div>
      </a-card>

      <a-card title="为什么同一策略在不同环境里结果会不同" size="small">
        <ul class="help-list">
          <li><strong>backtest</strong> 使用历史数据，重点是验证逻辑是否大体成立。</li>
          <li><strong>paper</strong> 使用真实行情，但不真实下单，更适合观察实时信号和风控行为。</li>
          <li><strong>sandbox</strong> 更接近交易所下单流程，但仍是测试环境。</li>
          <li><strong>live</strong> 才是真实市场结果，会受到流动性、延迟、滑点和资金管理的直接影响。</li>
        </ul>
      </a-card>

      <a-card title="为什么风控通常比信号更重要" size="small">
        <p class="help-text">很多新手会把注意力全部放在“如何让买卖点更准”，但在真实交易里，更常见的问题是：一次错误没有被及时限制，导致多次盈利被一次大亏损抹掉。系统里的止损、追踪止损、手续费、滑点和单日亏损停机，都是为了避免策略在不利阶段持续放大损失。</p>
      </a-card>

      <a-card title="怎么理解融合策略与信号源" size="small">
        <p class="help-text">融合策略的核心思想不是“更多指标一定更好”，而是把不同来源的判断拆开看，再按规则综合。比如 K 线节点看趋势结构，trade_flow 看短期买卖盘活跃度，indicator 看 RSI、MACD 等指标状态。多个节点之间可能一致，也可能冲突，所以系统才会有权重、最少可用节点数、是否允许降级等配置。</p>
      </a-card>

      <a-card title="新手常见误区" size="small">
        <ul class="help-list">
          <li>只看收益，不看回撤和亏损控制。</li>
          <li>把回测结果直接当成未来真实收益预期。</li>
          <li>还没看懂日志和快照，就频繁改参数。</li>
          <li>没有在 paper 或 sandbox 先走完整流程，就直接进入真实交易。</li>
          <li>以为指标越多越好，忽略了信号冲突和过度拟合的风险。</li>
        </ul>
      </a-card>

      <a-card title="对普通用户的建议" size="small">
        <ol class="help-list ordered">
          <li>先理解任务配置和策略配置的区别，再开始调参数。</li>
          <li>先在回测和 paper 中验证，再考虑更真实的环境。</li>
          <li>每次只改少量参数，并结合任务日志和交易日志看变化。</li>
          <li>把重点放在“长期是否稳定、风险是否可控”，不要只盯一次短期结果。</li>
        </ol>
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

.help-section + .help-section {
  margin-top: 16px;
}

.help-section h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.help-section p,
.help-text {
  margin: 0;
  color: rgba(0, 0, 0, 0.72);
  line-height: 1.8;
}
</style>
