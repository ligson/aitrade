<template>
  <a-layout style="min-height: 100vh">
    <a-layout-sider theme="dark" width="220">
      <div class="logo">aitrade 管理台</div>
      <a-menu theme="dark" mode="inline" :selected-keys="selectedKeys" @click="handleMenuClick">
        <a-menu-item key="trade-logs">交易日志</a-menu-item>
        <a-menu-item key="strategies">策略配置</a-menu-item>
        <a-menu-item v-if="auth.isAdmin" key="users">用户维护</a-menu-item>
      </a-menu>
    </a-layout-sider>
    <a-layout>
      <a-layout-header class="header">
        <div>{{ auth.currentUser?.nickname || auth.currentUser?.username }}</div>
        <a-space>
          <a-tag :color="auth.isAdmin ? 'blue' : 'default'">{{ auth.isAdmin ? '管理员' : '普通用户' }}</a-tag>
          <a-button type="link" @click="handleLogout">退出登录</a-button>
        </a-space>
      </a-layout-header>
      <a-layout-content style="padding: 24px">
        <RouterView />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const selectedKeys = computed(() => [route.path.replace('/', '') || 'trade-logs'])

function handleMenuClick(event: { key: string }) {
  router.push(`/${event.key}`)
}

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 600;
}

.header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}
</style>
