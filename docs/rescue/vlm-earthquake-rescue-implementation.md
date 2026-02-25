# 地震 VLM 受灾搜救实现细节

## 1. 文档范围

本文描述当前主链路：**地震场景 VLM 图像理解 + 标注图生成 + 自动调度 Agent 执行**。

关键代码入口：

- 分析服务：`/Users/cc/jishev2/nebulaguard/backend/services/earthquake_vlm_rescue.py`
- 调度服务：`/Users/cc/jishev2/nebulaguard/backend/services/dispatch_agent.py`
- API 编排：`/Users/cc/jishev2/nebulaguard/backend/main.py`
- 存储落库：`/Users/cc/jishev2/nebulaguard/backend/services/storage.py`

---

## 2. 模型来源与配置

当前通过 OpenAI 兼容接口接入 qwen3-vl-plus（或同类 VLM）：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_VLM_MODEL`

默认场景是**地震搜救**，要求模型只输出结构化 JSON。

---

## 3. 输入校验与预处理

接口：`POST /rescue/earthquake/analyze`

输入字段：

- `description`（可空）
- `lat` / `lng`（可空）
- `images[]`（至少 1 张，最多 `MAX_RESCUE_IMAGES`）

预处理流程：

1. 校验图片 MIME 类型，拒绝 HEIC/HEIF。
2. 校验单图大小（`MAX_UPLOAD_MB`）。
3. 使用 `PIL.Image.verify()` 做有效性校验。
4. 原图保存到 `uploads/earthquake_images/`。
5. 构造模型输入：`name + bytes + mime + url`。

---

## 4. VLM 推理与结构化解析

单图推理提示词要求模型严格返回 JSON，核心字段：

- `scene_risk_summary`
- `victims[]`：`bbox_norm`、`confidence`、`condition`、`position_hint`、`priority`
- `search_routes[]`
- `rescue_routes[]`

解析策略：

1. 支持从纯文本或 ```json 代码块提取 JSON。
2. 对 `bbox_norm` 做 `0~1` clamp 与合法性修正（防止越界/反向坐标）。
3. 对路线和步骤做长度、数量限制。
4. 模型输出异常时进入降级（不抛 500）。

---

## 5. 后处理与标注图生成

实现位置：`EarthquakeVLMRescueAnalyzer._build_annotation_image`

流程：

1. 读取原图并做 EXIF 矫正。
2. 将 `bbox_norm` 还原为像素坐标。
3. 绘制框、编号、置信度标签。
4. 保存到 `uploads/earthquake_annotations/`。
5. 返回 `annotated_image_url`。

每张图最终会产出：

- `original_image_url`
- `annotated_image_url`
- `detections[]`
- `detected_people`

---

## 6. 风险评分与结果聚合

受灾目标聚合结果字段（`analysis.victims[]`）：

- `id`
- `position_hint`
- `priority`
- `risk_level`（按置信度映射高/中）
- `condition`
- `bbox_norm`
- `image_url`
- `annotated_image_url`

路线聚合结果字段（`analysis.routes[]`）：

- `route_type`：`search` / `rescue`
- `name`
- `risk`
- `recommended_team`
- `steps[]`

总报告对象：

- `scene_overview`
- `victims`
- `routes`
- `command_notes`
- `image_findings`

---

## 7. 自动调度 Agent 执行

触发时机：每次地震图像分析完成后自动触发。

执行器：`execute_dispatch_agent_for_analysis` + `DispatchAgentPlanner`

执行步骤：

1. 使用 `analysis_id + version` 做幂等键（重复请求不重复派单）。
2. 读取社区快照（incident/task/team/dispatch）。
3. 生成计划（LLM 优先，失败回退启发式）。
4. 直接写入事件、任务、调度记录。
5. 落审计日志 + 时间轴 + WebSocket 广播。

保护规则：

- 单次任务创建上限 6。
- 不分配不存在队伍。
- 已完成任务不允许被自动覆盖。

---

## 8. 接口与事件

REST：

- `POST /rescue/earthquake/analyze`
- `GET /rescue/earthquake/analyses`
- `GET /dispatch-agent/runs`

兼容（Deprecated）：

- `POST /rescue/fire/analyze`（代理到地震接口）
- `GET /rescue/fire/analyses`（读取同源数据）

WebSocket：

- `earthquake_rescue_analysis`
- `dispatch_agent_executed`
- 兼容：`fire_rescue_analysis`

---

## 9. 降级策略

以下情况不会中断主流程：

1. 模型响应非 JSON。
2. 单张图片无法解析。
3. 标注图生成失败。
4. LLM 调度失败。

降级表现：

- `analysis_status=degraded` 或 `mock`
- 返回可执行的基础路线与提示
- 自动调度回退为启发式策略

---

## 10. 性能与稳定性建议

1. 多图并发推理（当前为串行，可引入并发池）。
2. 对重复图片建立 hash 缓存，避免重复调用 VLM。
3. 对超大图先限边压缩，降低推理耗时与 token 成本。
4. 标注图可异步写盘，缩短接口首包延迟。
5. 为调度 Agent 增加人工审批开关（生产环境建议）。

---

## 11. 验证清单

1. 上传单图/多图，返回包含 `annotated_image_url`。
2. 模型异常输入时接口不 500，返回降级结果。
3. 同一 `analysis_id` 重复触发，不重复创建任务。
4. WebSocket 能收到 `earthquake_rescue_analysis` 与 `dispatch_agent_executed`。
