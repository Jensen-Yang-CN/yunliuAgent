<template>
  <div class="object-detection">
    <el-card class="detection-card">
      <template #header>
        <div class="card-header">
          <span>目标识别检测</span>
          <div class="action-buttons">
            <el-button type="success" @click="startDetection" :disabled="!selectedVideo || isDetecting">开始检测</el-button>
            <el-button type="primary" @click="downloadProcessedVideo" v-if="processedFrames.length > 0">下载处理后的视频</el-button>
            <el-button type="warning" @click="resetAll" v-if="videoUrl || processedFrames.length > 0">重新上传</el-button>
          </div>
        </div>
      </template>
      <div class="detection-container">
        <template v-if="!videoUrl && !isDetecting && !processedFrames.length">
          <el-upload
            class="upload-area"
            action=""
            :auto-upload="false"
            :show-file-list="false"
            accept="video/*"
            @change="handleVideoChange"
            drag>
            <div class="upload-content">
              <el-icon class="video-icon"><VideoCamera /></el-icon>
              <div class="upload-text">
                <span class="main-text">点击或拖拽视频文件到此处</span>
                <span class="sub-text">支持 MP4、AVI、MOV 等常见视频格式</span>
              </div>
            </div>
          </el-upload>
        </template>
        <template v-else-if="videoUrl && !isDetecting && !processedFrames.length">
          <div class="video-wrapper">
            <video 
              ref="videoPlayer" 
              controls 
              :src="videoUrl"
              class="video-player">
            </video>
            <el-button class="reset-button" type="primary" @click="resetVideo">重新上传</el-button>
          </div>
        </template>
        <template v-else-if="processedFrames.length > 0 || isDetecting">
          <div class="video-wrapper">
            <!-- 使用Canvas替代视频标签，用于实时显示处理后的帧 -->
            <canvas ref="videoCanvas" class="video-player"></canvas>
            
            <div class="connection-status" :class="{ 'connected': wsConnected, 'disconnected': !wsConnected }">
              WebSocket: {{ wsConnected ? '已连接' : '未连接' }}
            </div>
            
            <div class="video-playback-error" v-if="hasPlaybackError">
              <div class="error-content">
                <el-icon class="warning-icon"><WarningFilled /></el-icon>
                <p>视频处理出错，请重试</p>
              </div>
            </div>
            
            <div class="video-controls" v-if="processedFrames.length > 0">
              <el-button type="primary" @click="togglePlayback">
                {{ isPlaying ? '暂停' : '播放' }}
              </el-button>
              <el-button type="danger" @click="stopPlayback">停止</el-button>
              <div class="video-stats">
                <span>{{ currentFps }} FPS</span> | 
                <span>帧: {{ currentFrameIndex + 1 }}/{{ totalFrames }}</span>
              </div>
            </div>
            
            <div class="progress-container" v-if="isDetecting">
              <div class="progress-text">处理进度: {{ progressPercent }}%</div>
              <div class="progress-bar-container">
                <div class="progress-bar" :style="{ width: progressPercent + '%' }"></div>
              </div>
            </div>
            
            <el-button class="reset-button" type="warning" @click="resetAll" v-if="!isDetecting">重新上传</el-button>
          </div>
        </template>
        <div class="detection-overlay" v-if="isDetecting && !processedFrames.length">
          <el-icon class="detecting-icon"><Loading /></el-icon>
          <span>正在检测中...</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted, computed } from 'vue'
import { VideoCamera, Loading, WarningFilled } from '@element-plus/icons-vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const videoUrl = ref(null)
const videoPlayer = ref(null)
const videoCanvas = ref(null)
const canvasCtx = ref(null)
const isDetecting = ref(false)
const selectedVideo = ref(null)
const processedVideoUrl = ref(null)
const processedVideoBlob = ref(null)
const processedFileName = ref(null)
const hasPlaybackError = ref(false)

// WebSocket相关
const ws = ref(null)
const wsConnected = ref(false)
const sessionId = ref(null)
const reconnectAttempts = ref(0)
const maxReconnectAttempts = 5
const reconnectInterval = 2000
let pingInterval = null

// 视频播放控制
const processedFrames = ref([])
const currentFrameIndex = ref(0)
const totalFrames = ref(0)
const isPlaying = ref(false)
const playbackSpeed = ref(1.0)
const lastFrameTime = ref(0)
const frameInterval = ref(33) // 默认30fps
let animationFrameId = null

// 进度和FPS计算
const progressPercent = ref(0)
const frameCount = ref(0)
const lastFpsUpdateTime = ref(0)
const currentFps = ref(0)

