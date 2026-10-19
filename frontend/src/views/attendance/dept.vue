<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header">
      <span class="page-title">部门考勤汇总</span>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>
    <el-form :inline="true" :model="q">
      <el-form-item label="月份">
        <el-date-picker v-model="q.month" type="month" value-format="YYYY-MM" placeholder="选择月份" style="width: 160px" @change="load" />
      </el-form-item>
    </el-form>
    <el-table :data="rows" border stripe empty-text="暂无数据">
      <el-table-column prop="dept_name" label="部门" min-width="160" />
      <el-table-column prop="total" label="应到" width="90" />
      <el-table-column prop="present" label="实到" width="90" />
      <el-table-column prop="late" label="迟到" width="90" />
      <el-table-column prop="absent" label="缺勤" width="90" />
      <el-table-column prop="leave" label="请假" width="90" />
      <el-table-column label="出勤率" width="110">
        <template #default="{ row }">
          <el-tag :type="rateType(row.rate)" size="small">{{ pct(row.rate) }}</el-tag>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { http } from '@/api/http'
import { Refresh } from '@element-plus/icons-vue'
const rows = ref([])
const loading = ref(false)
const q = reactive({ month: new Date().toISOString().slice(0, 7) })

const pct = (v) => (v == null ? '—' : (v * 100).toFixed(1) + '%')
const rateType = (v) => (v >= 0.9 ? 'success' : v >= 0.8 ? 'warning' : 'danger')

async function load() {
  loading.value = true
  try {
    // 后端返回「按员工」的月度汇总行，这里按部门归并成部门级指标
    const data = await http.get('/attendance/summary/dept/', { params: { month: q.month } })
    const raw = data?.rows || []
    const agg = new Map()
    for (const r of raw) {
      const key = r.dept || '未分配部门'
      if (!agg.has(key)) agg.set(key, { dept_name: key, total: 0, present: 0, late: 0, absent: 0, leave: 0 })
      const a = agg.get(key)
      a.total += r.work_days || 0
      a.present += r.present_days || 0
      a.late += r.late_count || 0
      a.absent += r.absent_count || 0
      a.leave += r.leave_days || 0
    }
    rows.value = [...agg.values()].map((a) => ({ ...a, rate: a.total ? a.present / a.total : 0 }))
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
onMounted(load)
</script>
<style scoped>
</style>
