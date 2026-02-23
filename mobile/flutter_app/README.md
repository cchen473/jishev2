# NebulaGuard Flutter 移动端

这个目录是 NebulaGuard 的原生移动端（Flutter）。

## 功能

- 用户注册 / 登录
- 地震上报（震感、建筑类型、结构备注、描述）
- 社区群聊（用户端聊天入口）
- 社区 AI 助手提问与答案记录
- 报平安（平安/需救援/失联代报）与社区回执统计
- 社区态势页（事件列表、避难点容量）
- Token 持久化登录

## 后端要求

默认连接：`http://10.0.2.2:8000`（Android 模拟器）

你也可以通过 `--dart-define` 覆盖：

```bash
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

说明：
- Android 模拟器访问宿主机通常用 `10.0.2.2`
- iOS 模拟器可用 `http://127.0.0.1:8000`
- 真机请替换为你的局域网 IP

## 运行

```bash
cd mobile/flutter_app
flutter create .
flutter pub get
flutter run
```

如果你首次把纯源码目录转成完整平台工程，可执行：

```bash
flutter create .
```

## 已对接后端接口

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `POST /report/earthquake`
- `GET /community/chat/messages`
- `POST /community/chat/send`
- `POST /community/assistant/ask`
- `POST /residents/checkins`
- `GET /residents/checkins/summary`
- `GET /incidents`
- `GET /shelters`

详细真机和模拟器测试步骤请参考：`/Users/cc/jishev2/nebulaguard/docs/mobile/flutter-testing-guide.md`
