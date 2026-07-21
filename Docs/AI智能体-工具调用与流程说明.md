# AI 智能体 - 工具调用与流程说明

本文档说明项目中“AI 智能体”是如何将业务能力封装为“工具（Tool）”，以及智能体如何基于自然语言自动选择并调用这些工具，最终把结果以“决策轨迹 + 结果”展示在前端对话界面。

---

## 1. 智能体能做什么

本项目中，智能体目前集成了两类能力，均以“工具”的形式对外暴露：

1) 安全帽检测（detect_helmet）
- 检测视频/图片中的安全帽与人员。
- 如果用户未提供 `file_path`，后端会自动从 `MultiDetection-backend/output_parts` 目录选择第一个 MP4 作为输入。
- 完成后返回统计摘要（人数/安全帽数/未戴数）与详细检测结果；并自动启动“实时预览”（占用通道 7）在对话页内嵌显示逐帧画面。

2) 大模型视频分析（VLM）（vlm_start_video_analysis / vlm_stop_video_analysis）
- 控制 YunliuAIVideo 聚合服务，启动/停止大模型视频推理流程。
- 仅做控制，不负责展示。视频分析可视化页面位于前端的 `VideoAnalysis.vue`。

> 说明：原“AI生成图片”工具目前不在“查看工具”列表中展示，但保留在代码中。

---

## 2. 相关文件与职责

后端（MultiDetection-backend）：
- `app/api/endpoints/agent.py`
  - 智能体对话入口：`POST /api/agent/chat`
  - 友好工具列表：`GET /api/agent/tools`（已做中文映射：安全帽检测 / 大模型视频分析）
  - 离线兜底：当 LLM 不可用或强调离线时，通过关键词识别直接调用工具（“安全帽/检测/helmet”“启动/停止 + 大模型视频/视频分析/VLM”）
  - 在“安全帽检测”结束后，内部将预览通道 7 绑定到本次检测文件，返回 `preview_stream_url`，前端对话页自动显示流

- `app/tools.py`
  - `HelmetDetectionTool.detect_from_file(file_path?, confidence_threshold=0.5)`
    - 未传 file_path：默认目录选第一个 MP4
    - 返回摘要 + 详细检测
  - `VLMVideoAnalysisTool.start()/stop()`
    - 调用 YunliuAIVideo 的 `16532` 端口接口
  - 工具定义（OpenAI 兼容格式）：`HELMET_DETECTION_TOOL_DEFINITION`、`VLM_START_TOOL_DEFINITION`、`VLM_STOP_TOOL_DEFINITION`

- `app/api/endpoints/video.py`
  - 多通道检测与推流（MJPEG）
  - `GET /api/video/video_stream/{channel_id}` 用于 `<img>` 直接展示逐帧画面
  - `POST /api/video/stop_stream/{channel_id}` 用于停止某通道流
  - （智能体预览在 7 号通道绑定文件，前端对话页显示）

前端（yunliu-mining-ai-system）：
- `src/views/AgentChat.vue`
  - 对话发送/接收、显示“工具调用/工具结果/决策轨迹”
  - 自动提取 `preview_stream_url` 显示为“实时预览”
  - “查看工具”弹窗做了中文名映射：
    - 安全帽检测 / 大模型视频分析

- 其它页面（保持原有能力，不影响智能体）
  - `VideoGrid.vue`：8 路检测页面
  - `ObjectDetection.vue`：单路检测
  - `VideoAnalysis.vue`：大模型视频分析可视化

---

## 3. 工具是如何封装的

每个“工具”包括两部分：
- 工具定义（OpenAI 兼容 schema）：告诉 LLM 这个工具叫啥、能干啥、需要哪些参数。
- 工具实现（Python 函数/方法）：智能体实际调用的可执行逻辑。

以“安全帽检测”为例（省略部分代码）：
```python
# tools.py
HELMET_DETECTION_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "detect_helmet",
        "description": "检测视频或图片中的安全帽和人员。未提供file_path时将自动从默认目录选择第一个MP4。",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "可选"},
                "confidence_threshold": {"type": "number", "default": 0.5}
            }
        }
    }
}

class HelmetDetectionTool:
    def detect_from_file(self, file_path: Optional[str] = None, confidence_threshold: float = 0.5) -> Dict[str, Any]:
        # file_path 为空时，从默认目录选择第一个 .mp4
        # 用 OpenCV 读取帧，YOLO 推理，绘制结果并返回摘要与详细结构
        ...
```

