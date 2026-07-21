<template>
  <div class="video-analysis">
    <el-row :gutter="24">
      <el-col :xl="16" :lg="15" :md="14" :sm="24" :xs="24">
        <el-card class="video-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><VideoCameraFilled /></el-icon>
              <span class="card-title">实时视频监控</span>
              <div style="margin-left: auto;">
                <el-button type="primary" size="small" @click="startAnalysis" :disabled="isAnalysisRunning">开始分析</el-button>
                <el-button type="danger" size="small" @click="stopAnalysis" :disabled="!isAnalysisRunning">停止分析</el-button>
              </div>
            </div>
          </template>
          <div class="video-player-wrapper">
            <img ref="videoPlayerRef" class="video-player-img" alt="Video Stream" @error="handleVideoError" />
            <div class="video-status-overlay" v-if="!isBackendConnected || isLoadingVideo">
              <div v-if="!isBackendConnected">
                <el-icon class="status-icon"><WarningFilled /></el-icon>
                <p>连接后端服务失败，请检查网络或稍后重试。</p>
              </div>
              <div v-else-if="isLoadingVideo">
                <el-icon class="status-icon is-loading"><Loading /></el-icon>
                <p>正在加载视频流...</p>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :xl="8" :lg="9" :md="10" :sm="24" :xs="24">
        <el-card class="alerts-card" shadow="hover" :body-style="{ padding: '0px' }">
          <template #header>
            <div class="card-header">
              <el-icon><BellFilled /></el-icon>
              <span class="card-title">预警信息</span>
            </div>
          </template>
          <div class="alerts-list-container">
            <el-scrollbar v-if="analysisResults.length > 0">
              <el-timeline class="alerts-timeline">
                <el-timeline-item
                  v-for="(alert, index) in analysisResults"
                  :key="alert.timestamp + '-' + index"
                  :type="getAlertType(alert)"
                  :timestamp="formatDisplayTimestamp(alert.timestamp)"
                  hollow
                  :class="{ 'alert-blink': alert.alert !== '无异常' && alert.is_new_alert }"
                >
                  <div class="alert-item-content" @click="openWarningDetailsModal(alert)">
                    <strong class="alert-type-title">{{ alert.alert_type || (alert.alert === '无异常' ? '状态正常' : '检测到异常') }}</strong>
                    <div class="alert-item-details">
                      <p v-if="alert.warning_json_parsed && alert.warning_json_parsed.safety_hazards && alert.warning_json_parsed.safety_hazards.length > 0">
                        <el-tag type="danger" size="small" effect="dark" style="margin-right: 5px;">隐患</el-tag>
                        {{ alert.warning_json_parsed.safety_hazards.join(', ') }}
                      </p>
                      <p v-if="alert.warning_json_parsed && alert.warning_json_parsed.violations && alert.warning_json_parsed.violations.length > 0">
                        <el-tag type="warning" size="small" effect="dark" style="margin-right: 5px;">违章</el-tag>
                        {{ alert.warning_json_parsed.violations.join(', ') }}
                      </p>
                      <p v-if="alert.warning_json_parsed && alert.warning_json_parsed.warning_message">
                         <el-tag type="info" size="small" style="margin-right: 5px;">信息</el-tag>
                        {{ alert.warning_json_parsed.warning_message }}
                      </p>
                      <div v-if="alert.warning_json_parsed && alert.warning_json_parsed.regulation_codes && alert.warning_json_parsed.regulation_codes.length > 0">
                        <el-tag type="primary" size="small" effect="light" style="margin-right: 5px;">规程</el-tag>
                        <ul class="regulation-list">
                          <li v-for="(code, i) in alert.warning_json_parsed.regulation_codes" :key="code">
                            {{ code }} - {{ alert.warning_json_parsed.regulation_contents[i] }}
                          </li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </el-timeline-item>
              </el-timeline>
            </el-scrollbar>
            <el-empty description="暂无预警信息" v-if="analysisResults.length === 0" style="padding: 20px 0;"></el-empty>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog
      v-model="warningDialogVisible"
      :title="selectedWarning && selectedWarning.alert !== '无异常' ? '预警详情 - 检测到异常' : '预警详情 - 状态正常'"
      width="70%"
      top="5vh"
      custom-class="warning-dialog"
      :before-close="handleCloseDialog"
    >
      <div v-if="selectedWarning" class="dialog-content-wrapper">
        <el-descriptions :column="2" border class="basic-info-desc">
            <template #title>
                <el-icon><InfoFilled /></el-icon> 基本信息
            </template>
            <el-descriptions-item label="检测时间">{{ formatTimestamp(selectedWarning.timestamp) }}</el-descriptions-item>
            <el-descriptions-item label="原始描述">{{ selectedWarning.description }}</el-descriptions-item>
            <el-descriptions-item label="预警类型">
                <el-tag :type="getAlertType(selectedWarning)" effect="dark">
                    {{ selectedWarning.alert_type || (selectedWarning.alert === '无异常' ? '状态正常' : '检测到异常') }}
                </el-tag>
            </el-descriptions-item>
        </el-descriptions>
        
        <div v-if="parsedWarningJson" class="structured-warning-content">
          <el-divider content-position="left">结构化预警内容</el-divider>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="安全隐患" v-if="parsedWarningJson.safety_hazards && parsedWarningJson.safety_hazards.length > 0">
              <el-tag type="danger" v-for="hazard in parsedWarningJson.safety_hazards" :key="hazard" style="margin-right: 5px;">{{ hazard }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="违章行为" v-if="parsedWarningJson.violations && parsedWarningJson.violations.length > 0">
              <el-tag type="warning" v-for="violation in parsedWarningJson.violations" :key="violation" style="margin-right: 5px;">{{ violation }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="预警信息" v-if="parsedWarningJson.warning_message">
              {{ parsedWarningJson.warning_message }}
            </el-descriptions-item>
            <el-descriptions-item label="相关规程" v-if="parsedWarningJson.regulation_codes && parsedWarningJson.regulation_codes.length > 0">
              <ul class="regulation-details-list">
                <li v-for="(code, i) in parsedWarningJson.regulation_codes" :key="code">
                  <strong>{{ code }}:</strong> {{ parsedWarningJson.regulation_contents[i] }}
                </li>
              </ul>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <el-row :gutter="20" style="margin-top: 20px;" v-if="selectedWarning.picture_file_name || selectedWarning.video_file_name">
          <el-col :span="selectedWarning.picture_file_name && selectedWarning.video_file_name ? 12 : 24" v-if="selectedWarning.picture_file_name">
            <el-card shadow="never">
                <template #header><h4>预警截图</h4></template>
                <el-image :src="getWarningMediaUrl(selectedWarning.picture_file_name)" alt="预警截图" fit="contain" style="width: 100%; height: 300px; border-radius: 4px;" :preview-src-list="[getWarningMediaUrl(selectedWarning.picture_file_name)]" :hide-on-click-modal="true" />
            </el-card>
          </el-col>
          <el-col :span="selectedWarning.picture_file_name && selectedWarning.video_file_name ? 12 : 24" v-if="selectedWarning.video_file_name">
             <el-card shadow="never">
                <template #header><h4>预警视频片段</h4></template>
                <video controls :src="getWarningMediaUrl(selectedWarning.video_file_name)" style="width: 100%; border-radius: 4px;">
                  您的浏览器不支持视频播放。
                </video>
            </el-card>
          </el-col>
        </el-row>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="warningDialogVisible = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue';
import { Loading, VideoCameraFilled, BellFilled, WarningFilled, InfoFilled } from '@element-plus/icons-vue';

const videoPlayerRef = ref(null);
const analysisResults = ref([]);
const isBackendConnected = ref(false);
const isLoadingVideo = ref(true);
const warningDialogVisible = ref(false);
const selectedWarning = ref(null);
const isAnalysisRunning = ref(false); // New reactive variable

let videoSocket = null;
let alertSocket = null;
let videoReconnectTimer = null;
let alertReconnectTimer = null;
const maxReconnectAttempts = 5;
let videoReconnectAttempts = 0;
let alertReconnectAttempts = 0;

const VITE_APP_WEBSOCKET_URL = import.meta.env.VITE_APP_WEBSOCKET_URL || 'ws://localhost:16532';
const VITE_APP_HTTP_URL = import.meta.env.VITE_APP_HTTP_URL || 'http://localhost:16532';

const startAnalysis = async () => {
  try {
    const response = await fetch(`${VITE_APP_HTTP_URL}/start_video_analysis`, { method: 'POST' });
    const data = await response.json();
    if (response.ok) {
      console.log('Video analysis started:', data.message);
      isAnalysisRunning.value = true;
      // Optionally, display a success message to the user
    } else {
      console.error('Failed to start video analysis:', data.message);
      // Optionally, display an error message to the user
    }
  } catch (error) {
    console.error('Error starting video analysis:', error);
    // Optionally, display an error message to the user
  }
};

const stopAnalysis = async () => {
  try {
    const response = await fetch(`${VITE_APP_HTTP_URL}/stop_video_analysis`, { method: 'POST' });
    const data = await response.json();
    if (response.ok) {
      console.log('Video analysis stopped:', data.message);
      isAnalysisRunning.value = false;
      // Optionally, display a success message to the user
    } else {
      console.error('Failed to stop video analysis:', data.message);
      // Optionally, display an error message to the user
    }
  } catch (error) {
    console.error('Error stopping video analysis:', error);
    // Optionally, display an error message to the user
  }
};

const connectVideoSocket = () => {
  if (videoSocket && videoSocket.readyState === WebSocket.OPEN) {
    console.log('Video WebSocket is already open.');
    return;
  }
  videoSocket = new WebSocket(`${VITE_APP_WEBSOCKET_URL}/video_feed`);
  isLoadingVideo.value = true;

  videoSocket.onopen = () => {
    console.log('Video WebSocket connection established.');
    isBackendConnected.value = true;
    videoReconnectAttempts = 0; // Reset on successful connection
    if (videoReconnectTimer) clearTimeout(videoReconnectTimer);
  };

  videoSocket.onmessage = (event) => {
    if (videoPlayerRef.value) {
      const url = URL.createObjectURL(event.data);
      videoPlayerRef.value.src = url;
      isLoadingVideo.value = false;
      videoPlayerRef.value.onload = () => {
        URL.revokeObjectURL(url);
      };
    }
  };

  videoSocket.onerror = (error) => {
    console.error('Video WebSocket error:', error);
    // isBackendConnected.value = false; // Keep true if attempting reconnect, or manage based on attempts
    // isLoadingVideo.value = false;
  };

  videoSocket.onclose = () => {
    console.log('Video WebSocket connection closed.');
    isBackendConnected.value = false;
    isLoadingVideo.value = false;
    if (videoReconnectAttempts < maxReconnectAttempts) {
      videoReconnectAttempts++;
      console.log(`Attempting to reconnect video WebSocket (attempt ${videoReconnectAttempts}/${maxReconnectAttempts})...`);
      if (videoReconnectTimer) clearTimeout(videoReconnectTimer);
      videoReconnectTimer = setTimeout(() => {
        connectVideoSocket();
      }, 5000); // Attempt reconnect after 5 seconds
    } else {
      console.error('Max video WebSocket reconnect attempts reached.');
    }
  };
};

const connectAlertSocket = () => {
  if (alertSocket && alertSocket.readyState === WebSocket.OPEN) {
    console.log('Alert WebSocket is already open.');
    return;
  }
  alertSocket = new WebSocket(`${VITE_APP_WEBSOCKET_URL}/alerts`);

  alertSocket.onopen = () => {
    console.log('Alert WebSocket connection established.');
    alertReconnectAttempts = 0; // Reset on successful connection
    if (alertReconnectTimer) clearTimeout(alertReconnectTimer);
  };

  alertSocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      const newAlert = {
        ...data,
        type: data.alert === '无异常' ? 'success' : 'warning',
        warning_json_parsed: data.warning_json ? JSON.parse(data.warning_json) : null,
        is_new_alert: data.alert !== '无异常', // Flag for new non-normal alerts
      };
      analysisResults.value.unshift(newAlert);

      if (newAlert.is_new_alert) {
        // Remove the blinking class after a short delay
        setTimeout(() => {
          const alertInArray = analysisResults.value.find(a => a.timestamp === newAlert.timestamp);
          if (alertInArray) {
            alertInArray.is_new_alert = false;
          }
        }, 6000); // Blink for 6 seconds
      }

      if (analysisResults.value.length > 20) {
        analysisResults.value.pop();
      }
    } catch (e) {
      console.error('Error parsing alert data:', e);
    }
  };

  alertSocket.onerror = (error) => {
    console.error('Alert WebSocket error:', error);
  };

  alertSocket.onclose = () => {
    console.log('Alert WebSocket connection closed.');
    if (alertReconnectAttempts < maxReconnectAttempts) {
      alertReconnectAttempts++;
      console.log(`Attempting to reconnect alert WebSocket (attempt ${alertReconnectAttempts}/${maxReconnectAttempts})...`);
      if (alertReconnectTimer) clearTimeout(alertReconnectTimer);
      alertReconnectTimer = setTimeout(() => {
        connectAlertSocket();
      }, 5000); // Attempt reconnect after 5 seconds
    } else {
      console.error('Max alert WebSocket reconnect attempts reached.');
    }
  };
};

