from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .api.endpoints import video, alarm, websocket, agent
from .db import Base, engine, SessionLocal  # 相对导入
from .models import AlarmRecord  # 相对导入
import asyncio
import os  # 导入 os 模块
import shutil  # 导入 shutil 模块用于删除目录

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI()

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境请限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 包含路由
app.include_router(video.router, prefix="/api/video", tags=["video"])
app.include_router(alarm.router, prefix="/api/alarms", tags=["alarms"])
app.include_router(websocket.router, prefix="/api/ws", tags=["websocket"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])

# 在应用启动时启动 WebSocket 报警推送任务并执行清理
@app.on_event("startup")
async def startup_event():
    # 1. 删除本地关键帧文件
    keyframes_dir = os.path.join("app", "static", "keyframes")
    if os.path.exists(keyframes_dir):
        print(f"Deleting keyframes directory: {keyframes_dir}")
        try:
            shutil.rmtree(keyframes_dir) # 删除整个目录及其内容
            print("Keyframes directory deleted successfully.")
        except OSError as e:
            print(f"Error deleting keyframes directory {keyframes_dir}: {e}")
    else:
        print(f"Keyframes directory not found: {keyframes_dir}")


    # 2. 删除数据库中的报警记录
    db = SessionLocal()
    try:
        print("Deleting all alarm records from database...")
        # 删除 AlarmRecord 表中的所有记录
        db.query(AlarmRecord).delete()
        db.commit()
        print("All alarm records deleted successfully.")
    except Exception as e:
        db.rollback() # 如果发生错误，回滚事务
        print(f"Error deleting alarm records: {e}")
    finally:
        db.close() # 关闭数据库会话

    # 启动 WebSocket 报警推送任务
    asyncio.create_task(websocket.periodic_alarm_push())

@app.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI project!"}


