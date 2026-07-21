<template>
  <div class="agent-chat-container">
    <el-card class="chat-card">
      <template #header>
        <div class="card-header">
          <span class="title">
            <el-icon><ChatDotRound /></el-icon>
            AI智能体对话
          </span>
          <div class="header-actions">
            <el-button 
              link 
              type="primary" 
              @click="clearHistory"
              :loading="clearingHistory">
              清除历史
            </el-button>
            <el-button 
              link 
              type="primary" 
              @click="showToolsList">
              查看工具
            </el-button>
            <el-button 
              link 
              :type="isConnected ? 'success' : 'danger'"
              @click="toggleConnection">
              {{ isConnected ? '已连接' : '未连接' }}
            </el-button>
          </div>
        </div>
      </template>

      <!-- 对话区域 -->
      <div class="chat-messages" ref="messagesContainer">
        <div 
          v-for="(msg, index) in messages" 
          :key="index"
          :class="['message', msg.role]">
          
          <!-- 用户消息 -->
          <div v-if="msg.role === 'user'" class="message-content">
            <el-avatar :size="32" icon="User" />
            <div class="message-text">
              <p>{{ msg.content }}</p>
            </div>
          </div>

          <!-- 助手消息 -->
          <div v-else-if="msg.role === 'assistant'" class="message-content">
            <el-avatar :size="32" icon="ChatDotRound" />
            <div class="message-text">
              <p v-if="msg.content">{{ msg.content }}</p>
              
              <!-- 工具调用信息 -->
              <div v-if="msg.toolCalls && msg.toolCalls.length > 0" class="tool-calls">
                <el-collapse>
                  <el-collapse-item 
                    v-for="(toolCall, idx) in msg.toolCalls"
                    :key="idx"
                    :title="`🔧 工具调用: ${toolCall.name}`">
                    <div class="tool-call-details">
                      <p><strong>工具名称:</strong> {{ toolCall.name }}</p>
                      <p><strong>参数:</strong></p>
                      <pre>{{ JSON.stringify(toolCall.arguments, null, 2) }}</pre>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>

              <!-- 工具结果 -->
              <div v-if="msg.toolResults && msg.toolResults.length > 0" class="tool-results">
                <el-collapse>
                  <el-collapse-item 
                    v-for="(result, idx) in msg.toolResults"
                    :key="idx"
                    title="📊 工具执行结果">
                    <div class="tool-result-details">
                      <pre>{{ JSON.stringify(JSON.parse(result.content), null, 2) }}</pre>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>

              <!-- 预览流操作与展示（当工具结果里包含 preview_stream_url 时显示） -->
              <div v-if="getPreviewUrlsFromMsg(msg).length" class="preview-actions">
                <el-button size="small" type="success" @click="togglePreview(index)">
                  {{ previewOpen[index] ? '隐藏实时预览' : '显示实时预览' }}
                </el-button>
              </div>

              <div v-if="previewOpen[index] && getPreviewUrlsFromMsg(msg).length" class="preview-streams">
                <div
                  v-for="(url, pidx) in getPreviewUrlsFromMsg(msg)"
                  :key="'pv'+pidx"
                  class="preview-item"
                >
                  <div class="preview-title">实时预览</div>
                  <img
                    class="preview-img"
                    :src="url"
                    :alt="'preview-'+pidx"
                  />
                </div>
              </div>

              <!-- 决策轨迹展示 -->
              <div v-if="msg.decisionTrace && msg.decisionTrace.length" class="decision-trace">
                <div class="trace-title">🧭 智能体决策轨迹</div>
                <el-timeline>
                  <el-timeline-item
                    v-for="(step, i) in msg.decisionTrace"
                    :key="i"
                    :timestamp="''"
                    :type="traceType(step.type)">
                    <div class="trace-item">
                      <div class="trace-type">{{ traceLabel(step.type) }}</div>
                      <div class="trace-detail">{{ step.detail }}</div>
                      
                      <!-- 工具调用展示 -->
                      <div v-if="step.tool_calls && step.tool_calls.length" class="trace-tool-calls">
                        <div class="trace-subtitle">工具调用</div>
                        <pre>{{ JSON.stringify(step.tool_calls, null, 2) }}</pre>
                      </div>
                      
                      <!-- 工具结果展示 -->
                      <div v-if="step.tool_results && step.tool_results.length" class="trace-tool-results">
                        <div class="trace-subtitle">工具结果</div>
                        <pre>{{ JSON.stringify(step.tool_results, null, 2) }}</pre>
                      </div>
                    </div>
                  </el-timeline-item>
                </el-timeline>
              </div>
            </div>
          </div>

          <!-- 系统消息 -->
          <div v-else-if="msg.role === 'system'" class="message-content system">
            <el-alert :title="msg.content" type="info" :closable="false" />
          </div>
        </div>

        <!-- 加载指示器 -->
        <div v-if="isLoading" class="message assistant">
          <div class="message-content">
            <el-avatar :size="32" icon="ChatDotRound" />
            <div class="message-text">
              <el-skeleton :rows="3" animated />
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="chat-input-area">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="3"
          placeholder="输入你的问题或指令（支持安全帽检测、AI图片生成等）"
          @keydown.ctrl.enter="sendMessage"
          :disabled="isLoading"
          clearable />
        
        <div class="input-actions">
          <el-checkbox v-model="useTools">
            使用工具
          </el-checkbox>
          <el-button 
            type="primary" 
            @click="sendMessage"
            :loading="isLoading"
            :disabled="!inputMessage.trim() || isLoading">
            <el-icon><Promotion /></el-icon>
            发送
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 工具列表对话框 -->
    <el-dialog 
      v-model="showToolsDialog" 
      title="可用工具列表"
      width="70%">
      <div class="tools-list">
        <el-card 
          v-for="tool in availableTools" 
          :key="tool.name"
          class="tool-card">
          <template #header>
            <div class="tool-header">
              <span class="tool-name">{{ tool.title || tool.name }}</span>
              <el-tag v-if="tool.title==='大模型视频分析'" type="success">VLM</el-tag>
              <el-tag v-else-if="tool.title==='安全帽检测'" type="success">YOLO</el-tag>
            </div>
          </template>
          <p class="tool-description">{{ tool.description }}</p>
          <div class="tool-parameters">
            <p><strong>参数:</strong></p>
            <pre>{{ JSON.stringify(tool.parameters, null, 2) }}</pre>
          </div>
        </el-card>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, Promotion } from '@element-plus/icons-vue'