const detectionForm = ref({
  type: 'person',
  confidence: 80
})

const detectionResults = ref([
  {
    id: 1,
    title: '人员检测',
    content: '检测到3名工作人员',
    time: '2024-03-20 10:40:00',
    type: 'success',
    confidence: 95
  },
  {
    id: 2,
    title: '安全帽检测',
    content: '发现1名工作人员未佩戴安全帽',
    time: '2024-03-20 10:39:00',
    type: 'warning',
    confidence: 88
  },
  {
    id: 3,
    title: '设备检测',
    content: '设备运行状态正常',
    time: '2024-03-20 10:38:00',
    type: 'success',
    confidence: 92
  }
])

// 连接WebSocket
const connectWebSocket = () => {
  if (ws.value) {
    try {
      ws.value.close()
    } catch (e) {
      console.error('关闭旧WebSocket连接失败:', e)
    }
  }
  
  // 根据开发环境或生产环境选择不同的WebSocket URL
  let wsUrl
  
  if (import.meta.env.DEV) {
    // 开发环境：使用与后端相同的端口，但考虑不同的主机名
    // 注意：WebSocket不会通过Vite的代理，所以需要直接连接后端
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    wsUrl = `${wsProtocol}//localhost:16532/ws/video`
  } else {
    // 生产环境：使用相对路径，与当前页面同源
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    wsUrl = `${wsProtocol}//${window.location.host}/ws/video`
  }
  
  console.log('尝试连接WebSocket:', wsUrl)
  console.log('当前页面URL:', window.location.href)
  console.log('开发环境:', import.meta.env.DEV ? '是' : '否')
  
  try {
    ws.value = new WebSocket(wsUrl)
    
    ws.value.onopen = () => {
      console.log('WebSocket连接已建立')
      wsConnected.value = true
      reconnectAttempts.value = 0
      
      // 开始定期发送ping以保持连接
      startPingInterval()
    }
    
    ws.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        
        // 处理不同类型的消息
        switch(data.type) {
          case 'connection':
            sessionId.value = data.session_id
            console.log('会话ID:', sessionId.value)
            break
            
          case 'start':
            // 视频处理开始
            handleVideoStart(data)
            break
            
          case 'frame':
            // 接收处理后的帧
            handleVideoFrame(data)
            break
            
          case 'progress':
            // 更新进度
            progressPercent.value = data.progress
            break
            
          case 'complete':
            // 处理完成
            handleVideoComplete(data)
            break
            
          case 'error':
            // 处理错误
            ElMessage.error('错误: ' + data.message)
            hasPlaybackError.value = true
            break
            
          case 'pong':
            // 收到服务器的pong响应
            break
        }
      } catch (e) {
        console.error('解析WebSocket消息失败:', e)
      }
    }
    
    ws.value.onclose = (event) => {
      console.log('WebSocket连接已关闭, 代码:', event.code, '原因:', event.reason)
      wsConnected.value = false
      
      // 尝试重新连接
      if (reconnectAttempts.value < maxReconnectAttempts) {
        reconnectAttempts.value++
        console.log(`尝试重新连接 (${reconnectAttempts.value}/${maxReconnectAttempts})...`)
        
        setTimeout(connectWebSocket, reconnectInterval)
      } else {
        console.error('达到最大重连次数，放弃重连')
        ElMessage.error('WebSocket连接失败，请刷新页面重试')
      }
    }
    
    ws.value.onerror = (error) => {
      console.error('WebSocket错误:', error)
      wsConnected.value = false
    }
  } catch (e) {
    console.error('创建WebSocket连接失败:', e)
    wsConnected.value = false
  }
}

// 处理视频开始
const handleVideoStart = (data) => {
  // 重置视频播放状态
  resetVideoPlayback()
  
  // 设置画布大小
  if (videoCanvas.value) {
    videoCanvas.value.width = data.videoInfo.width
    videoCanvas.value.height = data.videoInfo.height
    canvasCtx.value = videoCanvas.value.getContext('2d')
  }
  
  // 设置帧率
  frameInterval.value = 1000 / data.videoInfo.fps
  totalFrames.value = data.videoInfo.frameCount
  
  // 显示状态
  ElMessage.info('视频处理开始')
}

// 处理视频帧
const handleVideoFrame = (data) => {
  // 保存帧到缓存
  processedFrames.value.push({
    index: data.frameIndex,
    data: data.frameData
  })
  
  // 如果是第一帧，自动开始播放
  if (processedFrames.value.length === 1 && !isPlaying.value) {
    togglePlayback()
  }
  
  // 计算帧率
  const now = performance.now()
  frameCount.value++
  
  if (now - lastFpsUpdateTime.value > 1000) { // 每秒更新一次FPS
    currentFps.value = Math.round((frameCount.value * 1000) / (now - lastFpsUpdateTime.value))
    frameCount.value = 0
    lastFpsUpdateTime.value = now
  }
}

