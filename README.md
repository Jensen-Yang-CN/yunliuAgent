# 视频检测 AI 智能体系统

基于 YOLO 安全帽检测与 VLM 大模型视频分析能力，构建的 **自然语言驱动的 AI 智能体平台**。用户通过对话即可触发检测、分析任务，智能体自动完成意图理解、工具编排与结果呈现。

## 智能体核心能力

| 能力 | 说明 |
|------|------|
| **自然语言对话** | 支持"帮我检测安全帽""启动大模型视频分析"等自然语言指令，无需记忆命令或参数 |
| **工具自动调用** | 智能体自动识别用户意图，选择合适的工具（安全帽检测 / VLM 视频分析）并执行，无需手动指定 |
| **决策过程可视化** | 以时间线形式透明展示"用户输入 → 意图识别 → 工具调用 → 结果生成"全链路推理过程 |
| **在线 / 离线双模** | 在线模式接入千问 LLM 实现智能推理；离线模式基于关键词匹配独立运行，LLM 不可达时核心功能不受影响 |
| **实时预览** | 检测完成后对话页内嵌 MJPEG 视频流，即时查看检测画面 |

## 系统架构

```
┌──────────────────────────┐
│   AgentChat.vue (前端)    │  ← 用户自然语言对话 + 思维链可视化 + 实时预览
└────────────┬─────────────┘
             │ POST /api/agent/chat
             ▼
┌──────────────────────────┐
│   agent.py (路由分发)     │  ← 在线/离线双模选择 + 运行时自动降级
└────────────┬─────────────┘
             │
    ┌────────┴────────┐
    ▼                 ▼
┌───────────┐   ┌──────────────┐
│llm_agent  │   │ OfflineAgent │
│(千问LLM)  │   │ (关键词匹配)  │
└─────┬─────┘   └──────┬───────┘
      │                 │
      └────────┬────────┘
               ▼
┌──────────────────────────┐
│   tools.py (工具执行)     │  ← OpenAI Function Calling 兼容工具层
├──────────────────────────┤
│ HelmetDetectionTool       │  ← YOLO 安全帽检测
│ VLMVideoAnalysisTool      │  ← 大模型视频推理控制
└──────────────────────────┘
```

## 项目结构

```
├── MultiDetection-backend/          # 后端 (FastAPI)
│   └── app/
│       ├── api/endpoints/
│       │   └── agent.py             # ★ 智能体对话接口、双模切换、降级兜底
│       ├── tools.py                 # ★ 工具定义 (OpenAI Schema) + 工具实现
│       ├── llm_agent.py             # ★ 在线 LLM 智能体 (千问)
│       └── ...
├── yunliu-mining-ai-system/         # 前端 (Vue3 + Element Plus)
│   └── src/views/
│       └── AgentChat.vue            # ★ 对话界面 + 思维链时间线 + 实时预览
├── YunliuAIVideo/                   # VLM 视频分析服务
├── Docs/                            # 详细设计文档
│   ├── 面试准备-智能体模块常见问题.md
│   ├── AI智能体-工具调用与流程说明.md
│   ├── 智能体端到端调用流程详解.md
│   └── 智能体在线与离线模式详解.md
└── start_agent_system.py            # 一键启动脚本
```

## 快速开始

```bash
# 1. 启动后端
cd MultiDetection-backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# 2. 启动前端
cd yunliu-mining-ai-system
npm install
npm run dev

# 3. 访问 http://localhost:5173 → 对话页面
```

**在线模式**（需要千问 API Key）：
```bash
set ONLINE_AGENT=1
set DASHSCOPE_API_KEY=sk-xxxxxxxx
```

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue3 / Element Plus / Axios |
| 后端 | FastAPI / Python |
| 工具协议 | OpenAI Function Calling (兼容) |
| LLM | 千问 (Qwen-Plus) / DashScope API |
| 检测模型 | YOLO / OpenCV |
| 视频流 | MJPEG 多通道推流 |

## 智能体功能清单

- [x] OpenAI 兼容 Function Calling 工具注册与调用框架
- [x] 在线 LLM 驱动 + 离线关键词兜底双模架构
- [x] 运行时自动降级 (在线失败 → 离线接管)
- [x] 思维链式决策轨迹可视化 (四步时间线)
- [x] 工具调用参数与结果可折叠审计
- [x] MJPEG 实时视频流对话页内嵌预览
- [x] 对话历史清除
- [x] 工具列表中文化友好展示
- [ ] SSE / WebSocket 流式响应 (规划中)
- [ ] 多工具串联编排 (Tool Chaining) (规划中)
