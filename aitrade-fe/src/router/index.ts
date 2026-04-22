import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import BasicLayout from '@/layouts/BasicLayout.vue'
import LoginView from '@/views/login/LoginView.vue'
import UserListView from '@/views/users/UserListView.vue'
import TradeLogView from '@/views/trade-logs/TradeLogView.vue'
import StrategyConfigView from '@/views/strategies/StrategyConfigView.vue'

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
        },
        {
          path: 'trade-logs',
          name: 'trade-logs',
          component: TradeLogView,
        },
        {
          path: 'strategies',
          name: 'strategies',
          component: StrategyConfigView,
        },
      ],
    },
  ],
})

let restored = false
router.beforeEach(async (to) => {
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

export default router
