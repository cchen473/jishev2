from __future__ import annotations

import base64
import io
import json
import math
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _extract_json_block(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    fenced = re.findall(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text)
    candidates = fenced + [text]
    for item in candidates:
        candidate = item.strip()
        if "{" not in candidate or "}" not in candidate:
            continue
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end < 0 or end <= start:
            continue
        chunk = candidate[start : end + 1]
        try:
            payload = json.loads(chunk)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _position_hint_from_bbox(bbox_norm: list[float]) -> str:
    x1, y1, x2, y2 = bbox_norm
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    if cx < 0.33:
        h = "左侧"
    elif cx > 0.66:
        h = "右侧"
    else:
        h = "中部"

    if cy < 0.33:
        v = "上方"
    elif cy > 0.66:
        v = "下方"
    else:
        v = "中段"

    if h == "中部" and v == "中段":
        return "画面中央区域"
    return f"画面{v}{h}区域"


def _normalize_bbox_norm(raw_bbox: Any) -> list[float] | None:
    if not isinstance(raw_bbox, list) or len(raw_bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(v) for v in raw_bbox]
    except Exception:
        return None
    x1 = _clamp(x1, 0.0, 1.0)
    y1 = _clamp(y1, 0.0, 1.0)
    x2 = _clamp(x2, 0.0, 1.0)
    y2 = _clamp(y2, 0.0, 1.0)
    if x2 <= x1:
        x2 = min(1.0, x1 + 0.02)
    if y2 <= y1:
        y2 = min(1.0, y1 + 0.02)
    if x2 <= x1 or y2 <= y1:
        return None
    return [round(x1, 4), round(y1, 4), round(x2, 4), round(y2, 4)]


def _normalize_routes(raw_routes: Any, route_type: str) -> list[dict[str, Any]]:
    if not isinstance(raw_routes, list):
        return []
    routes: list[dict[str, Any]] = []
    for idx, route in enumerate(raw_routes, 1):
        if not isinstance(route, dict):
            continue
        name = str(route.get("name") or f"{'搜索' if route_type == 'search' else '救援'}路线-{idx}").strip()
        risk = str(route.get("risk") or "存在余震与结构破坏风险").strip()
        recommended_team = str(route.get("recommended_team") or "综合搜救组").strip()
        raw_steps = route.get("steps")
        if isinstance(raw_steps, list):
            steps = [str(item).strip() for item in raw_steps if str(item).strip()]
        else:
            steps = []
        if not steps:
            steps = ["按就近安全入口推进并保持与指挥中心通信。"]
        routes.append(
            {
                "name": name[:80],
                "risk": risk[:280],
                "recommended_team": recommended_team[:80],
                "steps": steps[:8],
                "route_type": route_type,
            }
        )
    return routes[:6]


def _normalize_victims(raw_victims: Any, max_count: int) -> list[dict[str, Any]]:
    if not isinstance(raw_victims, list):
        return []
    victims: list[dict[str, Any]] = []
    for item in raw_victims:
        if not isinstance(item, dict):
            continue
        bbox_norm = _normalize_bbox_norm(item.get("bbox_norm"))
        if not bbox_norm:
            continue
        confidence = _clamp(float(item.get("confidence", 0.0) or 0.0), 0.0, 1.0)
        condition = str(item.get("condition") or "疑似受困").strip()[:120]
        position_hint = str(item.get("position_hint") or "").strip()[:120]
        if not position_hint:
            position_hint = _position_hint_from_bbox(bbox_norm)
        try:
            priority = int(item.get("priority", 0) or 0)
        except Exception:
            priority = 0
        victims.append(
            {
                "bbox_norm": bbox_norm,
                "confidence": round(confidence, 4),
                "condition": condition or "疑似受困",
                "position_hint": position_hint,
                "priority": priority if priority > 0 else 0,
            }
        )
    victims.sort(key=lambda row: (row["priority"] or 10_000, -row["confidence"]))
    return victims[:max_count]


def _condition_risk_weight(condition: str) -> float:
    text = (condition or "").strip()
    if not text:
        return 0.45
    high_keywords = ("重伤", "昏迷", "被困", "无法移动", "大量出血")
    medium_keywords = ("受伤", "行动受限", "呼救", "疑似")
    if any(word in text for word in high_keywords):
        return 0.9
    if any(word in text for word in medium_keywords):
        return 0.65
    return 0.5


def _bbox_area(bbox_norm: list[float]) -> float:
    if len(bbox_norm) != 4:
        return 0.0
    return max(0.0, bbox_norm[2] - bbox_norm[0]) * max(0.0, bbox_norm[3] - bbox_norm[1])


def _bbox_center(bbox_norm: list[float]) -> tuple[float, float]:
    if len(bbox_norm) != 4:
        return (0.5, 0.5)
    return ((bbox_norm[0] + bbox_norm[2]) / 2.0, (bbox_norm[1] + bbox_norm[3]) / 2.0)


def _priority_score(confidence: float, area: float, condition: str) -> float:
    condition_weight = _condition_risk_weight(condition)
    area_component = min(area * 4.0, 0.24)
    confidence_component = _clamp(confidence, 0.0, 1.0) * 0.58
    score = confidence_component + area_component + condition_weight * 0.18
    return round(_clamp(score, 0.05, 0.99), 4)


def _cluster_hotspots(victims: list[dict[str, Any]], threshold: float = 0.16) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for victim in victims:
        bbox = victim.get("bbox_norm")
        if not isinstance(bbox, list):
            continue
        cx, cy = _bbox_center(bbox)
        assigned = False
        for cluster in clusters:
            dx = cx - cluster["center_x"]
            dy = cy - cluster["center_y"]
            if math.hypot(dx, dy) <= threshold:
                cluster["victim_ids"].append(str(victim.get("id") or ""))
                cluster["priority_scores"].append(float(victim.get("priority_score", 0.0) or 0.0))
                cluster["center_x"] = (
                    cluster["center_x"] * (cluster["count"] / (cluster["count"] + 1))
                    + cx / (cluster["count"] + 1)
                )
                cluster["center_y"] = (
                    cluster["center_y"] * (cluster["count"] / (cluster["count"] + 1))
                    + cy / (cluster["count"] + 1)
                )
                cluster["count"] += 1
                assigned = True
                break
        if not assigned:
            clusters.append(
                {
                    "center_x": cx,
                    "center_y": cy,
                    "count": 1,
                    "victim_ids": [str(victim.get("id") or "")],
                    "priority_scores": [float(victim.get("priority_score", 0.0) or 0.0)],
                }
            )

    hotspots: list[dict[str, Any]] = []
    for idx, cluster in enumerate(clusters, 1):
        scores = cluster.get("priority_scores") or [0.0]
        intensity = float(sum(scores) / max(1, len(scores)))
        level = "high" if intensity >= 0.7 else "medium" if intensity >= 0.5 else "low"
        hotspots.append(
            {
                "id": f"H-{idx}",
                "center_norm": [round(cluster["center_x"], 4), round(cluster["center_y"], 4)],
                "victim_ids": [item for item in cluster.get("victim_ids", []) if item],
                "intensity": round(intensity, 4),
                "level": level,
            }
        )
    hotspots.sort(key=lambda item: (item["intensity"], len(item["victim_ids"])), reverse=True)
    return hotspots[:8]


def _spatial_dispersion(victims: list[dict[str, Any]]) -> float:
    if len(victims) < 2:
        return 0.0
    centers = []
    for victim in victims:
        bbox = victim.get("bbox_norm")
        if isinstance(bbox, list):
            centers.append(_bbox_center(bbox))
    if len(centers) < 2:
        return 0.0
    mx = sum(point[0] for point in centers) / len(centers)
    my = sum(point[1] for point in centers) / len(centers)
    distances = [math.hypot(point[0] - mx, point[1] - my) for point in centers]
    return float(sum(distances) / len(distances))


def _algorithm_metrics(victims: list[dict[str, Any]], routes: list[dict[str, Any]]) -> dict[str, Any]:
    hotspots = _cluster_hotspots(victims)
    avg_priority = (
        sum(float(item.get("priority_score", 0.0) or 0.0) for item in victims) / len(victims)
        if victims
        else 0.0
    )
    dispersion = _spatial_dispersion(victims)
    victim_factor = min(len(victims) / 12.0, 1.0)
    dispersion_factor = min(dispersion / 0.35, 1.0)
    complexity_score = (
        victim_factor * 0.38 + avg_priority * 0.37 + dispersion_factor * 0.25
    ) * 100

    route_count = len(routes)
    hotspot_factor = min(len(hotspots) / 5.0, 1.0)
    coverage_score = (
        0.5
        + min(route_count / max(1, len(victims) + 1), 1.0) * 0.28
        + hotspot_factor * 0.22
    ) * 100

    return {
        "rescue_complexity_index": round(_clamp(complexity_score, 0.0, 100.0), 2),
        "coverage_score": round(_clamp(coverage_score, 0.0, 100.0), 2),
        "avg_priority_score": round(_clamp(avg_priority, 0.0, 1.0), 4),
        "victim_dispersion": round(dispersion, 4),
        "hotspots": hotspots,
        "priority_model": "confidence+condition+bbox_area weighted scoring",
    }


@dataclass
class EarthquakeVLMRescueAnalyzer:
    api_key: str
    model: str
    base_url: str | None
    upload_dir: Path
    max_images: int = 6
    max_victims_per_image: int = 10

    def __post_init__(self) -> None:
        self.annotation_dir = (self.upload_dir / "earthquake_annotations").resolve()
        self.annotation_dir.mkdir(parents=True, exist_ok=True)

    def _build_fallback(self, *, description: str, lat: float | None, lng: float | None) -> dict[str, Any]:
        coord = f"{lat:.5f}, {lng:.5f}" if lat is not None and lng is not None else "未知坐标"
        return {
            "scene_overview": f"地震现场图像分析降级（{coord}），未得到稳定识别结果。",
            "victims": [],
            "routes": [
                {
                    "name": "S1-分区搜索路线",
                    "risk": "局部坍塌与余震风险",
                    "recommended_team": "搜救组A",
                    "route_type": "search",
                    "steps": [
                        "按网格分区推进并优先搜索建筑出入口与楼梯间。",
                        "每 3 分钟回传现场图像并更新搜索覆盖率。",
                    ],
                },
                {
                    "name": "R1-安全撤离路线",
                    "risk": "道路碎片和次生坠落风险",
                    "recommended_team": "转运组B",
                    "route_type": "rescue",
                    "steps": [
                        "确认外围通道后进行分批转运。",
                        "优先转移老人、儿童和行动受限人员。",
                    ],
                },
            ],
            "command_notes": [
                "当前为 VLM 降级建议，请尽快补充更清晰的鸟瞰图。",
                f"现场描述参考：{description or '无'}",
            ],
            "image_findings": [],
            "algorithm_metrics": {
                "rescue_complexity_index": 35.0,
                "coverage_score": 52.0,
                "avg_priority_score": 0.38,
                "victim_dispersion": 0.0,
                "hotspots": [],
                "priority_model": "fallback",
            },
        }

    def _request_image_analysis(
        self,
        *,
        image_bytes: bytes,
        image_mime: str,
        description: str,
        lat: float | None,
        lng: float | None,
    ) -> dict[str, Any]:
        if OpenAI is None:
            return {"status": "mock", "error": "OpenAI SDK 不可用"}
        if not (self.api_key or "").strip():
            return {"status": "mock", "error": "未配置模型 API Key"}

        prompt = (
            "你是地震应急图像分析模型。请识别图中疑似受灾人员并规划搜索与救援路线。"
            "必须只返回 JSON 对象，字段如下："
            "{"
            '"scene_risk_summary": string,'
            '"victims":[{"bbox_norm":[x1,y1,x2,y2],"confidence":0-1,"condition":string,"position_hint":string,"priority":int}],'
            '"search_routes":[{"name":string,"steps":[string],"risk":string,"recommended_team":string}],'
            '"rescue_routes":[{"name":string,"steps":[string],"risk":string,"recommended_team":string}]'
            "}。"
            "bbox_norm 使用归一化坐标（0-1），严禁输出额外文本。"
            f" 场景描述：{description or '无'}。"
            f" 坐标：{lat if lat is not None else '未知'}, {lng if lng is not None else '未知'}。"
        )
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        user_content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{encoded}"}},
        ]

        client_kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        client = OpenAI(**client_kwargs)
        completion = client.chat.completions.create(
            model=self.model,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": "你是地震应急视觉专家，输出必须是 JSON。",
                },
                {"role": "user", "content": user_content},
            ],
        )
        raw = completion.choices[0].message.content if completion.choices else ""
        payload = _extract_json_block(raw if isinstance(raw, str) else "")
        if not payload:
            return {"status": "degraded", "error": "模型输出不是可解析 JSON", "raw": raw}
        return {"status": "ok", "payload": payload, "raw": raw}

    def _build_annotation_image(
        self,
        *,
        image_bytes: bytes,
        detections: list[dict[str, Any]],
        image_name: str,
    ) -> str:
        with Image.open(io.BytesIO(image_bytes)) as image:
            rgb = ImageOps.exif_transpose(image).convert("RGB")
        width, height = rgb.size
        draw = ImageDraw.Draw(rgb)
        font = ImageFont.load_default()

        for idx, det in enumerate(detections, 1):
            bbox = det.get("bbox_norm") or [0.1, 0.1, 0.2, 0.2]
            x1 = int(round(float(bbox[0]) * width))
            y1 = int(round(float(bbox[1]) * height))
            x2 = int(round(float(bbox[2]) * width))
            y2 = int(round(float(bbox[3]) * height))
            draw.rectangle((x1, y1, x2, y2), outline=(238, 106, 95), width=3)
            confidence = float(det.get("confidence", 0.0))
            label = f"P{idx} {confidence:.2f}"
            if hasattr(draw, "textbbox"):
                text_box = draw.textbbox((0, 0), label, font=font)
                text_w = max(0, text_box[2] - text_box[0])
                text_h = max(0, text_box[3] - text_box[1])
            else:
                text_w, text_h = draw.textsize(label, font=font)
            text_top = max(0, y1 - text_h - 4)
            draw.rectangle((x1, text_top, x1 + text_w + 8, text_top + text_h + 4), fill=(22, 24, 30))
            draw.text((x1 + 4, text_top + 2), label, fill=(245, 235, 215), font=font)

        stem = Path(image_name).stem or "earthquake"
        filename = f"{stem}_{uuid.uuid4().hex[:10]}_annotated.jpg"
        save_path = self.annotation_dir / filename
        rgb.save(save_path, format="JPEG", quality=92)
        return f"/uploads/earthquake_annotations/{filename}"

    def analyze(
        self,
        *,
        community_id: str,
        description: str,
        lat: float | None,
        lng: float | None,
        images: list[dict[str, Any]],
    ) -> dict[str, Any]:
        _ = community_id
        fallback = self._build_fallback(description=description, lat=lat, lng=lng)
        if not images:
            return {"status": "degraded", "analysis": fallback, "error": "未提供可分析图片"}

        image_findings: list[dict[str, Any]] = []
        victims: list[dict[str, Any]] = []
        routes: list[dict[str, Any]] = []
        command_notes: list[str] = []
        errors: list[str] = []

        for image_idx, image in enumerate(images[: self.max_images], 1):
            image_name = str(image.get("name") or f"image-{image_idx}")
            image_url = str(image.get("url") or "")
            raw = image.get("bytes")
            if not isinstance(raw, (bytes, bytearray)) or not raw:
                errors.append(f"{image_name}: 图片内容为空")
                continue
            mime = str(image.get("mime") or "image/jpeg")
            model_result = self._request_image_analysis(
                image_bytes=bytes(raw),
                image_mime=mime,
                description=description,
                lat=lat,
                lng=lng,
            )
            if model_result.get("status") != "ok":
                errors.append(f"{image_name}: {model_result.get('error', '模型调用失败')}")
                payload: dict[str, Any] = {}
            else:
                payload = model_result.get("payload") or {}

            normalized_victims = _normalize_victims(
                payload.get("victims"),
                max_count=self.max_victims_per_image,
            )
            search_routes = _normalize_routes(payload.get("search_routes"), "search")
            rescue_routes = _normalize_routes(payload.get("rescue_routes"), "rescue")
            if search_routes or rescue_routes:
                routes.extend(search_routes + rescue_routes)

            scene_summary = str(payload.get("scene_risk_summary") or "").strip()
            if scene_summary:
                command_notes.append(f"{image_name}：{scene_summary[:280]}")

            try:
                annotated_url = self._build_annotation_image(
                    image_bytes=bytes(raw),
                    detections=normalized_victims,
                    image_name=image_name,
                )
            except Exception as exc:
                annotated_url = ""
                errors.append(f"{image_name}: 标注图生成失败({exc})")

            image_victims: list[dict[str, Any]] = []
            for det_idx, det in enumerate(normalized_victims, 1):
                bbox_norm = det.get("bbox_norm", [])
                area = _bbox_area(bbox_norm if isinstance(bbox_norm, list) else [])
                score = _priority_score(
                    float(det.get("confidence", 0.0) or 0.0),
                    area,
                    str(det.get("condition") or ""),
                )
                victim_id = f"V-{len(victims) + 1}"
                evidence = (
                    f"VLM 置信度 {float(det.get('confidence', 0.0)):.2f}，"
                    f"状态判断：{det.get('condition', '疑似受困')}"
                )
                victim_payload = {
                    "id": victim_id,
                    "position_hint": det.get("position_hint", "未知区域"),
                    "priority": len(victims) + 1,
                    "risk_level": "高" if float(det.get("confidence", 0.0)) >= 0.72 else "中",
                    "condition": det.get("condition", "疑似受困"),
                    "confidence": det.get("confidence", 0.0),
                    "bbox_norm": bbox_norm,
                    "bbox_area": round(area, 5),
                    "priority_score": score,
                    "evidence": evidence,
                    "image_name": image_name,
                    "image_url": image_url,
                    "annotated_image_url": annotated_url or None,
                }
                victims.append(victim_payload)
                image_victims.append(
                    {
                        "id": f"{image_idx}-{det_idx}",
                        "bbox_norm": bbox_norm,
                        "confidence": det.get("confidence", 0.0),
                        "condition": det.get("condition", "疑似受困"),
                        "position_hint": det.get("position_hint", "未知区域"),
                        "priority": det.get("priority") or det_idx,
                        "priority_score": score,
                    }
                )

            image_findings.append(
                {
                    "image_name": image_name,
                    "original_image_url": image_url,
                    "annotated_image_url": annotated_url or image_url,
                    "detections": image_victims,
                    "detected_people": len(image_victims),
                }
            )

        unique_routes: list[dict[str, Any]] = []
        seen = set()
        for route in routes:
            key = (route.get("name"), route.get("route_type"))
            if key in seen:
                continue
            seen.add(key)
            unique_routes.append(route)
        if not unique_routes:
            unique_routes = fallback["routes"]

        victims.sort(
            key=lambda item: (
                float(item.get("priority_score", 0.0) or 0.0),
                float(item.get("confidence", 0.0) or 0.0),
            ),
            reverse=True,
        )
        for idx, victim in enumerate(victims, 1):
            victim["priority"] = idx

        metrics = _algorithm_metrics(victims, unique_routes)
        if metrics.get("hotspots"):
            command_notes.append(f"热点区域识别 {len(metrics['hotspots'])} 处，建议优先覆盖高热点。")
        command_notes.append(
            f"算法评估：复杂度 {metrics['rescue_complexity_index']:.1f} / 覆盖率 {metrics['coverage_score']:.1f}"
        )

        if not command_notes:
            command_notes = fallback["command_notes"]
        if errors:
            command_notes.append(f"部分图片处理异常：{'; '.join(errors[:3])}")

        coord = f"{lat:.5f}, {lng:.5f}" if lat is not None and lng is not None else "未知坐标"
        overview = (
            f"地震图像 VLM 分析完成（{coord}），共分析 {len(image_findings)} 张图，"
            f"识别疑似受灾人员 {len(victims)} 人。"
        )
        if not victims:
            overview = (
                f"地震图像 VLM 分析完成（{coord}），共分析 {len(image_findings)} 张图，"
                "当前未识别到明确受灾人员目标。"
            )

        analysis = {
            "scene_overview": overview,
            "victims": victims[:40],
            "routes": unique_routes[:10],
            "command_notes": command_notes[:10],
            "image_findings": image_findings,
            "algorithm_metrics": metrics,
        }

        status = "ok"
        if errors:
            status = "degraded"
        if not (self.api_key or "").strip() or OpenAI is None:
            status = "mock"

        return {
            "status": status,
            "analysis": analysis,
            "error": "; ".join(errors) if errors else None,
        }