const formatTimestamp = (isoTimestamp) => {
  if (!isoTimestamp) return '';
  const date = new Date(isoTimestamp);
  return date.toLocaleString('zh-CN', { hour12: false });
};

const formatDisplayTimestamp = (isoTimestamp) => {
  if (!isoTimestamp) return '';
  const date = new Date(isoTimestamp);
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
};

const getAlertType = (alert) => {
  if (!alert) return 'info';
  if (alert.alert === '无异常') return 'success';
  // Could be more granular based on alert.alert_type if available
  return 'danger'; 
};

const openWarningDetailsModal = (warning) => {
  if (warning.alert === '无异常' && !warning.warning_json_parsed) { // Allow opening if there's parsed JSON even if 'no abnormality'
      // Potentially show a simpler 'status normal' dialog or just log
      console.log("Status normal, no details to show unless parsed JSON exists.");
      return;
  }
  selectedWarning.value = warning;
  warningDialogVisible.value = true;
  if (warning.is_new_alert) {
      warning.is_new_alert = false; // Mark as seen when opened
  }
};

const handleCloseDialog = () => {
  warningDialogVisible.value = false;
  selectedWarning.value = null;
};

const getWarningMediaUrl = (fileName) => {
  if (!fileName) return '';
  return `${VITE_APP_HTTP_URL}/video_warning/${fileName}`;
};

