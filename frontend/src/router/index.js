import { createRouter, createWebHistory } from 'vue-router'
import { getToken, clearToken } from '@/utils/auth'
import { useUserStore } from '@/store/modules/user'
import { buildChildRoutes } from './dynamic'

const Layout = () => import('@/layout/DefaultLayout.vue')

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    name: 'Layout',
    component: Layout,
    redirect: '/dashboard/index',
    children: [],
  },
  {
    path: '/403',
    name: '403',
    component: () => import('@/views/error/403.vue'),
    meta: { public: true, title: '无访问权限' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: '404',
    component: () => import('@/views/error/404.vue'),
    // 注意：不设 public，未登录访问未知路径应先跳登录页，而非直接展示 404
    meta: { title: '页面不存在' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

let routesReady = false

router.beforeEach(async (to, from, next) => {
  document.title = to.meta.title ? `${to.meta.title} - OA 管理系统` : 'OA 管理系统'
  const token = getToken()

  if (!token) {
    if (to.meta.public) return next()
    return next('/login')
  }
  if (to.path === '/login') return next('/')

  const userStore = useUserStore()
  if (!routesReady) {
    try {
      if (!userStore.menus.length) await userStore.loadAccess()
      const children = buildChildRoutes(userStore.menus)
      const existing = new Set(router.getRoutes().map((r) => r.path))
      for (const r of children) {
        if (!existing.has(r.path)) router.addRoute('Layout', r)
      }
      routesReady = true
      // 必须按 path 重新解析：若用 { ...to } 会带上首次匹配到的 name（如 404 兜底），
      // 导致动态路由首次加载被错误地重定向到 404 页。
      return next({ path: to.fullPath, replace: true })
    } catch (e) {
      clearToken()
      return next('/login')
    }
  }

  // 按钮/页面级权限校验
  if (to.meta.permCode && !userStore.hasPerm(to.meta.permCode)) {
    return next('/403')
  }
  next()
})

export function resetRoutesReady() {
  routesReady = false
}

export default router
