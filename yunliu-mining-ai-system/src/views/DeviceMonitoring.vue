<template>
  <div class="device-monitoring">
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card class="device-list">
          <template #header>
            <div class="card-header">
              <span>设备监控列表</span>
              <el-button type="primary" @click="refreshData">刷新数据</el-button>
            </div>
          </template>
          <el-table :data="deviceList" style="width: 100%" v-loading="loading">
            <el-table-column prop="id" label="设备ID" width="100" />
            <el-table-column prop="name" label="设备名称" width="150" />
            <el-table-column prop="location" label="安装位置" width="150" />
            <el-table-column prop="temperature" label="温度" width="100">
              <template #default="scope">
                <span :class="{ 'warning-text': scope.row.temperature > 80 }">
                  {{ scope.row.temperature }}°C
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="pressure" label="压力" width="100">
              <template #default="scope">
                {{ scope.row.pressure }}MPa
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态">
              <template #default="scope">
                <el-tag :type="getStatusType(scope.row.status)">
                  {{ scope.row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="scope">
                <el-button type="primary" link @click="showDetails(scope.row)">
                  详情
                </el-button>
                <el-button type="danger" link @click="handleAlarm(scope.row)">
                  告警
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="alarm-list">
          <template #header>
            <div class="card-header">
              <span>实时告警</span>
            </div>
          </template>
          <el-timeline>
            <el-timeline-item
              v-for="alarm in alarmList"
              :key="alarm.id"
              :type="alarm.type"
              :timestamp="alarm.time">
              {{ alarm.content }}
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const loading = ref(false)
const deviceList = ref([
  {
    id: 'DEV001',
    name: '温度传感器',
    location: '1号矿井',
    temperature: 75,
    pressure: 2.5,
    status: '正常'
  },
  {
    id: 'DEV002',
    name: '压力传感器',
    location: '2号矿井',
    temperature: 85,
    pressure: 3.2,
    status: '警告'
  },
  {
    id: 'DEV003',
    name: '气体检测仪',
    location: '3号矿井',
    temperature: 65,
    pressure: 1.8,
    status: '正常'
  }
])

const alarmList = ref([
  {
    id: 1,
    content: '2号矿井压力传感器温度过高',
    time: '2024-03-20 10:30:00',
    type: 'warning'
  },
  {
    id: 2,
    content: '1号矿井气体浓度异常',
    time: '2024-03-20 10:25:00',
    type: 'danger'
  }
])

const getStatusType = (status) => {
  const types = {
    '正常': 'success',
    '警告': 'warning',
    '故障': 'danger'
  }
  return types[status] || 'info'
}

const refreshData = () => {
  loading.value = true
  setTimeout(() => {
    loading.value = false
  }, 1000)
}

const showDetails = (device) => {
  console.log('查看设备详情:', device)
}

const handleAlarm = (device) => {
  console.log('处理设备告警:', device)
}
</script>

<style scoped>
.device-monitoring {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.warning-text {
  color: #e6a23c;
}

.alarm-list {
  height: 100%;
}

.el-timeline {
  padding: 20px;
}
</style> 