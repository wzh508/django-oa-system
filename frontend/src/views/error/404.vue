<template>
  <div class="err-page">
    <el-result icon="info" title="404" sub-title="页面不存在或已被移除">
      <template #extra>
        <el-button type="primary" @click="$router.push('/dashboard/index')">返回工作台</el-button>
      </template>
    </el-result>
  </div>
</template>
<script setup></script>
<style scoped>
.err-page { height: 100vh; display: flex; align-items: center; justify-content: center; }
</style>
