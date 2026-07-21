import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue')
  },
  {
    path: '/device-monitoring',
    name: 'DeviceMonitoring',
    component: () => import('../views/DeviceMonitoring.vue')
  },
  {
    path: '/video-analysis',
    name: 'VideoAnalysis',
    component: () => import('../views/VideoAnalysis.vue')
  },
  {
    path: '/object-detection',
    name: 'ObjectDetection',
    component: () => import('../views/ObjectDetection.vue')
  },
  {
    // path: '/multi-video-detection',
    name: 'MultiVideoDetection',
    children: [
      {
        path: '/detection', 
        name: 'Detection',
        component: () => import('../views/VideoGrid.vue')
      },
      {
        path: '/alarms',
        name: 'MultiVideoHistory',
        component: () => import('../views/AlarmList.vue')
      },
      {
        path: '/keyframes',
        name: 'MultiVideoConfig',
        component: () => import('../views/KeyFrameViewer.vue')
      }
    ]
  },
  {
    path: '/drone-patrol',
    name: 'DronePatrol',
    component: () => import('../views/DronePatrol.vue')
  },
  {
    path: '/agent-chat',
    name: 'AgentChat',
    component: () => import('../views/AgentChat.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router 