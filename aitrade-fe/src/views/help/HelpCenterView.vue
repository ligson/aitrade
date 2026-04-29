<template>
  <a-card class="page-card">
    <a-space direction="vertical" size="large" style="width: 100%">
      <a-alert
        type="info"
        show-icon
        message="这里是面向普通用户的帮助中心。"
        description="如果你第一次使用本系统，建议先看系统使用指南，再看量化术语，最后看策略原则。这样能先理解怎么操作，再理解页面里的词是什么意思，最后再理解策略为什么这样设计。"
      />

      <a-card title="学习入口" size="small">
        <a-space wrap>
          <RouterLink to="/help-getting-started"><a-button type="primary">系统使用指南</a-button></RouterLink>
          <RouterLink to="/help-terminology"><a-button>量化术语</a-button></RouterLink>
          <RouterLink to="/help-strategy-principles"><a-button>策略原则</a-button></RouterLink>
        </a-space>
      </a-card>

      <a-card title="建议阅读顺序" size="small">
        <ol class="help-list ordered">
          <li>先看“系统使用指南”，理解菜单、页面和基本使用流程。</li>
          <li>再看“量化术语”，把常见英文、缩写和配置字段对应起来。</li>
          <li>最后看“策略原则”，理解信号、执行、风控和回测之间的关系。</li>
        </ol>
      </a-card>

      <a-card title="你可以在这里获得什么帮助" size="small">
        <div class="help-section">
          <h3>如何开始使用系统</h3>
          <p>帮助你理解先配什么、后看什么，以及任务、策略、信号源、回测之间的关系。</p>
        </div>
        <div class="help-section">
          <h3>常见量化英文与编码名解释</h3>
          <p>帮助你看懂页面里的 strategy、signal、indicator、slippage、paper、sandbox 等词。</p>
        </div>
        <div class="help-section">
          <h3>策略原理与风险边界</h3>
          <p>帮助你理解系统不是“自动赚钱按钮”，而是把信号、执行和风控组织起来的交易工具。</p>
        </div>
      </a-card>

      <a-card title="阅读提醒" size="small">
        <ul class="help-list">
          <li>帮助中心优先讲清楚怎么用、为什么这样用，不会展开所有底层实现细节。</li>
          <li>页面里的策略说明用于帮助理解原理，不代表收益承诺。</li>
          <li>如果你准备开始真实交易，建议先在 paper 或 sandbox 模式下熟悉完整流程。</li>
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

.help-section + .help-section {
  margin-top: 16px;
}

.help-section h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.help-section p {
  margin: 0;
  color: rgba(0, 0, 0, 0.65);
  line-height: 1.7;
}
</style>
