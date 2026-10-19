<template>
  <!-- 用户管理：在通用 CrudView 之上补「分配角色 / 重置密码」两个行内操作。
       后端 /accounts/users/<id>/roles/ 与 /reset-password/ 早已提供，
       但此前前端没有任何入口调用，导致新建的账号拿不到角色（菜单与权限为 0）。

       注意：外层必须是单一根节点 —— 布局的 <router-view> 套了 <transition>，
       多根节点会触发 Vue 警告「Component inside <Transition> renders non-element root node」。 -->
  <div>
    <CrudView>
      <template #row="{ row }">
        <el-button link type="warning" @click="openRoles(row)">分配角色</el-button>
        <el-button link type="info" @click="resetPwd(row)">重置密码</el-button>
      </template>
    </CrudView>

    <el-dialog
      v-model="vis"
      :title="`分配角色 - ${cur?.first_name || cur?.username || ''}`"
      width="520px"
    >
      <el-form label-width="80px">
        <el-form-item label="账号">
          <span>{{ cur?.username }}</span>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="roleIds" multiple filterable style="width: 100%" placeholder="请选择角色">
            <el-option v-for="r in roles" :key="r.id" :label="`${r.name}（${r.code}）`" :value="r.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="角色决定菜单与数据范围，保存后即时生效；未分配角色的账号登录后没有任何操作权限。"
      />
      <template #footer>
        <el-button @click="vis = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import CrudView from '@/components/CrudView.vue'
import { http } from '@/api/http'
import { accountsApi } from '@/api/modules'

const roles = ref([])
const roleIds = ref([])
const cur = ref(null)
const vis = ref(false)
const saving = ref(false)

async function loadRoles() {
  try {
    const d = await http.get(accountsApi.roles, { params: { page_size: 100 } })
    roles.value = d?.list || []
  } catch (e) {
    roles.value = []
  }
}

function openRoles(row) {
  cur.value = row
  roleIds.value = [...(row.role_ids || [])]
  vis.value = true
}

async function save() {
  saving.value = true
  try {
    await accountsApi.userAssignRoles(cur.value.id, { role_ids: roleIds.value })
    ElMessage.success('已保存，权限即时生效')
    vis.value = false
  } catch (e) {
    /* 错误已由请求拦截器提示 */
  } finally {
    saving.value = false
  }
}

async function resetPwd(row) {
  try {
    await ElMessageBox.confirm(
      `确认将「${row.first_name || row.username}」的密码重置为初始密码 Oa@123456？`,
      '提示',
      { type: 'warning' },
    )
  } catch (e) {
    return // 用户取消
  }
  try {
    await accountsApi.userResetPwd(row.id)
    ElMessage.success('已重置为初始密码，该用户下次登录需改密')
  } catch (e) {
    /* 拦截器提示 */
  }
}

onMounted(loadRoles)
</script>
