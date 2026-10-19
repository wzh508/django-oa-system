// 由后端菜单树动态生成前端路由（菜单即路由清单）
// 菜单节点：{ id, name, code, type, path, component, icon, permission_code, children }
// type=dir  → 仅作为分组，不生成路由；type=menu → 生成页面路由
// component 形如 "system/user" → 对应 src/views/system/user.vue；缺省回退到通用 CrudView
const viewModules = import.meta.glob('../views/**/*.vue')

function resolveComponent(componentPath) {
  const key = `../views/${componentPath}.vue`
  if (viewModules[key]) return viewModules[key]
  return () => import('../components/CrudView.vue')
}

function joinPath(base, child) {
  if (!child) return base
  if (child.startsWith('/')) return child
  const b = base.endsWith('/') ? base.slice(0, -1) : base
  return `${b}/${child}`
}

export function buildChildRoutes(menus, parentBase = '') {
  const routes = []
  for (const node of menus || []) {
    if (node.type === 'dir') {
      if (node.children && node.children.length) {
        routes.push(...buildChildRoutes(node.children, node.path))
      }
      continue
    }
    // menu / 其它可点击节点
    if (node.component) {
      const full = joinPath(parentBase, node.path)
      routes.push({
        path: full.replace(/^\//, ''),
        name: node.code,
        component: resolveComponent(node.component),
        meta: {
          title: node.name,
          icon: node.icon,
          permCode: node.permission_code,
          configKey: node.component,
        },
      })
    }
    if (node.children && node.children.length) {
      routes.push(...buildChildRoutes(node.children, parentBase))
    }
  }
  // 去重
  const seen = new Set()
  return routes.filter((r) => {
    if (seen.has(r.path)) return false
    seen.add(r.path)
    return true
  })
}
