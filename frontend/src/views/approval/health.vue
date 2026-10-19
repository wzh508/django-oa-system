<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header"><span class="page-title">流程健康度</span><el-button :icon="Refresh" @click="load">刷新</el-button></div>
    <el-row :gutter="16" v-if="report">
      <el-col :span="6" v-for="c in statCards" :key="c.label">
        <el-card shadow="hover" :body-style="{ padding: '16px' }">
          <div class="n">{{ c.value }}</div><div class="t">{{ c.label }}</div>
        </el-card>
      </el-col>
    </el-row>
    <el-card shadow="never" header="节点健康度明细" style="margin-top: 14px" v-if="rows.length">
      <el-table :data="rows" border stripe>
        <el-table-column prop="node" label="节点" min-width="160" />
        <el-table-column prop="total" label="处理数" width="90" />
        <el-table-column prop="avg_hours" label="平均时长(h)" width="120" />
        <el-table-column prop="overtime_rate" label="超时率" width="110">
          <template #default="{ row }"><el-tag :type="rateType(row.overtime_rate)" size="small">{{ pct(row.overtime_rate) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="reject_rate" label="驳回率" width="110">
          <template #default="{ row }"><el-tag :type="rateType(row.reject_rate)" size="small">{{ pct(row.reject_rate) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="bottleneck" label="瓶颈" width="90">
          <template #default="{ row }"><el-tag v-if="row.bottleneck" type="danger" size="small">瓶颈</el-tag><span v-else class="muted">—</span></template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-empty v-else-if="!loading" description="暂无健康度数据" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { http } from '@/api/http'
import { Refresh } from '@element-plus/icons-vue'
const loading = ref(false)
const report = ref(null)
const rows = ref([])
const statCards = ref([])

const pct = (v) => (v == null ? '—' : (v * 100).toFixed(1) + '%')
const rateType = (v) => (v > 0.3 ? 'danger' : v > 0.1 ? 'warning' : 'success')

async function load() {
  loading.value = true
  try {
    const data = await http.get('/workflow/health/report/')
    report.value = data
    const list = data?.nodes || []
    rows.value = list
    if (data) {
      statCards.value = [
        { label: '在途待办', value: data.pending_total ?? '—' },
        { label: '已超时待办', value: data.overdue_total ?? '—' },
        { label: '覆盖节点数', value: list.length },
        { label: '瓶颈节点数', value: list.filter((r) => r.bottleneck).length },
      ]
    }
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
onMounted(load)
</script>
<style scoped>
.n { font-size: 24px; font-weight: 700; }
.t { color: #909399; font-size: 13px; margin-top: 4px; }
.muted { color: #909399; }
</style>
