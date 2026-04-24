import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useRouteLoading } from '@/stores/routeLoading'

const BasicLayout = () => import('@/layouts/BasicLayout.vue')
const LoginView = () => import('@/views/login/LoginView.vue')
const UserListView = () => import('@/views/users/UserListView.vue')
const TradeLogView = () => import('@/views/trade-logs/TradeLogView.vue')
const StrategyConfigView = () => import('@/views/strategies/StrategyConfigView.vue')
const BacktestDataView = () => import('@/views/backtests/BacktestDataView.vue')
const BacktestView = () => import('@/views/backtests/BacktestView.vue')

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
          path: 'users',
          name: 'users',
          component: UserListView,
          meta: {
            title: '用户维护',
          },
        },
        {
          path: 'trade-logs',
          name: 'trade-logs',
          component: TradeLogView,
          meta: {
            title: '交易日志',
          },
        },
        {
          path: 'strategies',
          name: 'strategies',
          component: StrategyConfigView,
          meta: {
            title: '策略配置',
          },
        },
        {
          path: 'backtest-data',
          name: 'backtest-data',
          component: BacktestDataView,
          meta: {
            title: '历史数据管理',
          },
        },
        {
          path: 'backtests',
          name: 'backtests',
          component: BacktestView,
          meta: {
            title: '策略回测',
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
