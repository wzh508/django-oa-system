<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header">
      <span class="page-title">{{ id ? '编辑表单' : '新建表单' }}</span>
      <el-button type="primary" @click="save" :loading="saving">保存</el-button>
    </div>
    <el-form label-width="90px" :model="form" style="max-width: 760px">
      <el-form-item label="表单名称"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="编码"><el-input v-model="form.code" :disabled="!!id" placeholder="如 satisfaction" /></el-form-item>
      <el-form-item label="分类"><el-input v-model="form.category" placeholder="如 调查/行政" /></el-form-item>
    </el-form>
    <el-card shadow="never" header="字段设计">
      <el-table :data="fields" border>
        <el-table-column label="字段名(key)" min-width="140"><template #default="{ row }"><el-input v-model="row.key" size="small" /></template></el-table-column>
        <el-table-column label="标签" min-width="120"><template #default="{ row }"><el-input v-model="row.label" size="small" /></template></el-table-column>
        <el-table-column label="类型" width="130"><template #default="{ row }"><el-select v-model="row.type" size="small"><el-option v-for="t in types" :key="t" :label="t" :value="t" /></el-select></template></el-table-column>
        <el-table-column label="必填" width="70"><template #default="{ row }"><el-switch v-model="row.required" size="small" /></template></el-table-column>
        <el-table-column label="选项(JSON)" min-width="160"><template #default="{ row }"><el-input v-model="row.options" size="small" placeholder='[{"label":"A","value":"a"}]' :disabled="row.type !== 'select'" /></template></el-table-column>
        <el-table-column label="" width="50"><template #default="{ $index }"><el-button link type="danger" :icon="Delete" @click="fields.splice($index, 1)" /></template></el-table-column>
      </el-table>
      <el-button class="mt" :icon="Plus" @click="addField">添加字段</el-button>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { lowcodeApi } from '@/api/modules'
import { Plus, Delete } from '@element-plus/icons-vue'
const route = useRoute()
const router = useRouter()
const id = route.params.id || null
const loading = ref(false)
const saving = ref(false)
const types = ['text', 'textarea', 'number', 'date', 'select', 'switch']
const form = reactive({ name: '', code: '', category: '' })
const fields = ref([])

function addField() { fields.value.push({ key: '', label: '', type: 'text', required: false, options: '' }) }
async function load() {
  loading.value = true
  try {
    if (id) {
      const data = await http.get(`/lowcode/schemas/${id}/`)
      Object.assign(form, { name: data.name, code: data.code, category: data.category })
      fields.value = (data.fields || []).map((f) => ({ ...f, options: Array.isArray(f.options) ? JSON.stringify(f.options) : (f.options || '') }))
    }
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
async function save() {
  if (!form.name || !form.code) { ElMessage.warning('请填写名称与编码'); return }
  const fs = fields.value.filter((f) => f.key && f.label).map((f) => ({
    key: f.key, label: f.label, type: f.type, required: f.required,
    options: f.type === 'select' && f.options ? JSON.parse(f.options || '[]') : [],
  }))
  saving.value = true
  try {
    const payload = { name: form.name, code: form.code, category: form.category, fields: fs }
    if (id) await http.put(`/lowcode/schemas/${id}/`, payload)
    else await http.post(lowcodeApi.schemas, payload)
    ElMessage.success('保存成功'); router.push('/lowcode/form')
  } catch (e) {} finally { saving.value = false }
}
onMounted(load)
</script>
<style scoped>
.mt { margin-top: 10px; }
</style>
