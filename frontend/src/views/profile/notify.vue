<template>
  <div class="page-card">
    <div class="page-header"><span class="page-title">通知偏好</span></div>
    <el-alert type="info" :closable="false" title="通知偏好保存在本机，用于演示消息渠道的开关。" style="margin-bottom: 12px" />
    <el-form label-width="140px" style="max-width: 520px">
      <el-form-item v-for="n in items" :key="n.key" :label="n.label">
        <el-switch v-model="n.on" @change="persist" />
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
const items = reactive([
  { key: 'sys_msg', label: '系统站内信', on: true },
  { key: 'email', label: '邮件通知', on: false },
  { key: 'sms', label: '短信通知', on: false },
  { key: 'approve_push', label: '审批待办推送', on: true },
  { key: 'urgent_only', label: '仅接收紧急消息', on: false },
])
const KEY = 'oa_notify_pref'
function persist() { localStorage.setItem(KEY, JSON.stringify(items.map((i) => ({ key: i.key, on: i.on })))) }
onMounted(() => {
  try { const saved = JSON.parse(localStorage.getItem(KEY) || '[]'); saved.forEach((s) => { const t = items.find((i) => i.key === s.key); if (t) t.on = s.on }) } catch (e) {}
})
</script>
<style scoped>
</style>
