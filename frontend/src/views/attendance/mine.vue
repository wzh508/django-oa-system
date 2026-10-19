<template>
  <div class="page-card">
    <div class="page-header"><span class="page-title">我的考勤</span></div>
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="date" label="日期" width="120" />
      <el-table-column label="姓名" width="100">
        <template #default="{ row }">{{ row.user?.first_name || row.user?.username || '—' }}</template>
      </el-table-column>
      <el-table-column label="上班时间" width="130">
        <template #default="{ row }">{{ hhmm(row.sign_in_at) }}</template>
      </el-table-column>
      <el-table-column label="下班时间" width="130">
        <template #default="{ row }">{{ hhmm(row.sign_out_at) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }"><el-tag :type="statusType(row.status)" size="small">{{ row.status_display || statusLabel[row.status] || row.status }}</el-tag></template>
      </el-table-column>
      <el-table-column label="工时(h)" width="90">
        <template #default="{ row }">{{ ((row.work_minutes || 0) / 60).toFixed(1) }}</template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip />
    </el-table>
    <el-pagination class="pager" background layout="total, prev, pager, next" :total="total" :current-page="page" :page-size="pageSize" @current-change="(p) => load(p)" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { http } from '@/api/http'
import { attendanceApi } from '@/api/modules'
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const statusLabel = {
  normal: '正常', late: '迟到', early_leave: '早退', absent: '旷工', miss: '缺卡',
  leave: '请假', trip: '出差', rest: '休息日', holiday: '法定节假日',
}
const statusType = (s) =>
  s === 'normal' ? 'success'
    : s === 'late' || s === 'early_leave' || s === 'miss' ? 'warning'
      : s === 'absent' ? 'danger' : 'info'
const hhmm = (v) => (v ? String(v).slice(11, 16) : '—')

async function load(p) {
  if (p) page.value = p
  loading.value = true
  try {
    const data = await http.get(attendanceApi.records, { params: { page: page.value, page_size: pageSize.value } })
    rows.value = data?.list || []
    total.value = data?.total ?? 0
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
onMounted(() => load(1))
</script>
<style scoped>
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
