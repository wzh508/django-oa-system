<template>
  <div class="err-page">
    <el-result icon="warning" title="403" sub-title="抱歉，您没有访问该页面的权限">
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
