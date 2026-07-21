
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import uvicorn
import sys
import os
import importlib

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建主FastAPI应用
app = FastAPI()

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 导入main.py中的应用
try:
    logger.info("导入main.py中的应用...")
    # 直接导入main模块
    import lp

    # 将main.py中的所有路由添加到主应用
    for route in lp.app.routes:
        app.routes.append(route)

    logger.info("成功导入lp.py的路由")
    main_imported = True
except Exception as e:
    logger.error(f"导入lp.py失败: {str(e)}")
    main_imported = False

# 导入tt.py中的应用
try:
    logger.info("导入tt.py中的应用...")
    # 直接导入tt模块
    import main_server

    # 将tt.py中的所有路由添加到主应用
    for route in main_server.app.routes:
        # 添加路由到主应用
        app.routes.append(route)

    logger.info("成功导入mian_server.py的路由")
    tt_imported = True
except Exception as e:
    logger.error(f"导入mian_sercer.py失败: {str(e)}")
    tt_imported = False


@app.get("/")
async def root():
    """代理服务器根路由"""
    return {
        "message": "安全帽检测综合服务",
        "status": "运行中",
        "services": {
            "main": main_imported,
            "tt": tt_imported
        }
    }


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("安全帽检测综合服务启动中...")
    print("=" * 50)

    if main_imported:
        print("✓ lp.py服务已集成")
    else:
        print("✗ lp.py服务集成失败")

    if tt_imported:
        print("✓ gao.py服务已集成 (路由前缀: /tt)")
    else:
        print("✗ tgao.py服务集成失败")

    print("\n所有API都可在 http://localhost:8000 访问")
    print("tt.py的API路由: http://localhost:8000/...")
    print("main.py的API路由: http://localhost:8000/...")
    print("=" * 50)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=16532,
        log_level="info"
    )