<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header"><span class="page-title">流程瓶颈分析</span><el-button :icon="Refresh" @click="load">刷新</el-button></div>
    <el-card shadow="never" header="瓶颈节点排行" v-if="nodes.length">
      <el-table :data="nodes" border stripe>
        <el-table-column prop="node" label="节点" min-width="160" />
        <el-table-column prop="count" label="样本数" width="100" />
        <el-table-column prop="avg_hours" label="平均停留(h)" width="130" />
        <el-table-column prop="max_hours" label="最长停留(h)" width="130" />
        <el-table-column label="瓶颈指数" width="160">
          <template #default="{ row }"><el-progress :percentage="Math.min(100, Math.round((row.avg_hours / maxHours) * 100))" :color="row.avg_hours >= maxHours * 0.7 ? '#f56c6c' : '#409eff'" /></template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-empty v-else-if="!loading" description="暂无瓶颈数据" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { http } from '@/api/http'
import { insightApi } from '@/api/modules'
import { Refresh } from '@element-plus/icons-vue'
const loading = ref(false)
const nodes = ref([])
const maxHours = ref(1)
async function load() {
  loading.value = true
  try {
    const d = await insightApi.bottleneck()
    nodes.value = d?.nodes || []
    maxHours.value = Math.max(1, ...nodes.value.map((x) => x.avg_hours || 0))
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
onMounted(load)
</script>
<style scoped>
</style>
