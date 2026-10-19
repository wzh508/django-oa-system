<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header"><span class="page-title">个人信息</span></div>
    <el-row :gutter="16">
      <el-col :span="8">
        <el-card shadow="never" header="账户" align="center">
          <el-avatar :size="72">{{ (user?.first_name || user?.username || '?').slice(0, 1) }}</el-avatar>
          <h3 style="margin: 10px 0 2px">{{ user?.first_name || user?.username }}</h3>
          <div class="muted">{{ user?.username }} · {{ user?.employee_no || '—' }}</div>
          <el-tag size="small" class="mt">{{ user?.dept_name || '—' }} / {{ user?.position_name || '—' }}</el-tag>
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card shadow="never" header="资料编辑">
          <el-form label-width="90px" :model="form">
            <el-form-item label="姓名"><el-input v-model="form.first_name" /></el-form-item>
            <el-form-item label="手机号"><el-input v-model="form.mobile" /></el-form-item>
            <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
            <el-form-item label="性别">
              <el-select v-model="form.gender" style="width: 160px"><el-option label="未知" :value="0" /><el-option label="男" :value="1" /><el-option label="女" :value="2" /></el-select>
            </el-form-item>
            <el-form-item label="生日"><el-date-picker v-model="form.birthday" type="date" value-format="YYYY-MM-DD" /></el-form-item>
            <el-form-item label="地址"><el-input v-model="form.address" /></el-form-item>
            <el-form-item><el-button type="primary" @click="save" :loading="saving">保存</el-button></el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api/auth'
import { useUserStore } from '@/store/modules/user'
const userStore = useUserStore()
const loading = ref(false)
const saving = ref(false)
const user = ref(null)
const form = reactive({ first_name: '', mobile: '', email: '', gender: 0, birthday: '', address: '' })

async function load() {
  loading.value = true
  try {
    const u = await authApi.profile()
    user.value = u
    Object.assign(form, { first_name: u.first_name || '', mobile: u.mobile || '', email: u.email || '', gender: u.gender ?? 0, birthday: u.birthday || '', address: u.address || '' })
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
async function save() {
  saving.value = true
  try {
    await authApi.updateProfile({ ...form })
    ElMessage.success('已保存'); userStore.fetchProfile()
  } catch (e) {} finally { saving.value = false }
}
onMounted(load)
</script>
<style scoped>
.muted { color: #909399; font-size: 13px; }
.mt { margin-top: 8px; }
</style>
