# 报警记录的 API 路由
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...schemas import AlarmRecordResponse, AlarmRecordCreate
from ...crud import create_alarm, get_all_alarms
from ...db import get_db

router = APIRouter()

@router.post("/", response_model=AlarmRecordResponse)
def create_alarm_record(record: AlarmRecordCreate, db: Session = Depends(get_db)):
    # 确保将 channel 传递给 create_alarm 函数
    return create_alarm(db=db, description=record.description, keyframe_path=record.keyframe_path, channel=record.channel)

@router.get("/", response_model=list[AlarmRecordResponse])
def list_alarm_records(db: Session = Depends(get_db)):
    return get_all_alarms(db=db)
