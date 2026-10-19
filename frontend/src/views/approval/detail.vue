<template>
  <div class="page-card" v-loading="loading">
    <div v-if="inst">
      <div class="detail-head">
        <div>
          <h2 style="margin: 0 0 4px">{{ inst.title }}</h2>
          <div class="sub">
            <el-tag size="small">{{ inst.code }}</el-tag>
            <el-tag size="small" :type="statusType(inst.status)">{{ inst.status_display }}</el-tag>
            <span>发起人：{{ inst.applicant_name }}</span>
            <span>部门：{{ inst.dept_name }}</span>
            <span v-if="inst.amount">金额：¥{{ inst.amount }}</span>
            <span v-if="inst.days">天数：{{ inst.days }}</span>
          </div>
        </div>
        <div class="ops">
          <el-button v-if="myTask" type="success" @click="openAct('approve')">同意</el-button>
          <el-button v-if="myTask" type="danger" @click="openAct('reject')">驳回</el-button>
          <el-button v-if="isApplicant && inst.status === 'pending'" @click="doRevoke">撤回</el-button>
          <el-button v-if="isApplicant && inst.status === 'pending'" @click="openUrge">催办</el-button>
          <el-button v-if="inst.status === 'pending' && inst.pay_status === 'unpaid'" type="warning" @click="openPay">支付</el-button>
        </div>
      </div>

      <el-row :gutter="16" style="margin-top: 12px">
        <el-col :span="15">
          <el-card shadow="never" header="审批流程">
            <el-steps :active="currentStep" align-center finish-status="success">
              <el-step v-for="n in flowNodes" :key="n.order" :title="n.name" :status="stepStatus(n)" :description="nodeDesc(n)" />
            </el-steps>
            <el-divider>审批记录</el-divider>
            <el-timeline>
              <el-timeline-item v-for="r in records" :key="r.id" :timestamp="r.created_at" placement="top">
                <b>{{ r.node_name }}</b> · {{ r.operator_name }} ·
                <el-tag size="small" :type="r.action === 'approve' ? 'success' : r.action === 'reject' ? 'danger' : 'info'">{{ actionLabel[r.action] || r.action }}</el-tag>
                <div class="cmt" v-if="r.comment">{{ r.comment }}</div>
              </el-timeline-item>
            </el-timeline>
          </el-card>
        </el-col>
        <el-col :span="9">
          <el-card shadow="never" header="表单内容" v-if="formFields.length">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item v-for="f in formFields" :key="f.key" :label="f.label">{{ formatVal(f.value) }}</el-descriptions-item>
            </el-descriptions>
          </el-card>
          <el-card shadow="never" header="时效预测" v-if="prediction" style="margin-top: 12px">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="预计时长">{{ prediction.predicted_hours }} 小时</el-descriptions-item>
              <el-descriptions-item label="预计完成">{{ prediction.predicted_finish_at }}</el-descriptions-item>
              <el-descriptions-item label="风险等级">
                <el-tag :type="prediction.risk_level === 'high' ? 'danger' : prediction.risk_level === 'medium' ? 'warning' : 'success'" size="small">{{ prediction.risk_level }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="风险评分">{{ prediction.risk_score }}</el-descriptions-item>
            </el-descriptions>
          </el-card>
          <el-card shadow="never" header="报销明细" v-if="inst.pay_status !== undefined" style="margin-top: 12px">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="费用类型">{{ inst.fee_type_display }}</el-descriptions-item>
              <el-descriptions-item label="发票数">{{ inst.invoice_count }}</el-descriptions-item>
              <el-descriptions-item label="支付状态">
                <el-tag size="small" :type="inst.pay_status === 'paid' ? 'success' : 'warning'">{{ inst.pay_status_display }}</el-tag>
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <el-dialog v-model="actVisible" :title="actAction === 'approve' ? '同意' : '驳回'" width="460px">
      <el-input v-model="actComment" type="textarea" :rows="3" :placeholder="actAction === 'approve' ? '审批意见（可选）' : '驳回原因'" />
      <template #footer><el-button @click="actVisible = false">取消</el-button><el-button type="primary" @click="submitAct">确定</el-button></template>
    </el-dialog>

    <el-dialog v-model="urgeVisible" title="催办" width="460px">
      <el-input v-model="urgeComment" type="textarea" :rows="3" placeholder="催办说明（可选）" />
      <template #footer><el-button @click="urgeVisible = false">取消</el-button><el-button type="primary" @click="submitUrge">发送</el-button></template>
    </el-dialog>

    <el-dialog v-model="payVisible" title="支付" width="460px">
      <el-alert type="warning" :closable="false" title="确认向申请人支付该报销单？" />
      <template #footer><el-button @click="payVisible = false">取消</el-button><el-button type="primary" @click="submitPay">确认支付</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { http } from '@/api/http'
import { useUserStore } from '@/store/modules/user'
import { workflowApi } from '@/api/modules'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const inst = ref(null)
const flowNodes = ref([])
const records = ref([])
const prediction = ref(null)
const actVisible = ref(false)
const actAction = ref('approve')
const actComment = ref('')
const urgeVisible = ref(false)
const urgeComment = ref('')
const payVisible = ref(false)
const actionLabel = { approve: '通过', reject: '驳回', transfer: '转交', add_sign: '加签', rollback: '退回' }

const myTask = computed(() => {
  if (!inst.value?.tasks) return null
  return (inst.value.tasks || []).find((t) => t.assignee === userStore.user?.id && t.status === 'pending') || null
})
const isApplicant = computed(() => inst.value?.applicant === userStore.user?.id)

const formData = computed(() => inst.value?.form_data || {})
// 用实例冻结的 form_schema 提供中文标签与字段顺序；不在 schema 内的字段按原 key 兜底展示
const formFields = computed(() => {
  const data = formData.value || {}
  const schema = inst.value?.template_snapshot?.form_schema || []
  const out = []
  const seen = new Set()
  schema.forEach((f) => {
    const k = f?.key
    if (!k || seen.has(k)) return
    seen.add(k)
    out.push({ key: k, label: f.label || k, value: data[k] })
  })
  Object.keys(data).forEach((k) => {
    if (seen.has(k)) return
    seen.add(k)
    out.push({ key: k, label: k, value: data[k] })
  })
  return out
})
const currentStep = computed(() => {
  const idx = flowNodes.value.findIndex((n) => n.status === 'current')
  return idx >= 0 ? idx : flowNodes.value.length
})

function statusType(s) { return { draft: 'info', pending: 'warning', approved: 'success', rejected: 'danger', terminated: 'info', withdrawn: 'info' }[s] || 'info' }
function stepStatus(n) { return n.status === 'done' ? 'finish' : n.status === 'current' ? 'process' : 'wait' }
function nodeDesc(n) {
  const names = (n.assignees || []).map((a) => `${a.name}(${a.status === 'done' ? '已完成' : a.status === 'pending' ? '待处理' : a.status})`)
  return names.join('，') || (n.node_type === 'start' ? '发起' : n.node_type === 'end' ? '结束' : '')
}
function formatVal(v) { return v === null || v === undefined ? '—' : (typeof v === 'object' ? JSON.stringify(v) : v) }

async function load() {
  loading.value = true
  try {
    const data = await http.get(`/workflow/instances/${route.params.id}/`)
    inst.value = data
    flowNodes.value = data.flow_nodes || []
    records.value = data.records || []
    prediction.value = data.prediction || null
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}

function openAct(a) { actAction.value = a; actComment.value = ''; actVisible.value = true }
async function submitAct() {
  if (!myTask.value) return
  try {
    await workflowApi.actTask(myTask.value.id, { action: actAction.value, comment: actComment.value })
    ElMessage.success('操作成功')
    actVisible.value = false
    load()
  } catch (e) {}
}
async function doRevoke() {
  await ElMessageBox.confirm('确认撤回该申请？', '提示', { type: 'warning' })
  try { await workflowApi.revokeInstance(inst.value.id, {}); ElMessage.success('已撤回'); load() } catch (e) {}
}
function openUrge() { urgeComment.value = ''; urgeVisible.value = true }
async function submitUrge() {
  try { await workflowApi.urgeInstance(inst.value.id, { comment: urgeComment.value }); ElMessage.success('已催办'); urgeVisible.value = false } catch (e) {}
}
function openPay() { payVisible.value = true }
async function submitPay() {
  try { await workflowApi.expensePay(inst.value.id, {}); ElMessage.success('支付成功'); payVisible.value = false; load() } catch (e) {}
}

onMounted(load)
</script>
<style scoped>
.detail-head { display: flex; justify-content: space-between; align-items: flex-start; }
.sub { color: #909399; font-size: 13px; margin-top: 6px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.ops { display: flex; gap: 8px; flex-wrap: wrap; }
.cmt { color: #606266; margin-top: 4px; }
</style>
