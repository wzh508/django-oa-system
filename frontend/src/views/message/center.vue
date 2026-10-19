<template>
  <div class="page-card">
    <div class="page-header">
      <span class="page-title">消息中心</span>
      <div>
        <el-badge :value="unread" :hidden="!unread" type="danger"><el-button :icon="Bell" @click="load">刷新</el-button></el-badge>
        <el-button type="primary" :icon="Check" @click="readAll">全部已读</el-button>
      </div>
    </div>
    <el-table :data="rows" v-loading="loading" border stripe @row-click="onRow">
      <el-table-column prop="is_read" label="" width="50">
        <template #default="{ row }"><span class="dot" :class="{ on: !row.is_read }"></span></template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
      <el-table-column prop="level" label="级别" width="90">
        <template #default="{ row }"><el-tag :type="row.level === 'urgent' ? 'danger' : row.level === 'warning' ? 'warning' : 'info'" size="small">{{ levelLabel[row.level] || '普通' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="发送人" width="100">
        <template #default="{ row }">{{ row.sender_name || '系统' }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" min-width="160" />
      <el-table-column label="操作" width="80" fixed="right"><template #default="{ row }"><el-button v-if="!row.is_read" link type="primary" @click.stop="readOne(row)">标记已读</el-button><span v-else>—</span></template></el-table-column>
    </el-table>
    <el-pagination class="pager" background layout="total, prev, pager, next" :total="total" :current-page="page" :page-size="pageSize" @current-change="(p) => load(p)" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { messageApi } from '@/api/modules'
import { Bell, Check } from '@element-plus/icons-vue'
const rows = ref([])
const total = ref(0)
const unread = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const levelLabel = { info: '普通', warning: '提醒', urgent: '紧急' }

async function load(p) {
  if (p) page.value = p
  loading.value = true
  try {
    const [d, u] = await Promise.all([
      http.get(messageApi.list, { params: { page: page.value, page_size: pageSize.value } }),
      messageApi.unreadCount(),
    ])
    rows.value = d?.list || []
    total.value = d?.total ?? 0
    unread.value = u?.count ?? 0
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
function onRow(row) { if (!row.is_read) readOne(row) }
async function readOne(row) { try { await messageApi.read(row.id); row.is_read = true; unread.value = Math.max(0, unread.value - 1) } catch (e) {} }
async function readAll() { try { await messageApi.readAll(); ElMessage.success('已全部标记已读'); load() } catch (e) {} }
onMounted(() => load(1))
</script>
<style scoped>
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #c0c4cc; }
.dot.on { background: #f56c6c; }
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