“大模型视频分析（VLM）”控制工具：
```python
VLM_START_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "vlm_start_video_analysis",
        "description": "启动大模型视频推理（调用 YunliuAIVideo 的 /start_video_analysis）。",
        "parameters": {"type": "object", "properties": {}}
    }
}

class VLMVideoAnalysisTool:
    def start(self) -> Dict[str, Any]:
        return self._post_json("/start_video_analysis")
    def stop(self) -> Dict[str, Any]:
        return self._post_json("/stop_video_analysis")
```

---

## 4. 智能体如何调用工具

### 4.1 在线路径（LLM 可用时的标准函数调用）
> 注：目前启用“离线兜底”，可在此基础上恢复在线 LLM。

- 后端将对话历史与工具目录（tools definitions）发送给 LLM（OpenAI 兼容接口）。
- LLM 判断意图并返回 `tool_calls`（例如调用 `detect_helmet` 并给出 JSON 字符串参数）。
- 后端执行该工具实现函数，将结果以 `role: tool` 消息回补给 LLM，并再次请求让 LLM产出最终自然语言回答。
- 最终返回给前端：
  - message（自然语言）
  - tool_calls（调用了哪些工具）
  - tool_results（工具返回）
  - decision_trace（可观察到的“决策轨迹”）

### 4.2 离线兜底（当前默认稳定路径）
- 若 LLM 不可用或网络异常，智能体通过关键词判断意图：
  - “安全帽/检测/helmet”→ 调 `detect_helmet`
  - “启动 大模型视频/视频分析/VLM”→ 调 `vlm_start_video_analysis`
  - “停止 大模型视频/视频分析/VLM”→ 调 `vlm_stop_video_analysis`
- 同时生成 `decision_trace`，让前端可视化显示“用户 → 决策 → 工具执行 → 最终回答”的过程。

---

## 5. 决策轨迹（Decision Trace）

为了提升可解释性，前端不展示模型内部“思维链”，而是展示“可观察的决策过程”：
- user_message：用户输入
- llm_decision：模型（或离线兜底）决定调用哪个工具
- tool_execution：执行工具并得到结果（JSON）
- final_response：最终输出的自然语言回答

前端 `AgentChat.vue` 使用时间线组件逐项展示，工具结果 JSON 可折叠查看；若工具结果包含 `preview_stream_url`，则显示“实时预览”按钮/画面。

---

## 6. 运行流程（以“安全帽检测 + 实时预览”为例）

1) 前端输入：“帮我检测工地视频中的安全帽情况”
2) 后端智能体：
   - 离线兜底判断意图 → 调用 `detect_helmet`
   - 检测完成后，**进程内**将“预览通道 7”绑定到检测文件
   - 返回 `preview_stream_url` = `/api/video/video_stream/7`
3) 前端显示：
   - 决策轨迹（包含工具调用与结果）
   - “实时预览”区内嵌 `<img src=".../video_stream/7">` 显示 MJPEG 流

---

## 7. 常见问题与建议

- 工具列表显示英文名？
  - 已在 `GET /api/agent/tools` 做了友好映射：显示“安全帽检测”“大模型视频分析”。

- 预览流地址不显示？
  - 展开本条消息的工具结果，确认是否含 `preview_stream_url`
  - 新开标签直接访问该 URL，是否有 MJPEG 流
  - 检查后端 `video.py` 是否将 7 号通道绑定成功（`video_paths[7]`）

- 需要“停止预览”按钮？
  - 可在前端调用 `POST /api/video/stop_stream/7`，我可以在对话页加一个按钮一键调用。

---

## 8. 快速索引（涉及文件）

- 智能体入口：`MultiDetection-backend/app/api/endpoints/agent.py`
  - 聊天接口、离线兜底、预览通道绑定、工具列表映射
- 工具实现：`MultiDetection-backend/app/tools.py`
  - `HelmetDetectionTool`、`VLMVideoAnalysisTool` 及工具定义
- 多路检测/推流：`MultiDetection-backend/app/api/endpoints/video.py`
  - 上传/推流/停止流，通道管理（已扩为 8 路）
- 智能体对话页：`yunliu-mining-ai-system/src/views/AgentChat.vue`
  - 决策轨迹展示、工具结果展示、实时预览（通道 7）
- VLM 服务：`YunliuAIVideo/server.py`、`main_server.py`、`VLMAnalysis/*`

---

## 9. 结语

本项目将“安全帽检测”“大模型视频分析”能力，用“工具”的抽象统一对外，智能体在自然语言指令驱动下，自动决定调用并编排这两类工具；同时提供“离线兜底”与“决策轨迹”，保证功能稳定可用、过程清晰可见。在当前基础上，随时可接入在线 LLM 以恢复“智能化选择 + 连续工具调用”的完整闭环。