const parsedWarningJson = computed(() => {
  if (selectedWarning.value && selectedWarning.value.warning_json_parsed) {
    return selectedWarning.value.warning_json_parsed;
  }
  return null;
});

const handleVideoError = (event) => {
  console.error('Video stream error:', event);
  isLoadingVideo.value = false;
  if (videoPlayerRef.value) {
    // videoPlayerRef.value.src = 'path/to/error/placeholder.jpg'; 
  }
};

onMounted(() => {
  if (videoPlayerRef.value) {
     connectVideoSocket();
  }
  connectAlertSocket();
});

onUnmounted(() => {
  if (videoSocket) {
    videoSocket.onclose = null; // Prevent further reconnect attempts
    videoSocket.close();
  }
  if (alertSocket) {
    alertSocket.onclose = null; // Prevent further reconnect attempts
    alertSocket.close();
  }
  if (videoReconnectTimer) clearTimeout(videoReconnectTimer);
  if (alertReconnectTimer) clearTimeout(alertReconnectTimer);
});

</script>

<style scoped>
.video-analysis {
  padding: 20px;
  background-color: #f0f2f5;
  min-height: calc(100vh - 40px);
}

.card-header {
  display: flex;
  align-items: center;
  font-size: 18px;
  font-weight: bold;
  color: #303133;
}