// 通过Vite代理转发到后端，避免跨域和硬编码主机
const API_BASE_URL = 'http://localhost:8001/api/agent'
// 临时禁用 WebSocket，强制走 HTTP 以快速定位问题
const USE_WS = false

// 决策轨迹标签与样式
const traceLabel = (type) => ({
  user_message: '用户输入',
  llm_decision: '模型决策',
  tool_execution: '工具执行',
  final_response: '最终回复'
}[type] || type)

const traceType = (type) => ({
  user_message: 'primary',
  llm_decision: 'warning',
  tool_execution: 'success',
  final_response: 'info'
}[type] || 'info')

// 解析工具结果中的预览流地址（若存在）
const getPreviewUrl = (result) => {
  try {
    const obj = typeof result?.content === 'string' ? JSON.parse(result.content) : result?.content
    if (obj && obj.preview_stream_url) {
      const sep = obj.preview_stream_url.includes('?') ? '&' : '?'
      return `${obj.preview_stream_url}${sep}t=${Date.now()}`
    }
  } catch (e) {
    // ignore parse error
  }
  return ''
}

const getPreviewUrlsFromMsg = (msg) => {
  const urls = []
  if (!msg?.toolResults) return urls
  for (const r of msg.toolResults) {
    const u = getPreviewUrl(r)
    if (u) urls.push(u)
  }
  return urls
}

const togglePreview = (idx) => {
  previewOpen.value[idx] = !previewOpen.value[idx]
}

// 状态
const messages = ref([])
const inputMessage = ref('')
const isLoading = ref(false)
const isConnected = ref(false)
const useTools = ref(true)
const clearingHistory = ref(false)
const showToolsDialog = ref(false)
const availableTools = ref([])
const messagesContainer = ref(null)
const websocket = ref(null)
// 预览开关（按消息索引控制）
const previewOpen = ref({})

// 初始化
onMounted(() => {
  if (USE_WS) connectWebSocket()
  loadTools()
})

onUnmounted(() => {
  if (websocket.value) {
    websocket.value.close()
  }
})

