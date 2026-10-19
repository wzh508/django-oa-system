<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header">
      <span class="page-title">模板版本对比</span>
      <div>
        <span class="muted">对比版本：</span>
        <el-select v-model="otherId" placeholder="选择历史版本" style="width: 200px" @change="runDiff">
          <el-option v-for="v in versions" :key="v.id" :label="`v${v.version} · ${v.name}（${v.is_published ? '已发布' : '草稿'}）`" :value="v.id" />
        </el-select>
        <el-button :icon="Refresh" @click="runDiff">对比</el-button>
      </div>
    </div>
    <el-alert v-if="diff" type="info" :closable="false" :title="`当前 v${diff.left.version} ⇄ 对比 v${diff.right.version} · 共 ${diff.total} 处差异`" style="margin-bottom: 12px" />
    <el-table :data="diff?.changes || []" border stripe empty-text="无差异">
      <el-table-column prop="order" label="节点序" width="80" />
      <el-table-column prop="name" label="节点" min-width="140" />
      <el-table-column label="变更类型" width="110">
        <template #default="{ row }">
          <el-tag :type="row.type === 'added' ? 'success' : row.type === 'removed' ? 'danger' : 'warning'" size="small">{{ typeLabel[row.type] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="变更明细" min-width="360">
        <template #default="{ row }">
          <template v-if="row.type === 'added'">新增节点：{{ row.after?.name }}</template>
          <template v-else-if="row.type === 'removed'">移除节点：{{ row.before?.name }}</template>
          <template v-else>
            <div v-for="(v, k) in row.diff" :key="k" class="dline">
              <b>{{ k }}</b>：<span class="del">{{ short(v.before) }}</span> → <span class="add">{{ short(v.after) }}</span>
            </div>
          </template>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { http } from '@/api/http'
import { Refresh } from '@element-plus/icons-vue'
const route = useRoute()
const loading = ref(false)
const versions = ref([])
const otherId = ref(null)
const diff = ref(null)
const typeLabel = { added: '新增', removed: '移除', modified: '修改' }

function short(v) { return v === null || v === undefined ? '—' : (Array.isArray(v) ? v.join(',') : String(v)) }

async function load() {
  loading.value = true
  try {
    const cur = await http.get(`/workflow/templates/${route.params.id}/`)
    const data = await http.get('/workflow/templates/versions/', { params: { code: cur.code } })
    const all = Array.isArray(data) ? data : (data?.list || [])
    versions.value = all.filter((v) => v.id !== Number(route.params.id))
    if (versions.value.length) { otherId.value = versions.value[0].id; await runDiff() }
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
async function runDiff() {
  if (!otherId.value) return
  loading.value = true
  try {
    const data = await http.get(`/workflow/templates/${route.params.id}/diff/`, { params: { other: otherId.value } })
    diff.value = data
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
onMounted(load)
</script>
<style scoped>
.muted { color: #909399; }
.dline { font-size: 13px; margin: 2px 0; }
.del { color: #f56c6c; text-decoration: line-through; }
.add { color: #67c23a; }
</style>
