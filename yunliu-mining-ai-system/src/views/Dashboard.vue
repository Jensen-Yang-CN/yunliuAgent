<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <el-col :span="6" v-for="card in cards" :key="card.title">
        <el-card class="data-card" :body-style="{ padding: '20px' }">
          <div class="card-content">
            <el-icon class="card-icon" :class="card.color">
              <component :is="card.icon" />
            </el-icon>
            <div class="card-info">
              <div class="card-title">{{ card.title }}</div>
              <div class="card-value">{{ card.value }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="chart-row">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>设备运行状态</span>
            </div>
          </template>
          <div ref="deviceChart" class="chart"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>告警统计</span>
            </div>
          </template>
          <div ref="alarmChart" class="chart"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'
import {
  Monitor,
  VideoCamera,
  Warning,
  Connection
} from '@element-plus/icons-vue'

const cards = [
  {
    title: '在线设备',
    value: '42台',
    icon: 'Monitor',
    color: 'success'
  },
  {
    title: '视频分析任务',
    value: '12个',
    icon: 'VideoCamera',
    color: 'primary'
  },
  {
    title: '今日告警',
    value: '5次',
    icon: 'Warning',
    color: 'danger'
  },
  {
    title: '无人机巡检',
    value: '3次',
    icon: 'Connection',
    color: 'warning'
  }
]

const deviceChart = ref(null)
const alarmChart = ref(null)

onMounted(() => {
  const deviceChartInstance = echarts.init(deviceChart.value)
  deviceChartInstance.setOption({
    tooltip: {
      trigger: 'item'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [
      {
        name: '设备状态',
        type: 'pie',
        radius: '50%',
        data: [
          { value: 35, name: '正常运行' },
          { value: 5, name: '警告状态' },
          { value: 2, name: '故障停机' }
        ],
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  })

  const alarmChartInstance = echarts.init(alarmChart.value)
  alarmChartInstance.setOption({
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        data: [3, 5, 2, 7, 4, 1, 5],
        type: 'line',
        smooth: true
      }
    ]
  })
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
  
}

.data-card {
  margin-bottom: 20px;
}

.card-content {
  display: flex;
  align-items: center;
}

.card-icon {
  font-size: 48px;
  margin-right: 20px;
}

.success {
  color: #67c23a;
}

.primary {
  color: #409eff;
}

.danger {
  color: #f56c6c;
}

.warning {
  color: #e6a23c;
}

.card-info {
  flex-grow: 1;
}

.card-title {
  font-size: 14px;
  color: #909399;
}

.card-value {
  font-size: 24px;
  font-weight: bold;
  margin-top: 5px;
}

.chart-row {
  margin-top: 20px;
}

.chart {
  height: 300px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style> 