# Frontend (Earthquake Command)

## 环境变量

复制模板并填写：

```bash
cp .env.example .env.local
```

默认值说明：

- `NEXT_PUBLIC_BACKEND_HTTP_URL` 后端 HTTP 地址
- `NEXT_PUBLIC_BACKEND_WS_URL` 后端 WebSocket 地址
- `NEXT_PUBLIC_BACKEND_PORT` 后端端口
- `NEXT_PUBLIC_MAPBOX_TOKEN` 地图 token（建议填写）

## 启动

```bash
npm run dev
```

访问：

- 指挥中心：`http://localhost:3000`
- 移动端迁移说明：`http://localhost:3000/mobile`

## 页面说明

- `src/app/page.tsx` 成都指挥中心（登录注册、地图、事件中心、工单看板、复盘时间轴、通知回执、社区聊天、AI助手、火灾救援 YOLO 分析）
- `src/app/mobile/page.tsx` Flutter 原生用户端迁移说明页（不再承载用户端业务）
- `src/lib/api.ts` 统一 API 与 token 管理
- `src/lib/runtime-config.ts` 后端地址和地图 token

## 校验

```bash
npm run lint
```
