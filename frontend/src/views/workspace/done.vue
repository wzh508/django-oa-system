<template>
  <div class="page-card">
    <div class="page-header">
      <span class="page-title">已办中心</span>
    </div>
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="instance_title" label="事项" min-width="180" show-overflow-tooltip />
      <el-table-column prop="instance_code" label="单号" width="150" />
      <el-table-column prop="node_name" label="处理节点" width="120" />
      <el-table-column prop="applicant_name" label="发起人" width="100" />
      <el-table-column prop="status" label="结果" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'approved' ? 'success' : row.status === 'rejected' ? 'danger' : 'info'" size="small">{{ statusLabel[row.status] || row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="acted_at" label="处理时间" min-width="160" />
      <el-table-column prop="comment" label="意见" min-width="140" show-overflow-tooltip />
      <el-table-column label="详情" width="80" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="goDetail(row)">查看</el-button>
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
const router = useRouter()
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const statusLabel = { approved: '通过', rejected: '驳回', transferred: '转交', added: '加签', rolled_back: '退回', done: '完成' }

async function load(p) {
  if (p) page.value = p
  loading.value = true
  try {
    const data = await http.get('/workflow/tasks/', { params: { kind: 'done', page: page.value, page_size: pageSize.value } })
    rows.value = data?.list || []
    total.value = data?.total ?? 0
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
function goDetail(row) { router.push(`/approval/detail/${row.instance}`) }
onMounted(() => load(1))
</script>
<style scoped>
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
