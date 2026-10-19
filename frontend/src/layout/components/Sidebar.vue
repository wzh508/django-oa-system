<template>
  <el-menu
    :default-active="activeMenu"
    :collapse="collapsed"
    router
    unique-opened
    class="oa-menu"
    background-color="#1f2d3d"
    text-color="#bfcbd9"
    active-text-color="#409eff"
  >
    <sidebar-item v-for="node in menuTree" :key="node.id" :node="node" />
  </el-menu>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/store/modules/user'
import { useAppStore } from '@/store/modules/app'
import SidebarItem from './SidebarItem.vue'

const route = useRoute()
const userStore = useUserStore()
const appStore = useAppStore()

const collapsed = computed(() => appStore.sidebarCollapsed)

function withFullPath(nodes, base = '') {
  // visible=false 的菜单是「带参数的内部页」（详情 / 编辑 / 设计器），
  // 只能通过列表页按钮跳转，不能进侧边栏——否则点开就是字面量 :id 路径，接口必然 404。
  return (nodes || [])
    .filter((n) => n.visible !== false)
    .map((n) => {
      const node = { ...n }
      if (node.type === 'dir') {
        node._fullPath = node.path
        node.children = withFullPath(node.children, node.path)
      } else {
        const b = base.endsWith('/') ? base.slice(0, -1) : base
        node._fullPath = n.path && n.path.startsWith('/') ? n.path : `${b}/${n.path}`
      }
      return node
    })
}

const menuTree = computed(() => withFullPath(userStore.menus))
const activeMenu = computed(() => route.path)
</script>

<style scoped>
.oa-menu {
  border-right: none;
  height: 100%;
}
</style>
