<template>
  <div class="page-card">
    <div class="page-header">
      <span class="page-title">我的申请</span>
      <el-button type="primary" :icon="EditPen" @click="router.push('/approval/create')">发起申请</el-button>
    </div>
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="code" label="单号" width="160" />
      <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
      <el-table-column prop="template_name" label="类型" width="120" />
      <el-table-column prop="current_node_name" label="当前节点" width="120" />
      <el-table-column prop="status_display" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ row.status_display }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="submitted_at" label="提交时间" min-width="160" />
      <el-table-column prop="finished_at" label="结束时间" min-width="160" />
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="router.push(`/approval/detail/${row.id}`)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination class="pager" background layout="total, prev, pager, next" :total="total" :current-page="page" :page-size="pageSize" @current-change="(p) => load(p)" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { http } from '@/api/http'
import { EditPen } from '@element-plus/icons-vue'
const router = useRouter()
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)

function statusType(s) {
  return { draft: 'info', pending: 'warning', approved: 'success', rejected: 'danger', terminated: 'info', withdrawn: 'info' }[s] || 'info'
}
async function load(p) {
  if (p) page.value = p
  loading.value = true
  try {
    const data = await http.get('/workflow/instances/', { params: { page: page.value, page_size: pageSize.value } })
    rows.value = data?.list || []
    total.value = data?.total ?? 0
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
onMounted(() => load(1))
</script>
<style scoped>
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
