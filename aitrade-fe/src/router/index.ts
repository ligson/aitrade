import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useRouteLoading } from '@/stores/routeLoading'

const BasicLayout = () => import('@/layouts/BasicLayout.vue')
const LoginView = () => import('@/views/login/LoginView.vue')
const UserListView = () => import('@/views/users/UserListView.vue')
const TradeLogView = () => import('@/views/trade-logs/TradeLogView.vue')
const TradeTaskProfileView = () => import('@/views/trade-logs/TradeTaskProfileView.vue')
const TradeTaskControlView = () => import('@/views/trade-logs/TradeTaskControlView.vue')
const TradeTaskLogView = () => import('@/views/trade-logs/TradeTaskLogView.vue')
const StrategyConfigView = () => import('@/views/strategies/StrategyConfigView.vue')
const SignalSourceConfigView = () => import('@/views/strategies/SignalSourceConfigView.vue')
const BacktestDataView = () => import('@/views/backtests/BacktestDataView.vue')
const BacktestView = () => import('@/views/backtests/BacktestView.vue')
const SystemSettingsView = () => import('@/views/system/SystemSettingsView.vue')
const SystemAISettingsView = () => import('@/views/system/SystemAISettingsView.vue')
const SystemTradeSettingsView = () => import('@/views/system/SystemTradeSettingsView.vue')
const SystemDataSettingsView = () => import('@/views/system/SystemDataSettingsView.vue')
const SystemLogView = () => import('@/views/system/SystemLogView.vue')
const HelpCenterView = () => import('@/views/help/HelpCenterView.vue')
const HelpGettingStartedView = () => import('@/views/help/HelpGettingStartedView.vue')
const HelpTerminologyView = () => import('@/views/help/HelpTerminologyView.vue')
const HelpStrategyPrinciplesView = () => import('@/views/help/HelpStrategyPrinciplesView.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
    },
    {
      path: '/',
      component: BasicLayout,
      children: [
        {
          path: '',
          redirect: '/trade-logs',
        },
        {
          path: 'system-settings',
          name: 'system-settings',
          component: SystemSettingsView,
          meta: {
            title: '系统概览',
            breadcrumb: ['系统管理', '系统概览'],
          },
        },
        {
          path: 'system-ai-settings',
          name: 'system-ai-settings',
          component: SystemAISettingsView,
          meta: {
            title: 'AI 设置',
            breadcrumb: ['系统管理', 'AI 设置'],
          },
        },
        {
          path: 'system-trade-settings',
          name: 'system-trade-settings',
          component: SystemTradeSettingsView,
          meta: {
            title: '交易设置',
            breadcrumb: ['系统管理', '交易设置'],
          },
        },
        {
          path: 'system-data-settings',
          name: 'system-data-settings',
          component: SystemDataSettingsView,
          meta: {
            title: '数据设置',
            breadcrumb: ['系统管理', '数据设置'],
          },
        },
        {
          path: 'system-logs',
          name: 'system-logs',
          component: SystemLogView,
          meta: {
            title: '系统日志',
            breadcrumb: ['系统管理', '系统日志'],
          },
        },
        {
          path: 'users',
          name: 'users',
          component: UserListView,
          meta: {
            title: '用户维护',
            breadcrumb: ['系统管理', '用户维护'],
          },
        },
        {
          path: 'trade-tasks',
          redirect: '/trade-task-profiles',
        },
        {
          path: 'trade-task-profiles',
          name: 'trade-task-profiles',
          component: TradeTaskProfileView,
          meta: {
            title: '交易任务配置',
            breadcrumb: ['交易中心', '交易任务配置'],
          },
        },
        {
          path: 'trade-task-control',
          name: 'trade-task-control',
          component: TradeTaskControlView,
          meta: {
            title: '交易任务控制',
            breadcrumb: ['交易中心', '交易任务控制'],
          },
        },
        {
          path: 'trade-task-logs',
          name: 'trade-task-logs',
          component: TradeTaskLogView,
          meta: {
            title: '任务日志',
            breadcrumb: ['交易中心', '任务日志'],
          },
        },
        {
          path: 'trade-logs',
          name: 'trade-logs',
          component: TradeLogView,
          meta: {
            title: '交易日志',
            breadcrumb: ['交易中心', '交易日志'],
          },
        },
        {
          path: 'strategies',
          name: 'strategies',
          component: StrategyConfigView,
          meta: {
            title: '策略配置',
            breadcrumb: ['策略中心', '策略配置'],
          },
        },
        {
          path: 'signal-sources',
          name: 'signal-sources',
          component: SignalSourceConfigView,
          meta: {
            title: '信号源配置',
            breadcrumb: ['策略中心', '信号源配置'],
          },
        },
        {
          path: 'backtest-data',
          name: 'backtest-data',
          component: BacktestDataView,
          meta: {
            title: '历史数据管理',
            breadcrumb: ['数据中心', '历史数据管理'],
          },
        },
        {
          path: 'backtests',
          name: 'backtests',
          component: BacktestView,
          meta: {
            title: '策略回测',
            breadcrumb: ['策略中心', '策略回测'],
          },
        },
        {
          path: 'help-center',
          name: 'help-center',
          component: HelpCenterView,
          meta: {
            title: '帮助总览',
            breadcrumb: ['帮助中心', '帮助总览'],
          },
        },
        {
          path: 'help-getting-started',
          name: 'help-getting-started',
          component: HelpGettingStartedView,
          meta: {
            title: '系统使用指南',
            breadcrumb: ['帮助中心', '系统使用指南'],
          },
        },
        {
          path: 'help-terminology',
          name: 'help-terminology',
          component: HelpTerminologyView,
          meta: {
            title: '量化术语',
            breadcrumb: ['帮助中心', '量化术语'],
          },
        },
        {
          path: 'help-strategy-principles',
          name: 'help-strategy-principles',
          component: HelpStrategyPrinciplesView,
          meta: {
            title: '策略原则',
            breadcrumb: ['帮助中心', '策略原则'],
          },
        },
      ],
    },
  ],
})

let restored = false
const routeLoading = useRouteLoading()

router.beforeEach(async (to) => {
  routeLoading.start()
  const auth = useAuthStore()
  if (!restored) {
    restored = true
    await auth.restore()
  }
  if (to.path === '/login' && auth.isLoggedIn) {
    return '/trade-logs'
  }
  if (to.path !== '/login' && !auth.isLoggedIn) {
    return '/login'
  }
  return true
})

router.afterEach(() => {
  routeLoading.finish()
})

router.onError(() => {
  routeLoading.fail()
})

export { router }
export default router
