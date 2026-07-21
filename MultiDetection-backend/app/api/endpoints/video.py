import cv2
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from ultralytics import YOLO
import numpy as np
import os

router = APIRouter()

# 全局变量，支持8路视频
CHANNELS = 8
video_paths = [None] * CHANNELS
current_frames = [None] * CHANNELS
is_video_running = [False] * CHANNELS
current_person_counts = [0] * CHANNELS  # 添加人数统计
current_helmet_counts = [0] * CHANNELS  # 添加安全帽统计

# 获取当前文件的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
# 构建到模型文件的路径
model_path = os.path.abspath(os.path.join(current_dir, '..', '..', '..', 'models', 'best.pt'))
model = YOLO(model_path)  # 加载YOLO模型

def get_current_counts(channel_id: int):
    """获取指定通道的当前检测到的人数和安全帽数量"""
    if not 0 <= channel_id < CHANNELS:
        return 0, 0 # 或者抛出错误，这里返回0避免异常
    return current_person_counts[channel_id], current_helmet_counts[channel_id]

@router.post("/upload/{channel_id}")
async def upload_video(channel_id: int, file: UploadFile = File(...)):
    """上传视频文件到指定通道"""
    global video_paths
    if not 0 <= channel_id < CHANNELS:
        raise HTTPException(status_code=400, detail="无效的通道ID")
    try:
        # 保存上传的视频文件，文件名包含通道ID
        upload_dir = os.path.join("app", "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        video_paths[channel_id] = os.path.join(upload_dir, f"channel_{channel_id}_{file.filename}")

        with open(video_paths[channel_id], "wb") as buffer:
            buffer.write(await file.read())

        # 重置该通道的计数
        current_person_counts[channel_id] = 0
        current_helmet_counts[channel_id] = 0

        return {"filename": file.filename, "channel": channel_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"视频上传失败：{str(e)}")

def video_stream(channel_id: int):
    """处理指定通道的视频流并进行安全帽检测"""
    global current_frames, is_video_running, video_paths, current_person_counts, current_helmet_counts

    if not 0 <= channel_id < CHANNELS:
         raise HTTPException(status_code=400, detail="无效的通道ID")

    if not video_paths[channel_id]:
        # 如果没有上传视频，可以返回一个空白帧或者错误
        # 这里返回一个简单的提示帧
        blank_frame = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(blank_frame, f"Channel {channel_id + 1}: No video uploaded", (50, 180),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        _, buffer = cv2.imencode('.jpg', blank_frame)
        current_frames[channel_id] = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + current_frames[channel_id] + b'\r\n')
        is_video_running[channel_id] = False
        return # 退出生成器

    is_video_running[channel_id] = True
    cap = cv2.VideoCapture(video_paths[channel_id])

    if not cap.isOpened():
        raise HTTPException(status_code=404, detail=f"通道 {channel_id + 1}: 无法打开视频文件")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            is_video_running[channel_id] = False
            break

        # YOLO检测
        results = model(frame)

        # 处理检测结果
        person_count = 0
        helmet_count = 0

        for result in results:
            boxes = result.boxes

            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])

                if conf > 0.5:  # 置信度阈值
                    x1, y1, x2, y2 = map(int, box.xyxy[0])

                    if cls == 0:  # 安全帽
                        helmet_count += 1
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, "helmet", (x1, y1-10),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                    elif cls == 1:  # 人
                        person_count += 1
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                        cv2.putText(frame, "person", (x1, y1-10),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)

        # 显示检测统计 (Use calculated counts for display)
        cv2.putText(frame, f"Persons: {person_count} Helmets: {helmet_count}", (10, 30),
                  cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # 如果人数多于安全帽数量，显示警告
        if person_count > helmet_count:
            cv2.putText(frame, f"Warning: {person_count - helmet_count} person(s) without helmet", (10, 60),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

        # 转换为JPEG格式
        frame = cv2.resize(frame, (640, 360))
        _, buffer = cv2.imencode('.jpg', frame)
        current_frames[channel_id] = buffer.tobytes()

        # 更新全局计数 (Move update after encoding)
        current_person_counts[channel_id] = person_count
        current_helmet_counts[channel_id] = helmet_count


        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + current_frames[channel_id] + b'\r\n')

    cap.release()
    is_video_running[channel_id] = False

# current_frame_jpeg 函数不再需要，因为每个通道有自己的 current_frames[channel_id]
# def current_frame_jpeg():
#     """获取当前帧的 JPEG 数据"""
#     global current_frame
#     return current_frame

@router.get("/video_stream/{channel_id}")
def get_video_stream(channel_id: int):
    """指定通道的视频流接口"""
    if not 0 <= channel_id < CHANNELS:
        raise HTTPException(status_code=400, detail="无效的通道ID")
    return StreamingResponse(video_stream(channel_id), media_type="multipart/x-mixed-replace; boundary=frame")

# 添加一个停止视频流的接口（可选，但推荐）
@router.post("/stop_stream/{channel_id}")
def stop_video_stream(channel_id: int):
    """停止指定通道的视频流"""
    global is_video_running
    if not 0 <= channel_id < CHANNELS:
        raise HTTPException(status_code=400, detail="无效的通道ID")
    is_video_running[channel_id] = False
    return {"message": f"通道 {channel_id+1} 视频流停止请求已发送"}

@router.post("/start_preview")
def start_preview(file_path: str = Query(..., description="要预览的视频文件路径"), channel_id: int = Query(7, description="用于预览的通道ID")):
    """为智能体预览启动指定文件的流。不会上传拷贝，直接使用给定路径。"""
    global video_paths, current_person_counts, current_helmet_counts, is_video_running
    if not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail=f"文件不存在: {file_path}")
    if not 0 <= channel_id < CHANNELS:
        raise HTTPException(status_code=400, detail="无效的通道ID")
    video_paths[channel_id] = file_path
    current_person_counts[channel_id] = 0
    current_helmet_counts[channel_id] = 0
    # 确保下次拉流时从头开始
    is_video_running[channel_id] = False
    stream_url = f"/api/video/video_stream/{channel_id}"
    return {"message": "ok", "channel": channel_id, "stream_url": stream_url}
