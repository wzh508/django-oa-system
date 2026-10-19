<template>
  <el-container class="oa-layout">
    <el-aside :width="app.sidebarCollapsed ? '64px' : '220px'" class="oa-aside">
      <div class="logo">
        <span v-if="!app.sidebarCollapsed">OA 管理系统</span>
        <span v-else>OA</span>
      </div>
      <sidebar class="oa-aside-menu" />
    </el-aside>
    <el-container>
      <el-header height="56px" style="padding: 0">
        <header-bar />
      </el-header>
      <el-main class="oa-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useAppStore } from '@/store/modules/app'
import Sidebar from './components/Sidebar.vue'
import HeaderBar from './components/HeaderBar.vue'

const app = useAppStore()
</script>

<style scoped>
.oa-layout {
  height: 100vh;
}
.oa-aside {
  background: #1f2d3d;
  transition: width 0.2s;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 600;
  font-size: 16px;
  background: #18222e;
  letter-spacing: 1px;
}
.oa-aside-menu {
  flex: 1;
  overflow-y: auto;
}
.oa-main {
  background: #f0f2f5;
  padding: 16px;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
