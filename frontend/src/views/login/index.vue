<template>
  <div class="login-wrap">
    <el-card class="login-card" shadow="always">
      <div class="brand">
        <div class="logo">OA</div>
        <h2>中小企业 OA 管理系统</h2>
        <p class="subtitle">办公自动化 · 流程审批 · 智能分析</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" size="large" @keyup.enter="onSubmit">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="账号" :prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="密码" :prefix-icon="Lock" />
        </el-form-item>
        <el-form-item prop="captcha_code" v-if="captchaRequired">
          <div class="captcha-row">
            <el-input v-model="form.captcha_code" placeholder="图形验证码" :prefix-icon="Picture" style="flex: 1" @keyup.enter="onSubmit" />
            <img v-if="captcha.image" :src="captcha.image" class="captcha-img" title="点击刷新" @click="loadCaptcha" />
          </div>
        </el-form-item>
        <el-button type="primary" :loading="loading" class="login-btn" @click="onSubmit">登 录</el-button>
      </el-form>
      <div class="hint">演示账号：admin / Oa@123456（管理员）</div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Picture } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/modules/user'
import { authApi } from '@/api/auth'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref(null)
const loading = ref(false)
const captcha = reactive({ key: '', image: '' })

const captchaRequired = ref(true)
const form = reactive({ username: 'admin', password: 'Oa@123456', captcha_key: '', captcha_code: '' })
const rules = computed(() => ({
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  captcha_code: captchaRequired.value ? [{ required: true, message: '请输入验证码', trigger: 'blur' }] : [],
}))

async function initCaptcha() {
  try {
    const cfg = await authApi.loginConfig()
    captchaRequired.value = cfg?.captcha_required !== false
  } catch (e) {
    captchaRequired.value = true
  }
  if (captchaRequired.value) await loadCaptcha()
}

async function loadCaptcha() {
  try {
    const data = await authApi.captcha()
    captcha.key = data.key
    captcha.image = data.image
    form.captcha_key = data.key
  } catch (e) {
    /* 验证码服务不可用则跳过 */
  }
}

async function onSubmit() {
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const res = await userStore.login({ ...form })
      ElMessage.success('登录成功')
      router.push('/')
    } catch (e) {
      if (captchaRequired.value) loadCaptcha()
    } finally {
      loading.value = false
    }
  })
}

onMounted(initCaptcha)
</script>

<style scoped>
.login-wrap {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1f2d3d 0%, #409eff 100%);
}
.login-card {
  width: 380px;
  padding: 10px 24px 24px;
  border-radius: 12px;
}
.brand {
  text-align: center;
  margin-bottom: 18px;
}
.logo {
  width: 56px;
  height: 56px;
  margin: 0 auto 10px;
  border-radius: 12px;
  background: #409eff;
  color: #fff;
  font-weight: 700;
  font-size: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.brand h2 {
  margin: 6px 0 2px;
  font-size: 20px;
}
.subtitle {
  margin: 0;
  color: #909399;
  font-size: 13px;
}
.captcha-row {
  display: flex;
  gap: 10px;
  align-items: center;
}
.captcha-img {
  height: 40px;
  border-radius: 4px;
  cursor: pointer;
}
.login-btn {
  width: 100%;
}
.hint {
  margin-top: 14px;
  text-align: center;
  color: #909399;
  font-size: 12px;
}
</style>
