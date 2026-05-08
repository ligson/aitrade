<template>
  <a-layout class="basic-layout">
    <a-layout-sider theme="dark" width="220" :collapsed="collapsed" :trigger="null" collapsible class="basic-layout-sider">
      <div class="sider-brand">
        <div class="logo" :title="collapsed ? 'aitrade 管理台' : undefined">{{ collapsed ? 'AT' : 'aitrade 管理台' }}</div>
        <a-button type="text" class="sider-toggle" @click="toggleCollapsed">
          <component :is="collapsed ? MenuUnfoldOutlined : MenuFoldOutlined" />
        </a-button>
      </div>
      <a-menu
        theme="dark"
        mode="inline"
        :selected-keys="selectedKeys"
        :open-keys="menuOpenKeys"
        :inline-collapsed="collapsed"
        @click="handleMenuClick"
        @openChange="handleOpenChange"
      >
        <a-sub-menu v-for="group in visibleMenuGroups" :key="group.key">
          <template #icon>
            <component :is="group.icon" />
          </template>
          <template #title>{{ group.title }}</template>
          <a-menu-item v-for="item in group.children" :key="item.key">
            <template #icon>
              <component :is="item.icon" />
            </template>
            <span>{{ item.title }}</span>
          </a-menu-item>
        </a-sub-menu>
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
import {
  CloudDownloadOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  FundOutlined,
  HistoryOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SettingOutlined,
  TeamOutlined,
} from '@ant-design/icons-vue'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppBreadcrumb from '@/components/AppBreadcrumb.vue'
import { useAuthStore } from '@/stores/auth'

type MenuItem = {
  key: string
  title: string
  icon: object
  routePath: string
  adminOnly?: boolean
}

type MenuGroup = {
  key: string
  title: string
  icon: object
  children: MenuItem[]
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const collapsed = ref(false)
const openKeys = ref<string[]>([])

const menuGroups: MenuGroup[] = [
  {
    key: 'trading-center',
    title: '交易中心',
    icon: FundOutlined,
    children: [
      { key: 'trade-tasks', title: '任务中心', icon: DashboardOutlined, routePath: '/trade-tasks' },
      { key: 'trade-task-logs', title: '任务日志', icon: FileTextOutlined, routePath: '/trade-task-logs' },
      { key: 'trade-logs', title: '交易日志', icon: FundOutlined, routePath: '/trade-logs' },
    ],
  },
  {
    key: 'strategy-center',
    title: '策略中心',
    icon: HistoryOutlined,
    children: [
      { key: 'strategies', title: '策略配置', icon: SettingOutlined, routePath: '/strategies' },
      { key: 'signal-sources', title: '信号源配置', icon: DatabaseOutlined, routePath: '/signal-sources' },
      { key: 'backtests', title: '策略回测', icon: HistoryOutlined, routePath: '/backtests' },
    ],
  },
  {
    key: 'data-center',
    title: '数据中心',
    icon: DatabaseOutlined,
    children: [
      { key: 'backtest-data', title: '历史数据管理', icon: CloudDownloadOutlined, routePath: '/backtest-data' },
    ],
  },
  {
    key: 'system-management',
    title: '系统管理',
    icon: TeamOutlined,
    children: [
      // 交易所设置需要对所有登录用户可见，其他系统页继续只对管理员展示。
      { key: 'user-exchange-settings', title: '交易所设置', icon: SettingOutlined, routePath: '/user-exchange-settings' },
      // 系统设置已拆成概览、AI、交易、数据和日志多个入口，这里需要与路由和概览页导航保持一致。
      { key: 'system-settings', title: '系统概览', icon: SettingOutlined, routePath: '/system-settings', adminOnly: true },
      { key: 'system-deployment-settings', title: '部署设置', icon: DatabaseOutlined, routePath: '/system-deployment-settings', adminOnly: true },
      { key: 'system-ai-settings', title: 'AI 设置', icon: SettingOutlined, routePath: '/system-ai-settings', adminOnly: true },
      { key: 'system-trade-settings', title: '交易设置', icon: SettingOutlined, routePath: '/system-trade-settings', adminOnly: true },
      { key: 'system-data-settings', title: '数据设置', icon: DatabaseOutlined, routePath: '/system-data-settings', adminOnly: true },
      { key: 'system-logs', title: '系统日志', icon: FileTextOutlined, routePath: '/system-logs', adminOnly: true },
      { key: 'users', title: '用户维护', icon: TeamOutlined, routePath: '/users', adminOnly: true },
    ],
  },
  {
    key: 'help-center',
    title: '帮助中心',
    icon: FileTextOutlined,
    children: [
      { key: 'help-center', title: '帮助总览', icon: FileTextOutlined, routePath: '/help-center' },
      { key: 'help-getting-started', title: '系统使用指南', icon: FileTextOutlined, routePath: '/help-getting-started' },
      { key: 'help-terminology', title: '量化术语', icon: FileTextOutlined, routePath: '/help-terminology' },
      { key: 'help-strategy-principles', title: '策略原则', icon: FileTextOutlined, routePath: '/help-strategy-principles' },
    ],
  },
]

// adminOnly 只控制菜单展示层，真正的接口权限仍以后端校验为准。
const visibleMenuGroups = computed(() =>
  menuGroups
    .map((group) => ({
      ...group,
      children: group.children.filter((item) => !item.adminOnly || auth.isAdmin),
    }))
    .filter((group) => group.children.length > 0),
)

const currentMenuItem = computed(() => {
  const currentPath = route.path || '/trade-tasks'
  for (const group of visibleMenuGroups.value) {
    const item = group.children.find((child) => child.routePath === currentPath)
    if (item) {
      return item
    }
  }
  return visibleMenuGroups.value[0]?.children[0] || null
})

const currentGroupKey = computed(() => {
  const currentPath = route.path || '/trade-tasks'
  return visibleMenuGroups.value.find((group) => group.children.some((item) => item.routePath === currentPath))?.key || visibleMenuGroups.value[0]?.key || ''
})

const selectedKeys = computed(() => (currentMenuItem.value ? [currentMenuItem.value.key] : []))
const menuOpenKeys = computed(() => (collapsed.value ? [] : Array.from(new Set([currentGroupKey.value, ...openKeys.value].filter(Boolean)))))

watch(
  currentGroupKey,
  (value) => {
    if (value && !openKeys.value.includes(value)) {
      openKeys.value = [value, ...openKeys.value]
    }
  },
  { immediate: true },
)

function toggleCollapsed() {
  collapsed.value = !collapsed.value
}

function handleOpenChange(keys: string[]) {
  openKeys.value = keys
}

function handleMenuClick(event: { key: string }) {
  const target = visibleMenuGroups.value.flatMap((group) => group.children).find((item) => item.key === event.key)
  if (target) {
    router.push(target.routePath)
  }
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
