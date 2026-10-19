<template>
  <div class="page-card">
    <!-- 搜索区 -->
    <el-form v-if="cfg.search && cfg.search.length" :inline="true" :model="searchForm" class="search-bar">
      <el-form-item v-for="f in cfg.search" :key="f.prop" :label="f.label">
        <el-input
          v-if="f.type === 'text' || !f.type"
          v-model="searchForm[f.prop]"
          :placeholder="f.placeholder || ('请输入' + f.label)"
          clearable
          style="width: 180px"
        />
        <el-select
          v-else-if="f.type === 'select'"
          v-model="searchForm[f.prop]"
          :placeholder="f.placeholder || ('请选择' + f.label)"
          clearable
          style="width: 180px"
        >
          <el-option v-for="o in resolvedOptions(f)" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-date-picker
          v-else-if="f.type === 'date'"
          v-model="searchForm[f.prop]"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          style="width: 180px"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :icon="Search" @click="load(1)">查询</el-button>
        <el-button :icon="Refresh" @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- 操作条 -->
    <div class="page-header">
      <span class="page-title">{{ cfg.title || route.meta.title }}</span>
      <div>
        <el-button v-if="showOp('create')" type="primary" :icon="Plus" @click="openCreate">新增</el-button>
        <el-button v-if="showOp('export')" :icon="Download" @click="onExport">导出</el-button>
        <slot name="toolbar" />
      </div>
    </div>

    <!-- 表格 -->
    <el-table :data="rows" v-loading="loading" border stripe style="width: 100%">
      <el-table-column v-if="cfg.index !== false" type="index" label="#" width="50" />
      <el-table-column
        v-for="col in cfg.columns"
        :key="col.prop"
        :prop="col.prop"
        :label="col.label"
        :width="col.width"
        :min-width="col.minWidth || 120"
        :formatter="col.formatter ? (r) => col.formatter(r) : null"
        show-overflow-tooltip
      >
        <template #default="{ row }" v-if="col.type === 'tag' || col.type === 'money' || col.type === 'datetime' || col.type === 'date' || col.type === 'bool' || col.type === 'options'">
          <el-tag v-if="col.type === 'tag'" :type="col.tagType || 'info'" :effect="col.effect || 'light'">
            {{ col.options ? labelOf(col.options, row[col.prop]) : row[col.prop] }}
          </el-tag>
          <span v-else-if="col.type === 'money'">{{ money(row[col.prop]) }}</span>
          <span v-else-if="col.type === 'datetime'">{{ fmtDateTime(row[col.prop]) }}</span>
          <span v-else-if="col.type === 'date'">{{ fmtDate(row[col.prop]) }}</span>
          <el-tag v-else-if="col.type === 'bool'" :type="row[col.prop] ? 'success' : 'info'">
            {{ row[col.prop] ? '是' : '否' }}
          </el-tag>
          <span v-else-if="col.type === 'options'">{{ labelOf(col.options, row[col.prop]) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" :width="cfg.opWidth || 160" fixed="right" v-if="hasRowOp">
        <template #default="{ row }">
          <el-button v-if="showOp('edit')" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="showOp('delete')" link type="danger" @click="onDelete(row)">删除</el-button>
          <slot name="row" :row="row" />
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <el-pagination
      class="pager"
      background
      layout="total, prev, pager, next, sizes"
      :total="total"
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="[10, 20, 50, 100]"
      @current-change="(p) => load(p)"
      @size-change="(s) => { pageSize = s; load(1) }"
    />

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" :width="cfg.dialogWidth || '520px'">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item
          v-for="f in cfg.form"
          :key="f.prop"
          :label="f.label"
          :prop="f.prop"
        >
          <el-input
            v-if="f.type === 'text' || !f.type"
            v-model="form[f.prop]"
            :placeholder="f.placeholder"
            :disabled="f.disabled"
          />
          <el-input
            v-else-if="f.type === 'textarea'"
            v-model="form[f.prop]"
            type="textarea"
            :rows="3"
            :disabled="f.disabled"
          />
          <el-input
            v-else-if="f.type === 'password'"
            v-model="form[f.prop]"
            type="password"
            show-password
          />
          <el-input-number
            v-else-if="f.type === 'number'"
            v-model="form[f.prop]"
            :min="f.min ?? 0"
            controls-position="right"
            style="width: 100%"
          />
          <el-select
            v-else-if="f.type === 'select'"
            v-model="form[f.prop]"
            :placeholder="f.placeholder || ('请选择' + f.label)"
            clearable
            style="width: 100%"
          >
            <el-option v-for="o in resolvedOptions(f)" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
          <el-date-picker
            v-else-if="f.type === 'date'"
            v-model="form[f.prop]"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
          <el-date-picker
            v-else-if="f.type === 'datetime'"
            v-model="form[f.prop]"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 100%"
          />
          <el-switch v-else-if="f.type === 'switch'" v-model="form[f.prop]" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, Download } from '@element-plus/icons-vue'
import { crud } from '@/api/crud'
import { useUserStore } from '@/store/modules/user'
import { money, fmtDateTime, fmtDate, toOptions } from '@/utils/format'
import viewConfigs from '@/config/viewConfigs'

const route = useRoute()
const userStore = useUserStore()
const cfg = computed(() => viewConfigs[route.meta.configKey] || {})

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)

