<template>
  <div class="page-card" v-loading="running">
    <div class="page-header"><span class="page-title">流程沙盘回放（版本快照推演）</span></div>
    <el-alert type="success" :closable="false" title="基于历史实例与模板快照，在不影响在途单据的前提下推演流程配置的真实表现。" style="margin-bottom: 14px" />
    <el-form :inline="true" :model="q">
      <el-form-item label="模板">
        <el-select v-model="q.template" filterable style="width: 240px" @change="onTpl">
          <el-option v-for="t in templates" :key="t.id" :label="`${t.name}（v${t.version}）`" :value="t.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="版本">
        <el-select v-model="q.template_version" style="width: 120px">
          <el-option v-for="v in versions" :key="v.id" :label="`v${v.version}`" :value="v.version" />
        </el-select>
      </el-form-item>
      <el-form-item label="回溯天数"><el-input-number v-model="q.since_days" :min="1" :max="365" /></el-form-item>
      <el-form-item label="样本上限"><el-input-number v-model="q.limit" :min="1" :max="2000" /></el-form-item>
      <el-form-item><el-button type="primary" :icon="VideoPlay" @click="run">开始回放</el-button></el-form-item>
    </el-form>

    <el-card shadow="never" header="回放结果" v-if="result" style="margin-top: 12px">
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="样本数">{{ result.sample_count ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="平均预计时长(h)">{{ result.avg_predict_hours ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="预计会签率">{{ pct(result.countersign_rate) }}</el-descriptions-item>
        <el-descriptions-item label="预计驳回率">{{ pct(result.reject_rate) }}</el-descriptions-item>
        <el-descriptions-item label="回溯区间">{{ result.since_days ?? '—' }} 天</el-descriptions-item>
        <el-descriptions-item label="瓶颈节点">{{ result.bottleneck_top3?.[0]?.node || '—' }}</el-descriptions-item>
      </el-descriptions>
      <el-table :data="result.bottleneck_top3 || []" border stripe size="small" style="margin-top: 12px" empty-text="无瓶颈数据">
        <el-table-column prop="node" label="瓶颈节点" min-width="160" />
        <el-table-column prop="total" label="样本量" width="100" />
        <el-table-column prop="avg_hours" label="平均停留(h)" width="130" />
        <el-table-column prop="overtime_rate" label="超时率" width="110">
          <template #default="{ row }">{{ pct(row.overtime_rate) }}</template>
        </el-table-column>
      </el-table>
      <el-alert v-if="result.advice?.length" type="info" :closable="false" style="margin-top: 12px" title="优化建议">
        <div v-for="(a, i) in result.advice" :key="i" class="advice">· {{ a }}</div>
      </el-alert>
      <el-collapse style="margin-top: 10px">
        <el-collapse-item title="查看原始报告 JSON">
          <pre class="raw">{{ JSON.stringify(result, null, 2) }}</pre>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <el-card shadow="never" header="历史回放任务" style="margin-top: 12px">
      <el-table :data="reports" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="template_version" label="版本" width="80" />
        <el-table-column prop="since_days" label="回溯天数" width="100" />
        <el-table-column prop="limit" label="样本上限" width="90" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }"><el-tag :type="statusType(row.status)" size="small">{{ statusLabel[row.status] || row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="cost_ms" label="耗时(ms)" width="100" />
        <el-table-column prop="created_at" label="创建时间" min-width="160" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { workflowApi } from '@/api/modules'
import { VideoPlay } from '@element-plus/icons-vue'
const q = reactive({ template: null, template_version: null, since_days: 90, limit: 200 })
const templates = ref([])
const versions = ref([])
const reports = ref([])
const result = ref(null)
const running = ref(false)
const loading = ref(false)

const pct = (v) => (v == null ? '—' : (v * 100).toFixed(1) + '%')
const statusLabel = { pending: '排队中', running: '执行中', success: '已完成', failed: '失败' }
const statusType = (s) => (s === 'success' ? 'success' : s === 'failed' ? 'danger' : 'warning')
const asList = (r) => (Array.isArray(r) ? r : (r?.list || []))

async function load() {
  const t = await http.get('/workflow/templates/', { params: { page_size: 100 } })
  templates.value = asList(t)
  loading.value = true
  try { reports.value = asList(await workflowApi.replayReports()) } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
async function onTpl(id) {
  const cur = await http.get(`/workflow/templates/${id}/`)
  const data = await http.get('/workflow/templates/versions/', { params: { code: cur.code } })
  versions.value = asList(data)
  q.template_version = cur.version
}
async function run() {
  if (!q.template) { ElMessage.warning('请选择模板'); return }
  running.value = true
  result.value = null
  try {
    const data = await workflowApi.replayRun({ ...q })
    result.value = data.result || data
    load()
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { running.value = false }
}
onMounted(load)
</script>
<style scoped>
.raw { background: #f5f7fa; padding: 10px; border-radius: 6px; font-size: 12px; max-height: 360px; overflow: auto; }
</style>
