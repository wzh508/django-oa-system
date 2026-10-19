import { http } from './http'

// ============ 组织与权限 ============
export const accountsApi = {
  users: '/accounts/users/',
  roles: '/accounts/roles/',
  depts: '/accounts/departments/',
  positions: '/accounts/positions/',
  permissions: '/accounts/permissions/',
  menus: '/accounts/menus/',
  params: '/accounts/system-params/',
  oplog: '/accounts/operation-logs/',
  loginlog: '/accounts/login-logs/',
  dataScopeRules: '/accounts/data-scope-rules/',
  // 角色分配权限（沙盘落库）
  sandboxSimulate: (data) => http.post('/accounts/permission-sandbox/simulate/', data),
  sandboxApply: (data) => http.post('/accounts/permission-sandbox/apply/', data),
  sandboxRollback: (data) => http.post('/accounts/permission-sandbox/rollback/', data),
  sandboxChanges: () => http.get('/accounts/permission-sandbox/changes/'),
  explainPermission: (params) => http.get('/accounts/explain/permission/', params),
  explainDataScope: (params) => http.get('/accounts/explain/data-scope/', params),
  roleEffectivePerms: (id) => http.get(`/accounts/roles/${id}/effective-permissions/`),
  roleCheckCycle: () => http.get('/accounts/roles/check-cycle/'),
  permModules: () => http.get('/accounts/permissions/modules/'),
  treeDepts: () => http.get('/accounts/departments/tree/'),
  deptStats: () => http.get('/accounts/departments/stats/'),
  treeMenus: () => http.get('/accounts/menus/tree/'),
  userAssignRoles: (id, data) => http.post(`/accounts/users/${id}/roles/`, data),
  userResetPwd: (id) => http.post(`/accounts/users/${id}/reset-password/`, {}),
  userToggleActive: (id) => http.post(`/accounts/users/${id}/toggle-active/`, {}),
}

// ============ 审批流 ============
export const workflowApi = {
  templates: '/workflow/templates/',
  instances: '/workflow/instances/',
  tasks: '/workflow/tasks/',
  requests: '/workflow/requests/',
  urges: '/workflow/urges/',
  startInstance: (data) => http.post('/workflow/instances/start/', data),
  revokeInstance: (id, data) => http.post(`/workflow/instances/${id}/revoke/`, data),
  urgeInstance: (id, data) => http.post(`/workflow/instances/${id}/urge/`, data),
  terminateInstance: (id, data) => http.post(`/workflow/instances/${id}/terminate/`, data),
  instanceFlow: (id) => http.get(`/workflow/instances/${id}/flow/`),
  publishTemplate: (id) => http.post(`/workflow/templates/${id}/publish/`, {}),
  rollbackTemplate: (id) => http.post(`/workflow/templates/${id}/rollback/`, {}),
  diffTemplate: (id) => http.get(`/workflow/templates/${id}/diff/`),
  templateVersions: () => http.get('/workflow/templates/versions/'),
  actTask: (id, data) => http.post(`/workflow/tasks/${id}/act/`, data),
  batchApprove: (data) => http.post('/workflow/tasks/batch-approve/', data),
  replayRun: (data) => http.post('/workflow/replay/run/', data),
  replayReports: () => http.get('/workflow/replay/reports/'),
  replayResult: (id) => http.get(`/workflow/replay/${id}/result/`),
  healthReport: () => http.get('/workflow/health/report/'),
  expenseStats: () => http.get('/workflow/requests/stats/'),
  expenseAudit: (id, data) => http.post(`/workflow/requests/${id}/audit/`, data),
  expensePay: (id, data) => http.post(`/workflow/requests/${id}/pay/`, data),
  expenseTimeline: (id) => http.get(`/workflow/requests/${id}/timeline/`),
}

// ============ 智能分析（创新点 6.3） ============
export const insightApi = {
  refresh: () => http.post('/insight/refresh/', {}),
  risk: () => http.get('/insight/risk/'),
  bottleneck: () => http.get('/insight/bottleneck/'),
  stats: () => http.get('/insight/stats/'),
  urge: (data) => http.post('/insight/urge/', data || {}),
}

// ============ 低代码（创新点 6.5） ============
export const lowcodeApi = {
  schemas: '/lowcode/schemas/',
  records: '/lowcode/records/',
  publish: (id) => http.post(`/lowcode/schemas/${id}/publish/`, {}),
  render: (code) => http.get(`/lowcode/schemas/render/?code=${code}`),
  processRecord: (id, data) => http.post(`/lowcode/records/${id}/process/`, data),
}

// ============ 消息中心 ============
export const messageApi = {
  list: '/message/',
  read: (id) => http.post(`/message/${id}/read/`, {}),
  readAll: () => http.post('/message/read-all/', {}),
  unreadCount: () => http.get('/message/unread-count/'),
}

// ============ 人事 ============
export const hrApi = {
  staff: '/hr/staff/',
  transfers: '/hr/transfers/',
  contracts: '/hr/contracts/',
  trainings: '/hr/trainings/',
  analytics: () => http.get('/hr/analytics/structure/'),
}

// ============ 考勤 ============
export const attendanceApi = {
  rules: '/attendance/rules/',
  punch: '/attendance/punch/',
  records: '/attendance/records/',
  exceptions: '/attendance/exceptions/',
  punchToday: () => http.get('/attendance/punch/today/'),
  recordExport: () => http.get('/attendance/records/export/'),
  exceptionHandle: (id, data) => http.post(`/attendance/exceptions/${id}/handle/`, data),
  summaryDept: () => http.get('/attendance/summary/dept/'),
  summaryMonthly: () => http.get('/attendance/summary/monthly/'),
}

// ============ 公告 / 文档 / 会议 / 日程 ============
export const announcementApi = {
  notices: '/announcement/notices/',
  read: (id) => http.post(`/announcement/notices/${id}/read/`, {}),
  stats: () => http.get('/announcement/notices/stats/'),
}
export const documentApi = { docs: '/document/docs/' }
export const meetingApi = {
  rooms: '/meeting/rooms/',
  bookings: '/meeting/bookings/',
  minutes: '/meeting/minutes/',
}
export const scheduleApi = {
  schedules: '/schedule/schedules/',
  tasks: '/schedule/tasks/',
}
