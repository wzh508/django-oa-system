import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import { setupPermissionDirective } from './utils/permission'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// 注册全部 Element Plus 图标（菜单 icon 直接按组件名渲染）
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

setupPermissionDirective(app)

app.mount('#app')
