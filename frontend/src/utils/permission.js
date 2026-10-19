// v-permission 指令：无权限时移除元素
// 用法：<el-button v-permission="'expense:audit'">审核</el-button>
import { useUserStore } from '@/store/modules/user'

function hasPermission(code) {
  if (!code) return true
  const codes = useUserStore().codes
  if (!codes || codes.length === 0) return false
  if (codes.includes('*') || codes.includes('admin')) return true
  if (codes.includes(code)) return true
  // 模块级通配：expense:* 命中 expense:audit
  const module = code.split(':')[0]
  return codes.includes(`${module}:*`)
}

export function setupPermissionDirective(app) {
  app.directive('permission', {
    mounted(el, binding) {
      if (!hasPermission(binding.value)) {
        el.parentNode && el.parentNode.removeChild(el)
      }
    },
    updated(el, binding) {
      // 指令更新时重新判定（仅处理单值）
      if (!hasPermission(binding.value)) {
        el.style && (el.style.display = 'none')
      } else {
        el.style && (el.style.display = '')
      }
    },
  })
}

export { hasPermission }
