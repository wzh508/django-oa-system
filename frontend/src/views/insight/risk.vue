<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header"><span class="page-title">审批风险看板</span><el-button :icon="Refresh" @click="load">刷新</el-button></div>
    <el-row :gutter="16" v-if="data">
      <el-col :span="6" v-for="c in cards" :key="c.label"><el-card shadow="hover" :body-style="{ padding: '16px' }"><div class="n" :style="{ color: c.color }">{{ c.value }}</div><div class="t">{{ c.label }}</div></el-card></el-col>
    </el-row>
    <el-card shadow="never" header="在途单据风险明细（按风险分排序）" style="margin-top: 14px" v-if="risky.length">
      <el-table :data="risky" border stripe>
        <el-table-column prop="code" label="单号" width="160" />
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="risk_level" label="风险等级" width="100"><template #default="{ row }"><el-tag :type="row.risk_level === 'high' ? 'danger' : row.risk_level === 'medium' ? 'warning' : 'success'" size="small">{{ riskLabel[row.risk_level] || row.risk_level }}</el-tag></template></el-table-column>
        <el-table-column prop="risk_score" label="风险分" width="90" />
        <el-table-column prop="predicted_hours" label="预计时长(h)" width="120" />
        <el-table-column prop="current_node" label="当前节点" min-width="120" />
      </el-table>
    </el-card>
    <el-empty v-else-if="!loading" description="暂无风险数据" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { http } from '@/api/http'
import { insightApi } from '@/api/modules'
import { Refresh } from '@element-plus/icons-vue'
const loading = ref(false)
const data = ref(null)
const risky = ref([])
const cards = ref([])
const riskLabel = { high: '高', medium: '中', low: '低' }
async function load() {
  loading.value = true
  try {
    const d = await insightApi.risk()
    data.value = d
    risky.value = [...(d?.items || [])].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
    const dist = d?.distribution || {}
    cards.value = [
      { label: '在途单据', value: (d?.items || []).length, color: '#409eff' },
      { label: '高风险', value: dist.high ?? 0, color: '#f56c6c' },
      { label: '中风险', value: dist.medium ?? 0, color: '#e6a23c' },
      { label: '低风险', value: dist.low ?? 0, color: '#909399' },
    ]
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
onMounted(load)
</script>
<style scoped>
.n { font-size: 24px; font-weight: 700; }
.t { color: #909399; font-size: 13px; margin-top: 4px; }
</style>
