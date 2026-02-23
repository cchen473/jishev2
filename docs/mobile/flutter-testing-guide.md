# NebulaGuard Flutter 编译与测试手册（新手版）

> 适用目录：`/Users/cc/jishev2/nebulaguard/mobile/flutter_app`
>
> 本手册目标：让你在 macOS 上完成 **Android 模拟器 + iOS 模拟器 + Android 真机 + iPhone 真机** 联调。

## 1. 先确认你本机环境

### 1.1 安装 Flutter（macOS）

```bash
brew install --cask flutter
flutter --version
```

### 1.2 安装开发工具

- Android：安装 Android Studio（含 Android SDK、AVD）。
- iOS：安装 Xcode（App Store）。

### 1.3 检查环境是否齐全

```bash
flutter doctor -v
```

`flutter doctor` 全绿后再继续。若有红色项，按提示修复。

---

## 2. 生成完整 Flutter 平台工程（必须做一次）

当前仓库内 `mobile/flutter_app` 主要是源码骨架，第一次使用需要生成平台目录：

```bash
cd /Users/cc/jishev2/nebulaguard/mobile/flutter_app
flutter create .
flutter pub get
```

执行后应出现：

- `android/`
- `ios/`
- `macos/`（可选）

---

## 3. 先启动后端（所有移动端测试前置）

```bash
cd /Users/cc/jishev2/nebulaguard/backend
python3 -m pip install -r requirements.txt
python3 main.py
```

默认后端地址：`http://127.0.0.1:8000`

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

---

## 4. 模拟器测试（电脑上先跑通）

## 4.1 Android 模拟器

1. 打开 Android Studio -> Device Manager -> 启动一个 AVD。
2. 查看设备：

```bash
flutter devices
```

3. 启动 App（Android 模拟器访问宿主机后端要用 `10.0.2.2`）：

```bash
cd /Users/cc/jishev2/nebulaguard/mobile/flutter_app
flutter run -d <android_device_id> --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

## 4.2 iOS 模拟器

1. 打开模拟器：

```bash
open -a Simulator
```

2. 运行：

```bash
cd /Users/cc/jishev2/nebulaguard/mobile/flutter_app
flutter run -d <ios_simulator_id> --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

> iOS 模拟器通常可直接访问 `127.0.0.1`。

---

## 5. Android 真机测试（USB）

1. 手机打开“开发者选项” + “USB 调试”。
2. USB 连接电脑并授权。
3. 查看设备：

```bash
flutter devices
```

4. 真机不能用 `127.0.0.1`，必须用你电脑局域网 IP（如 `192.168.1.24`）：

```bash
flutter run -d <android_phone_id> --dart-define=API_BASE_URL=http://192.168.1.24:8000
```

5. 确保：手机和电脑在同一 Wi-Fi；防火墙放通 `8000`。

---

## 6. iPhone 真机测试（USB）

### 6.1 一次性准备

1. iPhone 打开“开发者模式”（iOS 16+）。
2. Xcode 登录你的 Apple ID（免费开发者账号也可）。
3. 首次编译前执行：

```bash
cd /Users/cc/jishev2/nebulaguard/mobile/flutter_app
open ios/Runner.xcworkspace
```

4. 在 Xcode -> Runner -> Signing & Capabilities：
   - Team 选择你的 Apple ID
   - Bundle Identifier 改成唯一值（如 `com.cc.nebulaguard`）

### 6.2 命令行运行

```bash
flutter run -d <iphone_device_id> --dart-define=API_BASE_URL=http://192.168.1.24:8000
```

> iPhone 真机也要用电脑局域网 IP，不可用 `127.0.0.1`。

---

## 7. 网络地址映射速查表

- Android 模拟器 -> 后端：`http://10.0.2.2:8000`
- iOS 模拟器 -> 后端：`http://127.0.0.1:8000`
- Android / iPhone 真机 -> 后端：`http://<你的电脑局域网IP>:8000`

查看本机 IP：

```bash
ipconfig getifaddr en0
```

---

## 8. 最小联调清单（你可以照着点）

1. 注册账号（带社区名）
2. 登录成功
3. 进入“上报”Tab 提交一条地震上报
4. 进入“群聊”Tab 发消息并勾选 AI 跟进
5. 进入“AI助手”Tab 单独提问
6. 进入“报平安”Tab 提交“平安/需要救援”
7. 进入“社区”Tab 查看事件与避难点数据

---

## 9. 常见报错与排查

## 9.1 `flutter: command not found`

未安装 Flutter 或 PATH 未生效。重新打开终端后运行 `flutter --version`。

## 9.2 Android 报 `Connection refused`

常见原因：

- 后端没启动
- 地址写成 `127.0.0.1`（Android 模拟器应改 `10.0.2.2`）
- 电脑防火墙拦截 `8000`

## 9.3 iOS 真机签名失败

- 未在 Xcode 设置 Team
- Bundle Identifier 重复
- 设备未信任开发证书

## 9.4 `MissingPluginException`

执行：

```bash
flutter clean
flutter pub get
flutter run
```

## 9.5 依赖冲突

```bash
flutter pub upgrade
```

---

## 10. 打包命令（发布前）

## 10.1 Android APK

```bash
cd /Users/cc/jishev2/nebulaguard/mobile/flutter_app
flutter build apk --release --dart-define=API_BASE_URL=https://your-api-domain
```

产物：`build/app/outputs/flutter-apk/app-release.apk`

## 10.2 Android App Bundle

```bash
flutter build appbundle --release --dart-define=API_BASE_URL=https://your-api-domain
```

产物：`build/app/outputs/bundle/release/app-release.aab`

## 10.3 iOS Release

```bash
flutter build ios --release --dart-define=API_BASE_URL=https://your-api-domain
```

然后用 Xcode Archive 上传 TestFlight。

---

## 11. 本项目建议测试顺序（最稳）

1. 后端先启动并确认 `/health` 正常
2. Android 模拟器跑通
3. iOS 模拟器跑通
4. Android 真机跑通
5. iPhone 真机跑通
6. 最后再做 release 构建
