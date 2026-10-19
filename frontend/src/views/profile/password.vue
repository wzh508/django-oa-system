<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header"><span class="page-title">修改密码</span></div>
    <el-form label-width="110px" :model="form" :rules="rules" ref="formRef" style="max-width: 460px">
      <el-form-item label="原密码" prop="old_password"><el-input v-model="form.old_password" type="password" show-password /></el-form-item>
      <el-form-item label="新密码" prop="new_password"><el-input v-model="form.new_password" type="password" show-password placeholder="至少 6 位" /></el-form-item>
      <el-form-item label="确认新密码" prop="confirm"><el-input v-model="form.confirm" type="password" show-password /></el-form-item>
      <el-form-item><el-button type="primary" @click="submit" :loading="saving">提交</el-button></el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api/auth'
const loading = ref(false)
const saving = ref(false)
const formRef = ref(null)
const form = reactive({ old_password: '', new_password: '', confirm: '' })
const rules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [{ required: true, min: 6, message: '新密码至少 6 位', trigger: 'blur' }],
  confirm: [{ required: true, validator: (r, v, cb) => v === form.new_password ? cb() : cb(new Error('两次密码不一致')), trigger: 'blur' }],
}
async function submit() {
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try { await authApi.changePassword({ old_password: form.old_password, new_password: form.new_password }); ElMessage.success('密码已修改'); form.old_password = form.new_password = form.confirm = '' } catch (e) {} finally { saving.value = false }
  })
}
onMounted(() => {})
</script>
<style scoped>
</style>
