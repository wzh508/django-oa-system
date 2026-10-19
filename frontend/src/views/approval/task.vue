<template>
  <div class="page-card" v-loading="loading">
    <div v-if="task">
      <div class="detail-head">
        <div>
          <h2 style="margin: 0 0 4px">{{ task.instance_title }}</h2>
          <div class="sub">
            <el-tag size="small">{{ task.instance_code }}</el-tag>
            <span>节点：{{ task.node_name }}</span>
            <span>发起人：{{ task.applicant_name }}</span>
            <span>类别：{{ task.category }}</span>
            <el-tag v-if="task.overdue" type="danger" size="small">已超时</el-tag>
          </div>
        </div>
      </div>
      <el-card shadow="never" header="审批意见" style="margin-top: 12px; max-width: 720px">
        <el-form label-width="80px">
          <el-form-item label="动作">
            <el-radio-group v-model="action">
              <el-radio value="approve" border>同意</el-radio>
              <el-radio value="reject" border>驳回</el-radio>
              <el-radio value="transfer" border>转交</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="意见">
            <el-input v-model="comment" type="textarea" :rows="3" :placeholder="action === 'reject' ? '请填写驳回原因' : '审批意见（可选）'" />
          </el-form-item>
          <el-form-item label="转交给" v-if="action === 'transfer'">
            <el-select v-model="transferTo" filterable placeholder="选择转交人" style="width: 240px">
              <el-option v-for="u in users" :key="u.id" :label="u.display_name || u.username" :value="u.id" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="submit" :loading="submitting">提交</el-button>
            <el-button @click="router.push('/approval/detail/' + task.instance)">查看详情</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>
    <el-empty v-else-if="!loading" description="任务不存在或已处理" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { workflowApi } from '@/api/modules'
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const task = ref(null)
const action = ref('approve')
const comment = ref('')
const transferTo = ref(null)
const users = ref([])

async function load() {
  const tid = route.query.id
  if (!tid) return
  loading.value = true
  try {
    const data = await http.get(`/workflow/tasks/${tid}/`)
    task.value = data
    const ud = await http.get('/accounts/users/', { params: { page_size: 200 } }).catch(() => null)
    users.value = ud?.list || []
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
async function submit() {
  if (!task.value) return
  if (action.value === 'reject' && !comment.value) { ElMessage.warning('请填写驳回原因'); return }
  if (action.value === 'transfer' && !transferTo.value) { ElMessage.warning('请选择转交人'); return }
  submitting.value = true
  try {
    await workflowApi.actTask(task.value.id, {
      action: action.value,
      comment: comment.value,
      transfer_to: action.value === 'transfer' ? transferTo.value : null,
    })
    ElMessage.success('处理成功')
    router.push('/workspace/todo')
  } catch (e) {} finally { submitting.value = false }
}
onMounted(load)
</script>
<style scoped>
.detail-head { display: flex; justify-content: space-between; }
.sub { color: #909399; font-size: 13px; margin-top: 6px; display: flex; gap: 10px; flex-wrap: wrap; }
</style>
