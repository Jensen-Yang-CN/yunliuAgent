"""
LLM Agent（在线模式，千问 OpenAI 兼容接口）

用途：作为“在线智能体”的实现，被 agent.py 通过开关（ONLINE_AGENT=1）启用。
- 依赖：openai>=1.0
- 环境变量：
  - DASHSCOPE_API_KEY = sk-xxxxx
  - 可选：模型名称，默认 qwen-plus
- 兼容：函数调用（tools）与多轮工具执行

注意：
- 本文件不包含任何具体业务工具逻辑。工具定义/处理函数由外部注册（register_tool）。
- 为保证与千问兼容，messages/assistant.tool_calls 的结构已规范化；tool role 消息 content 为字符串。
"""
from __future__ import annotations

import os
import json
import logging
from typing import Dict, Any, List, Optional, Callable

from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMAgent:
    """在线 LLM 智能体（千问）"""

    def __init__(self, api_key: Optional[str] = None, model: str = "qwen-plus", base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY 未配置，请设置环境变量或传入 api_key。")
        self.model = model
        self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"

        # OpenAI 兼容客户端（指向千问网关）
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        # 已注册工具：[{type:function, function:{name, description, parameters}}]
        self.tools: List[Dict[str, Any]] = []
        # 工具处理函数：name -> callable(**kwargs)
        self.tool_handlers: Dict[str, Callable[..., Any]] = {}
        # 对话历史（原始缓存，调用前会规范化）
        self.conversation_history: List[Dict[str, Any]] = []

        logger.info(f"LLMAgent(online) initialized with model={self.model}")

    # ---------------------- 工具注册 ----------------------
    def register_tool(self, tool_definition: Dict[str, Any], handler: Callable[..., Any]) -> None:
        name = tool_definition["function"]["name"]
        self.tools.append(tool_definition)
        self.tool_handlers[name] = handler
        logger.info(f"Tool registered: {name}")

    # ---------------------- 对话入口 ----------------------
    async def chat(self, user_message: str, use_tools: bool = True) -> Dict[str, Any]:
        # 记录用户输入
        self.conversation_history.append({"role": "user", "content": user_message})

        decision_trace: List[Dict[str, Any]] = [
            {"type": "user_message", "detail": user_message}
        ]

        # 第一次请求 LLM
        response = await self._call_llm(use_tools=use_tools)
        if response.get("tool_calls"):
            decision_trace.append({
                "type": "llm_decision",
                "detail": f"模型决定调用 {len(response['tool_calls'])} 个工具",
                "tool_calls": response["tool_calls"],
            })

        # 循环执行工具，直到模型不再请求工具
        while response.get("tool_calls"):
            tool_calls = response["tool_calls"]

            # 将 assistant 工具调用消息写入历史（OpenAI 兼容结构）
            self._append_assistant_message_with_tools(tool_calls, content=response.get("content"))

            # 执行工具
            tool_results = await self._execute_tool_calls(tool_calls)
            decision_trace.append({
                "type": "tool_execution",
                "detail": "已执行工具并获取结果",
                "tool_results": [json.loads(tr["content"]) if isinstance(tr.get("content"), str) else tr.get("content") for tr in tool_results]
            })

            # 将工具结果写入历史
            for tr in tool_results:
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tr["tool_call_id"],
                    "content": tr["content"],  # 字符串
                })

            # 再次请求 LLM 获取最终自然语言回复
            response = await self._call_llm(use_tools=False)

        # 写入最终 assistant 文本消息
        self.conversation_history.append({
            "role": "assistant",
            "content": response.get("content", "")
        })
        decision_trace.append({"type": "final_response", "detail": response.get("content", "")})

        return {
            "message": response.get("content", ""),
            "tool_calls": response.get("tool_calls", []),
            "tool_results": response.get("tool_results", []),
            "decision_trace": decision_trace,
        }

    # ---------------------- LLM 调用 ----------------------
    async def _call_llm(self, use_tools: bool = True) -> Dict[str, Any]:
        """调用千问接口（OpenAI 兼容），返回 {content, tool_calls}。"""
        # 规范化历史消息为 OpenAI 兼容结构
        messages = self._normalize_messages(self.conversation_history)
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if use_tools and self.tools:
            kwargs["tools"] = self.tools

        # 调试：打印请求消息（可注释）
        try:
            logger.debug("LLM request messages: %s", json.dumps(messages, ensure_ascii=False))
        except Exception:
            pass

        completion = self.client.chat.completions.create(**kwargs)

        # 解析响应
        result = {"content": "", "tool_calls": []}
        if completion.choices:
            choice = completion.choices[0]
            msg = choice.message
            if msg.content:
                result["content"] = msg.content
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                # 将 OpenAI tool_calls 转成通用结构 {id, name, arguments(dict)}
                tool_calls = []
                for tc in msg.tool_calls:
                    name = getattr(tc.function, "name", None)
                    args_str = getattr(tc.function, "arguments", "{}")
                    try:
                        args = json.loads(args_str) if isinstance(args_str, str) else (args_str or {})
                    except Exception:
                        args = {}
                    tool_calls.append({
                        "id": tc.id,
                        "name": name,
                        "arguments": args
                    })
                result["tool_calls"] = tool_calls

        logger.info(f"LLM response: content len={len(result.get('content',''))}, tool_calls={len(result.get('tool_calls', []))}")
        return result

    # ---------------------- 执行工具 ----------------------
    async def _execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for tc in tool_calls:
            name = tc.get("name")
            tc_id = tc.get("id")
            args = tc.get("arguments", {})
            try:
                handler = self.tool_handlers.get(name)
                if not handler:
                    raise RuntimeError(f"Unknown tool: {name}")

                # 同步/异步皆可
                if callable(handler):
                    import inspect
                    if inspect.iscoroutinefunction(handler):
                        out = await handler(**args)
                    else:
                        out = handler(**args)
                else:
                    raise RuntimeError(f"Tool handler not callable: {name}")

                results.append({
                    "tool_call_id": tc_id,
                    "content": json.dumps(out, ensure_ascii=False)
                })
                logger.info(f"Tool executed: {name}")
            except Exception as e:
                results.append({
                    "tool_call_id": tc_id,
                    "content": json.dumps({"error": str(e), "tool": name}, ensure_ascii=False)
                })
                logger.error(f"Tool '{name}' failed: {e}")
        return results

    # ---------------------- 历史规范化与消息写入 ----------------------
    def _normalize_messages(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        for m in history:
            role = m.get("role")
            content = m.get("content")
            normalized: Dict[str, Any] = {"role": role}
            if isinstance(content, str):
                normalized["content"] = content
            else:
                normalized["content"] = content if content is not None else ""

            # 兼容 assistant.tool_calls
            if role == "assistant" and m.get("tool_calls"):
                tc_out = []
                for tc in m.get("tool_calls", []):
                    if tc and isinstance(tc, dict) and tc.get("function") and tc.get("type") == "function":
                        # 已是 OpenAI 结构；确保 arguments 为字符串
                        fn = tc["function"]
                        args = fn.get("arguments", "{}")
                        if not isinstance(args, str):
                            args = json.dumps(args, ensure_ascii=False)
                        tc_out.append({
                            "id": tc.get("id"),
                            "type": "function",
                            "function": {"name": fn.get("name"), "arguments": args}
                        })
                    else:
                        # 紧凑结构 → OpenAI 结构
                        args_obj = tc.get("arguments") if isinstance(tc.get("arguments"), (dict, list)) else {}
                        tc_out.append({
                            "id": tc.get("id"),
                            "type": "function",
                            "function": {"name": tc.get("name"), "arguments": json.dumps(args_obj, ensure_ascii=False)}
                        })
                # 某些兼容服务要求 assistant 有 tool_calls 时 content 设为空串
                normalized["content"] = ""
                normalized["tool_calls"] = tc_out

            # 兼容 tool 消息
            if role == "tool":
                normalized = {
                    "role": "tool",
                    "tool_call_id": m.get("tool_call_id"),
                    "content": m.get("content", "")
                }

            messages.append(normalized)
        return messages

    def _append_assistant_message_with_tools(self, tool_calls: List[Dict[str, Any]], content: Optional[str] = None) -> None:
        # 将工具调用写为 OpenAI 兼容结构
        tc_list = []
        for tc in tool_calls:
            args = tc.get("arguments", {})
            tc_list.append({
                "id": tc.get("id"),
                "type": "function",
                "function": {
                    "name": tc.get("name"),
                    "arguments": json.dumps(args, ensure_ascii=False)
                }
            })
        self.conversation_history.append({
            "role": "assistant",
            "content": content or "",
            "tool_calls": tc_list,
        })

    # ---------------------- 历史管理 ----------------------
    def clear_history(self) -> None:
        self.conversation_history = []

    def get_history(self) -> List[Dict[str, Any]]:
        return self.conversation_history


# 全局实例管理（供外部按需初始化/复用）
_agent_instance: Optional[LLMAgent] = None


def get_agent() -> LLMAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = LLMAgent()
    return _agent_instance


def init_agent(api_key: Optional[str] = None, model: str = "qwen-plus") -> LLMAgent:
    global _agent_instance
    _agent_instance = LLMAgent(api_key=api_key, model=model)
    return _agent_instance

