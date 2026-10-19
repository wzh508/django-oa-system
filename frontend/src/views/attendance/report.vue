<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header">
      <span class="page-title">考勤报表</span>
      <el-button :icon="Download" @click="exportReport">导出报表</el-button>
    </div>
    <el-form :inline="true" :model="q">
      <el-form-item label="月份">
        <el-date-picker v-model="q.month" type="month" value-format="YYYY-MM" placeholder="选择月份" style="width: 160px" />
      </el-form-item>
      <el-button type="primary" :icon="Search" @click="load">查询</el-button>
    </el-form>
    <el-table :data="rows" border stripe empty-text="暂无数据">
      <el-table-column label="姓名" width="100">
        <template #default="{ row }">{{ row.name || row.username || '—' }}</template>
      </el-table-column>
      <el-table-column prop="dept" label="部门" min-width="140" />
      <el-table-column prop="work_days" label="应出勤" width="90" />
      <el-table-column prop="present_days" label="实际出勤" width="90" />
      <el-table-column prop="late_count" label="迟到" width="80" />
      <el-table-column prop="early_count" label="早退" width="80" />
      <el-table-column prop="absent_count" label="缺勤天数" width="90" />
      <el-table-column label="加班(h)" width="100">
        <template #default="{ row }">{{ ((row.overtime_minutes || 0) / 60).toFixed(1) }}</template>
      </el-table-column>
      <el-table-column label="出勤率" width="110">
        <template #default="{ row }">
          <el-tag :type="rateType(row.attendance_rate)" size="small">{{ pct(row.attendance_rate) }}</el-tag>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { Download, Search } from '@element-plus/icons-vue'
const rows = ref([])
const loading = ref(false)
const q = reactive({ month: new Date().toISOString().slice(0, 7) })

// 后端 attendance_rate 已是百分数（0-100），直接展示，勿再乘 100
const pct = (v) => (v == null ? '—' : Number(v).toFixed(1) + '%')
const rateType = (v) => (v >= 90 ? 'success' : v >= 80 ? 'warning' : 'danger')

async function load() {
  loading.value = true
  try {
    // 报表为「按员工汇总」的行数据，后端对应部门汇总接口的 rows
    const data = await http.get('/attendance/summary/dept/', { params: { month: q.month } })
    rows.value = data?.rows || []
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}

async function exportReport() {
  try {
    // 直接 window.open 不会带上 Authorization 头，改为带鉴权请求后本地下载
    const blob = await http.get('/attendance/records/export/', {
      params: { format: 'csv' },
      responseType: 'blob',
    })
    const url = URL.createObjectURL(new Blob([blob], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `attendance-${q.month || 'all'}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('已导出 CSV')
  } catch (e) {
    ElMessage.error('导出失败')
  }
}
onMounted(load)
</script>
<style scoped>
</style>
