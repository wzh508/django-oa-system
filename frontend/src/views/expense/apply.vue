<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header"><span class="page-title">报销申请</span></div>
    <el-form label-width="100px" :model="form" style="max-width: 820px">
      <el-form-item label="标题"><el-input v-model="form.title" placeholder="如 9月差旅费报销" /></el-form-item>
      <el-form-item label="费用类型">
        <el-select v-model="form.fee_type" style="width: 220px">
          <el-option v-for="f in feeTypes" :key="f.value" :label="f.label" :value="f.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="紧急程度">
        <el-radio-group v-model="form.urgency">
          <el-radio value="low" border>低</el-radio><el-radio value="normal" border>中</el-radio><el-radio value="high" border>高</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="费用明细">
        <el-table :data="items" border size="small">
          <el-table-column label="项目" min-width="160">
            <template #default="{ row }"><el-input v-model="row.name" size="small" placeholder="费用说明" /></template>
          </el-table-column>
          <el-table-column label="金额" width="140">
            <template #default="{ row }"><el-input-number v-model="row.amount" :min="0" :precision="2" size="small" style="width: 130px" /></template>
          </el-table-column>
          <el-table-column label="备注" min-width="140"><template #default="{ row }"><el-input v-model="row.note" size="small" /></template></el-table-column>
          <el-table-column label="" width="50"><template #default="{ $index }"><el-button link type="danger" :icon="Delete" @click="items.splice($index, 1)" /></template></el-table-column>
        </el-table>
        <el-button class="mt" :icon="Plus" @click="items.push({ name: '', amount: 0, note: '' })">添加明细</el-button>
      </el-form-item>
      <el-form-item label="发票张数"><el-input-number v-model="form.invoice_count" :min="0" /></el-form-item>
      <el-form-item label="合计"><b style="color:#f56c6c;font-size:18px">¥{{ total }}</b></el-form-item>
      <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
      <el-form-item>
        <el-button type="primary" @click="submit" :loading="saving">提交申请</el-button>
        <el-button @click="router.push('/expense/payment')">返回</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { http } from '@/api/http'
import { workflowApi } from '@/api/modules'
import { Plus, Delete } from '@element-plus/icons-vue'
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const feeTypes = [
  { label: '交通', value: 'traffic' }, { label: '差旅', value: 'travel' }, { label: '餐饮', value: 'meal' },
  { label: '办公', value: 'office' }, { label: '招待', value: 'entertain' }, { label: '其他', value: 'other' },
]
const form = reactive({ title: '', fee_type: 'travel', urgency: 'normal', invoice_count: 0, remark: '' })
const items = ref([{ name: '', amount: 0, note: '' }])
const total = computed(() => items.value.reduce((s, i) => s + (Number(i.amount) || 0), 0).toFixed(2))
async function submit() {
  if (!form.title) { ElMessage.warning('请填写标题'); return }
  const valid = items.value.every((i) => i.name)
  if (!valid) { ElMessage.warning('请补全明细说明'); return }
  saving.value = true
  try {
    await http.post(workflowApi.requests, {
      title: form.title, fee_type: form.fee_type, urgency: form.urgency,
      invoice_count: form.invoice_count, remark: form.remark,
      items: items.value.filter((i) => i.name), amount: Number(total.value),
    })
    ElMessage.success('提交成功'); router.push('/workspace/mine')
  } catch (e) {} finally { saving.value = false }
}
</script>
<style scoped>
.mt { margin-top: 10px; }
</style>
