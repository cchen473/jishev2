# NebulaGuard 项目治理规范（AGENT.md）

## 1. 角色职责

### 1.1 Product Owner

- 定义灾种范围、业务优先级与验收标准。
- 审批里程碑与高风险变更（自动执行、权限、数据迁移）。

### 1.2 Backend Agent

- 负责 FastAPI、数据模型、鉴权、WebSocket 事件。
- 保证新接口向后兼容，旧接口通过 deprecated 周期平滑迁移。

### 1.3 Frontend Agent（Web 管理端）

- 负责 `/` 指挥台的信息架构与可操作性。
- 统一设计令牌，避免模板化“AI 科技蓝”风格漂移。

### 1.4 Mobile Agent（Flutter 用户端）

- 负责上报、群聊、报平安、社区态势与调度回执可视化。
- 确保 Android/iOS 模拟器与真机联调可复现。

### 1.5 QA Agent

- 维护回归清单、接口门禁、发布验收记录。

---

## 2. 分支与提交规范

1. 分支命名：`codex/<area>-<short-topic>`。
2. 每次提交只做单一主题，避免大杂糅提交。
3. 建议提交格式：
   - `feat(backend): add earthquake vlm rescue pipeline`
   - `feat(frontend): add auto dispatch panel and chat viewport`
   - `docs: update spec and rescue implementation`

---

## 3. 接口变更规范

1. 新增优先，删除/改名需经过兼容周期。
2. 对外字段新增必须向后兼容。
3. 接口变更需同步更新：
   - `docs/spec/current-progress.spec.md`
   - 相关使用文档（README/模块文档）
4. 高风险变更必须提供回滚路径。

---

## 4. 自动执行 Agent 治理规则（强制）

1. **幂等**：自动执行必须使用稳定幂等键（如 `analysis_id + version`）。
2. **上限**：单次自动创建任务必须有上限（默认 <= 6）。
3. **资源约束**：不得分配不存在的队伍/资源。
4. **状态保护**：不得覆盖 `completed` 状态任务。
5. **审计必填**：每次自动执行必须写入 `dispatch_agent_runs` + `audit_logs` + `ops_timeline_events`。
6. **失败回退**：LLM 失败时必须降级到启发式方案，不允许直接 500。

---

## 5. 模型配置规范

1. 统一使用环境变量：
   - `OPENAI_API_KEY`
   - `OPENAI_BASE_URL`
   - `OPENAI_MODEL`
   - `OPENAI_VLM_MODEL`
2. 代码中禁止硬编码模型名与密钥。
3. 新增模型能力时必须提供降级策略与错误可解释信息。

---

## 6. 灾种语义一致性规范

1. 当前主灾种为地震，前后端文案与事件类型需一致。
2. 旧 `fire` 路径仅作为兼容层，需明确 `deprecated` 标记。
3. 新业务不得再引入 YOLO/火灾语义到主链路。

---

## 7. 交互与信息架构规范

1. 管理端必须保持“多工作区”结构（总览/调度/社区），避免单页无限堆叠。
2. 长内容区（聊天、日志、通知）必须使用独立滚动容器，禁止撑高整页。
3. 指挥终端/社区群聊/地震搜救统一使用右侧悬停抽屉，支持固定/取消固定状态。
4. 生产界面文案禁止“教学式说明”，仅保留功能标签、状态、时间、数量等可执行信息。
5. 任何新增功能都需补充用户交互说明，至少更新：
   - `docs/interaction/web-interaction-guide.md`
   - `docs/功能文档.md`

---

## 8. 算法功能迭代规范

1. 新算法输出必须“可解释”（含评分依据或模型字段说明）。
2. 算法结果必须可视化到前端（不能只落库不可见）。
3. 算法变更需验证回归：
   - 输出字段向后兼容
   - 无模型时可降级
   - 不引入 500 错误链
4. 建议至少包含一项可量化指标（如复杂度、覆盖率、热点强度）。

---

## 9. 数据库变更规范（SQLite 当前）

1. 仅追加表/列/索引，不破坏旧结构。
2. 结构更新需同步：
   - `backend/services/storage.py`
   - 对应 API 输入输出映射
3. 索引优先覆盖：
   - `community_id + created_at`
   - `incident_id + status + priority`

---

## 10. Definition of Done（DoD）

功能完成必须满足：

1. 代码实现 + 最小可用文档。
2. 错误处理完整（4xx/5xx可解释）。
3. 关键写操作有审计记录。
4. 涉及实时更新的能力有 WS 事件可验证。
5. 通过校验：
   - `python -m py_compile backend/main.py backend/services/storage.py backend/services/earthquake_vlm_rescue.py backend/services/dispatch_agent.py`
   - `npm run lint --prefix frontend`
   - `npm run build --prefix frontend`

---

## 11. UI 评审清单

1. 颜色层级清晰，状态色仅用于告警。
2. 聊天/日志等高频区保持独立滚动，不拉长整页。
3. 地图与任务区的主次关系明确，避免视觉噪音。
4. 动效克制并支持 `prefers-reduced-motion`。
5. 按钮、输入、焦点态可达且一致。

---

## 12. 发布清单

1. `/health` 通过。
2. 前端构建通过。
3. 核心链路走通：
   - 图像分析 -> 自动调度 -> 事件工单 -> 通知/时间轴
4. 文档同步完成：
   - `docs/spec/current-progress.spec.md`
   - `docs/rescue/vlm-earthquake-rescue-implementation.md`
   - `AGENT.md`

---

## 13. 安全与风险约定

1. 未经明确确认，不做 destructive 数据操作。
2. 密钥只能通过 `.env` 注入，不得入库或写死代码。
3. 自动执行默认开启时，必须具备审计与可追溯性。
