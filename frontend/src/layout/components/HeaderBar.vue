<template>
  <div class="oa-header">
    <div class="oa-header-left">
      <el-icon class="fold-btn" @click="app.toggleSidebar()">
        <component :is="app.sidebarCollapsed ? 'Expand' : 'Fold'" />
      </el-icon>
      <breadcrumb />
    </div>
    <div class="oa-header-right">
      <el-badge :value="unread" :hidden="!unread" class="bell">
        <el-icon class="bell-icon" @click="goMessage"><Bell /></el-icon>
      </el-badge>
      <el-dropdown @command="onCommand">
        <span class="user-area">
          <el-avatar class="avatar">{{ user.avatarText }}</el-avatar>
          <span class="username">{{ user.name }}</span>
          <el-icon><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">个人信息</el-dropdown-item>
            <el-dropdown-item command="password">修改密码</el-dropdown-item>
            <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useUserStore } from '@/store/modules/user'
import { useAppStore } from '@/store/modules/app'
import { messageApi } from '@/api/modules'
import Breadcrumb from './Breadcrumb.vue'

const router = useRouter()
const userStore = useUserStore()
const app = useAppStore()
const user = computed(() => ({
  name: userStore.name,
  avatarText: userStore.avatarText,
}))
const unread = ref(0)

async function loadUnread() {
  try {
    const data = await messageApi.unreadCount()
    unread.value = data?.unread_count || data?.count || 0
  } catch (e) {
    unread.value = 0
  }
}

function goMessage() {
  router.push('/message/center')
}

async function onCommand(cmd) {
  if (cmd === 'logout') {
    await ElMessageBox.confirm('确认退出登录？', '提示', { type: 'warning' })
    await userStore.logout()
    ElMessage.success('已退出')
    router.replace('/login')
  } else if (cmd === 'profile') {
    router.push('/profile/index')
  } else if (cmd === 'password') {
    router.push('/profile/password')
  }
}

onMounted(loadUnread)
</script>

<style scoped>
.oa-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
.oa-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.fold-btn {
  font-size: 20px;
  cursor: pointer;
}
.oa-header-right {
  display: flex;
  align-items: center;
  gap: 18px;
}
.bell-icon {
  font-size: 20px;
  cursor: pointer;
}
.user-area {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
}
.avatar {
  background: #409eff;
  color: #fff;
}
.username {
  font-size: 14px;
}
</style>
