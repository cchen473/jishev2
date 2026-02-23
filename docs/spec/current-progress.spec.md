# NebulaGuard 当前进度 Spec（2026-02-23）

## 1. 目标与范围

本 Spec 对齐一期目标：

1. 文档补齐（移动端测试 + YOLO实现说明 + 项目治理）。
2. 在现有系统基础上扩展为“应急闭环增强”能力。
3. 保持现有 API 兼容，新增能力通过新接口提供。

---

## 2. 当前总体状态

- 后端健康：`/health` 返回 `ok`。
- 前端状态：`npm run lint --prefix frontend` / `npm run build --prefix frontend` 可通过。
- 数据层：SQLite 已承载认证、社区、聊天、通知、地震上报、YOLO 分析。
- 移动端：Flutter 社区端已具备运行源码，需执行 `flutter create .` 生成平台目录。

---

## 3. 已完成（Done）

## 3.1 核心业务（既有）

- 用户注册/登录与社区绑定。
- 地震上报与社区通知广播。
- 社区群聊与 AI 助手问答。
- 火灾鸟瞰图 YOLO 检测与救援建议。

## 3.2 新增闭环能力（本次）

- 事件中心：`incidents`（创建/查询/更新）。
- 任务工单：`incident_tasks`（创建/查询/流转）。
- 救援队伍：`response_teams` + `team_memberships`。
- 资源调度：`dispatch_records`。
- 居民回执：`resident_checkins` + 统计接口。
- 失联人员：`missing_person_reports`。
- 避难点容量：`shelters` + `shelter_occupancy_events`。
- 风险区标绘：`hazard_zones`。
- 道路阻断：`road_blocks`。
- 通知模板：`community_notification_templates`。
- 通知回执：`notification_receipts`。
- 审计日志与复盘：`audit_logs` + `ops_timeline_events`。

## 3.3 前端管理端（本次）

- 新增事件中心组件 `IncidentBoard`。
- 新增工单看板组件 `TaskKanban`。
- 新增复盘时间轴 `TimelineRail`。
- 新增通知回执面板 `ReadReceiptPanel`。

## 3.4 Flutter 用户端（本次）

- 底部导航扩展为 5 Tab：上报、群聊、AI助手、报平安、社区。
- 群聊增强：快捷短语 chips + 更清晰消息卡片。
- 新增报平安页：支持状态上报和社区摘要。
- 新增社区页：事件/避难点可视化列表。

---

## 4. 进行中（In Progress）

1. Flutter 真机联调（依赖本机 Flutter/Xcode/Android SDK 环境）。
2. 管理端与移动端的实时链路统一（移动端当前聊天仍是轮询）。
3. 通知回执在管理端的统计可视化（已具备接口，图形化待加强）。

---

## 5. 待做（Todo）

1. 将 Flutter 聊天从轮询改为 WebSocket 推送。
2. 任务调度规则引擎（自动派单、超时升级、冲突检测）。
3. 风险区/道路阻断地图交互编辑（拖拽点、撤销重做）。
4. 失联人员地图追踪与批量指派。
5. 复盘导出（PDF/Markdown）与演练评分。
6. 数据库从 SQLite 平滑迁移 PostgreSQL（生产化）。

---

## 6. 技术债与缺口

1. 数据库 migration 体系缺失（当前为启动时建表）。
2. 缺少统一 RBAC 权限模型（现阶段社区级权限为主）。
3. 缺少后端自动化测试（pytest）覆盖。
4. Flutter 端无集成测试脚本（`integration_test` 需补齐）。
5. 大量业务事件暂未做幂等键控制。

---

## 7. 风险清单

1. 模型/推理风险：YOLO CPU 推理在多图场景可能延迟较高。
2. 规模风险：SQLite 在高并发下吞吐受限。
3. 运维风险：真机联调依赖局域网与本地防火墙配置。
4. 安全风险：当前审计可用，但细粒度权限仍需强化。

---

## 8. 里程碑

## M1（已完成）

- 单灾种（地震）指挥闭环可跑通。
- 社区聊天 + AI 助手 + YOLO 分析上线。

## M2（已完成）

- 事件-任务-调度-回执-复盘的数据结构与 API 落地。
- 管理端新增事件板、工单看板、时间轴与回执面板。

## M3（目标）

- Flutter WebSocket 实时化。
- 路线阻断与风险区地图编辑器上线。
- 自动派单策略上线。

## M4（目标）

- PostgreSQL 迁移。
- 权限模型与审计合规加强。
- 压测与发布基线建立。

---

## 9. 验收标准（一期）

1. 新增接口可正常 CRUD 并可在 WebSocket 观察到关键事件。
2. 管理端可创建事件、创建任务、推进任务状态、查看时间轴。
3. 用户端可提交报平安并在管理端统计看到变化。
4. 文档可指导新手完成 Flutter 模拟器+真机测试。
5. lint/build/py_compile 全通过，不破坏既有功能。

---

## 10. 版本节奏建议

- `v2.1`：闭环能力最小可用（本次）。
- `v2.2`：移动端实时化 + 地图交互编辑。
- `v2.3`：自动派单 + 复盘导出 + 压测。
- `v3.0`：数据库升级 + 权限体系 + 生产化部署。
