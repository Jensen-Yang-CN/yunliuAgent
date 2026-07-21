from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
import os
import tempfile
import uuid
import logging
import asyncio
import time
import threading
import base64
import json
from typing import Dict, List, Optional, Any
import uvicorn

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)

# 存储WebSocket连接
active_connections: Dict[str, WebSocket] = {}

# 存储正在处理的视频任务
video_tasks: Dict[str, Dict[str, Any]] = {}

# YOLOv11模型路径 - 请根据实际路径修改
MODEL_DIR = "E:\CodeBase_YangJunJie\yunliuAgent\yunliu-aivideo-zsl\Models"
YOLO_MODEL_PATH = os.path.join(MODEL_DIR, "best.pt")

# 确保模型目录存在
if not os.path.exists(MODEL_DIR):
    try:
        os.makedirs(MODEL_DIR)
        logger.info(f"创建模型目录: {MODEL_DIR}")
    except Exception as e:
        logger.error(f"创建模型目录失败: {str(e)}")

# 检查模型文件是否存在
if not os.path.exists(YOLO_MODEL_PATH):
    logger.warning(f"YOLOv11模型文件不存在: {YOLO_MODEL_PATH}")
    logger.warning("将使用模拟检测模式")
    USE_MOCK_DETECTION = True
else:
    USE_MOCK_DETECTION = False
    try:
        # 尝试导入YOLO相关库
        import torch
        from ultralytics import YOLO

        # 加载YOLOv11模型
        logger.info(f"加载YOLOv11模型: {YOLO_MODEL_PATH}")
        yolo_model = YOLO(YOLO_MODEL_PATH)
        logger.info("YOLOv11模型加载成功")
    except ImportError as e:
        logger.error(f"导入YOLO相关库失败: {e}")
        logger.warning("将使用模拟检测模式")
        USE_MOCK_DETECTION = True
    except Exception as e:
        logger.error(f"加载YOLOv11模型失败: {e}")
        logger.warning("将使用模拟检测模式")
        USE_MOCK_DETECTION = True


def process_frame_with_yolo(frame):
    """使用YOLOv11模型处理帧"""
    if USE_MOCK_DETECTION:
        # 模拟检测模式 - 随机绘制边界框
        height, width = frame.shape[:2]

        # 随机生成1-3个检测框
        num_detections = np.random.randint(1, 4)

        for _ in range(num_detections):
            # 随机生成检测框位置和大小
            x = np.random.randint(0, width - 100)
            y = np.random.randint(0, height - 100)
            w = np.random.randint(50, 100)
            h = np.random.randint(50, 100)

            # 随机决定是否戴安全帽 (70%概率戴安全帽)
            has_helmet = np.random.random() < 0.7

            # 根据是否戴安全帽设置颜色和标签
            if has_helmet:
                color = (0, 255, 0)  # 绿色 - 戴安全帽
                label = "Helmet"
            else:
                color = (0, 0, 255)  # 红色 - 未戴安全帽
                label = "No Helmet"

            # 绘制边界框
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

            # 添加标签
            cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        return frame
    else:
        # 使用实际的YOLOv11模型进行检测
        try:
            # 执行推理
            results = yolo_model(frame)

            # 在原始帧上绘制检测结果
            annotated_frame = results[0].plot()

            return annotated_frame
        except Exception as e:
            logger.error(f"YOLOv11处理帧失败: {e}")
            # 出错时返回原始帧
            return frame


async def process_video(session_id: str, video_path: str):
    """处理视频并通过WebSocket发送结果"""
    try:
        # 打开视频文件
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"无法打开视频: {video_path}")
            await active_connections[session_id].send_json({
                "type": "error",
                "message": "无法打开视频文件"
            })
            return

        # 获取视频信息
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        logger.info(f"视频信息: {width}x{height}, {fps}fps, {frame_count}帧")

        # 通知客户端视频处理开始
        await active_connections[session_id].send_json({
            "type": "start",
            "videoInfo": {
                "width": width,
                "height": height,
                "fps": fps,
                "frameCount": frame_count
            }
        })

        # 处理每一帧
        frame_index = 0
        start_time = time.time()

        while True:
            # 读取一帧
            ret, frame = cap.read()
            if not ret:
                break

            # 处理帧
            processed_frame = process_frame_with_yolo(frame)

            # 将帧编码为JPEG
            _, buffer = cv2.imencode('.jpg', processed_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])

            # 将帧转换为base64
            frame_base64 = base64.b64encode(buffer).decode('utf-8')

            # 通过WebSocket发送帧
            await active_connections[session_id].send_json({
                "type": "frame",
                "frameIndex": frame_index,
                "frameData": frame_base64
            })

            # 更新进度
            if frame_index % 10 == 0:  # 每10帧更新一次进度
                progress = min(100, int((frame_index / frame_count) * 100))
                await active_connections[session_id].send_json({
                    "type": "progress",
                    "progress": progress
                })

            # 控制发送速率，模拟实时处理
            frame_index += 1
            elapsed = time.time() - start_time
            expected_time = frame_index / fps

            if elapsed < expected_time:
                await asyncio.sleep(expected_time - elapsed)

        # 通知客户端处理完成
        await active_connections[session_id].send_json({
            "type": "complete",
            "message": "视频处理完成",
            "totalFrames": frame_index
        })

        # 释放资源
        cap.release()

    except Exception as e:
        logger.error(f"处理视频失败: {str(e)}", exc_info=True)
        if session_id in active_connections:
            await active_connections[session_id].send_json({
                "type": "error",
                "message": f"处理视频失败: {str(e)}"
            })
    finally:
        # 从任务列表中移除
        if session_id in video_tasks:
            del video_tasks[session_id]


