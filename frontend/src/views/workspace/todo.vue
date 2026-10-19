<template>
  <div class="page-card">
    <div class="page-header">
      <span class="page-title">待办中心</span>
      <el-button :icon="Refresh" @click="load(1)">刷新</el-button>
    </div>
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="instance_title" label="事项" min-width="180" show-overflow-tooltip />
      <el-table-column prop="instance_code" label="单号" width="150" />
      <el-table-column prop="node_name" label="当前节点" width="120" />
      <el-table-column prop="applicant_name" label="发起人" width="100" />
      <el-table-column prop="category" label="类别" width="90" />
      <el-table-column label="期限" width="160">
        <template #default="{ row }">
          <span>{{ row.due_at || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.overdue ? 'danger' : 'warning'" size="small">{{ row.overdue ? '已超时' : '待处理' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="goDetail(row)">详情</el-button>
          <el-button link type="success" @click="goTask(row)">审批</el-button>
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
import { Refresh } from '@element-plus/icons-vue'
const router = useRouter()
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)

async function load(p) {
  if (p) page.value = p
  loading.value = true
  try {
    const data = await http.get('/workflow/tasks/', { params: { kind: 'todo', page: page.value, page_size: pageSize.value } })
    rows.value = data?.list || []
    total.value = data?.total ?? 0
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
function goDetail(row) { router.push(`/approval/detail/${row.instance}`) }
function goTask(row) { router.push(`/approval/task?id=${row.id}`) }
onMounted(() => load(1))
</script>
<style scoped>
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
