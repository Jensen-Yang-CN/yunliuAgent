"""配置文件
包含视频监控系统的所有可配置参数
"""

from typing import Dict, Any
import logging
import os

# Get the directory of the current config.py file
_current_dir = os.path.dirname(os.path.abspath(__file__)) # VLMAnalysis directory

# Define base directory for YunliuAIVideo
_base_dir = os.path.dirname(_current_dir) # YunliuAIVideo directory

# Define VLMAnalysis directory and video_warning directory using absolute paths
VLM_ANALYSIS_DIR = _current_dir
VIDEO_WARNING_DIR = os.path.join(VLM_ANALYSIS_DIR, 'video_warning')

# 视频源配置
# Construct the absolute path to the video file relative to _base_dir
VIDEO_SOURCE = os.path.join(_base_dir, 'videoData', '工地施工.mp4')

# 视频处理配置
class VideoConfig:
    VIDEO_INTERVAL = 1800  # 视频分段时长(秒)
    ANALYSIS_INTERVAL = 10  # 分析间隔(秒)
    BUFFER_DURATION = 11  # 滑窗分析时长（实际模型分析视频时长）#强制抽帧，每秒一帧率
    WS_RETRY_INTERVAL = 3  # WebSocket重连间隔(秒)
    MAX_WS_QUEUE = 100  # 消息队列最大容量
    JPEG_QUALITY = 70  # JPEG压缩质量
    WARNING_COOLDOWN = 30  # 预警冷却时间（秒），避免频繁报警
    SAVE_WARNING_FRAMES = True  # 是否保存预警帧
    MAX_WARNING_HISTORY = 50  # 最大预警历史记录数



# API配置
class APIConfig:
    # 通义千问API配置
    #高晓晨：sk-9506fdf04cb4499c81835a417b9a609a
    QWEN_API_KEY = "sk-97f57ac0cbab4b2cafd5ad6b077cc07b"
    QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    QWEN_MODEL = "qwen-vl-max-latest"

    # 通义千问API（硅基流动）配置
    """
    QWEN_API_KEY = "sk-vpwcxnjhvzngxtsywdgbkanztamkyeunfppivtqlfiuokgfm"
    QWEN_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
    QWEN_MODEL = "Pro/Qwen/Qwen2.5-VL-7B-Instruct"
    """

    # deepseek-vl API配置
    DEEPSEEK_API_KEY = "sk-vpwcxnjhvzngxtsywdgbkanztamkyeunfppivtqlfiuokgfm"
    DEEPSEEK_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
    DEEPSEEK_MODEL = "deepseek-ai/deepseek-vl2"

    # Moonshot语言模型 API配置，这里可以换成其他语言模型或者本地部署的内容
    MOONSHOT_API_KEY = "sk-a4CQiWGi2JoUD239BrQAsrFuKyBVQxi9w0jrId9Bz5ru454O"
    MOONSHOT_API_URL = "https://api.moonshot.cn/v1/chat/completions"
    MOONSHOT_MODEL = "moonshot-v1-8k"
    
    # API请求配置
    REQUEST_TIMEOUT = 60.0 # 请求超时时间（秒）
    TEMPERATURE = 0.5 # 温度
    TOP_P = 0.01 
    TOP_K = 20
    REPETITION_PENALTY = 1.05

# RAG系统配置
class RAGConfig:
    # 知识库配置
    ENABLE_RAG = True  # 是否启用RAG
    HISTORY_SAVE_INTERVAL = 60  # 历史记录保存间隔（秒）
    VECTOR_API_URL = "http://172.16.10.44:8085/add_text/" # 启用RAG需要自行搭建rag服务，并构造相应api接口
    # Update HISTORY_FILE to be an absolute path within YunliuAIVideo directory
    HISTORY_FILE = os.path.join(_base_dir, "video_histroy_info.txt")  # 如果不启用RAG，历史记录将保存在该文件中
    # Milvus配置
    MILVUS_HOST = "localhost"
    MILVUS_PORT = "19530"
    KNOWLEDGE_COLLECTION = "enterprise_regulations"
    SIMILARITY_THRESHOLD = 0.6  # 相似度阈值，用于过滤结果（降低阈值以提高匹配率）

# 存档配置
ARCHIVE_DIR = "archive"

# 服务器配置
class ServerConfig:
    HOST = "0.0.0.0"
    PORT = 16532
    RELOAD = True
    WORKERS = 1

# 日志配置
LOG_CONFIG = {
    'level': logging.INFO,
    'format': '%(asctime)s - %(levelname)s - %(message)s',
    'handlers': [
        # Update log file path to be an absolute path within YunliuAIVideo directory
        {'type': 'file', 'filename': os.path.join(_base_dir, 'code.log')},
        {'type': 'stream'}
    ]
}

def update_config(args: Dict[str, Any]) -> None:
    """使用命令行参数更新配置
    
    Args:
        args: 包含命令行参数的字典
    """
    global VIDEO_SOURCE
    
    # 更新视频源
    if args.get('video_source'):
        VIDEO_SOURCE = args['video_source']
    
    # 更新视频处理配置
    for key in ['video_interval', 'analysis_interval', 'buffer_duration',
               'ws_retry_interval', 'max_ws_queue', 'jpeg_quality']:
        if key in args:
            setattr(VideoConfig, key.upper(), args[key])
    
    # 更新服务器配置
    for key in ['host', 'port', 'reload', 'workers']:
        if key in args:
            setattr(ServerConfig, key.upper(), args[key])
            
    # 更新API配置
    for key in ['qwen_api_key', 'qwen_api_url', 'qwen_model',
               'moonshot_api_key', 'moonshot_api_url', 'moonshot_model',
               'request_timeout', 'temperature', 'top_p', 'top_k',
               'repetition_penalty']:
        if key in args:
            setattr(APIConfig, key.upper(), args[key])
            
    # 更新RAG配置
    for key in ['enable_rag', 'vector_api_url', 'history_file',
               'history_save_interval']:
        if key in args:
            setattr(RAGConfig, key.upper(), args[key])


