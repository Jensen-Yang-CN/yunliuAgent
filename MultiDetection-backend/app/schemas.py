# Pydantic 数据模型，用于请求/响应校验
from pydantic import BaseModel
from datetime import datetime

class AlarmRecordCreate(BaseModel):
    description: str
    keyframe_path: str
    channel: int

class AlarmRecordResponse(BaseModel):
    id: int
    timestamp: datetime
    description: str
    keyframe_path: str
    channel: int

    class Config:
        orm_mode = True
