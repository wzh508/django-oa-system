<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header"><span class="page-title">打卡</span><span class="muted">{{ today }}</span></div>
    <el-row :gutter="16">
      <el-col :span="8" v-for="p in punches" :key="p.type">
        <el-card shadow="hover" :body-style="{ padding: '20px' }">
          <div class="pt">{{ p.label }}</div>
          <div class="pt-time">{{ p.time || '未打卡' }}</div>
          <el-button type="primary" :icon="Clock" @click="doPunch(p.type)" :loading="submitting">{{ p.time ? '重新打卡' : '打卡' }}</el-button>
        </el-card>
      </el-col>
    </el-row>
    <el-card shadow="never" header="今日打卡记录" style="margin-top: 14px">
      <el-timeline>
        <el-timeline-item v-for="r in records" :key="r.id" :timestamp="r.time" placement="top">
          {{ r.type === 'in' ? '上班打卡' : '下班打卡' }} · {{ r.source || '' }}
        </el-timeline-item>
      </el-timeline>
      <el-empty v-if="!records.length" description="暂无记录" />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { attendanceApi } from '@/api/modules'
import { Clock } from '@element-plus/icons-vue'
const loading = ref(false)
const submitting = ref(false)
const today = new Date().toLocaleDateString('zh-CN')
const punches = ref([{ type: 'in', label: '上班打卡', time: '' }, { type: 'out', label: '下班打卡', time: '' }])
const records = ref([])

async function load() {
  loading.value = true
  try {
    const data = await attendanceApi.punchToday()
    records.value = data?.records || []
    const map = {}; (data?.records || []).forEach((r) => { map[r.type] = r.time })
    punches.value.forEach((p) => { p.time = map[p.type] || '' })
  } catch (e) {} finally { loading.value = false }
}
async function doPunch(type) {
  submitting.value = true
  try { await http.post(attendanceApi.punch, { type }); ElMessage.success('打卡成功'); load() } catch (e) {} finally { submitting.value = false }
}
onMounted(load)
</script>
<style scoped>
.pt { color: #909399; font-size: 14px; }
.pt-time { font-size: 22px; font-weight: 700; margin: 8px 0 14px; }
.muted { color: #909399; }
</style>
