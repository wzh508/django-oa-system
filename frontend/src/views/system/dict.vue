<template>
  <div class="page-card">
    <div class="page-header"><span class="page-title">数据字典</span></div>
    <el-alert type="info" :closable="false" title="数据字典以系统参数为载体，集中维护全局可配置项。" style="margin-bottom: 12px" />
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="key" label="键" min-width="200" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="value" label="值" min-width="180" show-overflow-tooltip />
      <el-table-column prop="remark" label="说明" min-width="220" show-overflow-tooltip />
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { http } from '@/api/http'
const rows = ref([])
const loading = ref(false)
async function load() {
  loading.value = true
  try { const data = await http.get('/accounts/system-params/', { params: { page_size: 200 } }); rows.value = data?.list || [] } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
onMounted(load)
</script>
<style scoped>
</style>
