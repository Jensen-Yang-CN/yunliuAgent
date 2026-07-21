"""
工具模块 - 定义和实现智能体可用的工具
"""
import os
import cv2
import numpy as np
import logging
import tempfile
import base64
from typing import Dict, Any, List, Optional
from ultralytics import YOLO
from datetime import datetime
import urllib.request
import urllib.error
import json

logger = logging.getLogger(__name__)


class HelmetDetectionTool:
    """安全帽检测工具"""
    
    def __init__(self, model_path: str = None):
        if model_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.abspath(os.path.join(current_dir, '..', '..', 'models', 'best.pt'))
        
        self.model_path = model_path
        self.model = None
        self._load_model()
    
    def _load_model(self):
        try:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Model file not found: {self.model_path}")
            self.model = YOLO(self.model_path)
            logger.info(f"Helmet detection model loaded: {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load helmet detection model: {str(e)}")
            raise
    
    def detect_from_file(self, file_path: Optional[str] = None, confidence_threshold: float = 0.5) -> Dict[str, Any]:
        try:
            if not file_path:
                default_dir = r"E:\CodeBase_YangJunJie\yunliuAgent\yunliu-aivideo-zsl\MultiDetection-backend\output_parts"
                if not os.path.isdir(default_dir):
                    raise FileNotFoundError(f"Default directory not found: {default_dir}")
                candidates = [os.path.join(default_dir, f) for f in sorted(os.listdir(default_dir)) if f.lower().endswith('.mp4')]
                if not candidates:
                    raise FileNotFoundError(f"No MP4 files found in default directory: {default_dir}")
                file_path = candidates[0]
                logger.info(f"Auto-selected default video for detection: {file_path}")

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'}
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext in video_extensions:
                result = self._detect_from_video(file_path, confidence_threshold)
            elif file_ext in image_extensions:
                result = self._detect_from_image(file_path, confidence_threshold)
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")

            result["used_file_path"] = file_path
            return result
        except Exception as e:
            logger.error(f"Error in detect_from_file: {str(e)}")
            return {"success": False, "error": str(e), "file": file_path}
    
    def _detect_from_image(self, image_path: str, confidence_threshold: float = 0.5) -> Dict[str, Any]:
        try:
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Failed to read image: {image_path}")
            results = self.model(image)
            detections = self._parse_results(results, confidence_threshold)
            annotated_image = self._draw_detections(image, detections)
            output_dir = os.path.join(tempfile.gettempdir(), "helmet_detection")
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(output_dir, f"detected_{timestamp}.jpg")
            cv2.imwrite(output_path, annotated_image)
            return {
                "success": True, "file": image_path, "detections": detections, "output_image": output_path,
                "summary": {
                    "total_persons": len([d for d in detections if d["class"] == "person"]),
                    "total_helmets": len([d for d in detections if d["class"] == "helmet"]),
                    "persons_without_helmet": len([d for d in detections if d["class"] == "person"]) - len([d for d in detections if d["class"] == "helmet"])
                }
            }
        except Exception as e:
            logger.error(f"Error in _detect_from_image: {str(e)}")
            return {"success": False, "error": str(e), "file": image_path}
    
    def _detect_from_video(self, video_path: str, confidence_threshold: float = 0.5) -> Dict[str, Any]:
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"Failed to open video: {video_path}")
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            frame_detections = []
            total_persons = 0
            total_helmets = 0
            frames_with_violations = 0
            frame_interval = max(1, int(fps) if fps > 0 else 1)
            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % frame_interval == 0:
                    results = self.model(frame)
                    detections = self._parse_results(results, confidence_threshold)
                    persons = len([d for d in detections if d["class"] == "person"])
                    helmets = len([d for d in detections if d["class"] == "helmet"])
                    total_persons += persons
                    total_helmets += helmets
                    if persons > helmets:
                        frames_with_violations += 1
                    frame_detections.append({"frame": frame_idx, "persons": persons, "helmets": helmets, "detections": detections})
                frame_idx += 1
            cap.release()
            return {
                "success": True, "file": video_path,
                "video_info": {"fps": fps, "frame_count": frame_count, "width": width, "height": height, "duration": frame_count / fps if fps > 0 else 0},
                "frame_detections": frame_detections,
                "summary": {
                    "total_persons": total_persons, "total_helmets": total_helmets, "frames_with_violations": frames_with_violations,
                    "violation_rate": frames_with_violations / (len(frame_detections) if frame_detections else 1)
                }
            }
        except Exception as e:
            logger.error(f"Error in _detect_from_video: {str(e)}")
            return {"success": False, "error": str(e), "file": video_path}
    
    def _parse_results(self, results, confidence_threshold: float) -> List[Dict[str, Any]]:
        detections = []
        for result in results:
            for box in result.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                if conf > confidence_threshold:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    class_name = "helmet" if cls == 0 else "person"
                    detections.append({"class": class_name, "confidence": conf, "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "width": x2 - x1, "height": y2 - y1}})
        return detections
    
    def _draw_detections(self, image: np.ndarray, detections: List[Dict[str, Any]]) -> np.ndarray:
        annotated = image.copy()
        for detection in detections:
            bbox = detection["bbox"]
            class_name = detection["class"]
            color = (0, 255, 0) if class_name == "helmet" else (0, 0, 255)
            cv2.rectangle(annotated, (bbox["x1"], bbox["y1"]), (bbox["x2"], bbox["y2"]), color, 2)
            label = f"{detection['class']}: {detection['confidence']:.2f}"
            cv2.putText(annotated, label, (bbox["x1"], bbox["y1"] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return annotated


class AIImageGenerationTool:
    """AI图片生成工具（占位符）"""
    def __init__(self):
        logger.info("AI Image Generation Tool initialized (placeholder)")
    def generate_image(self, prompt: str, size: str = "1024x1024", quality: str = "standard") -> Dict[str, Any]:
        logger.info(f"Placeholder: Generating image with prompt: {prompt}")
        return {"success": True, "prompt": prompt, "message": "这是一个占位符工具，实际并未生成图片。", "image_url": "https://via.placeholder.com/512.png?text=Placeholder+Image"}


class VLMVideoAnalysisTool:
    """大模型视频推理工具（调用 YunliuAIVideo/main_server 接口）"""
    def __init__(self, base_url: str = None):
        self.base_url = base_url or "http://localhost:16532"

    def _post_json(self, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                try:
                    return {"success": True, "status": resp.status, "data": json.loads(raw)}
                except Exception:
                    return {"success": True, "status": resp.status, "data": raw}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="ignore")
            return {"success": False, "status": e.code, "error": raw}
        except Exception as e:
            return {"success": False, "status": None, "error": str(e)}

    def start(self) -> Dict[str, Any]:
        return self._post_json("/start_video_analysis")

    def stop(self) -> Dict[str, Any]:
        return self._post_json("/stop_video_analysis")

# 创建全局工具实例
helmet_detection_tool = HelmetDetectionTool()
ai_image_generation_tool = AIImageGenerationTool()
vlm_video_analysis_tool = VLMVideoAnalysisTool()


# 工具定义（OpenAI格式）
HELMET_DETECTION_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "detect_helmet",
        "description": "检测视频或图片中的安全帽和人员。若未提供file_path，将自动从默认目录中选择第一个MP4文件进行检测。默认目录: 'E:\\CodeBase_YangJunJie\\yunliuAgent\\yunliu-aivideo-zsl\\MultiDetection-backend\\output_parts'。",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "要检测的视频或图片文件的路径。"},
                "confidence_threshold": {"type": "number", "description": "检测置信度阈值，0-1，默认0.5"}
            }
        }
    }
}

AI_IMAGE_GENERATION_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "generate_image",
        "description": "（占位符）使用AI生成符合描述的图片。",
        "parameters": {
            "type": "object",
            "properties": {"prompt": {"type": "string", "description": "图片生成的提示词"}},
            "required": ["prompt"]
        }
    }
}

VLM_START_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "vlm_start_video_analysis",
        "description": "启动大模型视频推理。需要 YunliuAIVideo 服务在 16532 端口运行。",
        "parameters": {"type": "object", "properties": {}}
    }
}

VLM_STOP_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "vlm_stop_video_analysis",
        "description": "停止大模型视频推理。",
        "parameters": {"type": "object", "properties": {}}
    }
}
