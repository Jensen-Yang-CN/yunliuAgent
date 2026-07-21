<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  DataLine,
  Monitor,
  VideoCamera,
  Aim,
  Connection,
  ArrowDown,
  ChatDotRound
} from '@element-plus/icons-vue'

const route = useRoute()
const activeIndex = computed(() => route.path)
</script>

<template>
  <el-container class="layout-container">
    <el-aside width="200px" >
      <el-menu
        :default-active="activeIndex"
        class="el-menu-vertical"
        background-color="#001529"
        text-color="#fff"
        active-text-color="#ffd04b"
        router>
        <el-menu-item index="/dashboard">
          <el-icon><DataLine /></el-icon>
          <span>系统概览</span>
        </el-menu-item>
        <el-menu-item index="/device-monitoring">
          <el-icon><Monitor /></el-icon>
          <span>物理设备检测</span>
        </el-menu-item>
        <el-menu-item index="/video-analysis">
          <el-icon><VideoCamera /></el-icon>
          <span>大模型视频推理</span>
        </el-menu-item>
        <el-menu-item index="/object-detection">
          <el-icon><Aim /></el-icon>
          <span>目标识别检测</span>
        </el-menu-item>
          <el-sub-menu>
            <template #title>
              <el-icon><VideoCamera /></el-icon>
              <span>多路视频检测</span>
            </template>
            <el-menu-item index="/detection">实时检测</el-menu-item>
            <el-menu-item index="/alarms">报警记录</el-menu-item>
            <el-menu-item index="/keyframes">关键帧查看</el-menu-item>
          </el-sub-menu>
        <el-menu-item index="/drone-patrol">
          <el-icon><Connection /></el-icon>
          <span>无人机巡检</span>
        </el-menu-item>
        <el-menu-item index="/agent-chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>AI智能体对话</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    
    <el-container width="100%">
      <el-header width="100%">
        <div class="header-content">
          <h2>矿业生产AI监测系统</h2>
          <el-dropdown>
            <span class="user-info">
              管理员 <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item>个人信息</el-dropdown-item>
                <el-dropdown-item>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <el-main>
        <router-view v-slot="{ Component }">
          <keep-alive include="VideoGrid">
            <component :is="Component" />
          </keep-alive>
        </router-view> 
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout-container {
 
  height: 100vh;
  width: 100%;
}

.el-aside {
  background-color: #001529;
}



.el-menu-vertical {
  height: 100%;
  border-right: none;
}

.el-header {
  background-color: #fff;
  border-bottom: 1px solid #dcdfe6;
  padding: 0 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
  width:100%;
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.el-main {
  background-color: #f0f2f5;
  padding: 20px;
  display: flex; /* Use flexbox for the main content area */
  flex-direction: column; /* Stack children vertically */
  height: calc(100vh - 60px); /* Full viewport height minus header height */
  overflow: hidden; /* Prevent the main area itself from scrolling */
}
</style>
