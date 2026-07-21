# 封装数据库的增删查操作
from sqlalchemy.orm import Session
from .models import AlarmRecord

def create_alarm(db: Session, description: str, keyframe_path: str, channel: int):
    alarm = AlarmRecord(description=description, keyframe_path=keyframe_path, channel=channel)
    db.add(alarm)
    db.commit()
    db.refresh(alarm)
    return alarm

def get_all_alarms(db: Session):
    return db.query(AlarmRecord).all()
