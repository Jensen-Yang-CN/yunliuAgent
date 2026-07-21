"""
智能体API测试脚本
"""
import asyncio
import json
import sys
from pathlib import Path

# 添加后端路径
BACKEND_DIR = Path(__file__).parent / "MultiDetection-backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.llm_agent import init_agent
from app.tools import (
    helmet_detection_tool,
    ai_image_generation_tool,
    HELMET_DETECTION_TOOL_DEFINITION,
    AI_IMAGE_GENERATION_TOOL_DEFINITION
)


async def test_agent():
    """测试智能体"""
    
    print("\n" + "=" * 60)
    print("  AI智能体API测试")
    print("=" * 60 + "\n")
    
    # 初始化智能体
    print("1. 初始化智能体...")
    agent = init_agent()
    print("✓ 智能体已初始化\n")
    
    # 注册工具
    print("2. 注册工具...")
    agent.register_tool(HELMET_DETECTION_TOOL_DEFINITION, helmet_detection_tool.detect_from_file)
    agent.register_tool(AI_IMAGE_GENERATION_TOOL_DEFINITION, ai_image_generation_tool.generate_image)
    print("✓ 工具已注册\n")
    
    # 显示可用工具
    print("3. 可用工具:")
    for tool in agent.tools:
        tool_func = tool["function"]
        print(f"   - {tool_func['name']}: {tool_func['description']}")
    print()
    
    # 测试对话
    test_cases = [
        {
            "message": "你好，我是一个安全帽检测系统的管理员。请告诉我你能做什么？",
            "description": "测试1: 基本问候"
        },
        {
            "message": "我需要检测一个视频中的安全帽。假设视频路径是/path/to/video.mp4",
            "description": "测试2: 安全帽检测请求"
        },
        {
            "message": "生成一个关于工地安全的宣传图片",
            "description": "测试3: 图片生成请求"
        },
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"4.{i} {test_case['description']}")
        print(f"   用户: {test_case['message']}")
        
        try:
            result = await agent.chat(test_case['message'], use_tools=True)
            
            print(f"   助手: {result['message']}")
            
            if result['tool_calls']:
                print(f"   工具调用: {len(result['tool_calls'])} 个")
                for tool_call in result['tool_calls']:
                    print(f"     - {tool_call['name']}")
            
            if result['tool_results']:
                print(f"   工具结果: {len(result['tool_results'])} 个")
            
            print()
        
        except Exception as e:
            print(f"   ✗ 错误: {str(e)}\n")
    
    # 显示对话历史
    print("5. 对话历史:")
    history = agent.get_history()
    print(f"   总消息数: {len(history)}")
    for i, msg in enumerate(history, 1):
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')[:50]
        print(f"   {i}. [{role}] {content}...")
    
    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60 + "\n")


async def test_tools_directly():
    """直接测试工具"""
    
    print("\n" + "=" * 60)
    print("  工具直接测试")
    print("=" * 60 + "\n")
    
    # 测试安全帽检测工具
    print("1. 测试安全帽检测工具")
    print("   (注: 需要实际的视频/图片文件)")
    
    # 创建一个测试图片
    import cv2
    import numpy as np
    
    test_image_path = "test_image.jpg"
    
    # 创建一个简单的测试图片
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(img, "Test Image", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.imwrite(test_image_path, img)
    
    print(f"   已创建测试图片: {test_image_path}")
    
    try:
        result = helmet_detection_tool.detect_from_file(test_image_path)
        print(f"   结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"   ✗ 错误: {str(e)}")
    
    # 清理测试文件
    import os
    if os.path.exists(test_image_path):
        os.remove(test_image_path)
    
    print()
    
    # 测试AI图片生成工具
    print("2. 测试AI图片生成工具")
    
    try:
        result = ai_image_generation_tool.generate_image(
            prompt="一个工地上的工人戴着安全帽",
            size="1024x1024",
            quality="standard"
        )
        print(f"   结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"   ✗ 错误: {str(e)}")
    
    print("\n" + "=" * 60)
    print("  工具测试完成")
    print("=" * 60 + "\n")


def main():
    """主函数"""
    
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  AI智能体测试脚本".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    
    # 运行异步测试
    asyncio.run(test_agent())
    asyncio.run(test_tools_directly())
    
    print("✓ 所有测试完成")


if __name__ == "__main__":
    main()


