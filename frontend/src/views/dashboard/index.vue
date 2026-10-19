<template>
  <div class="dashboard">
    <el-row :gutter="16">
      <el-col :span="6" v-for="c in cards" :key="c.title">
        <el-card shadow="hover" class="stat-card" :body-style="{ padding: '18px 20px' }">
          <div class="stat-icon" :style="{ background: c.bg }"><el-icon :size="26"><component :is="c.icon" /></el-icon></div>
          <div class="stat-body">
            <div class="stat-num">{{ c.value }}</div>
            <div class="stat-title">{{ c.title }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="16">
        <el-card shadow="never" header="我的待办">
          <template #header>
            <div class="card-head"><span>我的待办</span><el-button text type="primary" @click="go('/workspace/todo')">全部</el-button></div>
          </template>
          <el-table :data="todos" v-loading="loading" size="small" empty-text="暂无待办">
            <el-table-column prop="instance_title" label="事项" min-width="160" show-overflow-tooltip />
            <el-table-column prop="node_name" label="当前节点" width="110" />
            <el-table-column prop="applicant_name" label="发起人" width="100" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.overdue ? 'danger' : 'warning'" size="small">{{ row.overdue ? '超时' : '待处理' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="go(`/approval/task?id=${row.id}`)">处理</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" header="快捷入口" :body-style="{ padding: '12px' }">
          <div class="quick-grid">
            <div class="quick-item" v-for="q in quick" :key="q.path" @click="go(q.path)">
              <el-icon :size="22"><component :is="q.icon" /></el-icon>
              <span>{{ q.label }}</span>
            </div>
          </div>
          <el-divider />
          <div class="msg-tip">未读消息：<b>{{ unread }}</b> 条 <el-button text type="primary" @click="go('/message/center')">前往</el-button></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { markRaw, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { messageApi } from '@/api/modules'
import { Tickets, Document, ChatDotRound, Clock, EditPen, Money, Bell, Calendar, User } from '@element-plus/icons-vue'

const router = useRouter()
const loading = ref(false)
const todos = ref([])
const unread = ref(0)
const cards = ref([
  { title: '待办任务', value: 0, icon: markRaw(Tickets), bg: '#409eff' },
  { title: '我的申请', value: 0, icon: markRaw(Document), bg: '#67c23a' },
  { title: '未读消息', value: 0, icon: markRaw(ChatDotRound), bg: '#e6a23c' },
  { title: '今日打卡', value: '—', icon: markRaw(Clock), bg: '#909399' },
])
const quick = [
  { label: '发起申请', path: '/approval/create', icon: markRaw(EditPen) },
  { label: '报销申请', path: '/expense/apply', icon: markRaw(Money) },
  { label: '打卡', path: '/attendance/punch', icon: markRaw(Bell) },
  { label: '会议预约', path: '/meeting/booking', icon: markRaw(Calendar) },
  { label: '员工档案', path: '/hr/staff', icon: markRaw(User) },
  { label: '公告', path: '/announcement/list', icon: markRaw(ChatDotRound) },
]

function go(p) { router.push(p) }

async function load() {
  loading.value = true
  try {
    const m = await messageApi.unreadCount().catch(() => null)
    // 待办
    try {
      const tdata = await import('@/api/http').then(({ http }) => http.get('/workflow/tasks/', { params: { status: 'pending', page_size: 8 } }))
      todos.value = (tdata?.list || [])
      cards.value[0].value = tdata?.total ?? todos.value.length
    } catch (e) {}
    // 我的申请
    try {
      const idata = await import('@/api/http').then(({ http }) => http.get('/workflow/instances/', { params: { page_size: 1 } }))
      cards.value[1].value = idata?.total ?? 0
    } catch (e) {}
    unread.value = m?.count ?? 0
    cards.value[2].value = unread.value
    // 今日打卡
    try {
      const p = await import('@/api/http').then(({ http }) => http.get('/attendance/punch/today/'))
      cards.value[3].value = (p?.punches || []).length
    } catch (e) { /* 无打卡权限则保持 — */ }
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<style scoped>
.stat-card { display: flex; align-items: center; gap: 14px; }
.stat-icon { width: 52px; height: 52px; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: #fff; }
.stat-num { font-size: 26px; font-weight: 700; line-height: 1.1; }
.stat-title { color: #909399; font-size: 13px; margin-top: 2px; }
.card-head { display: flex; justify-content: space-between; align-items: center; }
.quick-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.quick-item { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 12px 4px; border-radius: 8px; cursor: pointer; color: #606266; }
.quick-item:hover { background: #ecf5ff; color: #409eff; }
.msg-tip { font-size: 13px; color: #606266; }
</style>
