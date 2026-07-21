## 安装依赖
```
pip install -r requirements.txt
```
## 数据库配置

数据库配置文件位于  MultiDetection-backend\app\db.py
```
DATABASE_URL = "mysql+pymysql://root:root@localhost:3306/FastAPIDemo"
```
替换为自己的用户名和密码，数据库名为FastAPIDemo
## 运行命令
```
uvicorn app.main:app --reload --port 8000
``` 