// WebSocket连接
const connectWebSocket = () => {
  try {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/agent/ws/chat`
    
    websocket.value = new WebSocket(wsUrl)
    
    websocket.value.onopen = () => {
      isConnected.value = true
      ElMessage.success('已连接到AI智能体')
      console.log('WebSocket connected')
    }
    
    websocket.value.onmessage = (event) => {
      const data = JSON.parse(event.data)
      handleWebSocketMessage(data)
    }
    
    websocket.value.onerror = (error) => {
      console.error('WebSocket error:', error)
      ElMessage.error('连接错误')
      isConnected.value = false
    }
    
    websocket.value.onclose = () => {
      isConnected.value = false
      console.log('WebSocket disconnected')
    }
  } catch (error) {
    console.error('Failed to connect WebSocket:', error)
    ElMessage.error('无法连接到服务器')
  }
}

// 处理WebSocket消息
const handleWebSocketMessage = (data) => {
  const { type, message, content, tool_calls, tool_results, error, status } = data
  
  if (type === 'connection') {
    console.log('Connected with session:', data.session_id)
  } else if (type === 'response') {
    isLoading.value = false
    messages.value.push({
      role: 'assistant',
      content: message,
      toolCalls: tool_calls,
      toolResults: tool_results,
      decisionTrace: data.decision_trace || []
    })
    scrollToBottom()
  } else if (type === 'status') {
    if (status === 'processing') {
      messages.value.push({
        role: 'system',
        content: message
      })
    }
  } else if (type === 'error') {
    isLoading.value = false
    ElMessage.error(error || '发生错误')
  }
}

// 发送消息
const sendMessage = async () => {
  if (!inputMessage.value.trim()) {
    return
  }
  
  const userMessage = inputMessage.value
  inputMessage.value = ''
  isLoading.value = true
  
  // 添加用户消息到显示
  messages.value.push({
    role: 'user',
    content: userMessage
  })
  
  scrollToBottom()
  
  try {
    console.log('[AgentChat] Sending via HTTP fallback')
    await sendMessageHTTP(userMessage)
  } catch (error) {
    console.error('Error sending message:', error)
    ElMessage.error('发送消息失败')
    isLoading.value = false
  }
}

// HTTP方式发送消息（备用）
const sendMessageHTTP = async (message) => {
  try {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message: message,
        use_tools: useTools.value
      })
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const data = await response.json()
    isLoading.value = false
    
    messages.value.push({
      role: 'assistant',
      content: data.message,
      toolCalls: data.tool_calls,
      toolResults: data.tool_results,
      decisionTrace: data.decision_trace || []
    })
    
    scrollToBottom()
  } catch (error) {
    console.error('Error in HTTP request:', error)
    ElMessage.error('请求失败')
    isLoading.value = false
  }
}

// 清除历史
const clearHistory = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清除所有对话历史吗？',
      '警告',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    clearingHistory.value = true
    
    const response = await fetch(`${API_BASE_URL}/clear_history`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({})
    })
    
    if (response.ok) {
      messages.value = []
      ElMessage.success('历史已清除')
    }
  } catch (error) {
    if (error.message !== 'cancel') {
      ElMessage.error('清除失败')
    }
  } finally {
    clearingHistory.value = false
  }
}

// 加载工具列表
const loadTools = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/tools`)
    if (response.ok) {
      const data = await response.json()
      availableTools.value = data.tools
    }
  } catch (error) {
    console.error('Failed to load tools:', error)
  }
}

// 显示工具列表
const showToolsList = () => {
  showToolsDialog.value = true
}

// 切换连接
const toggleConnection = () => {
  if (isConnected.value) {
    if (websocket.value) {
      websocket.value.close()
    }
  } else {
    connectWebSocket()
  }
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}
</script>

<style scoped>
.agent-chat-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  /* Allow the container to shrink if needed, crucial for flexbox scrolling */
  min-height: 0;
}

.chat-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: bold;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 20px;
  /* 确保在flex布局中有一个最小高度，以触发滚动 */
  max-height: 600px;
}

.message {
  margin-bottom: 16px;
  display: flex;
  animation: slideIn 0.3s ease-in-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message.user {
  justify-content: flex-end;
}

.message.assistant {
  justify-content: flex-start;
}

.message-content {
  display: flex;
  gap: 12px;
  max-width: 70%;
}

.message.user .message-content {
  flex-direction: row-reverse;
}

.message-text {
  background-color: white;
  padding: 12px 16px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.message.user .message-text {
  background-color: #409eff;
  color: white;
}

.message-text p {
  margin: 0;
  word-break: break-word;
  white-space: pre-wrap;
}

.message-text.system {
  width: 100%;
}

.tool-calls,
.tool-results {
  margin-top: 12px;
}

.tool-call-details,
.tool-result-details {
  padding: 12px;
  background-color: #f5f7fa;
  border-radius: 4px;
}

.tool-call-details p,
.tool-result-details p {
  margin: 8px 0;
}

.tool-call-details pre,
.tool-result-details pre {
  background-color: #fff;
  padding: 8px;
  border-radius: 4px;
  overflow: auto; /* Changed from overflow-x to auto for both directions */
  font-size: 12px;
  max-height: 400px; /* Added max-height to make it scrollable */
  white-space: pre-wrap; /* Ensure long lines wrap */
  word-break: break-all; /* Break long strings */
}

.chat-input-area {
  border-top: 1px solid #dcdfe6;
  padding-top: 16px;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.tools-list {
  max-height: 600px;
  overflow-y: auto;
}

.tool-card {
  margin-bottom: 16px;
}

.tool-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.tool-name {
  font-weight: bold;
  font-size: 16px;
}

.tool-description {
  margin: 8px 0;
  color: #606266;
}

.tool-parameters {
  margin-top: 12px;
}

.tool-parameters pre {
  background-color: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
}
/* 可滚动的工具结果与调用详情 */
.tool-result-details {
  max-height: 320px;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
}

.tool-result-details pre {
  white-space: pre-wrap;
  word-break: break-word;
}

/* 决策轨迹中较大的块也支持滚动展示 */
.trace-tool-results,
.trace-tool-calls {
  max-height: 320px;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
  background-color: #f5f7fa;
  border-radius: 4px;
  padding: 12px;
}

.trace-subtitle {
  font-weight: 600;
  margin-bottom: 8px;
  color: #606266;
}

.decision-trace .el-timeline {
  padding-right: 4px;
}
</style>

