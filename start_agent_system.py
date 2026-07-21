"""
智能体系统启动脚本
"""
import os
import sys
import subprocess
import time
from pathlib import Path

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent

# 后端目录
BACKEND_DIR = PROJECT_ROOT / "MultiDetection-backend"

# 前端目录
FRONTEND_DIR = PROJECT_ROOT / "yunliu-mining-ai-system"

def print_header(text):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")

def check_python():
    """检查Python环境"""
    print_header("检查Python环境")
    
    version = sys.version_info
    print(f"✓ Python版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("✗ 需要Python 3.8或更高版本")
        return False
    
    return True

def check_dependencies():
    """检查依赖"""
    print_header("检查Python依赖")
    
    required_packages = [
        'fastapi',
        'uvicorn',
        'openai',
        'ultralytics',
        'cv2',
        'torch'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} (缺失)")
            missing.append(package)
    
    if missing:
        print(f"\n缺失的包: {', '.join(missing)}")
        print("请运行: pip install " + " ".join(missing))
        return False
    
    return True

def check_model():
    """检查模型文件"""
    print_header("检查模型文件")
    
    model_path = PROJECT_ROOT / "Models" / "best.pt"
    
    if model_path.exists():
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"✓ 模型文件存在: {model_path}")
        print(f"  大小: {size_mb:.2f} MB")
        return True
    else:
        print(f"✗ 模型文件不存在: {model_path}")
        print("  请确保best.pt文件在Models目录中")
        return False

def check_api_key():
    """检查API密钥"""
    print_header("检查API密钥")
    
    api_key = os.getenv("DASHSCOPE_API_KEY")
    
    if api_key:
        # 只显示前几个字符
        masked_key = api_key[:10] + "..." + api_key[-5:]
        print(f"✓ API密钥已设置: {masked_key}")
        return True
    else:
        print("⚠ API密钥未设置")
        print("  请设置环境变量: DASHSCOPE_API_KEY=sk-...")
        print("  或在代码中配置API密钥")
        return False

def start_backend():
    """启动后端服务"""
    print_header("启动后端服务")
    
    os.chdir(BACKEND_DIR)
    
    print(f"工作目录: {os.getcwd()}")
    print("启动命令: python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    print("\n后端服务启动中...")
    
    try:
        subprocess.Popen([
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--reload",
            "--host", "0.0.0.0",
            "--port", "8000"
        ])
        print("✓ 后端服务已启动 (http://localhost:8000)")
        return True
    except Exception as e:
        print(f"✗ 启动后端服务失败: {e}")
        return False

def start_frontend():
    """启动前端服务"""
    print_header("启动前端服务")
    
    os.chdir(FRONTEND_DIR)
    
    print(f"工作目录: {os.getcwd()}")
    
    # 检查node_modules
    if not (FRONTEND_DIR / "node_modules").exists():
        print("node_modules不存在，正在安装依赖...")
        try:
            subprocess.run(["npm", "install"], check=True, shell=True)
        except Exception as e:
            print(f"✗ npm install失败: {e}")
            return False
    
    print("启动命令: npm run dev")
    print("\n前端服务启动中...")
    
    try:
        # Windows 需要 shell=True
        subprocess.Popen(["npm", "run", "dev"], shell=True)
        print("✓ 前端服务已启动 (http://localhost:5173)")
        return True
    except Exception as e:
        print(f"✗ 启动前端服务失败: {e}")
        return False

def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  AI智能体系统启动脚本".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    
    # 检查环境
    checks = [
        ("Python环境", check_python),
        ("Python依赖", check_dependencies),
        ("模型文件", check_model),
        ("API密钥", check_api_key),
    ]
    
    all_passed = True
    for check_name, check_func in checks:
        if not check_func():
            all_passed = False
    
    if not all_passed:
        print_header("环境检查未完全通过")
        print("请解决上述问题后重试")
        sys.exit(1)
    
    print_header("环境检查完成")
    print("✓ 所有检查均已通过")
    
    # 启动服务
    print_header("启动服务")
    
    backend_ok = start_backend()
    time.sleep(3)  # 等待后端启动
    
    frontend_ok = start_frontend()
    
    if backend_ok and frontend_ok:
        print_header("系统启动完成")
        print("✓ 后端服务: http://localhost:8000")
        print("✓ 前端服务: http://localhost:5173")
        print("✓ API文档: http://localhost:8000/docs")
        print("\n按 Ctrl+C 停止服务")
        
        try:
            # 保持主进程运行
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n系统已停止")
    else:
        print_header("系统启动失败")
        if not backend_ok:
            print("✗ 后端服务启动失败")
        if not frontend_ok:
            print("✗ 前端服务启动失败")
        sys.exit(1)

if __name__ == "__main__":
    main()

