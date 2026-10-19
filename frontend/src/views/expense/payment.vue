<template>
  <div class="page-card">
    <div class="page-header"><span class="page-title">支付跟踪</span></div>
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="code" label="单号" width="160" />
      <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
      <el-table-column prop="applicant_name" label="申请人" width="100" />
      <el-table-column prop="amount" label="金额" width="100"><template #default="{ row }">¥{{ row.amount }}</template></el-table-column>
      <el-table-column prop="status_display" label="审批状态" width="100" />
      <el-table-column prop="pay_status_display" label="支付状态" width="100">
        <template #default="{ row }"><el-tag :type="row.pay_status === 'paid' ? 'success' : row.pay_status === 'paying' ? 'warning' : 'info'" size="small">{{ row.pay_status_display }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.pay_status === 'unpaid' && row.status === 'approved'" link type="warning" @click="pay(row)">支付</el-button>
          <span v-else>—</span>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination class="pager" background layout="total, prev, pager, next" :total="total" :current-page="page" :page-size="pageSize" @current-change="(p) => load(p)" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { workflowApi } from '@/api/modules'
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
async function load(p) {
  if (p) page.value = p
  loading.value = true
  try {
    const data = await http.get(workflowApi.requests, { params: { page: page.value, page_size: pageSize.value } })
    rows.value = data?.list || []
    total.value = data?.total ?? 0
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
async function pay(row) {
  try { await workflowApi.expensePay(row.id, {}); ElMessage.success('支付成功'); load() } catch (e) {}
}
onMounted(() => load(1))
</script>
<style scoped>
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
