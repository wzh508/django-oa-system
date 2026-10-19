<template>
  <div class="page-card" v-loading="loading">
    <div v-if="staff">
      <div class="head">
        <el-avatar :size="56">{{ (staff.real_name || staff.username || '?').slice(0, 1) }}</el-avatar>
        <div class="info">
          <h2 style="margin: 0">{{ staff.real_name || staff.username }}</h2>
          <div class="meta">
            <span>工号：{{ staff.employee_no || '—' }}</span>
            <span>部门：{{ staff.dept_name || '—' }}</span>
            <span>岗位：{{ staff.position_name || '—' }}</span>
          </div>
        </div>
        <el-button @click="router.push('/hr/staff')">返回</el-button>
      </div>
      <el-tabs v-model="tab" style="margin-top: 10px">
        <el-tab-pane label="基本信息" name="base">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="姓名">{{ staff.real_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="性别">{{ label(GENDER, staff.gender) }}</el-descriptions-item>
            <el-descriptions-item label="学历">{{ staff.education || '—' }}</el-descriptions-item>
            <el-descriptions-item label="婚姻状况">{{ label(MARITAL, staff.marital_status) }}</el-descriptions-item>
            <el-descriptions-item label="籍贯">{{ staff.native_place || '—' }}</el-descriptions-item>
            <el-descriptions-item label="专业">{{ staff.major || '—' }}</el-descriptions-item>
            <el-descriptions-item label="紧急联系人">{{ staff.emergency_contact || '—' }}</el-descriptions-item>
            <el-descriptions-item label="联系电话">{{ staff.emergency_phone || '—' }}</el-descriptions-item>
            <el-descriptions-item label="转正日期">{{ staff.probation_end || '—' }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        <el-tab-pane label="合同" name="contract">
          <el-table :data="contracts" border size="small">
            <el-table-column label="类型" width="120"><template #default="{ row }">{{ label(CONTRACT_TYPE, row.contract_type) }}</template></el-table-column>
            <el-table-column prop="sign_date" label="签约日" width="130" />
            <el-table-column prop="start_date" label="开始" width="130" />
            <el-table-column prop="end_date" label="结束" width="130" />
            <el-table-column label="状态" width="90"><template #default="{ row }">{{ label(CONTRACT_STATUS, row.status) }}</template></el-table-column>
            <el-table-column prop="salary" label="薪资" width="100" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="入转调离" name="transfer">
          <el-table :data="transfers" border size="small">
            <el-table-column label="类型" width="100"><template #default="{ row }">{{ label(TRANSFER_TYPE, row.type) }}</template></el-table-column>
            <el-table-column prop="from_dept_name" label="原部门" width="140" />
            <el-table-column prop="to_dept_name" label="新部门" width="140" />
            <el-table-column prop="effective_date" label="生效" width="130" />
            <el-table-column label="状态" width="90"><template #default="{ row }">{{ label(TRANSFER_STATUS, row.status) }}</template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="培训" name="training">
          <el-table :data="trainings" border size="small">
            <el-table-column prop="title" label="主题" min-width="180" />
            <el-table-column prop="organization" label="机构" min-width="140" />
            <el-table-column prop="start_date" label="开始" width="130" />
            <el-table-column prop="hours" label="学时" width="80" />
            <el-table-column prop="score" label="成绩" width="80" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>
    <el-empty v-else-if="!loading" description="员工不存在" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { http } from '@/api/http'
import { hrApi } from '@/api/modules'
const route = useRoute()
const router = useRouter()
// 枚举值 → 中文标签（后端返回的是存储值，直接展示会露出英文/数字）
const GENDER = { 0: '未知', 1: '男', 2: '女' }
const MARITAL = { single: '未婚', married: '已婚', divorced: '离异', other: '其他' }
const CONTRACT_TYPE = { fixed: '固定期限', nonfixed: '无固定期限', intern: '实习', labor: '劳务', parttime: '兼职' }
const CONTRACT_STATUS = { active: '生效中', expired: '已到期', terminated: '已解除' }
const TRANSFER_TYPE = { onboard: '入职', regular: '转正', transfer: '调岗', offboard: '离职', rejoin: '复职' }
const TRANSFER_STATUS = { pending: '待生效', done: '已生效', cancelled: '已取消' }
function label(map, value) {
  if (value === null || value === undefined || value === '') return '—'
  return map[value] || value
}
const loading = ref(false)
const staff = ref(null)
const tab = ref('base')
const contracts = ref([])
const transfers = ref([])
const trainings = ref([])

async function load() {
  loading.value = true
  try {
    const data = await http.get(`/hr/staff/${route.params.id}/`)
    staff.value = data
    const [c, t, tr] = await Promise.all([
      http.get(hrApi.contracts, { params: { employee: data.user, page_size: 50 } }).catch(() => null),
      http.get(hrApi.transfers, { params: { employee: data.user, page_size: 50 } }).catch(() => null),
      http.get(hrApi.trainings, { params: { employee: data.user, page_size: 50 } }).catch(() => null),
    ])
    contracts.value = c?.list || []
    transfers.value = t?.list || []
    trainings.value = tr?.list || []
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
onMounted(load)
</script>
<style scoped>
.head { display: flex; align-items: center; gap: 16px; }
.info { flex: 1; }
.meta { color: #909399; font-size: 13px; margin-top: 6px; display: flex; gap: 14px; flex-wrap: wrap; }
</style>
