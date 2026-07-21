# main_server.py
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import asyncio
import logging
from fastapi.middleware.cors import CORSMiddleware
from torch.distributed.nn.jit import templates

# 从 VLMAnalysis 子模块导入必要的类和配置
from VLMAnalysis.video_server import processor, archiver, AlertService # 假设这些实例在 video_server.py 中创建和导出
from VLMAnalysis.config import ServerConfig, VIDEO_SOURCE, LOG_CONFIG, ARCHIVE_DIR, VLM_ANALYSIS_DIR, VIDEO_WARNING_DIR # Added VLM_ANALYSIS_DIR and VIDEO_WARNING_DIR

# 配置日志记录 (与 video_server.py 保持一致，或考虑集中管理)
# LOG_CONFIG['handlers'][0]['filename'] is now an absolute path from config.py
logging.basicConfig(
    level=LOG_CONFIG['level'],
    format=LOG_CONFIG['format'],
    handlers=[logging.FileHandler(LOG_CONFIG['handlers'][0]['filename'], encoding='utf-8'), logging.StreamHandler()]
)

app = FastAPI(title="智能视频监控系统 - 主服务")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# VLM_ANALYSIS_DIR and VIDEO_WARNING_DIR are now absolute paths from config.py
# 获取 VLMAnalysis 目录的绝对路径，用于模板和静态文件
# vlm_analysis_dir = os.path.join(os.path.dirname(__file__), 'VLMAnalysis') # No longer needed

# 配置静态文件服务
# video_warning_dir = os.path.join(vlm_analysis_dir, "video_warning") # No longer needed
if not os.path.exists(VIDEO_WARNING_DIR):
    os.makedirs(VIDEO_WARNING_DIR)
app.mount("/video_warning", StaticFiles(directory=VIDEO_WARNING_DIR), name="video_warning")


@app.on_event("startup")
async def startup():
    # 确保 processor 已经初始化并且其 start_processing 方法可用
    # if hasattr(processor, 'start_processing') and callable(processor.start_processing):
    #     asyncio.create_task(processor.start_processing())
    # else:
    #     logging.error("VideoProcessor not initialized correctly or start_processing method is missing.")
    logging.info("Application startup complete. Video processing will not start automatically.")

@app.post("/start_video_analysis")
async def start_video_analysis():
    if hasattr(processor, 'start_processing') and callable(processor.start_processing):
        if not processor.is_running(): # Add a method to check if already running
            asyncio.create_task(processor.start_processing())
            logging.info("Video analysis process started by API call.")
            return {"message": "Video analysis started."}
        else:
            logging.info("Video analysis is already running.")
            return {"message": "Video analysis is already running."}
    else:
        logging.error("VideoProcessor not initialized correctly or start_processing method is missing.")
        return {"message": "Failed to start video analysis."}

@app.post("/stop_video_analysis")
async def stop_video_analysis():
    if hasattr(processor, 'stop_processing') and callable(processor.stop_processing):
        await processor.stop_processing() # Ensure this is an async method or call it appropriately
        logging.info("Video analysis process stopped by API call.")
        return {"message": "Video analysis stopped."}
    else:
        logging.error("VideoProcessor not initialized correctly or stop_processing method is missing.")
        return {"message": "Failed to stop video analysis."}

@app.websocket("/alerts")
async def alert_websocket(websocket: WebSocket):
    await AlertService.register(websocket)
    try:
        while True:
            await websocket.receive_text()  # 维持连接
    except WebSocketDisconnect:
        logging.info(f"Client disconnected from alerts: {websocket.client}")
    except Exception as e:
        logging.error(f"Alerts WebSocket error: {e}")
    finally:
        AlertService._connections.remove(websocket) # 确保断开连接时移除

@app.websocket("/video_feed")
async def video_feed(websocket: WebSocket):
    try:
        await websocket.accept()
        processor.start_push_queue = 1
        await processor.video_streamer(websocket)
    except WebSocketDisconnect:
        logging.info(f"Client disconnected from video feed: {websocket.client}")
        processor.start_push_queue = 0
        processor.frame_queue = asyncio.Queue() # 重置队列
    except Exception as e:
        logging.error(f"Video feed WebSocket error: {e}")
        processor.start_push_queue = 0
        processor.frame_queue = asyncio.Queue() # 重置队列
    finally:
        # 确保在任何情况下都清理状态
        processor.start_push_queue = 0
        if hasattr(processor, 'frame_queue') and isinstance(processor.frame_queue, asyncio.Queue):
             # 清空队列以释放可能等待的putter
            while not processor.frame_queue.empty():
                try:
                    processor.frame_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
        else:
            processor.frame_queue = asyncio.Queue()

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "video_source": VIDEO_SOURCE})

# 此处可以为大模型视频分析模块添加新的HTTP接口
# 例如: /analyze_video (POST请求，接收视频文件或URL，返回分析结果)

if __name__ == "__main__":
    # 确保 ARCHIVE_DIR 存在
    # Construct archive_path using VLM_ANALYSIS_DIR and ARCHIVE_DIR from config.py
    archive_path = os.path.join(VLM_ANALYSIS_DIR, ARCHIVE_DIR)
    if not os.path.exists(archive_path):
        os.makedirs(archive_path)
        logging.info(f"Created archive directory: {archive_path}")

    uvicorn.run(
        app="main_server:app", # 指向当前文件中的 app 实例
        host=ServerConfig.HOST,
        port=ServerConfig.PORT,
        reload=ServerConfig.RELOAD,
        workers=ServerConfig.WORKERS
    )