.card-header .el-icon {
  margin-right: 8px;
  font-size: 20px;
}

.video-card, .alerts-card {
  border-radius: 8px;
  margin-bottom: 20px;
}

.video-player-wrapper {
  position: relative;
  width: 100%;
  padding-top: 56.25%; 
  background-color: #000;
  border-radius: 4px;
  overflow: hidden;
}

.video-player-img {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.video-status-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #fff;
  text-align: center;
  padding: 20px;
  border-radius: 4px;
}

.status-icon {
  font-size: 48px;
  margin-bottom: 15px;
}

.status-icon.is-loading {
  animation: rotate 1.5s linear infinite;
}

.alerts-list-container {
  height: calc(100vh - 160px); /* Adjusted based on typical header height */
  min-height: 300px;
  overflow-y: auto;
}

.alerts-timeline {
  padding: 15px;
}

.alert-item-content {
  padding: 12px 15px;
  cursor: pointer;
  border-radius: 6px;
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
  background-color: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 12px;
}

.alert-item-content:hover {
  background-color: #f7f9fc;
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
}

.alert-type-title {
  font-weight: 600; /* Slightly bolder */
  margin-bottom: 8px;
  display: block;
  color: #303133;
  font-size: 15px; /* Slightly larger */
}

.alert-item-details p {
  font-size: 13px; /* Slightly smaller for details */
  color: #555;
  margin-bottom: 6px;
  line-height: 1.6;
  display: flex; /* For aligning tag and text */
  align-items: center; /* For aligning tag and text */
}
.alert-item-details .el-tag {
  flex-shrink: 0; /* Prevent tag from shrinking */
}

