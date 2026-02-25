# NebulaGuard 当前进度 Spec（2026-02-24）

## 1. 目标与范围

当前阶段目标：

1. 将救援链路从 YOLO/火灾语义迁移为**地震 + VLM**主链路。
2. 建立“分析 -> 自动调度 -> 事件工单 -> 时间轴”闭环。
3. 保持旧 `/rescue/fire/*` 接口短期兼容，不破坏已有调用。
4. 优化主站体验（多工作区分屏、聊天独立滚动、地图放大、自动调度可视化）。

---

## 2. 当前总体状态

- 后端健康：`/health` 返回 `ok`。
- 前端状态：`npm run lint` / `npm run build`（frontend）可通过。
- 救援主链路：已切换为 `POST /rescue/earthquake/analyze`。
- 自动调度：分析完成后自动执行，结果入库并广播。
- 数据层：SQLite 已新增 `earthquake_rescue_analyses`、`dispatch_agent_runs`。
- 交互文档：已补充管理端交互指南，支持新手按步骤走完整闭环。

---

## 3. 已完成（Done）

### 3.1 地震 VLM 救援主链路

- 新增服务：`backend/services/earthquake_vlm_rescue.py`。
- 输入多图后进行 VLM 结构化识别。
- 支持受灾目标 `bbox_norm` 归一化校验与纠偏。
- 支持后端标注图生成并返回 `annotated_image_url`。
- 聚合输出：`scene_overview / victims / routes / command_notes / image_findings`。
- 新增算法层：`priority_score`、热点聚类、复杂度指数、覆盖率评估。

### 3.2 兼容发布策略

- 新增接口：
  - `POST /rescue/earthquake/analyze`
  - `GET /rescue/earthquake/analyses`
- 旧接口保留代理（deprecated）：
  - `POST /rescue/fire/analyze`
  - `GET /rescue/fire/analyses`
- WS 新增：`earthquake_rescue_analysis`，并保留兼容 `fire_rescue_analysis`。

### 3.3 自动调度 Agent（全自动）

- 新增服务：`backend/services/dispatch_agent.py`。
- 分析完成后自动触发调度执行器。
- 幂等键：`analysis_id + version`。
- 自动落地：incident / task / dispatch。
- 全量写入：`dispatch_agent_runs`、`audit_logs`、`ops_timeline_events`。
- WS 新增：`dispatch_agent_executed`。

### 3.4 管理端 UI 升级（主站 `/`）

- 左侧 rail 改为可交互工作区：总览 / 调度 / 社区（多页分区体验）。
- 右侧新增悬停抽屉工作台：`指挥终端 / 社区群聊 / 地震搜救` 从右侧滑出，可固定展开。
- 聊天区域改为独立滚动窗口，输入区固定，整页恢复自然滚动。
- 地图默认缩放提升至近景（社区中心可配置）。
- 救援面板语义迁移为“地震受灾搜救分析”。
- 任务看板重构为 4 状态分栏（待接单/已接单/处理中/已完成），支持按优先级排序和快速推进状态。
- Agent 面板改为纯数据轨迹显示（状态/产出/错误/时间），移除说明型文案。
- 恢复移动端 Web 上报入口（含图片上传与避险建议返回），与 Flutter 客户端并行可用。

### 3.5 文档补齐（本轮）

- 新增交互文档：`docs/interaction/web-interaction-guide.md`
- 更新功能文档：`docs/功能文档.md`（含项目实用价值说明）
- 更新治理规范：`AGENT.md`

---

## 4. 进行中（In Progress）

1. Flutter 端对新救援语义与自动调度结果的展示对齐。
2. 自动调度策略分级（全自动 / 审批后执行）开关设计。
3. README 中历史文案持续去旧语义（fire/YOLO）收尾。

---

## 5. 待做（Todo）

1. 自动调度回滚工具（按 run_id 撤销本次自动创建项）。
2. 调度约束可配置化（每社区任务上限、队伍白名单）。
3. 调度冲突检测（同队伍多任务并发冲突）。
4. 地图叠加危险区与路线阻断联动展示。
5. 事件复盘导出（Markdown/PDF）。
6. Agent 执行轨迹支持按 incident_id 过滤与反查。

---

## 6. 技术债与风险

1. 仍为 SQLite，社区并发上升后需要 PostgreSQL 迁移。
2. VLM 输出受模型稳定性影响，需要持续完善 schema 校验。
3. 自动执行为高风险操作，需加强审批与风控阈值。
4. 多图串行推理时延偏高，后续应改并发与缓存。

---

## 7. 里程碑

### M2（已完成）

- 地震 VLM 分析与标注图主链路上线。
- 自动调度 Agent 执行与审计链路上线。
- Web 主站核心体验改造完成。

### M3（下一阶段）

- 调度审批开关 + 回滚能力。
- Flutter 端完整接入实时调度结果。
- 地图风险区/阻断信息联动。

### M4（中期）

- PostgreSQL 迁移与性能基线。
- 权限细粒度化（RBAC + 操作级授权）。

---

## 8. 验收标准（当前阶段）

1. 新接口可稳定输出地震 VLM 识别结果与标注图 URL。
2. 分析后自动生成事件/任务/调度并可在 UI 看见。
3. 同一分析重复触发不会重复派单（幂等）。
4. 聊天窗口不再拉长整页，工作区切换清晰可用，地图首屏更聚焦。
5. lint/build/py_compile 通过。

---

## 9. 后续功能扩展方案（供评审）

1. 余震风险热力图（按时间窗刷新）。
2. 楼栋级搜救覆盖率与盲区提示。
3. 失联人员与报平安自动对账。
4. 队伍负载均衡与疲劳阈值告警。
5. 物资消耗预测（4h/8h）。
6. 避难点拥挤度预测与分流推荐。
7. 多渠道通知（App/短信/语音）统一回执。
8. 演练沙盘回放与评分系统。
9. SOP 模板化一键下发。
10. 指挥复盘自动报告（Markdown/PDF）。
