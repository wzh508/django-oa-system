<template>
  <el-breadcrumb separator="/" class="oa-breadcrumb">
    <el-breadcrumb-item :to="{ path: '/dashboard/index' }">工作台</el-breadcrumb-item>
    <el-breadcrumb-item v-if="current">{{ current }}</el-breadcrumb-item>
  </el-breadcrumb>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const current = computed(() => route.meta.title || '')
</script>

<style scoped>
.oa-breadcrumb {
  display: inline-flex;
  align-items: center;
}
</style>
