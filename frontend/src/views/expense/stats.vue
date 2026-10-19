<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header"><span class="page-title">报销统计</span></div>
    <el-row :gutter="16">
      <el-col :span="6" v-for="c in cards" :key="c.label">
        <el-card shadow="hover" :body-style="{ padding: '16px' }"><div class="n">{{ c.value }}</div><div class="t">{{ c.label }}</div></el-card>
      </el-col>
    </el-row>
    <el-row :gutter="16" style="margin-top: 14px">
      <el-col :span="12">
        <el-card shadow="never" header="按费用类型"><div v-for="i in byType" :key="i.label" class="bar-row"><span class="bl">{{ i.label }}</span><div class="btrack"><div class="bfill" :style="{ width: pct(i.value) + '%' }"></div></div><span class="bv">¥{{ i.value }}</span></div></el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" header="按状态">
          <el-table :data="byStatus" border size="small">
            <el-table-column prop="label" label="状态" />
            <el-table-column prop="count" label="笔数" width="100" />
            <el-table-column prop="amount" label="金额" width="120"><template #default="{ row }">¥{{ row.amount }}</template></el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { http } from '@/api/http'
import { workflowApi } from '@/api/modules'
const loading = ref(false)
const cards = ref([])
const byType = ref([])
const byStatus = ref([])
const maxType = ref(1)
function pct(v) { return maxType.value ? Math.round((v / maxType.value) * 100) : 0 }
const FEE_LABEL = { traffic: '交通费', travel: '差旅费', meal: '餐饮费', office: '办公费', entertain: '招待费', other: '其他' }
const STATUS_LABEL = { draft: '草稿', pending: '审批中', approved: '已通过', rejected: '已驳回' }
async function load() {
  loading.value = true
  try {
    const data = await workflowApi.expenseStats()
    const byStatusList = data?.by_status || []
    cards.value = [
      { label: '报销总笔数', value: byStatusList.reduce((a, b) => a + (b.count || 0), 0) },
      { label: '报销总额', value: '¥' + (data?.total_amount ?? 0) },
      { label: '审批中', value: data?.pending ?? 0 },
      { label: '待支付金额', value: '¥' + (data?.unpaid_amount ?? 0) },
    ]
    byType.value = (data?.by_type || []).map((t) => ({ label: t.fee_type_display || FEE_LABEL[t.fee_type] || t.fee_type, value: t.total }))
    maxType.value = Math.max(1, ...byType.value.map((x) => x.value))
    byStatus.value = byStatusList.map((s) => ({ label: STATUS_LABEL[s.status] || s.status, count: s.count, amount: s.total }))
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
onMounted(load)
</script>
<style scoped>
.n { font-size: 24px; font-weight: 700; }
.t { color: #909399; font-size: 13px; margin-top: 4px; }
.bar-row { display: flex; align-items: center; gap: 10px; margin: 8px 0; font-size: 13px; }
.bl { width: 80px; color: #606266; }
.btrack { flex: 1; background: #f0f2f5; border-radius: 4px; height: 16px; overflow: hidden; }
.bfill { height: 100%; background: #409eff; border-radius: 4px; }
.bv { width: 90px; text-align: right; color: #909399; }
</style>
