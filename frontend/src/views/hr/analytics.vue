<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header"><span class="page-title">员工结构分析</span></div>
    <el-row :gutter="16">
      <el-col :span="12" v-for="panel in panels" :key="panel.title">
        <el-card shadow="never" :header="panel.title" style="margin-bottom: 16px">
          <div v-for="item in panel.data" :key="item.label" class="bar-row">
            <span class="bl">{{ item.label }}</span>
            <div class="btrack"><div class="bfill" :style="{ width: pct(item.value, panel.max) + '%', background: panel.color }"></div></div>
            <span class="bv">{{ item.value }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { http } from '@/api/http'
import { hrApi } from '@/api/modules'
const loading = ref(false)
const panels = ref([])
function pct(v, max) { return max ? Math.round((v / max) * 100) : 0 }

async function load() {
  loading.value = true
  try {
    const data = await hrApi.analytics()
    const byDept = (data?.by_dept || []).map((d) => ({ label: d.dept_name || d.name, value: d.count }))
    const byEdu = (data?.by_education || []).map((d) => ({ label: d.education, value: d.count }))
    const byAge = (data?.by_age || []).map((d) => ({ label: d.range, value: d.count }))
    const byTenure = (data?.by_tenure || []).map((d) => ({ label: d.range, value: d.count }))
    panels.value = [
      { title: '按部门分布', color: '#409eff', data: byDept, max: Math.max(1, ...byDept.map((x) => x.value)) },
      { title: '按学历分布', color: '#67c23a', data: byEdu, max: Math.max(1, ...byEdu.map((x) => x.value)) },
      { title: '按年龄分布', color: '#e6a23c', data: byAge, max: Math.max(1, ...byAge.map((x) => x.value)) },
      { title: '按司龄分布', color: '#909399', data: byTenure, max: Math.max(1, ...byTenure.map((x) => x.value)) },
    ]
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
onMounted(load)
</script>
<style scoped>
.bar-row { display: flex; align-items: center; gap: 10px; margin: 8px 0; font-size: 13px; }
.bl { width: 90px; color: #606266; }
.btrack { flex: 1; background: #f0f2f5; border-radius: 4px; height: 16px; overflow: hidden; }
.bfill { height: 100%; border-radius: 4px; transition: width .4s; }
.bv { width: 40px; text-align: right; color: #909399; }
</style>