.alert-item-details ul.regulation-list {
  font-size: 13px;
  color: #555;
  margin-top: 4px;
  margin-bottom: 0;
  padding-left: 25px; /* Indent under the '规程' tag */
  list-style-type: none; /* Remove default bullets */
}
.alert-item-details ul.regulation-list li {
  margin-bottom: 3px;
  position: relative;
}
.alert-item-details ul.regulation-list li::before {
  content: "●";
  position: absolute;
  left: -15px;
  top: 1px;
  font-size: 10px;
  color: #909399;
}


.el-timeline-item__timestamp {
  font-size: 12px !important; /* Smaller timestamp */
  color: #a0a0a0 !important;
}

/* Blinking animation for new alerts */
.alert-blink .alert-item-content {
  animation: pulse 1.5s infinite; /* Changed to pulse and adjusted duration slightly */
  will-change: box-shadow; /* Hint to the browser for optimization */
}

@keyframes pulse { 
  0% { 
    box-shadow: 0 0 0 0 rgba(244, 67, 54, 0.7); /* Adjusted alpha for better visibility */
  } 
  70% { 
    box-shadow: 0 0 0 10px rgba(244, 67, 54, 0); 
  } 
  100% { 
    box-shadow: 0 0 0 0 rgba(244, 67, 54, 0); 
  } 
}

/* Dialog Styles */
.warning-dialog .el-dialog__header {
    border-bottom: 1px solid #ebeef5;
    padding: 15px 20px;
}
.warning-dialog .el-dialog__title {
    font-size: 18px;
    font-weight: 600;
}

.dialog-content-wrapper {
    max-height: 75vh;
    overflow-y: auto;
    padding: 0 10px; /* Add some padding for scrollbar */
}

.basic-info-desc.el-descriptions {
    margin-bottom: 20px;
}

.basic-info-desc .el-descriptions__title,
.structured-warning-content .el-divider__text {
    font-size: 16px;
    font-weight: 500;
    color: #303133;
    display: flex;
    align-items: center;
}
.basic-info-desc .el-descriptions__title .el-icon {
    margin-right: 6px;
    font-size: 18px;
}

.structured-warning-content .el-descriptions {
    margin-top: 15px;
}

.el-descriptions-item__label {
    font-weight: 500 !important;
}

.regulation-details-list {
    list-style-type: none;
    padding-left: 0;
}
.regulation-details-list li {
    margin-bottom: 8px;
    padding-left: 15px;
    position: relative;
}
.regulation-details-list li::before {
    content: "➢";
    position: absolute;
    left: 0;
    color: #409EFF;
}

.el-dialog__body h4 {
  margin-top: 10px;
  margin-bottom: 8px;
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 768px) {
  .alerts-list-container {
    height: auto;
    max-height: 350px;
  }
  .el-dialog {
    width: 95% !important;
    top: 2vh !important;
  }
  .dialog-content-wrapper {
    max-height: 85vh;
  }
  .el-descriptions {
      font-size: 13px; /* Smaller font for descriptions on mobile */
  }
  .el-descriptions-item__label,
  .el-descriptions-item__content {
      font-size: 13px; /* Smaller font for descriptions on mobile */
  }
}
</style>