"""
智能体API路由 - 处理前端的对话请求
"""
import logging
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import asyncio
import os
import sys
import urllib.request
import urllib.parse

# --- Robust imports to handle Python path issues in different execution environments ---
CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
APP_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))  # .../app
BACKEND_ROOT = os.path.abspath(os.path.join(APP_DIR, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

try:
    from app.llm_agent import init_agent as init_online_agent
    from app.tools import (
        helmet_detection_tool, ai_image_generation_tool, vlm_video_analysis_tool,
        HELMET_DETECTION_TOOL_DEFINITION, AI_IMAGE_GENERATION_TOOL_DEFINITION,
        VLM_START_TOOL_DEFINITION, VLM_STOP_TOOL_DEFINITION
    )
except ImportError as e:
    logging.critical(f"CRITICAL: Could not import modules via standard path. This should not happen. Error: {e}")
    # As a last resort, this might indicate a severe path issue. The robust import in the original file was a workaround.
    # For this final version, we rely on the corrected sys.path.
    raise


logger = logging.getLogger(__name__)

# --- Agent Setup 检查设置的环境变量 ONLINE_AGENT 是否为 "1"。 ---
ONLINE_AGENT = os.getenv("ONLINE_AGENT", "0") == "1"

# --- 离线智能体(Fallback) 兜底策略，在线模式（LLMAgent）位于MultiDetection-backend\app\llm_agent.py---
class OfflineAgent:
    def __init__(self):
        self.model = "offline"
        self.tools = [
            HELMET_DETECTION_TOOL_DEFINITION,
            AI_IMAGE_GENERATION_TOOL_DEFINITION,
            VLM_START_TOOL_DEFINITION,
            VLM_STOP_TOOL_DEFINITION
        ]
        self.conversation_history = []
# 第 53-61 行：chat() 方法的核心——用关键词判断意图
    async def chat(self, user_message: str, use_tools: bool = True) -> Dict[str, Any]:
        msg = user_message or ""
        self.conversation_history.append({"role": "user", "content": msg})
        lower = msg.lower()
        is_helmet = ("安全帽" in msg) or ("检测" in msg) or ("helmet" in lower)
        is_image = ("生成" in msg and ("图" in msg or "图片" in msg)) or ("image" in lower)
        is_vlm_start = ("启动" in msg) and (("大模型视频" in msg) or ("视频分析" in msg) or ("vlm" in lower))
        is_vlm_stop  = ("停止" in msg) and (("大模型视频" in msg) or ("视频分析" in msg) or ("vlm" in lower))

        decision_trace = [{"type": "user_message", "detail": msg}]

        if is_vlm_start:
            # ... (VLM start logic)
            return self._handle_vlm_start(decision_trace)

        if is_vlm_stop:
            # ... (VLM stop logic)
            return self._handle_vlm_stop(decision_trace)

        if is_helmet:
            # ... (Helmet detection logic)
            return self._handle_helmet_detection(decision_trace)

        if is_image:
            # ... (Image generation logic)
            return self._handle_image_generation(msg, decision_trace)

        info = "无法识别意图。请明确说明要进行‘安全帽检测’、‘大模型视频分析’或‘生成图片’。"
        decision_trace.append({"type": "final_response", "detail": info})
        return {"message": info, "tool_calls": [], "tool_results": [], "decision_trace": decision_trace}

    def _handle_vlm_start(self, decision_trace):
        decision_trace.append({"type": "llm_decision", "detail": "离线模式：调用 vlm_start_video_analysis"})
        res = vlm_video_analysis_tool.start()
        decision_trace.append({"type": "tool_execution", "detail": "已调用 /start_video_analysis", "tool_results": [res]})
        final_msg = "已启动大模型视频推理" if res.get("success") else f"启动失败: {res.get('error')}"
        decision_trace.append({"type": "final_response", "detail": final_msg})
        return {"message": final_msg, "tool_calls": [{"name": "vlm_start_video_analysis"}], "tool_results": [{"content": json.dumps(res)}], "decision_trace": decision_trace}

    def _handle_vlm_stop(self, decision_trace):
        decision_trace.append({"type": "llm_decision", "detail": "离线模式：调用 vlm_stop_video_analysis"})
        res = vlm_video_analysis_tool.stop()
        decision_trace.append({"type": "tool_execution", "detail": "已调用 /stop_video_analysis", "tool_results": [res]})
        final_msg = "已停止大模型视频推理" if res.get("success") else f"停止失败: {res.get('error')}"
        decision_trace.append({"type": "final_response", "detail": final_msg})
        return {"message": final_msg, "tool_calls": [{"name": "vlm_stop_video_analysis"}], "tool_results": [{"content": json.dumps(res)}], "decision_trace": decision_trace}
# 匹配到哪个关键词就走哪个 _handle_xxx 方法。以安全帽检测为例，会发现每个 _handle_xxx 的结构完全一致：记录决策 → 执行工具 → 生成回复，这就是决策轨迹的四步标准化
    def _handle_helmet_detection(self, decision_trace):
        decision_trace.append({"type": "llm_decision", "detail": "离线模式：调用 detect_helmet"})
        res = helmet_detection_tool.detect_from_file()
        decision_trace.append({"type": "tool_execution", "detail": "已执行 detect_helmet", "tool_results": [res]})
        summary = res.get("summary", {})
        persons = summary.get("total_persons", 0)
        helmets = summary.get("total_helmets", 0)
        without = summary.get("persons_without_helmet", max(0, persons - helmets))
        used_file = res.get("used_file_path") or res.get("file")
        final_msg = f"已完成安全帽检测。视频: {used_file}。发现人员: {persons}，安全帽: {helmets}，未戴: {without}."
        decision_trace.append({"type": "final_response", "detail": final_msg})
        return {"message": final_msg, "tool_calls": [{"name": "detect_helmet"}], "tool_results": [{"content": json.dumps(res)}], "decision_trace": decision_trace}

    def _handle_image_generation(self, msg, decision_trace):
        decision_trace.append({"type": "llm_decision", "detail": "离线模式：调用 generate_image"})
        res = ai_image_generation_tool.generate_image(prompt=msg)
        decision_trace.append({"type": "tool_execution", "detail": "已执行 generate_image", "tool_results": [res]})
        final_msg = f"图片生成工具(占位符)已调用。 {res.get('message')}"
        decision_trace.append({"type": "final_response", "detail": final_msg})
        return {"message": final_msg, "tool_calls": [{"name": "generate_image"}], "tool_results": [{"content": json.dumps(res)}], "decision_trace": decision_trace}

    def clear_history(self):
        self.conversation_history = []

    def get_history(self) -> List[Dict[str, Any]]:
        return self.conversation_history

# --- Agent Initialization ---
agent_offline = OfflineAgent()
agent_online = None
if ONLINE_AGENT:
    try:
        agent_online = init_online_agent(api_key=os.getenv("DASHSCOPE_API_KEY"), model="qwen-plus")
        agent_online.register_tool(HELMET_DETECTION_TOOL_DEFINITION, helmet_detection_tool.detect_from_file)#安全帽检测
        agent_online.register_tool(VLM_START_TOOL_DEFINITION, vlm_video_analysis_tool.start)#启动视频分析
        agent_online.register_tool(VLM_STOP_TOOL_DEFINITION, vlm_video_analysis_tool.stop)#停止视频分析
        agent_online.register_tool(AI_IMAGE_GENERATION_TOOL_DEFINITION, ai_image_generation_tool.generate_image)#AI图片生成
        logger.info("Online LLM agent initialized and tools registered.")
    except Exception as e:
        logger.error(f"Init online agent failed: {e}")
        agent_online = None

router = APIRouter()

# --- API Models and Endpoints ---
class ChatRequest(BaseModel):
    message: str
#这是返回给前端的统一数据结构，和你前端 AgentChat.vue 里 data.message、data.tool_calls、data.tool_results、data.decision_trace 四个字段一一对应：
class ChatResponse(BaseModel):
    message: str                                   # 自然语言最终回复
    tool_calls: List[Dict[str, Any]] = []          # 调用了哪些工具
    tool_results: List[Dict[str, Any]] = []        # 工具返回的 JSON 结果
    decision_trace: List[Dict[str, Any]] = []      # 四步决策轨迹

#前面的if 管"启动前选谁"，下面的try-except 管"运行中挂了怎么办"。
@router.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        logger.info(f"Received chat request: {request.message}")
         # 第一层：主动选择 —— 用三元表达式决定用哪个 agent
        active_agent = agent_online if ONLINE_AGENT and agent_online else agent_offline
        result = await active_agent.chat(request.message)
        return ChatResponse(**result)
    except Exception as e:
          # 第二层：运行时保险 —— 在线挂了自动切离线
        logger.error(f"Chat endpoint error, trying offline fallback. Error: {repr(e)}")
        try:
            result = await agent_offline.chat(request.message)
            return ChatResponse(**result)
        except Exception as fe:
            # 第三层：兜底也挂了 —— 至少返回一个能看的错误消息
            logger.error(f"Fallback also failed: {repr(fe)}")
            err_msg = f"在线和离线模式均执行失败: {fe}"
            return ChatResponse(message=err_msg, decision_trace=[{"type": "final_response", "detail": err_msg}])
#LLM 的工具 schema 是英文的（detect_helmet），但前端用户看到的是中文名
@router.get("/tools")
async def get_tools() -> Dict[str, Any]:
    active_agent = agent_online if ONLINE_AGENT and agent_online else agent_offline
    tools_display: List[Dict[str, Any]] = []
    tool_names = {t["function"]["name"] for t in active_agent.tools}
# 遍历当前活跃 agent 的工具，做中英文映射
    if "detect_helmet" in tool_names:
        tools_display.append({"name": "detect_helmet", "title": "安全帽检测", "description": "检测视频或图片中的安全帽与人员..."})
    if "vlm_start_video_analysis" in tool_names:
        tools_display.append({"name": "vlm_video_analysis", "title": "大模型视频分析", "description": "控制视频推理流程..."})
    if "generate_image" in tool_names:
        tools_display.append({"name": "generate_image", "title": "AI图片生成 (占位符)", "description": "调用一个占位符图片生成工具。"})
#前端"查看工具"弹窗里显示的"安全帽检测""大模型视频分析"就是这里返回的。
    return {"tools": tools_display, "count": len(tools_display)}

@router.post("/clear_history")
async def clear_history() -> Dict[str, str]:
    try:
        active_agent = agent_online if ONLINE_AGENT and agent_online else agent_offline
        active_agent.clear_history()
        logger.info(f"History cleared for {'online' if ONLINE_AGENT and agent_online else 'offline'} agent.")
        return {"message": "对话历史已成功清除"}
    except Exception as e:
        logger.error(f"Error in clear_history endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ... (other endpoints like /history, /status, /ws/chat can be updated similarly)
