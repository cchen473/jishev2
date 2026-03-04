# NebulaGuard 安装与启动

## 1. 环境要求

操作系统: macOS、Linux、Windows等  
Python: 3.10+  
Node.js: 18+  
Flutter: 3.24+  
iOS开发: Xcode  
Android开发: Android Studio  

## 2. 配置

### 2.1 后端（backend/.env）

BACKEND_HOST: 0.0.0.0  
BACKEND_PORT: 8000  
OPENAI_API_KEY: sk-xxx  
OPENAI_BASE_URL: https://...  
OPENAI_VLM_MODEL: qwen3-vl-plus  
DATABASE_PATH: backend/data/nebulaguard.db  
UPLOAD_DIR: backend/uploads  

### 2.2 前端（frontend/.env.local）

NEXT_PUBLIC_API_BASE_URL: http://localhost:8000  

### 2.3 Flutter

API_BASE_URL（iOS Simulator）: http://127.0.0.1:8000  
API_BASE_URL（Android Emulator）: http://10.0.2.2:8000  
API_BASE_URL（真机）: http://电脑局域网IP:8000  

## 3. 安装与启动

### 3.1 后端

进入目录: cd /Users/cc/jishev2/nebulaguard/backend  
安装依赖: pip install -r requirements.txt  
启动: python3 main.py  
检查: http://127.0.0.1:8000/health  

### 3.2 Web

进入目录: cd /Users/cc/jishev2/nebulaguard/frontend  
安装依赖: npm install  
启动: npm run dev  
访问: http://localhost:3000  

### 3.3 Flutter

进入目录: cd /Users/cc/jishev2/nebulaguard/mobile/flutter_app  
安装依赖: flutter pub get  
查看设备: flutter devices  
启动（iOS）: flutter run -d <device_id> --dart-define=API_BASE_URL=http://127.0.0.1:8000  
启动（Android）: flutter run -d <device_id> --dart-define=API_BASE_URL=http://10.0.2.2:8000  
