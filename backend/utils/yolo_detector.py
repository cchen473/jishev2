from __future__ import annotations

import io
import threading
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

try:
    import onnxruntime as ort
except Exception:  # pragma: no cover - optional runtime dependency
    ort = None

try:
    import requests
except Exception:  # pragma: no cover - optional runtime dependency
    requests = None


def _position_hint(center_x: float, center_y: float) -> str:
    if center_x < 0.33:
        h = "左侧"
    elif center_x > 0.66:
        h = "右侧"
    else:
        h = "中部"

    if center_y < 0.33:
        v = "上方"
    elif center_y > 0.66:
        v = "下方"
    else:
        v = "中段"

    if h == "中部" and v == "中段":
        return "画面中央区域"
    return f"画面{v}{h}区域"


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list[int]:
    if boxes.size == 0:
        return []

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []

    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        inter_w = np.maximum(0.0, xx2 - xx1)
        inter_h = np.maximum(0.0, yy2 - yy1)
        inter = inter_w * inter_h
        union = areas[i] + areas[order[1:]] - inter
        iou = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0.0)
        remained = np.where(iou <= iou_threshold)[0]
        order = order[remained + 1]

    return keep


class YoloPersonDetector:
    """YOLO ONNX detector focused on person (COCO class id 0)."""

    def __init__(
        self,
        *,
        model_path: Path,
        model_url: str | None,
        input_size: int = 640,
        confidence_threshold: float = 0.3,
        iou_threshold: float = 0.45,
        max_detections: int = 80,
    ) -> None:
        self.model_path = model_path
        self.model_url = (model_url or "").strip() or None
        self.input_size = int(max(320, min(input_size, 1280)))
        self.confidence_threshold = float(max(0.01, min(confidence_threshold, 0.99)))
        self.iou_threshold = float(max(0.05, min(iou_threshold, 0.95)))
        self.max_detections = int(max(1, min(max_detections, 300)))
        self._session: Any | None = None
        self._input_name: str | None = None
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return ort is not None

    def detect_people(self, image_bytes: bytes) -> dict[str, Any]:
        if ort is None:
            raise RuntimeError("onnxruntime 未安装，无法执行 YOLO 推理")
        session = self._ensure_session()
        if not image_bytes:
            return {"width": 0, "height": 0, "detections": []}

        with Image.open(io.BytesIO(image_bytes)) as img:
            rgb = ImageOps.exif_transpose(img).convert("RGB")
            orig = np.asarray(rgb)
        height, width = int(orig.shape[0]), int(orig.shape[1])
        if width <= 1 or height <= 1:
            return {"width": width, "height": height, "detections": []}

        tensor, scale, pad_w, pad_h = self._preprocess(orig)
        outputs = session.run(None, {self._input_name: tensor})
        detections = self._postprocess(
            outputs=outputs,
            width=width,
            height=height,
            scale=scale,
            pad_w=pad_w,
            pad_h=pad_h,
        )
        return {"width": width, "height": height, "detections": detections}

    def _ensure_model_file(self) -> None:
        if self.model_path.exists():
            return
        if not self.model_url:
            raise RuntimeError(f"YOLO 模型文件不存在: {self.model_path}")
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        payload = b""
        errors: list[str] = []

        if requests is not None:
            try:
                resp = requests.get(self.model_url, timeout=90)
                resp.raise_for_status()
                payload = resp.content
            except Exception as exc:  # pragma: no cover - network runtime
                errors.append(f"requests: {exc}")

        if not payload:
            try:
                with urllib.request.urlopen(self.model_url, timeout=90) as resp:
                    payload = resp.read()
            except Exception as exc:  # pragma: no cover - network runtime
                errors.append(f"urllib: {exc}")

        if not payload:
            detail = " | ".join(errors) if errors else "无可用下载方法"
            raise RuntimeError(f"下载 YOLO 模型失败：{detail}")
        self.model_path.write_bytes(payload)

    def _ensure_session(self) -> Any:
        with self._lock:
            if self._session is not None and self._input_name:
                return self._session
            self._ensure_model_file()
            self._session = ort.InferenceSession(  # type: ignore[union-attr]
                str(self.model_path),
                providers=["CPUExecutionProvider"],
            )
            self._input_name = self._session.get_inputs()[0].name
            return self._session

    def _preprocess(self, image: np.ndarray) -> tuple[np.ndarray, float, float, float]:
        h, w = image.shape[:2]
        target = self.input_size
        scale = min(target / h, target / w)
        new_w, new_h = int(round(w * scale)), int(round(h * scale))
        resized = np.array(
            Image.fromarray(image).resize((new_w, new_h), resample=Image.Resampling.BILINEAR)
        )
        canvas = np.full((target, target, 3), 114, dtype=np.uint8)
        pad_w = (target - new_w) / 2.0
        pad_h = (target - new_h) / 2.0
        left = int(np.floor(pad_w))
        top = int(np.floor(pad_h))
        canvas[top : top + new_h, left : left + new_w] = resized
        tensor = canvas.transpose(2, 0, 1).astype(np.float32)[None] / 255.0
        return tensor, scale, pad_w, pad_h

    def _postprocess(
        self,
        *,
        outputs: list[np.ndarray],
        width: int,
        height: int,
        scale: float,
        pad_w: float,
        pad_h: float,
    ) -> list[dict[str, Any]]:
        if not outputs:
            return []
        pred = outputs[0]
        if pred.ndim != 3:
            return []
        if pred.shape[1] < pred.shape[2]:
            pred = np.transpose(pred, (0, 2, 1))
        pred = pred[0]
        if pred.ndim != 2 or pred.shape[1] < 6:
            return []

        cols = pred.shape[1]
        boxes_xywh = pred[:, :4]

        if cols >= 85:
            objectness = pred[:, 4]
            class_scores = pred[:, 5:]
            person_scores = objectness * class_scores[:, 0]
        elif cols >= 84:
            class_scores = pred[:, 4:]
            person_scores = class_scores[:, 0]
        else:
            return []

        mask = person_scores >= self.confidence_threshold
        if not np.any(mask):
            return []

        boxes_xywh = boxes_xywh[mask]
        person_scores = person_scores[mask]

        xyxy = np.zeros_like(boxes_xywh, dtype=np.float32)
        xyxy[:, 0] = boxes_xywh[:, 0] - boxes_xywh[:, 2] / 2.0
        xyxy[:, 1] = boxes_xywh[:, 1] - boxes_xywh[:, 3] / 2.0
        xyxy[:, 2] = boxes_xywh[:, 0] + boxes_xywh[:, 2] / 2.0
        xyxy[:, 3] = boxes_xywh[:, 1] + boxes_xywh[:, 3] / 2.0

        xyxy[:, [0, 2]] = (xyxy[:, [0, 2]] - pad_w) / scale
        xyxy[:, [1, 3]] = (xyxy[:, [1, 3]] - pad_h) / scale
        xyxy[:, [0, 2]] = np.clip(xyxy[:, [0, 2]], 0, max(0, width - 1))
        xyxy[:, [1, 3]] = np.clip(xyxy[:, [1, 3]], 0, max(0, height - 1))

        keep = _nms(xyxy, person_scores, self.iou_threshold)[: self.max_detections]
        image_area = float(width * height)
        results: list[dict[str, Any]] = []
        for idx in keep:
            x1, y1, x2, y2 = xyxy[idx]
            w = float(max(0.0, x2 - x1))
            h = float(max(0.0, y2 - y1))
            center_x = float((x1 + x2) / 2.0 / width)
            center_y = float((y1 + y2) / 2.0 / height)
            area_ratio = (w * h / image_area) if image_area > 0 else 0.0
            results.append(
                {
                    "confidence": round(float(person_scores[idx]), 4),
                    "bbox_xyxy": [
                        int(round(float(x1))),
                        int(round(float(y1))),
                        int(round(float(x2))),
                        int(round(float(y2))),
                    ],
                    "center_x": round(center_x, 4),
                    "center_y": round(center_y, 4),
                    "area_ratio": round(float(area_ratio), 6),
                    "position_hint": _position_hint(center_x, center_y),
                }
            )
        return results
