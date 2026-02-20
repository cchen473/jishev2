# NebulaGuard Earthquake Command System

面向成都社区场景的地震指挥系统（Web 指挥中心 + 移动上报端 + 实时协同后端）。

## 当前能力

- 地震单灾种指挥：系统默认基准城市为成都（`30.5728, 104.0668`）。
- 社区化协同：用户注册/登录后自动创建或加入社区群组。
- 震情上报：支持上报震感等级、建筑/房屋结构、现场描述和可选图片。
- VLM 避险建议：可选调用 OpenAI 视觉模型分析现场图片和结构风险，失败自动降级规则建议。
- 社区通知：上报后自动生成避险通知广播到同社区用户，支持手动发送通知。
- 实时链路：WebSocket 推送任务过程、震情上报和社区通知。
- 数据持久化：SQLite 存储用户、社区、上报、通知、任务和任务事件。

## 项目结构

- `backend/` FastAPI + SQLite + RAG + Auth + WebSocket
- `frontend/` Next.js 指挥中心与移动上报页面
- `backend/data/policies/protocols.md` 应急策略文档
- `docs/功能文档.md` 功能说明文档

## 快速启动

### 1) 后端

```bash
cd backend
cp .env.example .env
pip install -r requirements.txt
python main.py
```

默认端口 `8000`。

### 2) 前端

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

默认访问：

- 指挥中心: `http://localhost:3000`
- 移动上报页: `http://localhost:3000/mobile`

## 核心接口

### 认证与社区

- `POST /auth/register` 注册并创建/加入社区
- `POST /auth/login` 登录
- `GET /auth/me` 当前用户
- `GET /community/notifications` 社区通知列表
- `POST /community/alerts` 手动广播社区通知

### 地震业务

- `GET /reports/recent?limit=50` 最近地震上报（需登录）
- `GET /system/summary` 社区摘要（需登录）
- `POST /report/earthquake` 地震上报（JSON）
- `POST /report/earthquake_with_media` 地震上报（带图片）
- `POST /ai/route_advice` 文本避险建议

### 指挥任务

- `POST /mission/start` 启动任务（需登录）
- `WS /ws/mission?token=...` 实时任务/上报/通知通道

## 环境变量说明（后端）

关键变量见 `backend/.env.example`：

- `BASE_CITY`、`BASE_LAT`、`BASE_LNG`：城市基准（默认成都）
- `OPENAI_API_KEY`、`OPENAI_MODEL`、`OPENAI_VLM_MODEL`
- `AUTH_SECRET`、`AUTH_TOKEN_EXP_MINUTES`
- `DATABASE_PATH`、`UPLOAD_DIR`、`MAX_UPLOAD_MB`

## 备注

当前实现适合单机或小规模社区演示环境。生产化建议：接入 PostgreSQL、完善权限模型、增加消息队列与审计链路。
