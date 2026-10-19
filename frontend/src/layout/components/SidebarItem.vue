<template>
  <el-sub-menu
    v-if="node.type === 'dir' && node.children && node.children.length"
    :index="String(node.id)"
  >
    <template #title>
      <el-icon v-if="node.icon"><component :is="node.icon" /></el-icon>
      <span>{{ node.name }}</span>
    </template>
    <sidebar-item v-for="c in node.children" :key="c.id" :node="c" />
  </el-sub-menu>
  <el-menu-item v-else-if="node._fullPath" :index="node._fullPath">
    <el-icon v-if="node.icon"><component :is="node.icon" /></el-icon>
    <template #title>{{ node.name }}</template>
  </el-menu-item>
</template>

<script setup>
defineProps({ node: { type: Object, required: true } })
</script>

<script>
export default { name: 'SidebarItem' }
</script>
