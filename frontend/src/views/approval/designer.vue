<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header">
      <span class="page-title">流程设计器{{ id ? '（编辑）' : '（新建）' }}</span>
      <el-button type="primary" @click="save" :loading="saving">保存模板</el-button>
    </div>
    <el-row :gutter="16">
      <el-col :span="10">
        <el-card shadow="never" header="基础信息">
          <el-form label-width="90px" :model="tpl">
            <el-form-item label="名称"><el-input v-model="tpl.name" /></el-form-item>
            <el-form-item label="编码"><el-input v-model="tpl.code" :disabled="!!id" placeholder="如 leave" /></el-form-item>
            <el-form-item label="类别"><el-input v-model="tpl.category" placeholder="如 人事/财务" /></el-form-item>
            <el-form-item label="图标"><el-input v-model="tpl.icon" placeholder="如 Document" /></el-form-item>
            <el-form-item label="描述"><el-input v-model="tpl.description" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="表单结构">
              <el-input v-model="formSchemaText" type="textarea" :rows="4" placeholder='[{ "key":"reason","label":"事由","type":"textarea","required":true }]' />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
      <el-col :span="14">
        <el-card shadow="never" header="审批节点">
          <el-table :data="nodes" border>
            <el-table-column label="顺序" width="60">
              <template #default="{ row, $index }">
                <el-button link :icon="Top" @click="move($index, -1)" />
                <el-button link :icon="Bottom" @click="move($index, 1)" />
              </template>
            </el-table-column>
            <el-table-column label="节点名" min-width="120">
              <template #default="{ row }"><el-input v-model="row.name" size="small" /></template>
            </el-table-column>
            <el-table-column label="类型" width="120">
              <template #default="{ row }"><el-select v-model="row.node_type" size="small"><el-option v-for="t in nodeTypes" :key="t" :label="t" :value="t" /></el-select></template>
            </el-table-column>
            <el-table-column label="审批人来源" min-width="140">
              <template #default="{ row }">
                <el-select v-model="row.approver_source" size="small" @change="row.approver_ids = row.approver_source === 'role' ? [] : row.approver_ids">
                  <el-option label="指定用户" value="user" />
                  <el-option label="角色" value="role" />
                  <el-option label="部门主管" value="dept_leader" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="审批人/角色" min-width="160">
              <template #default="{ row }">
                <el-select v-if="row.approver_source === 'user'" v-model="row.approver_ids" multiple size="small" style="width: 100%">
                  <el-option v-for="u in users" :key="u.id" :label="u.display_name || u.username" :value="u.id" />
                </el-select>
                <el-select v-else-if="row.approver_source === 'role'" v-model="row.approver_role_codes" multiple size="small" filterable style="width: 100%">
                  <el-option v-for="r in roles" :key="r.code" :label="r.name" :value="r.code" />
                </el-select>
                <span v-else class="muted">自动</span>
              </template>
            </el-table-column>
            <el-table-column label="SLA(h)" width="80">
              <template #default="{ row }"><el-input-number v-model="row.sla_hours" :min="0" size="small" style="width: 70px" /></template>
            </el-table-column>
            <el-table-column label="" width="50">
              <template #default="{ $index }"><el-button link type="danger" :icon="Delete" @click="nodes.splice($index, 1)" /></template>
            </el-table-column>
          </el-table>
          <el-button class="mt" :icon="Plus" @click="addNode">添加节点</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { workflowApi } from '@/api/modules'
import { Plus, Delete, Top, Bottom } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const id = route.params.id || null
const loading = ref(false)
const saving = ref(false)
const users = ref([])
const roles = ref([])
const tpl = reactive({ name: '', code: '', category: '', icon: '', description: '' })
const formSchemaText = ref('[]')
const nodes = ref([])
const nodeTypes = ['start', 'approval', 'cc', 'condition', 'end']

function addNode() {
  nodes.value.push({
    name: '节点' + (nodes.value.length + 1), order: nodes.value.length,
    node_type: 'approval', approver_source: 'user', approver_ids: [], approver_role_codes: [], sla_hours: 24,
  })
}
function move(i, d) {
  const j = i + d
  if (j < 0 || j >= nodes.value.length) return
  const a = nodes.value[i]; nodes.value[i] = nodes.value[j]; nodes.value[j] = a
}

async function load() {
  loading.value = true
  try {
    const [ud, rd] = await Promise.all([
      http.get('/accounts/users/', { params: { page_size: 200 } }),
      http.get('/accounts/roles/', { params: { page_size: 100 } }),
    ])
    users.value = ud?.list || []
    roles.value = rd?.list || []
    if (id) {
      const data = await http.get(`/workflow/templates/${id}/`)
      Object.assign(tpl, { name: data.name, code: data.code, category: data.category, icon: data.icon, description: data.description })
      formSchemaText.value = JSON.stringify(data.form_schema || [], null, 2)
      nodes.value = (data.nodes || []).map((n) => ({ ...n, approver_ids: n.approver_ids || [], approver_role_codes: n.approver_role_codes || [] }))
    }
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
async function save() {
  let schema
  try { schema = JSON.parse(formSchemaText.value || '[]') } catch (e) { ElMessage.error('表单结构 JSON 格式错误'); return }
  const payload = {
    name: tpl.name, code: tpl.code, category: tpl.category, icon: tpl.icon, description: tpl.description,
    form_schema: schema,
    nodes: nodes.value.map((n, i) => ({ ...n, order: i })),
  }
  saving.value = true
  try {
    if (id) await http.put(`/workflow/templates/${id}/`, payload)
    else await http.post('/workflow/templates/', payload)
    ElMessage.success('保存成功')
    router.push('/approval/template')
  } catch (e) {} finally { saving.value = false }
}
onMounted(load)
</script>
<style scoped>
.mt { margin-top: 10px; }
.muted { color: #909399; }
</style>
