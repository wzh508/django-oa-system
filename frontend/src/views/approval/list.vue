<template>
  <div class="page-card">
    <div class="page-header">
      <span class="page-title">申请列表</span>
    </div>
    <el-form :inline="true" :model="search" class="search-bar">
      <el-form-item label="关键字"><el-input v-model="search.keyword" placeholder="单号/标题" clearable style="width: 180px" /></el-form-item>
      <el-form-item label="状态">
        <el-select v-model="search.status" placeholder="全部" clearable style="width: 140px">
          <el-option v-for="o in statusOpts" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
      </el-form-item>
      <el-button type="primary" :icon="Search" @click="load(1)">查询</el-button>
    </el-form>
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="code" label="单号" width="160" />
      <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
      <el-table-column prop="template_name" label="类型" width="120" />
      <el-table-column prop="applicant_name" label="发起人" width="100" />
      <el-table-column prop="current_node_name" label="当前节点" width="120" />
      <el-table-column prop="status_display" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ row.status_display }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="urgency" label="紧急" width="80">
        <template #default="{ row }"><el-tag :type="row.urgency === 'high' ? 'danger' : 'info'" size="small">{{ urgLabel[row.urgency] || row.urgency }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="risk_level" label="风险" width="80">
        <template #default="{ row }"><el-tag v-if="row.risk_level" :type="row.risk_level === 'high' ? 'danger' : 'warning'" size="small">{{ row.risk_level }}</el-tag><span v-else>—</span></template>
      </el-table-column>
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }"><el-button link type="primary" @click="router.push(`/approval/detail/${row.id}`)">详情</el-button></template>
      </el-table-column>
    </el-table>
    <el-pagination class="pager" background layout="total, prev, pager, next" :total="total" :current-page="page" :page-size="pageSize" @current-change="(p) => load(p)" />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { http } from '@/api/http'
import { Search } from '@element-plus/icons-vue'
const router = useRouter()
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const search = reactive({ keyword: '', status: '' })
const statusOpts = [
  { label: '草稿', value: 'draft' }, { label: '审批中', value: 'pending' },
  { label: '通过', value: 'approved' }, { label: '驳回', value: 'rejected' },
  { label: '已撤回', value: 'withdrawn' }, { label: '已终止', value: 'terminated' },
]
const urgLabel = { low: '低', normal: '中', high: '高' }
function statusType(s) {
  return { draft: 'info', pending: 'warning', approved: 'success', rejected: 'danger', terminated: 'info', withdrawn: 'info' }[s] || 'info'
}
async function load(p) {
  if (p) page.value = p
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (search.keyword) params.keyword = search.keyword
    if (search.status) params.status = search.status
    const data = await http.get('/workflow/instances/', { params })
    rows.value = data?.list || []
    total.value = data?.total ?? 0
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
onMounted(() => load(1))
</script>
<style scoped>
.search-bar { margin-bottom: 8px; }
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
