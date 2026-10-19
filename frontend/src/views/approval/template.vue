<template>
  <div class="page-card">
    <div class="page-header">
      <span class="page-title">流程模板</span>
      <el-button type="primary" :icon="Plus" @click="goDesigner()">新建模板</el-button>
    </div>
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="code" label="编码" width="120" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="category" label="类别" width="100" />
      <el-table-column prop="version" label="版本" width="70" />
      <el-table-column prop="node_count" label="节点数" width="80" />
      <el-table-column prop="instance_count" label="实例数" width="90" />
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="row.is_published ? 'success' : 'info'" size="small">{{ row.is_published ? '已发布' : '草稿' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="goDesigner(row.id)">设计</el-button>
          <el-button link type="success" @click="publish(row)" v-if="!row.is_published">发布</el-button>
          <el-button link type="warning" @click="goDiff(row.id)">版本对比</el-button>
          <el-button link type="primary" @click="goSandbox(row.id)">沙盘回放</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination class="pager" background layout="total, prev, pager, next" :total="total" :current-page="page" :page-size="pageSize" @current-change="(p) => load(p)" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { workflowApi } from '@/api/modules'
import { Plus } from '@element-plus/icons-vue'
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
    const data = await http.get('/workflow/templates/', { params: { page: page.value, page_size: pageSize.value } })
    rows.value = data?.list || []
    total.value = data?.total ?? 0
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
function goDesigner(id) { router.push(id ? `/approval/designer/${id}` : '/approval/designer') }
function goDiff(id) { router.push(`/approval/diff/${id}`) }
function goSandbox(id) { router.push('/approval/sandbox') }
async function publish(row) {
  try { await workflowApi.publishTemplate(row.id); ElMessage.success('发布成功'); load() } catch (e) {}
}
onMounted(() => load(1))
</script>
<style scoped>
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
