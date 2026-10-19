<template>
  <router-view />
</template>

<script setup>
// 应用根组件：仅承载路由出口
</script>

<style>
html, body, #app {
  height: 100%;
  margin: 0;
  padding: 0;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: #f0f2f5;
  color: #1f2329;
}
* { box-sizing: border-box; }
.page-card { background: #fff; border-radius: 8px; padding: 16px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04); }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.page-title { font-size: 18px; font-weight: 600; }
</style>
