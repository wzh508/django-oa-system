<template>
  <div class="page-card" v-loading="loading">
    <div v-if="notice">
      <div class="head">
        <h2 style="margin: 0">{{ notice.title }}</h2>
        <div class="meta">
          <el-tag size="small" :type="levelType(notice.level)">{{ notice.level }}</el-tag>
          <span>{{ notice.publisher_name }}</span><span>{{ notice.dept_name }}</span><span>{{ notice.published_at }}</span><span>阅读 {{ notice.read_count }}</span>
        </div>
      </div>
      <el-divider />
      <div class="content" v-html="notice.content"></div>
    </div>
    <el-empty v-else-if="!loading" description="公告不存在" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { http } from '@/api/http'
import { announcementApi } from '@/api/modules'
const route = useRoute()
const loading = ref(false)
const notice = ref(null)
function levelType(l) { return l === 'urgent' ? 'danger' : l === 'important' ? 'warning' : 'info' }
async function load() {
  loading.value = true
  try {
    const data = await http.get(`/announcement/notices/${route.params.id}/`)
    notice.value = data
    await announcementApi.read(route.params.id).catch(() => {})
  } catch (e) {
    notice.value = null
  } finally { loading.value = false }
}
onMounted(load)
</script>
<style scoped>
.meta { color: #909399; font-size: 13px; margin-top: 8px; display: flex; gap: 12px; flex-wrap: wrap; }
.content { line-height: 1.8; color: #303133; }
</style>
