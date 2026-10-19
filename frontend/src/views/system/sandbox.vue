<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header"><span class="page-title">权限沙盘（可解释 RBAC）</span></div>
    <el-alert type="success" :closable="false" title="变更前先在沙盘中预演影响面，确认后再落库；所有变更均可按批次回滚。" style="margin-bottom: 14px" />

    <el-row :gutter="16">
      <el-col :span="14">
        <el-card shadow="never" header="变更预演">
          <el-form label-width="90px">
            <el-form-item label="目标角色">
              <el-select v-model="sim.role_id" filterable style="width: 240px"><el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" /></el-select>
            </el-form-item>
            <el-form-item label="新增权限">
              <el-select v-model="sim.add_codes" multiple filterable style="width: 100%" placeholder="选择要新增的权限码"><el-option v-for="p in perms" :key="p.id" :label="`${p.name}（${p.code}）`" :value="p.code" /></el-select>
            </el-form-item>
            <el-form-item label="移除权限">
              <el-select v-model="sim.del_codes" multiple filterable style="width: 100%" placeholder="选择要移除的权限码"><el-option v-for="p in perms" :key="p.id" :label="`${p.name}（${p.code}）`" :value="p.code" /></el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :icon="MagicStick" @click="simulate" :loading="simulating">预演影响面</el-button>
              <el-button type="success" :disabled="!impact" @click="apply" :loading="applying">确认落库</el-button>
            </el-form-item>
          </el-form>
          <el-descriptions v-if="impact" :column="1" border size="small">
            <el-descriptions-item label="影响用户数">{{ impact.affected_users }}</el-descriptions-item>
            <el-descriptions-item label="新增权限">{{ (impact.added || []).join('，') || '无' }}</el-descriptions-item>
            <el-descriptions-item label="移除权限">{{ (impact.removed || []).join('，') || '无' }}</el-descriptions-item>
            <el-descriptions-item label="风险提示">{{ impact.warning || '无' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never" header="权限解释">
          <el-select v-model="explainCode" filterable style="width: 100%" placeholder="选择权限码查看解释" @change="explain">
            <el-option v-for="p in perms" :key="p.id" :label="`${p.code}`" :value="p.code" />
          </el-select>
          <el-descriptions v-if="explainData" :column="1" border size="small" style="margin-top: 12px">
            <el-descriptions-item label="名称">{{ explainData.name }}</el-descriptions-item>
            <el-descriptions-item label="说明">{{ explainData.description || '—' }}</el-descriptions-item>
            <el-descriptions-item label="拥有该权限的角色">{{ (explainData.roles || []).join('，') || '无' }}</el-descriptions-item>
            <el-descriptions-item label="授予用户数">{{ explainData.user_count }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
        <el-card shadow="never" header="变更批次" style="margin-top: 14px">
          <el-table :data="changes" size="small" border>
            <el-table-column prop="batch_id" label="批次" width="120" show-overflow-tooltip />
            <el-table-column prop="role" label="角色" width="90" />
            <el-table-column prop="applied" label="状态" width="80"><template #default="{ row }"><el-tag :type="row.applied ? 'success' : 'warning'" size="small">{{ row.applied ? '已生效' : '待生效' }}</el-tag></template></el-table-column>
            <el-table-column label="" width="70"><template #default="{ row }"><el-button v-if="row.applied" link type="danger" @click="rollback(row)">回滚</el-button></template></el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { accountsApi } from '@/api/modules'
import { MagicStick } from '@element-plus/icons-vue'
const loading = ref(false)
const simulating = ref(false)
const applying = ref(false)
const roles = ref([])
const perms = ref([])
const changes = ref([])
const impact = ref(null)
const explainCode = ref('')
const explainData = ref(null)
const sim = reactive({ role_id: null, add_codes: [], del_codes: [] })

async function load() {
  loading.value = true
  try {
    const [r, p, c] = await Promise.all([
      http.get(accountsApi.roles, { params: { page_size: 100 } }),
      http.get(accountsApi.permissions, { params: { page_size: 500 } }),
      accountsApi.sandboxChanges(),
    ])
    roles.value = r?.list || []
    perms.value = p?.list || []
    changes.value = c || []
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
async function simulate() {
  if (!sim.role_id) { ElMessage.warning('请选择角色'); return }
  simulating.value = true
  try { impact.value = await accountsApi.sandboxSimulate({ ...sim }); } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { simulating.value = false }
}
async function apply() {
  applying.value = true
  try { const res = await accountsApi.sandboxApply({ ...sim, confirm: true }); ElMessage.success('已落库'); impact.value = null; load() } catch (e) {} finally { applying.value = false }
}
async function rollback(row) {
  try { await accountsApi.sandboxRollback({ batch_id: row.batch_id }); ElMessage.success('已回滚'); load() } catch (e) {}
}
async function explain() {
  if (!explainCode.value) return
  try { explainData.value = await accountsApi.explainPermission({ code: explainCode.value }) } catch (e) {}
}
onMounted(load)
</script>
<style scoped>
</style>
