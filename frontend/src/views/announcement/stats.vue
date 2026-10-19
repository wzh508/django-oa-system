<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header"><span class="page-title">公告阅读统计</span></div>
    <el-row :gutter="16">
      <el-col :span="6" v-for="c in cards" :key="c.label">
        <el-card shadow="hover" :body-style="{ padding: '16px' }"><div class="n">{{ c.value }}</div><div class="t">{{ c.label }}</div></el-card>
      </el-col>
    </el-row>
    <el-card shadow="never" header="按分类" style="margin-top: 14px" v-if="byCategory.length">
      <el-table :data="byCategory" border>
        <el-table-column label="分类"><template #default="{ row }">{{ CATEGORY[row.category] || row.category }}</template></el-table-column>
        <el-table-column prop="count" label="数量" width="100" />
        <el-table-column prop="read_count" label="阅读数" width="120" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { http } from '@/api/http'
import { announcementApi } from '@/api/modules'
const CATEGORY = { notice: '通知', announcement: '公告', policy: '制度' }
const loading = ref(false)
const cards = ref([])
const byCategory = ref([])
async function load() {
  loading.value = true
  try {
    const data = await announcementApi.stats()
    cards.value = [
      { label: '公告总数', value: data?.total ?? '—' },
      { label: '总阅读数', value: data?.total_read ?? '—' },
      { label: '置顶数', value: data?.top_count ?? '—' },
      { label: '本月新增', value: data?.month_count ?? '—' },
    ]
    byCategory.value = data?.by_category || []
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
onMounted(load)
</script>
<style scoped>
.n { font-size: 24px; font-weight: 700; }
.t { color: #909399; font-size: 13px; margin-top: 4px; }
</style>