// 处理视频完成
const handleVideoComplete = (data) => {
  ElMessage.success('视频处理完成')
  progressPercent.value = 100
  isDetecting.value = false
  
  // 更新总帧数
  totalFrames.value = data.totalFrames || processedFrames.value.length
  
  // 如果没有帧数据但处理已完成，可能是出现了错误
  if (processedFrames.value.length === 0) {
    ElMessage.warning('未接收到处理后的视频帧，请重试')
    hasPlaybackError.value = true
    return
  }
  
  // 如果当前不在播放状态，自动开始播放
  if (!isPlaying.value) {
    // 重置到第一帧
    currentFrameIndex.value = 0
    if (processedFrames.value.length > 0) {
      displayFrame(processedFrames.value[0].data)
    }
    
    // 延迟一下再开始播放，确保UI已更新
    setTimeout(() => {
      togglePlayback()
    }, 500)
  }
}

// 定期发送ping以保持连接
const startPingInterval = () => {
  if (pingInterval) {
    clearInterval(pingInterval)
  }
  
  pingInterval = setInterval(() => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type: 'ping', time: Date.now() }))
    }
  }, 30000)
}

// 重置视频播放状态
const resetVideoPlayback = () => {
  // 停止当前播放
  isPlaying.value = false
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }
  
  // 重置变量
  processedFrames.value = []
  currentFrameIndex.value = 0
  totalFrames.value = 0
  lastFrameTime.value = 0
  frameCount.value = 0
  lastFpsUpdateTime.value = 0
  currentFps.value = 0
  
  // 清空画布
  if (canvasCtx.value && videoCanvas.value) {
    canvasCtx.value.clearRect(0, 0, videoCanvas.value.width, videoCanvas.value.height)
  }
}

// 切换播放/暂停
const togglePlayback = () => {
  if (!processedFrames.value.length) return
  
  isPlaying.value = !isPlaying.value
  
  if (isPlaying.value) {
    // 如果已经播放到最后，从头开始
    if (currentFrameIndex.value >= processedFrames.value.length - 1) {
      currentFrameIndex.value = 0
    }
    lastFrameTime.value = performance.now()
    playVideo()
  } else if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }
}

// 停止播放
const stopPlayback = () => {
  isPlaying.value = false
  
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }
  
  // 重置到第一帧
  currentFrameIndex.value = 0
  if (processedFrames.value.length > 0) {
    displayFrame(processedFrames.value[0].data)
  }
}

// 播放视频
const playVideo = () => {
  if (!isPlaying.value) return
  
  const now = performance.now()
  const elapsed = now - lastFrameTime.value
  
  // 根据帧率和播放速度确定是否应该显示下一帧
  if (elapsed >= frameInterval.value / playbackSpeed.value) {
    // 显示当前帧
    if (currentFrameIndex.value < processedFrames.value.length) {
      const frame = processedFrames.value[currentFrameIndex.value]
      displayFrame(frame.data)
      currentFrameIndex.value++
    }
    
    // 如果播放到最后一帧，停止播放或循环
    if (currentFrameIndex.value >= processedFrames.value.length) {
      if (processedFrames.value.length >= totalFrames.value && !isDetecting.value) {
        // 如果已经接收到所有帧，循环播放
        currentFrameIndex.value = 0
      } else if (!isDetecting.value) {
        // 如果不是正在检测中，暂停播放
        isPlaying.value = false
        return
      }
      // 如果正在检测中，等待更多帧
    }
    
    lastFrameTime.value = now
  }
  
  // 请求下一帧动画
  animationFrameId = requestAnimationFrame(playVideo)
}

// 显示帧
const displayFrame = (frameData) => {
  if (!canvasCtx.value || !videoCanvas.value) return
  
  const img = new Image()
  img.onload = function() {
    canvasCtx.value.drawImage(img, 0, 0, videoCanvas.value.width, videoCanvas.value.height)
  }
  img.src = 'data:image/jpeg;base64,' + frameData
}

