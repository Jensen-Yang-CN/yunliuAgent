# 数据库连接管理
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os

# 使用 SQLite 数据库（无需任何配置，开箱即用）
# 如果需要使用 MySQL，请取消注释下面的行并注释掉 SQLite 的行
# DATABASE_URL = "mysql+pymysql://root:root@localhost:3306/FastAPIDemo"

DATABASE_URL = "sqlite:///./test.db"

# SQLite 需要 check_same_thread=False
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# 数据库会话生成器
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
