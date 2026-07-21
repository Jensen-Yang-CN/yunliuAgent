# 定义 MySQL 数据表，用 SQLAlchemy 处理
from sqlalchemy import Column, Integer, String, DateTime
# from sqlalchemy.ext.declarative import declarative_base # 移除此行
from datetime import datetime, timedelta, timezone
from .db import Base  # 相对导入 Base

# Base = declarative_base() # 移除此行

def beijing_time():
    """返回当前北京时间"""
    tz_beijing = timezone(timedelta(hours=8))  # 北京时间 UTC+8
    return datetime.now(tz_beijing)

class AlarmRecord(Base): # 现在继承的是从 app.db 导入的 Base
    __tablename__ = "alarm_records"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=beijing_time)
    description = Column(String(255))
    keyframe_path = Column(String(255))  # 关键帧图片路径
    channel = Column(Integer) # 添加通道字段