@app.websocket("/ws/video")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接处理"""
    # 生成会话ID
    session_id = str(uuid.uuid4())

    try:
        # 接受WebSocket连接
        await websocket.accept()
        logger.info(f"WebSocket连接已建立: {session_id}")

        # 存储连接
        active_connections[session_id] = websocket

        # 发送会话ID给客户端
        await websocket.send_json({
            "type": "connection",
            "session_id": session_id
        })

        # 保持连接，等待客户端关闭
        while True:
            # 接收消息
            try:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    logger.info(f"收到WebSocket消息: {message}")

                    # 处理ping消息
                    if message.get("type") == "ping":
                        logger.debug(f"收到ping消息，发送pong响应")
                        await websocket.send_json({
                            "type": "pong",
                            "time": time.time(),
                            "session_id": session_id
                        })
                except json.JSONDecodeError:
                    logger.warning(f"收到无效的JSON消息: {data}")
            except WebSocketDisconnect:
                logger.info(f"WebSocket连接已关闭: {session_id}")
                break
            except Exception as e:
                logger.error(f"处理WebSocket消息时出错: {str(e)}")
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket连接已关闭: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket连接处理失败: {str(e)}", exc_info=True)
    finally:
        # 移除连接
        if session_id in active_connections:
            del active_connections[session_id]
            logger.info(f"已移除WebSocket连接: {session_id}")

        # 取消正在处理的任务
        if session_id in video_tasks:
            # 这里可以添加取消任务的逻辑
            del video_tasks[session_id]
            logger.info(f"已取消视频处理任务: {session_id}")


@app.post("/upload")
async def upload_video(video: UploadFile = File(...), request: Request = None):
    """处理视频上传并开始处理"""
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    logger.info(f"创建临时目录: {temp_dir}")

    try:
        # 尝试从多个来源获取会话ID
        session_id = None

        # 检查是否有表单数据
        form = await request.form()
        logger.debug(f"收到表单数据: {form}")

        if "session_id" in form:
            session_id = form["session_id"]
            logger.info(f"从表单数据获取会话ID: {session_id}")

        # 如果表单中没有，检查查询参数
        if not session_id:
            query_params = request.query_params
            logger.debug(f"查询参数: {query_params}")
            if "session_id" in query_params:
                session_id = query_params["session_id"]
                logger.info(f"从查询参数获取会话ID: {session_id}")

        # 记录所有请求头，可能有助于调试
        headers = request.headers
        logger.debug(f"请求头: {headers}")

        # 检查会话ID
        logger.info(f"最终会话ID: {session_id}")

        if not session_id:
            logger.warning("未提供会话ID")
            return JSONResponse(
                content={"error": "未提供会话ID，请先建立WebSocket连接"},
                status_code=400
            )

        if session_id not in active_connections:
            logger.warning(f"无效的会话ID: {session_id}，当前活动连接: {list(active_connections.keys())}")
            # 如果没有活动连接，可能是WebSocket断开了，尝试使用任何可用的连接
            if active_connections:
                # 使用第一个可用的连接
                available_session = list(active_connections.keys())[0]
                logger.info(f"使用可用的会话ID: {available_session}")
                session_id = available_session
            else:
                return JSONResponse(
                    content={"error": "无效的会话ID，请先建立WebSocket连接"},
                    status_code=400
                )

        # 记录上传的文件信息
        logger.info(f"接收到文件: {video.filename}, 类型: {video.content_type}")

        # 检查文件名
        if not video.filename:
            logger.warning("上传的文件没有文件名")
            return JSONResponse(
                content={"error": "上传的文件没有文件名"},
                status_code=400
            )

        # 获取文件扩展名
        file_ext = os.path.splitext(video.filename)[1] if '.' in video.filename else '.mp4'

        # 生成唯一的文件名
        unique_filename = f"video_{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(temp_dir, unique_filename)

        # 读取上传的文件内容
        content = await video.read()
        content_size = len(content)
        logger.info(f"文件内容大小: {content_size} 字节")

        # 检查文件大小
        if content_size == 0:
            logger.warning("上传的文件为空")
            return JSONResponse(
                content={"error": "上传的文件为空"},
                status_code=400
            )

        # 保存文件
        with open(file_path, "wb") as f:
            f.write(content)

        # 验证文件是否成功保存
        saved_size = os.path.getsize(file_path)
        logger.info(f"保存的文件大小: {saved_size} 字节")

        if saved_size != content_size:
            logger.warning(f"文件大小不匹配: 接收 {content_size} 字节, 保存 {saved_size} 字节")

        # 启动异步任务处理视频
        task = asyncio.create_task(process_video(session_id, file_path))

        # 存储任务信息
        video_tasks[session_id] = {
            "task": task,
            "file_path": file_path,
            "start_time": time.time()
        }

        # 返回成功响应
        return JSONResponse(
            content={
                "success": True,
                "message": "文件上传成功，开始处理视频",
                "session_id": session_id
            }
        )

    except Exception as e:
        logger.error(f"处理上传失败: {str(e)}", exc_info=True)
        return JSONResponse(
            content={"error": f"处理失败: {str(e)}"},
            status_code=500
        )




if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("安全帽检测服务启动中...")
    print("=" * 50)

    if USE_MOCK_DETECTION:
        print("\n警告: 未找到YOLOv11模型或相关库，将使用模拟检测模式")
    else:
        print("\nYOLOv11模型加载成功")



    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="debug"
    )