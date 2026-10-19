<template>
  <div class="page-card">
    <div class="page-header"><span class="page-title">报销审核</span></div>
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="code" label="单号" width="160" />
      <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
      <el-table-column prop="applicant_name" label="申请人" width="100" />
      <el-table-column prop="dept_name" label="部门" width="120" />
      <el-table-column prop="fee_type_display" label="类型" width="90" />
      <el-table-column prop="amount" label="金额" width="100"><template #default="{ row }">¥{{ row.amount }}</template></el-table-column>
      <el-table-column prop="current_node" label="当前节点" min-width="120" show-overflow-tooltip />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="success" @click="openAct(row, 'approve')">通过</el-button>
          <el-button link type="danger" @click="openAct(row, 'reject')">驳回</el-button>
          <el-button link type="primary" @click="router.push(`/approval/detail/${row.instance_id}`)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="vis" :title="act === 'approve' ? '通过审核' : '驳回'" width="460px">
      <el-input v-model="comment" type="textarea" :rows="3" :placeholder="act === 'reject' ? '请填写驳回原因' : '审核意见（可选）'" />
      <template #footer><el-button @click="vis=false">取消</el-button><el-button type="primary" @click="submit">确定</el-button></template>
    </el-dialog>
    <el-pagination class="pager" background layout="total, prev, pager, next" :total="total" :current-page="page" :page-size="pageSize" @current-change="(p) => load(p)" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { workflowApi } from '@/api/modules'
const router = useRouter()
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const vis = ref(false)
const act = ref('approve')
const comment = ref('')
const cur = ref(null)

async function load(p) {
  if (p) page.value = p
  loading.value = true
  try {
    const data = await http.get(workflowApi.requests, { params: { status: 'pending', page: page.value, page_size: pageSize.value } })
    rows.value = data?.list || []
    total.value = data?.total ?? 0
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
function openAct(row, a) { cur.value = row; act.value = a; comment.value = ''; vis.value = true }
async function submit() {
  if (act.value === 'reject' && !comment.value) { ElMessage.warning('请填写驳回原因'); return }
  try { await workflowApi.expenseAudit(cur.value.id, { action: act.value, comment: comment.value }); ElMessage.success('操作成功'); vis.value = false; load() } catch (e) {}
}
onMounted(() => load(1))
</script>
<style scoped>
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
