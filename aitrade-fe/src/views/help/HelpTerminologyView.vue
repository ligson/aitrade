<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="这页用来解释系统里常见的量化英文、缩写和编码名。"
        description="如果你看到页面里某个词大概认识，但不确定它在本系统中的具体含义，可以优先来这里对照。术语页更偏用户理解，不展开底层代码实现。"
      />

      <a-card title="基础交易术语" size="small">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="position">持仓。表示你当前是否已经买入，以及买入后的数量、成本、止损等状态。</a-descriptions-item>
          <a-descriptions-item label="stop loss">止损。价格向不利方向运行到某个位置时，系统触发退出，以控制单笔亏损。</a-descriptions-item>
          <a-descriptions-item label="take profit">止盈。达到预期收益后退出。当前系统里更常见的是通过信号或风控逻辑实现退出，而不是简单固定止盈。</a-descriptions-item>
          <a-descriptions-item label="slippage">滑点。你希望成交的价格和实际成交价格之间的差异。市场越波动、流动性越差，滑点越明显。</a-descriptions-item>
          <a-descriptions-item label="fee rate">手续费率。交易所对成交收取的费用比例，会直接影响净收益。</a-descriptions-item>
        </a-descriptions>
      </a-card>

      <a-card title="策略与信号术语" size="small">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="strategy">策略。决定什么时候买、什么时候卖、什么时候观望的一组规则。</a-descriptions-item>
          <a-descriptions-item label="signal">信号。策略在某个时点给出的判断结果，例如 buy、sell、hold。</a-descriptions-item>
          <a-descriptions-item label="indicator">指标。根据 K 线或价格序列计算出来的参考量，例如 RSI、MACD。</a-descriptions-item>
          <a-descriptions-item label="trade_flow">成交流信号源。通过逐笔成交数据观察买卖盘占比、成交额失衡等特征，帮助判断短期偏向。</a-descriptions-item>
          <a-descriptions-item label="confidence">置信度。策略或节点对当前判断有多强烈，数值越高通常表示偏向越明确。</a-descriptions-item>
          <a-descriptions-item label="bias">偏向。常见取值是 buy、sell、hold，用来表达节点偏多、偏空或中性。</a-descriptions-item>
          <a-descriptions-item label="signal source">信号源。为融合策略提供输入的独立来源，比如 trade_flow、indicator 等。</a-descriptions-item>
          <a-descriptions-item label="snapshot">快照。任务启动瞬间冻结下来的配置副本，后续改页面配置不会回写影响已运行任务。</a-descriptions-item>
        </a-descriptions>
      </a-card>

      <a-card title="运行与回测术语" size="small">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="backtest">回测。用历史数据验证策略在过去某段时间内的表现。</a-descriptions-item>
          <a-descriptions-item label="paper">纸上交易。使用真实行情，但不真实下单，适合先看信号与风控是否符合预期。</a-descriptions-item>
          <a-descriptions-item label="sandbox">沙盒交易。连接交易所的测试环境，流程更接近真实下单，但不使用真实资金。</a-descriptions-item>
          <a-descriptions-item label="live">真实交易。直接连接真实市场和真实账户，风险最高，必须在充分验证后再使用。</a-descriptions-item>
          <a-descriptions-item label="run id">运行实例 ID。一次任务启动后的独立编号，可用于串联任务日志和交易日志。</a-descriptions-item>
          <a-descriptions-item label="daily loss stop">单日亏损停机。达到设定的当日亏损阈值后，系统会停止继续运行，以限制风险扩散。</a-descriptions-item>
        </a-descriptions>
      </a-card>

      <a-card title="怎么看这些术语" size="small">
        <ul class="help-list">
          <li>先关注这些词在页面里代表什么，不用一开始就追底层计算细节。</li>
          <li>同一个术语在不同系统里含义可能略有差异，这里以本系统页面与配置语义为准。</li>
          <li>如果你已经能看懂术语，但还不理解它们为什么重要，建议继续阅读“策略原则”。</li>
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
</style>
