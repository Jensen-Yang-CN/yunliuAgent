"""智能视频监控系统 (2025.02.26版)
核心功能：
1. 实时视频流采集与缓冲 
2. 智能多模态异常检测 
3. 视频分段存储与特征归档 
4. WebSocket实时警报推送 
"""
 
import cv2 
import asyncio 
import json 
import argparse
import os
from datetime import datetime 
from concurrent.futures import ThreadPoolExecutor 
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.websockets import WebSocketState
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from collections import deque 
from typing import Optional, Dict, Any 
import numpy as np 
import logging 
from .direct_analyzer import DirectAnalyzer  # 使用优化后的直接分析器
import time
import uvicorn 
from multiprocessing import set_start_method 
from .config import VideoConfig, ServerConfig, VIDEO_SOURCE, LOG_CONFIG, ARCHIVE_DIR, update_config, VLM_ANALYSIS_DIR # Added VLM_ANALYSIS_DIR

# 配置日志记录
logging.basicConfig(
    level=LOG_CONFIG['level'],
    format=LOG_CONFIG['format'],
    handlers=[logging.FileHandler(LOG_CONFIG['handlers'][0]['filename'], encoding='utf-8'), logging.StreamHandler()]
)

# 解析命令行参数
def parse_args():
    parser = argparse.ArgumentParser(description='智能视频监控系统')
    parser.add_argument('--video_source', type=str, help='视频源路径')
    parser.add_argument('--video_interval', type=int, help='视频分段时长(秒)')
    parser.add_argument('--analysis_interval', type=int, help='分析间隔(秒)')
    parser.add_argument('--buffer_duration', type=int, help='滑窗分析时长')
    parser.add_argument('--ws_retry_interval', type=int, help='WebSocket重连间隔(秒)')
    parser.add_argument('--max_ws_queue', type=int, help='消息队列最大容量')
    parser.add_argument('--jpeg_quality', type=int, help='JPEG压缩质量')
    parser.add_argument('--host', type=str, help='服务器主机地址')
    parser.add_argument('--port', type=int, help='服务器端口')
    parser.add_argument('--reload', type=bool, help='是否启用热重载')
    parser.add_argument('--workers', type=int, help='工作进程数')
    
    args = parser.parse_args()
    return {k: v for k, v in vars(args).items() if v is not None}

# 更新配置
args = parse_args()
update_config(args)




# 初始化视频源
video_source = VIDEO_SOURCE
cap = cv2.VideoCapture(video_source)     # 读取视频

if not cap.isOpened():
    logging.error(f"无法打开视频源: {video_source}")
    # 可以选择抛出异常或退出程序
    exit()

# 尝试读取几帧以获取视频信息
frame = None
for i in range(5):
    ret, temp_frame = cap.read()
    if ret:
        frame = temp_frame
        break # 成功读取一帧即可
    
if frame is None:
    logging.error(f"无法从视频源读取帧: {video_source}. 请检查视频文件是否有效或视频流是否可用.")
    cap.release()
    exit()
    
width = frame.shape[1]
height = frame.shape[0] 
fps = cap.get(cv2.CAP_PROP_FPS)
cv2.destroyAllWindows()
cap.release()
print("fps",fps)

