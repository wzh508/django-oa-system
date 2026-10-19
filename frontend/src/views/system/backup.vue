<template>
  <div class="page-card" v-loading="loading">
    <div class="page-header"><span class="page-title">数据备份</span></div>
    <el-alert type="info" :closable="false" title="系统提供 MySQL 全量备份与媒体文件归档脚本，建议配合定时任务（crontab / 任务计划程序）每日执行。" style="margin-bottom: 14px" />
    <el-card shadow="never" header="备份方式">
      <el-steps :active="3" align-center finish-status="finish">
        <el-step title="数据库备份" description="mysqldump 导出 SQL" />
        <el-step title="静态文件" description="归档 media 目录" />
        <el-step title="异地归档" description="上传至对象存储/网盘" />
      </el-steps>
      <el-divider />
      <pre class="code"># Linux / macOS
./scripts/bootstrap_env.sh   # 首次：建环境、迁移、初始化
./scripts/run.sh             # 日常：启动后端 + Celery

# Windows
scripts\bootstrap_env.ps1
scripts\run.ps1

# 单独备份数据库
mysqldump -u$DB_USER -p$DB_NAME &gt; backup/oa_$(date +%F).sql</pre>
    </el-card>
    <el-card shadow="never" header="恢复指引" style="margin-top: 14px">
      <ol class="tips">
        <li>停止应用服务，避免写入冲突。</li>
        <li>使用 <code>mysql -u$DB_USER -p$DB_NAME &lt; backup/oa_YYYY-MM-DD.sql</code> 恢复数据库。</li>
        <li>还原 media 归档目录到项目原路径。</li>
        <li>重启服务并验证登录与菜单加载。</li>
      </ol>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const loading = ref(false)
</script>
<style scoped>
.code { background: #1f2d3d; color: #c8e1ff; padding: 14px; border-radius: 6px; font-size: 12px; overflow: auto; }
.tips { padding-left: 18px; line-height: 2; color: #606266; }
</style>
