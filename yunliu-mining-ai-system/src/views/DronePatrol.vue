<template>
  <div class="drone-patrol">
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card class="map-card">
          <template #header>
            <div class="card-header">
              <span>无人机巡检地图</span>
              <el-button-group>
                <el-button type="primary" @click="startPatrol">开始巡检</el-button>
                <el-button type="danger" @click="stopPatrol">停止巡检</el-button>
              </el-button-group>
            </div>
          </template>
          <div class="map-container">
            <div class="map-placeholder" v-if="!isPatrolling">
              <el-icon class="map-icon"><Location /></el-icon>
              <span>地图加载中...</span>
            </div>
            <div class="patrol-overlay" v-if="isPatrolling">
              <el-icon class="patrol-icon"><Loading /></el-icon>
              <span>正在巡检中...</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="patrol-info">
          <template #header>
            <div class="card-header">
              <span>巡检信息</span>
            </div>
          </template>
          <div class="info-content">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="无人机编号">
                DRONE-001
              </el-descriptions-item>
              <el-descriptions-item label="当前状态">
                <el-tag :type="isPatrolling ? 'success' : 'info'">
                  {{ isPatrolling ? '巡检中' : '待机' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="电池电量">
                <el-progress :percentage="85" />
              </el-descriptions-item>
              <el-descriptions-item label="飞行高度">
                50米
              </el-descriptions-item>
              <el-descriptions-item label="飞行速度">
                15km/h
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>
        <el-card class="patrol-task">
          <template #header>
            <div class="card-header">
              <span>巡检任务</span>
            </div>
          </template>
          <div class="task-list">
            <el-timeline>
              <el-timeline-item
                v-for="task in patrolTasks"
                :key="task.id"
                :type="task.type"
                :timestamp="task.time">
                <div class="task-item">
                  <div class="task-title">{{ task.title }}</div>
                  <div class="task-content">{{ task.content }}</div>
                </div>
              </el-timeline-item>
            </el-timeline>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Location, Loading } from '@element-plus/icons-vue'

const isPatrolling = ref(false)
const patrolTasks = ref([
  {
    id: 1,
    title: '设备检查',
    content: '完成1号矿井设备巡检',
    time: '2024-03-20 10:45:00',
    type: 'success'
  },
  {
    id: 2,
    title: '环境监测',
    content: '完成2号矿井空气质量检测',
    time: '2024-03-20 10:44:00',
    type: 'success'
  },
  {
    id: 3,
    title: '异常发现',
    content: '发现3号矿井设备异常',
    time: '2024-03-20 10:43:00',
    type: 'warning'
  }
])

const startPatrol = () => {
  isPatrolling.value = true
  // 模拟巡检过程
  setTimeout(() => {
    isPatrolling.value = false
    patrolTasks.value.unshift({
      id: Date.now(),
      title: '巡检完成',
      content: '完成新一轮巡检任务',
      time: new Date().toLocaleString(),
      type: 'success'
    })
  }, 3000)
}

const stopPatrol = () => {
  isPatrolling.value = false
}
</script>

<style scoped>
.drone-patrol {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.map-container {
  position: relative;
  width: 100%;
  height: 500px;
  background-color: #000;
  border-radius: 4px;
  overflow: hidden;
}

.map-placeholder {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #fff;
  background-color: #1a1a1a;
}

.map-icon {
  font-size: 48px;
  margin-bottom: 20px;
}

.patrol-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #fff;
}

.patrol-icon {
  font-size: 48px;
  margin-bottom: 20px;
  animation: rotate 2s linear infinite;
}

.info-content {
  margin-bottom: 20px;
}

.task-list {
  height: 300px;
  overflow-y: auto;
}

.task-item {
  padding: 10px;
}

.task-title {
  font-weight: bold;
  margin-bottom: 5px;
}

.task-content {
  color: #666;
  font-size: 14px;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style> 