# 视频流处理器 
class VideoProcessor:
    def __init__(self, video_source):
        self.video_source = video_source
        self.cap = cv2.VideoCapture(video_source)
        ret, frame = self.cap.read()
        self.buffer = deque(maxlen=int(fps * VideoConfig.BUFFER_DURATION))
        self.executor = ThreadPoolExecutor()
        self.analyzer = DirectAnalyzer()  # 使用优化后的直接分析器
        self.last_analysis = datetime.now().timestamp() 
        self._running = False 
        self.lock = asyncio.Lock()
        self.frame_queue = asyncio.Queue()  # 添加一个异步队列用于缓存帧
        self.start_push_queue = 0
        self._processing_task = None # To keep track of the processing task
 
    @property 
    def fps(self) -> float:
        return self.cap.get(cv2.CAP_PROP_FPS) or 30.0 
 
    async def video_streamer(self, websocket: WebSocket):
        try:
            while True:
                #start_time = time.monotonic() 
                frame = await self.frame_queue.get()  # 从队列中获取帧
                # 压缩为JPEG格式（调整quality参数控制质量）
                _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), VideoConfig.JPEG_QUALITY])
                
                # 通过WebSocket发送二进制数据
                await websocket.send_bytes(buffer.tobytes())
                #elapsed = time.monotonic()  - start_time
                #await asyncio.sleep(1 / self.fps- elapsed-0.02)  # 发送的数度需要比生产的速度快，根据视频的fps来等待
                #if count%60==0:
                #    print("长度",self.frame_queue.qsize())
        except Exception as e:
            print(f"Error: {e}")
        finally:
            print("停止直播")
    
    async def frame_generator(self):
        """异步视频帧生成器"""
        count = 0
        while self._running:
            start_time = time.monotonic() 
            ret, frame = self.cap.read() 
            count = count + 1
            if not ret:
                logging.info("Video stream ended. Re-opening for loop playback...")
                self.cap.release()
                self.cap = cv2.VideoCapture(self.video_source)
                if not self.cap.isOpened():
                    logging.error(f"Failed to re-open video source for loop: {self.video_source}")
                    self._running = False # Stop processing if re-open fails
                    break
                ret, frame = self.cap.read() # Read the first frame after re-opening
                if not ret:
                    logging.error(f"Failed to read frame after re-opening video source: {self.video_source}")
                    self._running = False # Stop processing if read fails
                    break
                logging.info("Video source re-opened successfully for loop playback.")
            
            # 转换颜色空间并缓冲 
            if frame.dtype != np.uint8:
                frame = frame.astype(np.uint8)
            if len(frame.shape) == 2:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            self.buffer.append({ 
                "frame": frame,
                "timestamp": datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
            })
            
            yield frame 
            
            
            if self.start_push_queue:
                await self.frame_queue.put(frame)  # 将帧放入队列

            # 控制帧生成速度

            elapsed = time.monotonic() - start_time
            await asyncio.sleep(max(0, 1/self.fps - elapsed))  # 控制帧生成速度

        # await self._reconnect() # This reconnect is for stream interruption, not loop
 
    async def _reconnect(self):
        """视频流重连逻辑"""
        await asyncio.sleep(VideoConfig.WS_RETRY_INTERVAL) 
        self.cap.release() 
        self.cap = cv2.VideoCapture(self.video_source)
        ret, frame = self.cap.read()
 
    async def start_processing(self):
        """启动处理流水线"""
        if self._running:
            logging.info("Processing is already running.")
            return
        self._running = True 
        count = 0
        start = time.time()
        # Store the task to be able to cancel it later
        self._processing_task = asyncio.create_task(self._process_frames_loop())
        logging.info("Video processing loop started.")

    async def _process_frames_loop(self):
        """Internal loop for frame generation and analysis triggering."""
        count = 0
        async for frame in self.frame_generator(): 
            asyncio.create_task(archiver.write_frame(frame))
            count = count + 1
            
            # 定时触发分析 
            if (datetime.now().timestamp() - self.last_analysis) >= VideoConfig.ANALYSIS_INTERVAL and count >= fps * VideoConfig.ANALYSIS_INTERVAL:
                print("count", count)
                print("fps * interval",fps * VideoConfig.ANALYSIS_INTERVAL,fps)
                count = 0
                asyncio.create_task(self.trigger_analysis())
                self.last_analysis = datetime.now().timestamp() 
        logging.info("Video processing loop finished.")
           
    async def trigger_analysis(self):
        """触发异步分析"""
        try: 
            async with self.lock:
                clip = list(self.buffer) 
                if not clip:
                    return 
                
                # 记录分析开始时间
                analysis_start = time.time()
                
                # 获取视频帧和时间戳
                frames = [f["frame"] for f in clip]
                timestamps = (clip[0]['timestamp'], clip[-1]['timestamp'])
                
                # 使用优化后的分析器直接分析视频帧
                result = await self.analyzer.analyze(frames, self.fps, timestamps)
                
                # 记录分析耗时
                analysis_time = time.time() - analysis_start
                logging.info(f"视频分析完成，耗时: {analysis_time:.2f}秒")
                
                # 如果检测到异常，立即发送预警
                if result["alert"] != "无异常":
                    logging.warning(f"检测到安全隐患或违章行为，发送预警")
                    # 添加时间戳
                    result["timestamp"] = datetime.now().isoformat()
                    await AlertService.notify(result) 
                else:
                    # 每隔一段时间发送一次正常状态通知
                    current_time = time.time()
                    if not hasattr(self, 'last_normal_notify') or current_time - self.last_normal_notify > 30:
                        self.last_normal_notify = current_time
                        await AlertService.notify({"alert": "无异常", "timestamp": datetime.now().isoformat()})
            
        except Exception as e:
                logging.error(f"分析失败: {str(e)}")
        
    def is_running(self) -> bool:
        """Check if the video processing is currently running."""
        return self._running

    async def stop_processing(self):
        """停止处理流水线"""
        if not self._running:
            logging.info("Processing is not running.")
            return
        self._running = False
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                logging.info("Video processing task was cancelled.")
            finally:
                self._processing_task = None
        # Release video capture resources
        if self.cap.isOpened():
            self.cap.release()
            logging.info("Video capture released.")
        # Clear buffer and queue
        self.buffer.clear()
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        logging.info("Video processing stopped.")

