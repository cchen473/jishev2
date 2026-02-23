# NebulaGuard Earthquake Command System

面向成都社区场景的地震指挥系统（Web 管理端 + Flutter 原生用户端 + 实时协同后端）。

## 当前能力

- 地震单灾种指挥：系统默认基准城市为成都（`30.5728, 104.0668`）。
- 社区化协同：用户注册/登录后自动创建或加入社区群组。
- 社区 AI 管理助手：支持群聊中自动回复与单独提问。
- 社区聊天：社区成员可在群聊实时交流，消息通过 WebSocket 同步。
- 震情上报：支持上报震感等级、建筑/房屋结构、现场描述和可选图片。
- VLM 避险建议：可选调用 OpenAI 视觉模型分析现场图片和结构风险，失败自动降级规则建议。
- 社区通知：上报后自动生成避险通知广播到同社区用户，支持手动发送通知。
- 火灾救援分析：上传鸟瞰图，基于原生 YOLO 人员检测识别受灾群众并生成救援路线建议（不依赖 VLM）。
- 事件闭环增强：支持事件中心、工单流转、救援队编组、资源调度、居民报平安、避难点容量、风险区标绘、道路阻断、通知回执、审计与复盘时间轴。
- 实时链路：WebSocket 推送任务过程、震情上报和社区通知。
- 数据持久化：SQLite 存储用户、社区、上报、通知、群聊、火灾救援分析、任务和任务事件。

## 项目结构

- `backend/` FastAPI + SQLite + RAG + Auth + WebSocket
- `frontend/` Next.js 指挥中心（管理端）
- `mobile/flutter_app/` Flutter 原生用户端（上报 + 群聊 + AI 助手）
- `backend/data/policies/protocols.md` 应急策略文档
- `docs/功能文档.md` 功能说明文档
- `docs/mobile/flutter-testing-guide.md` Flutter 编译与真机测试手册
- `docs/rescue/yolo-aerial-detection-implementation.md` YOLO 鸟瞰检测实现细节
- `docs/spec/current-progress.spec.md` 项目进度 Spec
- `AGENT.md` 项目治理规范

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

默认访问（管理端）：

- 指挥中心: `http://localhost:3000`
- 移动端迁移说明页: `http://localhost:3000/mobile`

### 3) Flutter 原生用户端

```bash
cd mobile/flutter_app
flutter pub get
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

## 核心接口

### 认证与社区

- `POST /auth/register` 注册并创建/加入社区
- `POST /auth/login` 登录
- `GET /auth/me` 当前用户
- `GET /community/notifications` 社区通知列表
- `POST /community/alerts` 手动广播社区通知
- `GET /community/chat/messages` 社区聊天记录
- `POST /community/chat/send` 发送群聊消息（可触发 AI 助手回复）
- `POST /community/assistant/ask` 单独提问社区 AI 助手
- `POST /community/notification-templates` 新建通知模板
- `GET /community/notification-templates` 查询通知模板
- `POST /community/notifications/receipt` 上报通知回执（已读/确认）
- `GET /community/notifications/{notification_id}/receipts/summary` 通知回执统计

### 地震业务

- `GET /reports/recent?limit=50` 最近地震上报（需登录）
- `GET /system/summary` 社区摘要（需登录）
- `POST /report/earthquake` 地震上报（JSON）
- `POST /report/earthquake_with_media` 地震上报（带图片）
- `POST /ai/route_advice` 文本避险建议

### 火灾救援

- `POST /rescue/fire/analyze` 上传鸟瞰图，执行 YOLO 受困人员检测并生成救援路线
- `GET /rescue/fire/analyses` 查看社区内最近火灾救援分析

### 应急闭环

- `POST /incidents` / `GET /incidents` / `PATCH /incidents/{incident_id}`
- `POST /incidents/{incident_id}/tasks` / `GET /tasks` / `PATCH /tasks/{task_id}`
- `POST /teams` / `GET /teams`
- `POST /dispatches` / `GET /dispatches`
- `POST /residents/checkins` / `GET /residents/checkins/summary`
- `POST /missing-persons` / `GET /missing-persons`
- `POST /shelters` / `GET /shelters` / `PATCH /shelters/{shelter_id}/occupancy`
- `POST /hazards/zones` / `GET /hazards/zones`
- `POST /roads/blocks` / `GET /roads/blocks`
- `GET /ops/timeline` / `GET /ops/audit-logs`

### 指挥任务

- `POST /mission/start` 启动任务（需登录）
- `WS /ws/mission?token=...` 实时任务/上报/通知通道

## 环境变量说明（后端）

关键变量见 `backend/.env.example`：

- `BASE_CITY`、`BASE_LAT`、`BASE_LNG`：城市基准（默认成都）
- `OPENAI_API_KEY`、`OPENAI_MODEL`、`OPENAI_VLM_MODEL`
- `YOLO_MODEL_PATH`、`YOLO_MODEL_URL`、`YOLO_CONFIDENCE_THRESHOLD`
- `AUTH_SECRET`、`AUTH_TOKEN_EXP_MINUTES`
- `DATABASE_PATH`、`UPLOAD_DIR`、`MAX_UPLOAD_MB`

## 数据库说明

后端默认使用 SQLite（`backend/data/nebulaguard.db`），并已包含以下核心表结构与索引：

- 用户与社区：`users`、`communities`、`community_memberships`
- 业务数据：`earthquake_reports`、`community_notifications`、`community_chat_messages`、`fire_rescue_analyses`
- 闭环增强：`incidents`、`incident_tasks`、`response_teams`、`dispatch_records`、`resident_checkins`、`missing_person_reports`、`shelters`、`shelter_occupancy_events`、`hazard_zones`、`road_blocks`、`notification_receipts`、`audit_logs`、`ops_timeline_events`
- 指挥任务：`missions`、`mission_events`
- 性能索引：已为社区聊天、通知、上报、火灾分析按 `community_id + created_at` 建立索引

## 备注

当前实现适合单机或小规模社区演示环境。生产化建议：接入 PostgreSQL、完善权限模型、增加消息队列与审计链路。
