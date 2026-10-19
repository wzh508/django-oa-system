<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header"><span class="page-title">{{ id ? '编辑公告' : '发布公告' }}</span></div>
    <el-form label-width="90px" :model="form" style="max-width: 760px" ref="formRef">
      <el-form-item label="标题" required><el-input v-model="form.title" /></el-form-item>
      <el-form-item label="分类">
        <el-select v-model="form.category" style="width: 200px">
          <el-option label="通知" value="notice" /><el-option label="公告" value="announcement" /><el-option label="制度" value="policy" />
        </el-select>
      </el-form-item>
      <el-form-item label="级别">
        <el-select v-model="form.level" style="width: 200px">
          <el-option label="普通" value="normal" /><el-option label="重要" value="important" /><el-option label="紧急" value="urgent" />
        </el-select>
      </el-form-item>
      <el-form-item label="发布部门">
        <el-select v-model="form.dept" filterable style="width: 240px"><el-option v-for="d in depts" :key="d.id" :label="d.name" :value="d.id" /></el-select>
      </el-form-item>
      <el-form-item label="置顶"><el-switch v-model="form.is_top" /></el-form-item>
      <el-form-item label="内容" required><el-input v-model="form.content" type="textarea" :rows="8" /></el-form-item>
      <el-form-item>
        <el-button type="primary" @click="submit" :loading="saving">保存</el-button>
        <el-button @click="router.push('/announcement/list')">返回</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { announcementApi } from '@/api/modules'
const route = useRoute()
const router = useRouter()
const id = route.params.id || null
const loading = ref(false)
const saving = ref(false)
const depts = ref([])
const form = reactive({ title: '', category: 'notice', level: 'normal', dept: null, is_top: false, content: '' })

async function load() {
  loading.value = true
  try {
    const d = await http.get('/accounts/departments/', { params: { page_size: 200 } })
    depts.value = d?.list || []
    if (id) {
      const data = await http.get(`/announcement/notices/${id}/`)
      Object.assign(form, { title: data.title, category: data.category, level: data.level, dept: data.dept, is_top: data.is_top, content: data.content })
    } else if (depts.value.length) {
      form.dept = depts.value[0].id
    }
  } catch (e) {
    if (id) router.push('/announcement/list')
  } finally { loading.value = false }
}
async function submit() {
  if (!form.title || !form.content) { ElMessage.warning('请填写标题与内容'); return }
  saving.value = true
  try {
    if (id) await http.put(`/announcement/notices/${id}/`, form)
    else await http.post(announcementApi.notices, form)
    ElMessage.success('保存成功'); router.push('/announcement/list')
  } catch (e) {} finally { saving.value = false }
}
onMounted(load)
</script>
<style scoped>
</style>