# 警报服务 
class AlertService:
    _connections = set()
    _alert_history = []  # 存储最近的预警信息
    _max_history = 10    # 最大历史记录数

    @classmethod
    async def register(cls, websocket: WebSocket):
        await websocket.accept()
        cls._connections.add(websocket)
        
        # 发送历史预警信息
        if cls._alert_history:
            for alert in cls._alert_history:
                try:
                    await websocket.send_text(alert)
                except Exception as e:
                    logging.warning(f"发送历史预警失败: {str(e)}")

    @classmethod
    async def notify(cls, data: Dict):
        """广播警报信息"""
        # 确保数据包含时间戳
        if "timestamp" not in data:
            data["timestamp"] = datetime.now().isoformat()
            
        # 序列化消息
        message = json.dumps(data)
        
        # 如果是预警信息（非无异常），保存到历史记录
        if data.get("alert") != "无异常":
            cls._alert_history.append(message)
            # 限制历史记录数量
            if len(cls._alert_history) > cls._max_history:
                cls._alert_history = cls._alert_history[-cls._max_history:]

        # 广播消息
        for conn in list(cls._connections):
            try:
                if conn.client_state == WebSocketState.CONNECTED:
                    await conn.send_text(message)
                else:
                    cls._connections.remove(conn)
            except Exception as e:
                logging.warning(f"推送失败: {str(e)}")
                cls._connections.remove(conn)

# 视频存储服务 
class VideoArchiver:
    def __init__(self):
        self.current_writer: Optional[cv2.VideoWriter] = None 
        self.last_split = datetime.now() 
 
    async def write_frame(self, frame: np.ndarray): 
        """异步写入视频帧"""
        if self._should_split():
            self._create_new_file()
 
        if self.current_writer is not None:
            self.current_writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
 
    def _should_split(self) -> bool:
        return (datetime.now() - self.last_split).total_seconds() >= VideoConfig.VIDEO_INTERVAL 
 
    def _create_new_file(self):
        if self.current_writer is not None:
            self.current_writer.release() 
 
        # Construct archive path using VLM_ANALYSIS_DIR and ARCHIVE_DIR
        archive_path = os.path.join(VLM_ANALYSIS_DIR, ARCHIVE_DIR)
        os.makedirs(archive_path, exist_ok=True) # Ensure archive directory exists
        filename = os.path.join(archive_path, f"{datetime.now().strftime('%Y%m%d_%H%M')}.mp4")
        self.current_writer = cv2.VideoWriter(
            filename, 
            cv2.VideoWriter_fourcc(*'mp4v'), 
            fps, 
            (width, height)
        )
        self.last_split = datetime.now() 
 
# 全局实例，供 main_server.py 导入
processor = VideoProcessor(video_source)
archiver = VideoArchiver()

# 移除 FastAPI 应用定义、路由和 uvicorn.run
# 这些功能已移至 ../main_server.py

# 保留命令行示例作为参考
# python ../main_server.py --video_source "./测试视频/小猫开门.mp4"
# python ../main_server.py --video_source "./测试视频/工地施工.mp4"