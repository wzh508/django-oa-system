<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header"><span class="page-title">发起申请</span></div>
    <el-form label-width="110px" style="max-width: 720px">
      <el-form-item label="流程模板">
        <el-select v-model="tplId" filterable placeholder="选择要发起的流程" style="width: 360px" @change="onTpl">
          <el-option v-for="t in templates" :key="t.id" :label="`${t.name}（v${t.version}）`" :value="t.id" />
        </el-select>
      </el-form-item>
      <template v-if="template">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="请输入申请标题" style="width: 360px" />
        </el-form-item>
        <template v-if="formSchema.length">
          <el-form-item v-for="f in formSchema" :key="f.key" :label="f.label" :required="f.required">
            <el-input v-if="f.type === 'text' || f.type === 'textarea'" v-model="formData[f.key]" :type="f.type === 'textarea' ? 'textarea' : 'text'" :rows="2" style="width: 360px" />
            <el-input-number v-else-if="f.type === 'number'" v-model="formData[f.key]" :min="0" style="width: 200px" />
            <el-date-picker v-else-if="f.type === 'date'" v-model="formData[f.key]" type="date" value-format="YYYY-MM-DD" style="width: 200px" />
            <el-select v-else-if="f.type === 'select'" v-model="formData[f.key]" style="width: 240px">
              <el-option v-for="o in (f.options || [])" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-input v-else v-model="formData[f.key]" style="width: 360px" />
          </el-form-item>
        </template>
        <el-form-item>
          <el-button type="primary" @click="submit" :loading="submitting">提交申请</el-button>
          <el-button @click="form.title=''; Object.keys(formData).forEach(k=>formData[k]='')">重置</el-button>
        </el-form-item>
      </template>
    </el-form>
    <el-empty v-if="!loading && !templates.length" description="暂无可发起的流程模板" />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { workflowApi } from '@/api/modules'

const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const templates = ref([])
const tplId = ref(null)
const template = ref(null)
const formSchema = ref([])
const form = reactive({ title: '' })
const formData = reactive({})

async function loadTpls() {
  loading.value = true
  try {
    const data = await http.get('/workflow/templates/', { params: { only_active: '1', page_size: 100 } })
    templates.value = data?.list || []
  } catch (e) { /* 错误已由 http 拦截器统一提示 */ } finally { loading.value = false }
}
async function onTpl(id) {
  const data = await http.get(`/workflow/templates/${id}/`)
  template.value = data
  formSchema.value = Array.isArray(data.form_schema) ? data.form_schema : []
  Object.keys(formData).forEach((k) => delete formData[k])
  formSchema.value.forEach((f) => { formData[f.key] = f.default !== undefined ? f.default : (f.type === 'number' ? 0 : '') })
}
async function submit() {
  if (!template.value) { ElMessage.warning('请选择模板'); return }
  if (!form.title) { ElMessage.warning('请填写标题'); return }
  submitting.value = true
  try {
    await workflowApi.startInstance({ template_code: template.value.code, title: form.title, form_data: { ...formData } })
    ElMessage.success('提交成功')
    router.push('/workspace/mine')
  } catch (e) {} finally { submitting.value = false }
}
onMounted(loadTpls)
</script>
<style scoped>
</style>
