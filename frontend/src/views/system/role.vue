<template>
  <div class="page-card">
    <div class="page-header"><span class="page-title">角色管理</span></div>
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="name" label="角色" width="140" />
      <el-table-column prop="code" label="编码" width="140" />
      <el-table-column prop="data_scope" label="数据范围" width="120">
        <template #default="{ row }"><el-tag size="small">{{ scopeLabel[row.data_scope] || row.data_scope }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="description" label="说明" min-width="200" show-overflow-tooltip />
      <el-table-column prop="user_count" label="用户数" width="90" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="edit(row)">授权</el-button>
          <el-button link type="success" @click="showPerms(row)">权限明细</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="vis" :title="`授权 - ${cur?.name}`" width="640px">
      <el-form label-width="90px">
        <el-form-item label="数据范围">
          <el-select v-model="editForm.data_scope" style="width: 240px">
            <el-option v-for="s in scopeOpts" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="权限点">
          <el-select v-model="editForm.permission_ids" multiple filterable style="width: 100%" placeholder="选择权限点">
            <el-option v-for="p in perms" :key="p.id" :label="`${p.name}（${p.code}）`" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="vis=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="permVis" :title="`${cur?.name} - 有效权限`" width="560px">
      <div v-if="effPerms.length">
        <el-tag v-for="c in effPerms" :key="c" class="ptag" size="small">{{ c }}</el-tag>
      </div>
      <el-empty v-else description="无权限" />
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { accountsApi } from '@/api/modules'
const rows = ref([])
const perms = ref([])
const loading = ref(false)
const vis = ref(false)
const permVis = ref(false)
const cur = ref(null)
const effPerms = ref([])
const scopeOpts = [
  { label: '全部', value: 'ALL' }, { label: '本部门及下级', value: 'DEPT_TREE' },
  { label: '仅本人', value: 'SELF' }, { label: '自定义', value: 'CUSTOM' },
]
const scopeLabel = { ALL: '全部', DEPT_TREE: '本部门及下级', SELF: '仅本人', CUSTOM: '自定义' }
const editForm = reactive({ data_scope: 'SELF', permission_ids: [] })

async function load() {
  loading.value = true
  try {
    const [r, p] = await Promise.all([
      http.get(accountsApi.roles, { params: { page_size: 100 } }),
      http.get(accountsApi.permissions, { params: { page_size: 500 } }),
    ])
    rows.value = r?.list || []
    perms.value = p?.list || []
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
function edit(row) {
  cur.value = row
  editForm.data_scope = row.data_scope
  accountsApi.roleEffectivePerms(row.id).then((d) => {
    // 取角色的自身权限 id 集合
    const selfCodes = new Set(d?.self || [])
    editForm.permission_ids = perms.value.filter((p) => selfCodes.has(p.code)).map((p) => p.id)
  })
  vis.value = true
}
async function save() {
  try { await http.put(`/accounts/roles/${cur.value.id}/`, { data_scope: editForm.data_scope, permission_ids: editForm.permission_ids }); ElMessage.success('已保存'); vis.value = false; load() } catch (e) {}
}
async function showPerms(row) {
  cur.value = row
  const d = await accountsApi.roleEffectivePerms(row.id)
  effPerms.value = d?.inherited || []
  permVis.value = true
}
onMounted(load)
</script>
<style scoped>
.ptag { margin: 4px; }
</style>
