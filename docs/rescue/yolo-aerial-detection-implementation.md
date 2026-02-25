# 鸟瞰图 YOLO 受灾群众检测实现细节（Deprecated）

> 状态：已废弃（2026-02-24 起不再作为主链路）  
> 当前主链路已切换为地震场景 VLM 分析，请优先阅读  
> `/Users/cc/jishev2/nebulaguard/docs/rescue/vlm-earthquake-rescue-implementation.md`

## 1. 文档范围

本文描述 NebulaGuard 中“火灾现场鸟瞰图受灾群众检测”后端实现，代码入口：

- YOLO 推理器：`/Users/cc/jishev2/nebulaguard/backend/utils/yolo_detector.py`
- 业务编排：`/Users/cc/jishev2/nebulaguard/backend/main.py`
- API 接口：`POST /rescue/fire/analyze`

目标：**原生 YOLO 检测 + 路线建议生成，不依赖 VLM。**

---

## 2. 模型来源与加载

## 2.1 模型文件来源

- 默认模型路径：`YOLO_MODEL_PATH=./backend/models/yolo11n.onnx`
- 默认下载地址：
  `YOLO_MODEL_URL=https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.onnx`

当本地不存在模型文件时，系统自动下载（优先 `requests`，回退 `urllib`）。

## 2.2 运行时依赖

- `onnxruntime`（CPUExecutionProvider）
- `numpy`
- `Pillow`

若 `onnxruntime` 不可用，流程进入降级策略，不会调用 VLM。

---

## 3. 检测流程总览

1. 接口接收 1~6 张鸟瞰图（表单字段 `images`）。
2. 每张图执行 YOLO(person) 检测。
3. 汇总所有候选人框，计算风险分数并排序。
4. 生成受困人员列表（victims）与救援路线建议（routes）。
5. 结果写入 `fire_rescue_analyses` 并通过 WebSocket 广播。

---

## 4. 图像预处理（Preprocess）

实现函数：`YoloPersonDetector._preprocess`

- 输入图转 RGB，并做 EXIF 方向矫正。
- 使用 letterbox 方式缩放到正方形输入（默认 640）。
- 背景填充值：`114`（YOLO 常用）。
- 输出张量格式：`NCHW`，值域归一化到 `[0,1]`。

关键参数：

- `YOLO_INPUT_SIZE`（默认 640）
- `YOLO_CONFIDENCE_THRESHOLD`（默认 0.30）
- `YOLO_IOU_THRESHOLD`（默认 0.45）
- `YOLO_MAX_DETECTIONS`（默认 80）

---

## 5. 推理与后处理（Postprocess）

## 5.1 输出解析

实现函数：`YoloPersonDetector._postprocess`

- 兼容不同 YOLO ONNX 输出形状（`[1,N,C]` / `[1,C,N]`）。
- 仅保留 COCO 的 `person` 类（class id 0）。
- 得分计算兼容两类输出：
  - 带 objectness：`objectness * class_score_person`
  - 不带 objectness：直接取 person score

## 5.2 边框还原

- `xywh -> xyxy`
- 逆 letterbox：去 pad 并除以 scale
- 坐标裁剪到图像边界

## 5.3 NMS

实现函数：`_nms`

- 按 score 降序
- IoU 超阈值抑制
- 只保留前 `max_detections`

---

## 6. 候选评分与风险分级

实现函数：`_analysis_from_yolo_detections`

每个检测框风险分数：

`risk_score = min(0.99, confidence * 0.72 + min(area_ratio * 4.5, 0.28))`

解释：

- `confidence`：模型对“人”的置信度
- `area_ratio`：框面积占整图比例（越大通常越近/越显著）

风险等级映射：

- `>= 0.62` -> 高
- `>= 0.45` -> 中
- 其余 -> 低

输出 victim 字段包含：

- `id`
- `position_hint`
- `priority`
- `evidence`
- `bbox_xyxy`
- `confidence`
- `center`
- `area_ratio`
- `risk_level`

---

## 7. 路线生成策略

实现函数：`_build_fire_routes`

- 无检测目标：返回“网格巡检 + 外围封控”路线。
- 有检测目标：
  - 取前 3 个高优先候选生成主线（突入线）。
  - 后续候选用于侧翼补盲线。

输出字段：

- `name`
- `steps[]`
- `risk`
- `recommended_team`

---

## 8. 降级策略（不使用 VLM）

实现函数：`heuristic_fire_rescue_analysis`

触发条件：

- 未上传图片
- `onnxruntime` 缺失
- 模型下载失败
- 全部图片无法解析
- 推理阶段异常

降级输出仍保证：

- 场景概览
- 两条基础路线
- 指挥备注（包含降级原因）

---

## 9. API 输入输出说明

## 9.1 输入（`POST /rescue/fire/analyze`）

- `description`（form，可空）
- `lat` / `lng`（form，可空）
- `images`（form 文件，至少 1 张，最多 `MAX_FIRE_IMAGES`）

约束：

- 文件必须 `image/*`
- 单图大小 <= `MAX_UPLOAD_MB`

## 9.2 输出（简化）

- `analysis_status`: `ok` / `degraded`
- `analysis_error`: 错误信息（可空）
- `result.analysis.scene_overview`
- `result.analysis.victims[]`
- `result.analysis.routes[]`
- `result.analysis.command_notes[]`
- `result.analysis.detection_summary[]`

---

## 10. 数据落库与广播

- 落库表：`fire_rescue_analyses`
- 同时创建社区通知：`community_notifications`
- WebSocket 广播：
  - `fire_rescue_analysis`
  - `community_alert`
  - `ops_timeline_event`

---

## 11. 性能与稳定性建议

1. 对同批图像采用并发推理（当前为串行，可升级线程池）。
2. 增加图像缓存键（hash）避免重复推理。
3. 大图先做分辨率上限压缩，降低 CPU 推理时延。
4. 在生产环境将 ONNXRuntime provider 升级为 CUDA（若 GPU 可用）。
5. 对检测结果增加去重策略（跨图同一目标聚合）。
6. 补充标注数据做灾害域微调（提升烟雾遮挡场景召回率）。

---

## 12. 可追溯代码清单

- 检测器类：`YoloPersonDetector`
- 关键函数：
  - `_preprocess`
  - `_postprocess`
  - `_nms`
  - `_analysis_from_yolo_detections`
  - `_build_fire_routes`
  - `run_fire_rescue_analysis`
- API：`fire_rescue_analyze`
