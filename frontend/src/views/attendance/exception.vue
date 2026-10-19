<template>
  <div class="page-card">
    <div class="page-header"><span class="page-title">异常考勤</span></div>
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="date" label="日期" width="120" />
      <el-table-column label="姓名" width="100">
        <template #default="{ row }">{{ row.user?.first_name || row.user?.username || '—' }}</template>
      </el-table-column>
      <el-table-column prop="dept_name" label="部门" width="140" />
      <el-table-column prop="type" label="异常类型" width="110">
        <template #default="{ row }"><el-tag type="danger" size="small">{{ typeLabel[row.type] || row.type }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="reason" label="原因" min-width="160" show-overflow-tooltip />
      <el-table-column prop="status" label="处理状态" width="100">
        <template #default="{ row }"><el-tag :type="row.status === 'handled' ? 'success' : 'warning'" size="small">{{ row.status === 'handled' ? '已处理' : '待处理' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status !== 'handled'" link type="primary" @click="handle(row)">处理</el-button>
          <span v-else>—</span>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="vis" title="异常处理" width="460px">
      <el-input v-model="reason" type="textarea" :rows="3" placeholder="处理说明" />
      <template #footer><el-button @click="vis=false">取消</el-button><el-button type="primary" @click="submit">确定</el-button></template>
    </el-dialog>
    <el-pagination class="pager" background layout="total, prev, pager, next" :total="total" :current-page="page" :page-size="pageSize" @current-change="(p) => load(p)" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { attendanceApi } from '@/api/modules'
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const vis = ref(false)
const reason = ref('')
const cur = ref(null)
const typeLabel = { late: '迟到', early: '早退', absent: '缺勤', forget: '漏打卡' }

async function load(p) {
  if (p) page.value = p
  loading.value = true
  try {
    const data = await http.get(attendanceApi.exceptions, { params: { page: page.value, page_size: pageSize.value } })
    rows.value = data?.list || []
    total.value = data?.total ?? 0
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
function handle(row) { cur.value = row; reason.value = ''; vis.value = true }
async function submit() {
  try {
    // 后端约定：{ result: 处理说明, status: handled|ignored }
    await attendanceApi.exceptionHandle(cur.value.id, { result: reason.value, status: 'handled' })
    ElMessage.success('已处理'); vis.value = false; load()
  } catch (e) {}
}
onMounted(() => load(1))
</script>
<style scoped>
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
