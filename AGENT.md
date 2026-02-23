# NebulaGuard 项目治理规范（AGENT.md）

## 1. 角色职责

## 1.1 Product Owner

- 定义应急业务目标与优先级。
- 审批里程碑与验收标准。

## 1.2 Backend Agent

- 负责 FastAPI 接口、数据模型、鉴权、WebSocket 事件。
- 保证新增接口不破坏已有接口兼容性。

## 1.3 Frontend Agent（Web 管理端）

- 负责 `/` 指挥台交互体验与信息结构。
- 按设计令牌执行 UI，禁止模板化泛蓝科技风。

## 1.4 Mobile Agent（Flutter）

- 负责用户端上报、群聊、报平安、社区态势。
- 确保 Android/iOS 模拟器与真机可运行。

## 1.5 QA Agent

- 维护接口测试清单、回归清单、发布门禁。

---

## 2. 分支与提交规范

1. 分支命名：`codex/<area>-<short-topic>`
   - 例：`codex/backend-incident-workflow`
2. 提交粒度：单一主题；禁止“超大杂糅提交”。
3. 提交信息建议：
   - `feat(backend): add incident and task workflow APIs`
   - `feat(frontend): add incident board and timeline rail`
   - `docs: add flutter testing guide`

---

## 3. 接口变更规范

1. 新增接口优先，避免直接删除旧接口。
2. 变更前更新：
   - `docs/spec/current-progress.spec.md`
   - `README.md`（如有外部可见变化）
3. 返回字段新增需向后兼容。
4. 高风险变更必须附带回滚路径。

---

## 4. 数据库变更规范（SQLite 当前）

1. 仅追加表/列/索引，避免破坏旧表。
2. 表结构变更需同步更新：
   - `backend/services/storage.py`
   - 对应 API 入参与出参映射
3. 索引原则：
   - 查询高频条件优先（如 `community_id + created_at`）
   - 任务检索加状态索引（`incident_id,status,priority`）
4. 生产化前准备 Alembic 迁移策略。

---

## 5. Definition of Done（DoD）

一个功能仅在以下全部满足时视为完成：

1. 代码实现 + 最小文档更新。
2. 接口错误处理完整（4xx/5xx 可解释）。
3. 审计日志记录关键写操作。
4. WebSocket 对应事件可回放（若该功能涉及实时更新）。
5. 通过以下校验：
   - `python -m py_compile backend/main.py backend/services/storage.py`
   - `npm run lint --prefix frontend`
   - `npm run build --prefix frontend`

---

## 6. UI 评审清单

1. 颜色层级清晰，状态色只用于告警。
2. 字体层级明确（标题/正文/等宽数据）。
3. 信息密度高但不拥挤，卡片结构一致。
4. 动效克制（150-250ms）并支持 `prefers-reduced-motion`。
5. 关键操作可达（按钮、focus、错误提示明确）。

---

## 7. 发布清单

1. 后端健康检查通过：`/health`。
2. 前端 build 通过。
3. Flutter 端至少 1 台模拟器 + 1 台真机验证。
4. 关键链路验证：
   - 上报 -> 通知 -> 聊天 -> 事件 -> 任务 -> 回执 -> 时间轴
5. 更新文档：
   - `docs/spec/current-progress.spec.md`
   - `docs/mobile/flutter-testing-guide.md`（如移动端流程变化）

---

## 8. 风险控制约定

1. 未经明确确认，不做 destructive 数据操作。
2. 敏感配置（token/key）仅通过 `.env` 注入，不硬编码。
3. 新增外部依赖需说明必要性与回滚方案。
