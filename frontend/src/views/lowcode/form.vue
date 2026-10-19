<template>
  <div class="page-card">
    <div class="page-header">
      <span class="page-title">表单管理</span>
      <el-button type="primary" :icon="Plus" @click="router.push('/lowcode/design')">新建表单</el-button>
    </div>
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="code" label="编码" width="140" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="category" label="分类" width="110" />
      <el-table-column prop="version" label="版本" width="70" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }"><el-tag :type="row.status === 'published' ? 'success' : 'info'" size="small">{{ row.status === 'published' ? '已发布' : '草稿' }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="record_count" label="提交数" width="90" />
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="router.push(`/lowcode/design/${row.id}`)">设计</el-button>
          <el-button link type="success" v-if="row.status !== 'published'" @click="publish(row)">发布</el-button>
          <el-button link type="warning" @click="preview(row)">预览</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination class="pager" background layout="total, prev, pager, next" :total="total" :current-page="page" :page-size="pageSize" @current-change="(p) => load(p)" />

    <el-dialog v-model="previewVis" :title="previewRow?.name + ' · 提交数据'" width="760px">
      <el-table :data="records" border size="small" v-loading="recordsLoading">
        <el-table-column v-for="f in previewFields" :key="f.key" :prop="f.key" :label="f.label" min-width="140" show-overflow-tooltip />
        <el-table-column prop="created_at" label="提交时间" width="160" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { lowcodeApi } from '@/api/modules'
import { Plus } from '@element-plus/icons-vue'
const router = useRouter()
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const previewVis = ref(false)
const previewRow = ref(null)
const records = ref([])
const recordsLoading = ref(false)
const previewFields = ref([])

async function load(p) {
  if (p) page.value = p
  loading.value = true
  try {
    const data = await http.get(lowcodeApi.schemas, { params: { page: page.value, page_size: pageSize.value } })
    rows.value = data?.list || []
    total.value = data?.total ?? 0
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
async function publish(row) { try { await lowcodeApi.publish(row.id); ElMessage.success('已发布'); load() } catch (e) {} }
async function preview(row) {
  previewRow.value = row
  previewVis.value = true
  const data = await lowcodeApi.render(row.code)
  previewFields.value = (data?.fields || []).map((f) => ({ key: f.key, label: f.label }))
  recordsLoading.value = true
  try { const rd = await http.get(lowcodeApi.records, { params: { form_code: row.code, page_size: 50 } }); records.value = rd?.list || [] } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { recordsLoading.value = false }
}
onMounted(() => load(1))
</script>
<style scoped>
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
