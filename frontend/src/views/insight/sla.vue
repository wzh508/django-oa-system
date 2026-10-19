<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header">
      <span class="page-title">时效预测分析</span>
      <div>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
        <el-button type="primary" :icon="MagicStick" :loading="refreshing" @click="doRefresh">重算预测</el-button>
      </div>
    </div>
    <el-card shadow="never" header="整体时效指标" v-if="stats">
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="平均处理时长">{{ stats.avg_hours }} 小时</el-descriptions-item>
        <el-descriptions-item label="已完成单量">{{ stats.completed ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="准时率">{{ Math.round((stats.on_time_rate ?? 0) * 100) }}%</el-descriptions-item>
      </el-descriptions>
    </el-card>
    <el-card shadow="never" header="按模板基线" style="margin-top: 14px" v-if="baseline.length">
      <el-table :data="baseline" border stripe>
        <el-table-column prop="template" label="模板" min-width="160" />
        <el-table-column prop="avg_hours" label="平均时长(h)" width="130" />
        <el-table-column prop="sample_count" label="样本数" width="100" />
      </el-table>
    </el-card>
    <el-empty v-else-if="!loading" description="暂无预测数据" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { insightApi } from '@/api/modules'
import { Refresh, MagicStick } from '@element-plus/icons-vue'
const loading = ref(false)
const refreshing = ref(false)
const stats = ref(null)
const baseline = ref([])
async function load() {
  loading.value = true
  try {
    const d = await insightApi.stats()
    stats.value = d
    baseline.value = d?.by_template || []
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
async function doRefresh() {
  refreshing.value = true
  try { await insightApi.refresh(); ElMessage.success('已重算'); load() } catch (e) {} finally { refreshing.value = false }
}
onMounted(load)
</script>
<style scoped>
</style>
