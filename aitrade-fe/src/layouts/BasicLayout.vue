<template>
  <a-layout class="basic-layout">
    <a-layout-sider theme="dark" width="220" :collapsed="collapsed" :trigger="null" collapsible class="basic-layout-sider">
      <div class="sider-brand">
        <div class="logo" :title="collapsed ? 'aitrade 管理台' : undefined">{{ collapsed ? 'AT' : 'aitrade 管理台' }}</div>
        <a-button type="text" class="sider-toggle" @click="toggleCollapsed">
          <component :is="collapsed ? MenuUnfoldOutlined : MenuFoldOutlined" />
        </a-button>
      </div>
      <a-menu theme="dark" mode="inline" :selected-keys="selectedKeys" :inline-collapsed="collapsed" @click="handleMenuClick">
        <a-menu-item v-for="item in visibleMenuItems" :key="item.key">
          <template #icon>
            <component :is="item.icon" />
          </template>
          <span>{{ item.title }}</span>
        </a-menu-item>
      </a-menu>
    </a-layout-sider>
    <a-layout class="basic-layout-main">
      <a-layout-header class="header">
        <a-space>
          <div>{{ auth.currentUser?.nickname || auth.currentUser?.username }}</div>
          <a-tag :color="auth.isAdmin ? 'blue' : 'default'">{{ auth.isAdmin ? '管理员' : '普通用户' }}</a-tag>
          <a-button type="link" @click="handleLogout">退出登录</a-button>
        </a-space>
      </a-layout-header>
      <a-layout-content class="basic-layout-content">
        <div class="basic-layout-breadcrumb">
          <AppBreadcrumb />
        </div>
        <div class="basic-layout-content-body app-scrollbar">
          <RouterView />
        </div>
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { FundOutlined, MenuFoldOutlined, MenuUnfoldOutlined, SettingOutlined, TeamOutlined } from '@ant-design/icons-vue'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppBreadcrumb from '@/components/AppBreadcrumb.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const collapsed = ref(false)

const menuItems = [
  { key: 'trade-logs', title: '交易日志', icon: FundOutlined },
  { key: 'strategies', title: '策略配置', icon: SettingOutlined },
  { key: 'users', title: '用户维护', icon: TeamOutlined, adminOnly: true },
]

const visibleMenuItems = computed(() => menuItems.filter((item) => !item.adminOnly || auth.isAdmin))
const selectedKeys = computed(() => [route.path.split('/')[1] || 'trade-logs'])

function toggleCollapsed() {
  collapsed.value = !collapsed.value
}

function handleMenuClick(event: { key: string }) {
  router.push(`/${event.key}`)
}

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.basic-layout {
  height: 100vh;
  overflow: hidden;
}

.basic-layout-sider :deep(.ant-layout-sider-children) {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.basic-layout-main {
  min-width: 0;
  min-height: 0;
}

.sider-brand {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 56px;
  padding: 0 40px 0 16px;
  flex: 0 0 auto;
}

.logo {
  color: #fff;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sider-toggle {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.88);
}

.sider-toggle:hover,
.sider-toggle:focus {
  color: #fff;
  background: rgba(255, 255, 255, 0.14);
}

.basic-layout-sider.ant-layout-sider-collapsed .sider-brand {
  padding: 0 8px;
}

.basic-layout-sider.ant-layout-sider-collapsed .logo {
  font-size: 15px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
}

.basic-layout-content {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: calc(100vh - 64px);
  background: #f5f7fa;
}

.basic-layout-breadcrumb {
  flex: 0 0 auto;
  padding: 16px 24px 12px;
}

.basic-layout-content-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 0 24px 24px;
}
</style>
