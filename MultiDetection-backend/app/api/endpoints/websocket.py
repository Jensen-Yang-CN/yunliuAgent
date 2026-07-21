from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ...db import SessionLocal
from ...crud import create_alarm
# 引入 video.py 中的当前帧 JPEG 数据列表、获取计数函数和视频运行状态列表
from .video import current_frames, get_current_counts, is_video_running  # 相对导入
import asyncio
import datetime
import os
import pytz

router = APIRouter()
active_connections = []  # 维护活跃的 WebSocket 连接列表

def get_beijing_time():
    """获取当前北京时间"""
    tz = pytz.timezone("Asia/Shanghai")  # 设置时区为北京时间
    return datetime.datetime.now(tz)

def save_keyframe(frame_data, channel_id):
    """将当前帧 JPEG 数据保存为文件，包含通道信息"""
    timestamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y%m%d%H%M%S")
    filename = f"channel_{channel_id}_keyframe_{timestamp}.jpg"
    keyframe_dir = os.path.join("app", "static", "keyframes")
    keyframe_path_full = os.path.join(keyframe_dir, filename)
    print(f"Saving keyframe to: {keyframe_path_full}")

    # 创建关键帧目录（如果不存在）
    os.makedirs(keyframe_dir, exist_ok=True)

    # 将当前帧保存为 JPEG 文件
    with open(keyframe_path_full, "wb") as f:
        f.write(frame_data)

    # 返回相对路径，用于前端访问
    return f"/static/keyframes/{filename}"


async def periodic_alarm_push():
    """基于安全帽检测结果推送报警"""
    while True:
        # 遍历当前可用通道数量（与视频模块保持一致）
        for channel_id in range(len(is_video_running)):
            # 检查当前通道的视频流是否正在运行
            if is_video_running[channel_id]: # 添加此检查
                frame_data = current_frames[channel_id] # 获取当前通道的帧数据
                if frame_data:
                    # 获取当前通道的检测结果人数和安全帽数量
                    person_count, helmet_count = get_current_counts(channel_id)

                    if person_count > helmet_count:  # 只在人数多于安全帽数量时报警
                        # 保存关键帧和发送报警
                        keyframe_path = save_keyframe(frame_data, channel_id)

                        # 写入数据库
                        db = SessionLocal()
                        try:
                            create_alarm(
                                db=db,
                                description=f"通道{channel_id + 1}检测到 {person_count - helmet_count} 人未佩戴安全帽",
                                keyframe_path=keyframe_path,
                                channel=channel_id # 存储通道ID
                            )
                        finally:
                            db.close()

                        # 推送报警到所有活跃连接
                        for connection in active_connections:
                            try:
                                await connection.send_json({
                                    "channel": channel_id, # 添加通道ID
                                    "timestamp": get_beijing_time().strftime("%Y年%m月%d日 %H:%M:%S"),
                                    "description": f"通道{channel_id + 1}检测到 {person_count - helmet_count} 人未佩戴安全帽",
                                    "keyframe_path": keyframe_path,
                                })
                            except Exception as e:
                                print(f"Error sending WebSocket message: {e}")
            # else: # 可选：如果视频停止，可以打印一条消息
            #     print(f"Channel {channel_id + 1} video stopped, skipping alarm check.")


        await asyncio.sleep(2)  # 降低检测频率到2秒一次


@router.websocket("/ws/alarms")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 接口用于推送报警"""
    await websocket.accept()
    active_connections.append(websocket)
    print(f"New WebSocket connection: {len(active_connections)} active connections")

    # 如果这是第一个连接，启动报警推送任务
    # 注意：这里需要确保 periodic_alarm_push 只启动一次，无论有多少个websocket连接
    # 可以使用一个标志位来控制
    if len(active_connections) == 1:
         # 检查是否已经有任务在运行，避免重复启动
         # 这是一个简化的例子，更健壮的方式是使用 asyncio.Task 或其他同步原语
         pass # 假设主应用启动时已经创建了 periodic_alarm_push 任务

    try:
        while True:
            # 保持 WebSocket 连接活跃，或者处理接收到的消息（如果需要）
            await websocket.receive_text() # 或者 await asyncio.sleep(1)
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print(f"WebSocket disconnected: {len(active_connections)} active connections")
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            active_connections.remove(websocket)
        except ValueError:
            pass # Connection might have been removed already


# 确保 periodic_alarm_push 在应用启动时运行
# 这部分代码通常放在 main.py 中应用启动事件里
# 例如:
# from fastapi import FastAPI
# from app.api.endpoints import websocket
# import asyncio
#
# app = FastAPI()
#
# @app.on_event("startup")
# async def startup_event():
#     asyncio.create_task(websocket.periodic_alarm_push())
#
# app.include_router(websocket.router)
