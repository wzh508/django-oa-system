<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header"><span class="page-title">二次授权记录（敏感访问）</span></div>
    <el-table :data="rows" border stripe empty-text="暂无授权记录">
      <el-table-column prop="created_at" label="时间" min-width="160" />
      <el-table-column prop="operator_name" label="操作人" width="110" />
      <el-table-column prop="model_label" label="对象" min-width="140" />
      <el-table-column prop="action" label="动作" width="100" />
      <el-table-column prop="reason" label="原因" min-width="200" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }"><el-tag :type="row.status === 'approved' ? 'success' : row.status === 'rejected' ? 'danger' : 'warning'" size="small">{{ statusLabel[row.status] || row.status }}</el-tag></template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { http } from '@/api/http'
const loading = ref(false)
const rows = ref([])
const statusLabel = { pending: '待审', approved: '已批准', rejected: '已拒绝' }
async function load() {
  loading.value = true
  try { const data = await http.get('/accounts/sensitive/logs/', { params: { page_size: 50 } }); rows.value = data?.list || data || [] } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
onMounted(load)
</script>
<style scoped>
</style>