const searchForm = reactive({})
const form = reactive({})
const dialogVisible = ref(false)
const dialogTitle = ref('')
const editingId = ref(null)
const formRef = ref(null)

const formRules = computed(() => {
  const rules = {}
  ;(cfg.value.form || []).forEach((f) => {
    if (f.required) rules[f.prop] = [{ required: true, message: `${f.label}不能为空`, trigger: 'blur' }]
  })
  return rules
})

const hasRowOp = computed(() => showOp('edit') || showOp('delete') || cfg.value.rowSlot)

function showOp(op) {
  const ops = cfg.value.ops || ['create', 'edit', 'delete']
  if (!ops.includes(op)) return false
  const perms = cfg.value.perms || {}
  if (op === 'create' && perms.create && !userStore.hasPerm(perms.create)) return false
  if (op === 'edit' && perms.edit && !userStore.hasPerm(perms.edit)) return false
  if (op === 'delete' && perms.delete && !userStore.hasPerm(perms.delete)) return false
  return true
}

function labelOf(options, value) {
  if (!options) return value
  const arr = resolvedOptionsStatic(options)
  const hit = arr.find((o) => o.value === value)
  return hit ? hit.label : value
}

function resolvedOptionsStatic(options) {
  if (Array.isArray(options)) return options
  return []
}

function resolvedOptions(field) {
  // 支持静态数组或动态 {api, label, value}
  if (Array.isArray(field.options)) return field.options
  if (field._options) return field._options
  return []
}

async function loadOpts() {
  const fields = [...(cfg.value.search || []), ...(cfg.value.form || [])]
  for (const f of fields) {
    if (f.options && typeof f.options === 'object' && f.options.api) {
      try {
        const data = await crud.list(f.options.api, { page_size: 200 })
        const list = data?.list || data || []
        f._options = toOptions(list, f.options.label || 'name', f.options.value || 'id')
      } catch (e) {
        f._options = []
      }
    }
  }
}

function buildSearchParams() {
  const p = { page: page.value, page_size: pageSize.value }
  ;(cfg.value.search || []).forEach((f) => {
    const v = searchForm[f.prop]
    if (v !== undefined && v !== null && v !== '') p[f.prop] = v
  })
  // 额外固定查询参数
  if (cfg.value.extraParams) Object.assign(p, cfg.value.extraParams)
  return p
}

async function load(p) {
  if (p) page.value = p
  loading.value = true
  try {
    const data = await crud.list(cfg.value.base, buildSearchParams())
    rows.value = data?.list || data || []
    total.value = data?.total ?? (Array.isArray(data) ? data.length : 0)
  } catch (e) {
    rows.value = []
  } finally {
    loading.value = false
  }
}

function resetSearch() {
  Object.keys(searchForm).forEach((k) => (searchForm[k] = ''))
  load(1)
}

function openCreate() {
  editingId.value = null
  dialogTitle.value = `新增${cfg.value.title || ''}`
  Object.keys(form).forEach((k) => delete form[k])
  ;(cfg.value.form || []).forEach((f) => {
    form[f.prop] = f.default !== undefined ? f.default : (f.type === 'switch' ? false : '')
  })
  dialogVisible.value = true
}

async function openEdit(row) {
  editingId.value = row.id
  dialogTitle.value = `编辑${cfg.value.title || ''}`
  try {
    const data = await crud.get(cfg.value.base, row.id)
    Object.keys(form).forEach((k) => delete form[k])
    ;(cfg.value.form || []).forEach((f) => {
      form[f.prop] = data?.[f.prop] ?? (f.type === 'switch' ? false : '')
    })
    dialogVisible.value = true
  } catch (e) {
    ElMessage.error('加载详情失败')
  }
}

async function submit() {
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      if (editingId.value) {
        await crud.update(cfg.value.base, editingId.value, { ...form })
        ElMessage.success('更新成功')
      } else {
        await crud.create(cfg.value.base, { ...form })
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      load()
    } catch (e) {
      /* 错误已在拦截器提示 */
    }
  })
}

async function onDelete(row) {
  await ElMessageBox.confirm('确认删除该记录？', '提示', { type: 'warning' })
  try {
    await crud.remove(cfg.value.base, row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    /* 拦截器提示 */
  }
}

function onExport() {
  if (cfg.value.exportUrl) {
    window.open(cfg.value.exportUrl, '_blank')
  } else {
    ElMessage.info('该模块暂不支持导出')
  }
}

onMounted(async () => {
  await loadOpts()
  load(1)
})
</script>

<style scoped>
.search-bar {
  margin-bottom: 8px;
}
.pager {
  margin-top: 14px;
  justify-content: flex-end;
}
</style>
