# NebulaGuard 架构与模块框架图（用于文档插图）

本文件用于《软件应用与开发类作品设计和开发文档》中的“概要设计”和“详细设计”章节配图。

建议插入位置：
- 图A：放在《概要设计》第一段后，作为总体架构图
- 图B：放在《详细设计》中“Web 指挥终端”段落后
- 图C：放在《详细设计》中“移动端上报与建议”段落后
- 图D：放在《详细设计》中“一键预警与社区触达”段落后
- 图E：放在《详细设计》中“AI 到调度闭环监管”段落后

---

## 图A 总体架构（Web + Mobile + AI + 数据）

```mermaid
flowchart TB
  subgraph Client[接入层]
    W[Web 指挥终端]
    M[Flutter 居民端]
  end

  subgraph Service[业务服务层 FastAPI]
    A[认证与社区服务]
    R[地震上报服务]
    C[社区聊天与通知]
    I[事件与任务服务]
    D[调度与资源服务]
    WS[WebSocket 实时通道]
  end

  subgraph AI[智能决策层]
    V[VLM 图像理解]
    G[自动调度 Agent]
  end

  subgraph Data[数据与治理层]
    DB[(SQLite 业务数据)]
    FS[上传文件存储]
    AU[审计日志]
    TL[复盘时间轴]
  end

  W --> A
  W --> I
  W --> D
  W --> C
  M --> A
  M --> R
  M --> C
  R --> V
  V --> G
  G --> I
  G --> D
  A --> DB
  R --> DB
  C --> DB
  I --> DB
  D --> DB
  R --> FS
  I --> AU
  D --> AU
  I --> TL
  D --> TL
  WS --> W
  WS --> M
  C --> WS
  I --> WS
  D --> WS
```

---

## 图B Web 指挥终端模块框架

```mermaid
flowchart LR
  subgraph Web[Web 指挥终端]
    O[总览工作区]
    T[调度工作区]
    S[社区工作区]
    P[右侧操作面板]
  end

  subgraph Overview[总览]
    MAP[地图态势]
    KPI[核心指标]
    LIVE[实时动态]
  end

  subgraph Dispatch[调度]
    INC[事件中心]
    TASK[任务看板]
    AG[Agent 轨迹]
  end

  subgraph Community[社区]
    CHAT[社区群聊]
    NOTICE[通知回执]
    WARN[一键预警]
  end

  O --> MAP
  O --> KPI
  O --> LIVE
  T --> INC
  T --> TASK
  T --> AG
  S --> CHAT
  S --> NOTICE
  S --> WARN
  P --> CHAT
  P --> WARN
```

---

## 图C 移动端“上报-建议-反馈”框架

```mermaid
flowchart TD
  U1[居民登录社区] --> U2[提交地震上报]
  U2 --> U3[上传房间构造/周边环境图片]
  U3 --> U4[后端校验并触发 VLM]
  U4 --> U5[返回避险建议 Markdown]
  U5 --> U6[移动端打字机式渲染]
  U6 --> U7[居民反馈与群聊补充]
  U7 --> U8[指挥端更新任务与通知]
```

---

## 图D 一键预警与社区触达框架

```mermaid
flowchart LR
  A[管理端点击一键预警] --> B[后端写入社区预警记录]
  B --> C[WebSocket 广播预警事件]
  C --> D[移动端弹窗提醒]
  C --> E[Web 通知状态更新]
  D --> F[居民确认/回执]
  F --> G[回执统计与复盘]
```

---

## 图E AI 到调度闭环监管框架

```mermaid
flowchart TD
  X1[现场图片与文本上报] --> X2[VLM 输出结构化风险建议]
  X2 --> X3[调度 Agent 读取队伍与任务状态]
  X3 --> X4[生成 incident/task/dispatch]
  X4 --> X5[写库并生成审计日志]
  X5 --> X6[前端看板实时更新]
  X6 --> X7[执行反馈回流时间轴]
```

