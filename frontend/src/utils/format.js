// 通用格式化工具
export function fmtDateTime(v) {
  if (!v) return ''
  const d = new Date(v)
  if (isNaN(d.getTime())) return v
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

export function fmtDate(v) {
  if (!v) return ''
  return (v || '').slice(0, 10)
}

export function money(v) {
  if (v === null || v === undefined || v === '') return '0.00'
  const n = Number(v)
  return isNaN(n) ? v : n.toFixed(2)
}

export function yesNo(v) {
  return v ? '是' : '否'
}

// 把对象列表转成级联/下拉选项 [{label,value}]
export function toOptions(list, labelKey = 'name', valueKey = 'id') {
  return (list || []).map((it) => ({ label: it[labelKey], value: it[valueKey] }))
}

// 简单的状态标签映射
export const STATUS_TAG = {
  pending: 'warning',
  running: 'primary',
  approved: 'success',
  rejected: 'danger',
  draft: 'info',
  paid: 'success',
  paying: 'warning',
  done: 'success',
  todo: 'warning',
}