const handleVideoChange = (file) => {
  const fileName = file.raw.name.toLowerCase()
  if (!fileName.endsWith('.mp4') && !fileName.endsWith('.avi') && !fileName.endsWith('.mov')) {
    ElMessage.warning('请上传 MP4、AVI 或 MOV 格式的视频文件')
    return
  }

  // 释放之前的资源
  if (videoUrl.value) {
    URL.revokeObjectURL(videoUrl.value)
    videoUrl.value = null
  }
  
  // 清理之前的选中视频和处理结果
  selectedVideo.value = null
  resetProcessedVideo()
  
  // 使用克隆方式创建文件对象，避免文件锁定
  const fileReader = new FileReader();
  fileReader.onload = function(e) {
    const blob = new Blob([e.target.result], { type: file.raw.type });
    selectedVideo.value = new File([blob], file.raw.name, { type: file.raw.type });
    videoUrl.value = URL.createObjectURL(blob);
  };
  fileReader.readAsArrayBuffer(file.raw);
}

const resetVideo = () => {
  if (videoUrl.value) {
    URL.revokeObjectURL(videoUrl.value)
    videoUrl.value = null
  }
  selectedVideo.value = null
}

const resetProcessedVideo = () => {
  if (processedVideoUrl.value) {
    URL.revokeObjectURL(processedVideoUrl.value)
    processedVideoUrl.value = null
  }
  processedVideoBlob.value = null
  processedFileName.value = null
  
  // 重置视频播放状态
  resetVideoPlayback()
}

const downloadProcessedVideo = () => {
  if (!processedVideoBlob.value && processedFrames.value.length === 0) {
    ElMessage.warning('没有可下载的处理后视频')
    return
  }
  
  // 如果有处理后的视频blob，直接下载
  if (processedVideoBlob.value) {
    const url = URL.createObjectURL(processedVideoBlob.value)
    const link = document.createElement('a')
    link.href = url
    link.download = processedFileName.value || 'processed_video.mp4'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    
    ElMessage.success('下载已开始')
    return
  }
  
  // 如果只有帧数据，尝试将帧转换为视频
  ElMessage.info('正在准备下载，请稍候...')
  
  // 这里可以添加将帧转换为视频的逻辑
  // 由于浏览器限制，可能需要服务器端支持
  ElMessage.warning('暂不支持直接下载处理后的帧，请使用截图功能')
}

const startDetection = async () => {
  if (!selectedVideo.value) {
    ElMessage.warning('请先上传视频文件')
    return
  }

  // 如果正在处理中，阻止重复请求
  if (isDetecting.value) {
    ElMessage.warning('视频正在处理中，请稍候...')
    return
  }

  // 确保WebSocket已连接
  if (!wsConnected.value || !sessionId.value) {
    ElMessage.warning('WebSocket未连接，正在尝试重新连接...')
    connectWebSocket()
    setTimeout(() => {
      if (wsConnected.value) {
        startDetection()
      } else {
        ElMessage.error('无法连接到WebSocket服务，请刷新页面重试')
      }
    }, 1000)
    return
  }

  try {
    isDetecting.value = true
    progressPercent.value = 0
    
    // 验证文件格式
    const fileName = selectedVideo.value.name.toLowerCase()
    if (!fileName.endsWith('.mp4') && !fileName.endsWith('.avi') && !fileName.endsWith('.mov')) {
      throw new Error('仅支持 MP4、AVI、MOV 格式的视频文件')
    }

    // 清理之前的处理结果
    resetProcessedVideo()

    // 添加随机后缀以避免文件名冲突
    const timestamp = Date.now()
    const randomStr = Math.random().toString(36).substring(2, 8)
    const safeFileName = `video_${timestamp}_${randomStr}.${fileName.split('.').pop()}`
    processedFileName.value = `processed_${safeFileName}`

    // 创建一个新的Blob对象
    const fileArrayBuffer = await selectedVideo.value.arrayBuffer()
    const fileBlob = new Blob([fileArrayBuffer], { type: selectedVideo.value.type })
    
    // 使用FormData上传
    const formData = new FormData()
    formData.append('video', new File([fileBlob], safeFileName, { 
      type: selectedVideo.value.type 
    }))
    formData.append('session_id', sessionId.value)

    ElMessage.info('正在上传视频，请稍候...')

    try {
      // 获取后端URL
      let uploadUrl
      
      if (import.meta.env.DEV) {
        // 开发环境：直接连接后端
        uploadUrl = `http://localhost:16532/upload?session_id=${encodeURIComponent(sessionId.value)}`
      } else {
        // 生产环境：使用相对路径
        uploadUrl = `/upload?session_id=${encodeURIComponent(sessionId.value)}`
      }
      
      console.log('上传URL:', uploadUrl)
      
      // 发送请求
      const response = await fetch(uploadUrl, {
        method: 'POST',
        body: formData,
      })

      // 检查响应状态
      if (!response.ok) {
        // 尝试读取错误信息
        const contentType = response.headers.get('content-type')
        if (contentType && contentType.includes('application/json')) {
          const errorData = await response.json()
          throw new Error(errorData.error || `服务器错误: ${response.status}`)
        } else {
          throw new Error(`服务器错误: ${response.status}`)
        }
      }

      const result = await response.json()
      console.log('上传成功:', result)
      ElMessage.success('视频已上传，开始处理...')

    } catch (error) {
      console.error('视频处理请求失败:', error)
      throw error
    }

  } catch (error) {
    console.error('视频处理错误:', error)
    ElMessage.error(`视频处理失败: ${error.message || '请重试'}`)
    isDetecting.value = false
  }
}

const handleVideoError = (event) => {
  console.error('视频播放错误:', event)
  hasPlaybackError.value = true
  ElMessage.warning('视频无法播放，请尝试下载后查看')
}

// 在组件挂载时连接WebSocket
onMounted(() => {
  connectWebSocket()
  
  // 初始化Canvas上下文
  if (videoCanvas.value) {
    canvasCtx.value = videoCanvas.value.getContext('2d')
  }
})

// 在组件卸载时清理资源
onUnmounted(() => {
  if (videoUrl.value) {
    URL.revokeObjectURL(videoUrl.value)
  }
  if (processedVideoUrl.value) {
    URL.revokeObjectURL(processedVideoUrl.value)
  }
  
  // 关闭WebSocket连接
  if (ws.value) {
    ws.value.close()
  }
  
  // 清除定时器
  if (pingInterval) {
    clearInterval(pingInterval)
  }
  
  // 取消动画帧
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
  }
})

const resetAll = () => {
  // 停止播放
  if (isPlaying.value) {
    isPlaying.value = false
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId)
      animationFrameId = null
    }
  }
  
  // 重置视频
  resetVideo()
  
  // 重置处理后的视频
  resetProcessedVideo()
  
  // 重置其他状态
  isDetecting.value = false
  hasPlaybackError.value = false
  progressPercent.value = 0
  
  // 清空画布
  if (canvasCtx.value && videoCanvas.value) {
    canvasCtx.value.clearRect(0, 0, videoCanvas.value.width, videoCanvas.value.height)
  }
  
  ElMessage.info('已重置，可以上传新视频')
}
</script>

<style scoped>
.object-detection {
  padding: 20px;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
}

.detection-card {
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.action-buttons {
  display: flex;
  gap: 10px;
}

.detection-container {
  position: relative;
  width: 100%;
  min-height: 500px;
}

.upload-area {
  width: 100%;
  height: 500px;
}

.upload-area :deep(.el-upload) {
  width: 100%;
  height: 100%;
}

.upload-area :deep(.el-upload-dragger) {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f5f7fa;
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: #909399;
}

.upload-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: 16px;
}

.main-text {
  font-size: 16px;
  margin-bottom: 8px;
}

.sub-text {
  font-size: 14px;
  color: #909399;
}

.video-icon {
  font-size: 64px;
  color: #409EFF;
}

.video-wrapper {
  width: 100%;
  position: relative;
  overflow: hidden;
}

.video-player {
  width: 100%;
  height: 500px;
  object-fit: contain;
  background-color: #000;
}

.reset-button {
  position: absolute;
  top: 20px;
  right: 20px;
  z-index: 1;
}

.video-controls {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin-top: 15px;
}

.video-stats {
  margin-left: auto;
  font-size: 14px;
  color: #606266;
}

.detection-overlay {
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
  z-index: 2;
}

.detecting-icon {
  font-size: 48px;
  margin-bottom: 20px;
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.video-playback-error {
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  transform: translateY(-50%);
  background-color: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 20px;
  text-align: center;
  z-index: 1;
}

.error-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.warning-icon {
  font-size: 40px;
  color: #E6A23C;
}

.connection-status {
  position: absolute;
  top: 10px;
  left: 10px;
  padding: 5px 10px;
  border-radius: 4px;
  font-size: 12px;
  z-index: 1;
}

.connected {
  background-color: rgba(67, 160, 71, 0.7);
  color: white;
}

.disconnected {
  background-color: rgba(244, 67, 54, 0.7);
  color: white;
}

.progress-container {
  margin-top: 10px;
  margin-bottom: 15px;
}

.progress-text {
  margin-bottom: 5px;
  font-size: 14px;
  text-align: center;
}

.progress-bar-container {
  width: 100%;
  height: 20px;
  background-color: #e9e9e9;
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background-color: #409EFF;
  transition: width 0.3s;
}
</style> 