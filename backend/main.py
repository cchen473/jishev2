from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    from backend.agents.manager import MissionManager
    from backend.config import settings
    from backend.services.dispatch_agent import DispatchAgentPlanner
    from backend.services.earthquake_vlm_rescue import EarthquakeVLMRescueAnalyzer
    from backend.services.storage import Storage
    from backend.utils.auth import (
        create_access_token,
        decode_access_token,
        hash_password,
        verify_password,
    )
    from backend.utils.rag_engine import retrieve_policy
except ImportError:
    from agents.manager import MissionManager
    from config import settings
    from services.dispatch_agent import DispatchAgentPlanner
    from services.earthquake_vlm_rescue import EarthquakeVLMRescueAnalyzer
    from services.storage import Storage
    from utils.auth import (
        create_access_token,
        decode_access_token,
        hash_password,
        verify_password,
    )
    from utils.rag_engine import retrieve_policy

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings.upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(settings.upload_dir)), name="uploads")

storage = Storage(settings.database_path)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "8")) * 1024 * 1024
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff]{2,32}$")
MAX_RESCUE_IMAGES = int(os.getenv("MAX_RESCUE_IMAGES", os.getenv("MAX_FIRE_IMAGES", "6")))
UNSUPPORTED_AERIAL_IMAGE_TYPES = {"image/heic", "image/heif"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif"}
IMAGE_EXTENSION_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}

bearer_scheme = HTTPBearer(auto_error=False)


class MissionRequest(BaseModel):
    description: str = Field(..., min_length=2, max_length=500)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=32)
    display_name: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    community_name: str = Field(..., min_length=2, max_length=80)
    community_district: str = Field(default="默认行政区", max_length=80)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)


class EarthquakeReportRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    felt_level: int = Field(..., ge=1, le=12)
    building_type: str = Field(..., min_length=1, max_length=64)
    structure_notes: str = Field(default="", max_length=1000)
    description: str = Field(default="", max_length=1000)


class LegacyReportRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    type: str = Field(default="earthquake", min_length=2, max_length=64)
    description: str = Field(default="", max_length=1000)
    felt_level: int = Field(default=5, ge=1, le=12)
    building_type: str = Field(default="未知建筑", max_length=64)
    structure_notes: str = Field(default="", max_length=1000)


class CommunityAlertRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=80)
    content: str = Field(..., min_length=2, max_length=600)


class OneClickWarningRequest(BaseModel):
    title: str = Field(default="地震紧急预警", min_length=2, max_length=80)
    content: str = Field(
        default="请立即远离玻璃和外墙，按社区避险路线前往最近集合点，保持手机畅通并等待后续调度。",
        min_length=2,
        max_length=600,
    )


class CommunityChatRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=3000)
    ask_ai: bool = Field(default=False)


class CommunityAssistantRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=3000)


class RouteAdviceRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    type: str = Field(default="earthquake", min_length=2, max_length=64)
    description: str = Field(default="", max_length=1000)
    felt_level: int = Field(default=5, ge=1, le=12)
    building_type: str = Field(default="未知建筑", max_length=64)
    structure_notes: str = Field(default="", max_length=1000)


class IncidentCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=120)
    description: str = Field(default="", max_length=3000)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    source: str = Field(default="manual", max_length=64)


class IncidentUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=3000)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    priority: str | None = Field(default=None, pattern="^(low|medium|high|critical)$")
    status: str | None = Field(default=None, pattern="^(new|verified|responding|stabilized|closed)$")


class IncidentTaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=140)
    description: str = Field(default="", max_length=3000)
    status: str = Field(default="new", pattern="^(new|assigned|accepted|in_progress|blocked|completed)$")
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    assignee_user_id: str | None = None
    team_id: str | None = None
    due_at: str | None = None


class IncidentTaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=140)
    description: str | None = Field(default=None, max_length=3000)
    status: str | None = Field(default=None, pattern="^(new|assigned|accepted|in_progress|blocked|completed)$")
    priority: str | None = Field(default=None, pattern="^(low|medium|high|critical)$")
    assignee_user_id: str | None = None
    team_id: str | None = None
    due_at: str | None = None


class TeamCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    specialty: str = Field(..., min_length=2, max_length=80)
    status: str = Field(default="standby", pattern="^(standby|deployed|offline)$")
    leader_user_id: str | None = None
    contact: str | None = Field(default=None, max_length=120)
    base_lat: float | None = Field(default=None, ge=-90, le=90)
    base_lng: float | None = Field(default=None, ge=-180, le=180)
    base_location_text: str | None = Field(default=None, max_length=120)
    equipment: list[str] = Field(default_factory=list, max_length=40)
    vehicles: list[str] = Field(default_factory=list, max_length=20)
    personnel_count: int = Field(default=0, ge=0, le=200)
    capacity: int = Field(default=8, ge=1, le=200)
    availability_score: float = Field(default=1.0, ge=0, le=1)
    member_user_ids: list[str] = Field(default_factory=list, max_length=30)


class TeamMemberAddRequest(BaseModel):
    user_id: str = Field(..., min_length=6, max_length=64)
    role: str = Field(default="member", pattern="^(leader|member|support)$")


class DispatchCreateRequest(BaseModel):
    incident_id: str | None = None
    task_id: str | None = None
    team_id: str | None = None
    resource_type: str = Field(..., min_length=2, max_length=64)
    resource_name: str = Field(..., min_length=2, max_length=120)
    quantity: int = Field(default=1, ge=1, le=100000)
    status: str = Field(default="allocated", pattern="^(allocated|in_transit|delivered|consumed|returned)$")
    notes: str | None = Field(default=None, max_length=1200)


class ResidentCheckinRequest(BaseModel):
    incident_id: str | None = None
    subject_name: str = Field(..., min_length=1, max_length=80)
    relation: str = Field(default="self", pattern="^(self|family|neighbor|other)$")
    status: str = Field(default="safe", pattern="^(safe|need_help|missing_proxy)$")
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    notes: str | None = Field(default=None, max_length=1000)


class MissingPersonCreateRequest(BaseModel):
    incident_id: str | None = None
    name: str = Field(..., min_length=1, max_length=80)
    age: int | None = Field(default=None, ge=0, le=120)
    contact: str | None = Field(default=None, max_length=120)
    last_seen_location: str | None = Field(default=None, max_length=200)
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    status: str = Field(default="open", pattern="^(open|searching|located|closed)$")
    notes: str | None = Field(default=None, max_length=1200)


class ShelterCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    address: str = Field(..., min_length=2, max_length=200)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    capacity: int = Field(..., ge=1, le=200000)
    current_occupancy: int = Field(default=0, ge=0, le=200000)
    status: str = Field(default="open", pattern="^(open|limited|full|closed)$")


class ShelterOccupancyUpdateRequest(BaseModel):
    delta: int | None = Field(default=None, ge=-200000, le=200000)
    absolute_occupancy: int | None = Field(default=None, ge=0, le=200000)
    status: str | None = Field(default=None, pattern="^(open|limited|full|closed)$")
    reason: str | None = Field(default=None, max_length=800)


class HazardPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class HazardZoneCreateRequest(BaseModel):
    incident_id: str | None = None
    name: str = Field(..., min_length=2, max_length=120)
    risk_level: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    zone_type: str = Field(default="hazard", pattern="^(hazard|block|safe_corridor)$")
    polygon: list[HazardPoint] = Field(..., min_length=3, max_length=100)
    notes: str | None = Field(default=None, max_length=1200)
    status: str = Field(default="active", pattern="^(active|resolved|archived)$")


class RoadBlockCreateRequest(BaseModel):
    incident_id: str | None = None
    title: str = Field(..., min_length=2, max_length=120)
    details: str | None = Field(default=None, max_length=1200)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    severity: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    status: str = Field(default="active", pattern="^(active|cleared|archived)$")


class NotificationTemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    level: str = Field(default="info", pattern="^(info|warning|danger)$")
    title_template: str = Field(..., min_length=2, max_length=120)
    content_template: str = Field(..., min_length=2, max_length=600)


class NotificationReceiptRequest(BaseModel):
    notification_id: str = Field(..., min_length=6, max_length=64)
    status: str = Field(default="read", pattern="^(read|confirmed)$")


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[WebSocket, dict[str, str | None]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_context: dict[str, Any] | None) -> None:
        await websocket.accept()
        metadata = {
            "user_id": user_context["id"] if user_context else None,
            "community_id": (
                str(user_context.get("community", {}).get("id"))
                if user_context and user_context.get("community")
                else None
            ),
        }
        async with self._lock:
            self.active_connections[websocket] = metadata

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active_connections.pop(websocket, None)

    async def broadcast(self, message: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self.active_connections.keys())
        stale: list[WebSocket] = []
        for conn in targets:
            try:
                await conn.send_json(message)
            except Exception:
                stale.append(conn)
        if stale:
            async with self._lock:
                for item in stale:
                    self.active_connections.pop(item, None)

    async def broadcast_to_community(self, community_id: str, message: dict[str, Any]) -> None:
        async with self._lock:
            targets = [
                conn
                for conn, meta in self.active_connections.items()
                if meta.get("community_id") == community_id
            ]
        stale: list[WebSocket] = []
        for conn in targets:
            try:
                await conn.send_json(message)
            except Exception:
                stale.append(conn)
        if stale:
            async with self._lock:
                for item in stale:
                    self.active_connections.pop(item, None)


manager = ConnectionManager()
earthquake_rescue_analyzer = EarthquakeVLMRescueAnalyzer(
    api_key=settings.openai_api_key,
    model=settings.openai_vlm_model or settings.openai_model,
    base_url=settings.openai_base_url,
    upload_dir=settings.upload_dir,
    max_images=MAX_RESCUE_IMAGES,
)
dispatch_agent_planner = DispatchAgentPlanner(
    api_key=settings.openai_api_key,
    model=settings.openai_model,
    base_url=settings.openai_base_url,
    max_tasks=6,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_public_image_url(filename: str) -> str:
    return f"/uploads/{filename}"


async def read_and_validate_image_upload(image: UploadFile) -> tuple[bytes, str, str]:
    ext = Path(image.filename or "").suffix.lower()
    if not ext:
        ext = ".jpg"
    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail="Invalid file type. Image required.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large. Limit is {MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
        )
    try:
        with Image.open(io.BytesIO(content)) as verified:
            verified.verify()
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Invalid file type. Image required.") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Image validation failed.") from exc

    uploaded_type = (image.content_type or "").strip().lower()
    if uploaded_type.startswith("image/"):
        mime = uploaded_type
    else:
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Invalid file type. Image required.")
        mime = IMAGE_EXTENSION_MIME.get(ext, "image/jpeg")
    return content, ext, mime


def normalize_advice_text(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("-").lstrip("*").strip()
        if not line:
            continue
        if line[0].isdigit() and len(line) > 2 and line[1] in {".", "、"}:
            line = line[2:].strip()
        lines.append(line)
    if lines:
        return lines[:6]
    return [text.strip()] if text.strip() else []


def heuristic_shelter_advice(
    felt_level: int,
    building_type: str,
    structure_notes: str,
) -> list[str]:
    level_advice = [
        "立即执行‘趴下-掩护-稳住’，远离窗户、吊灯和高柜。",
        "若在室内，不要乘坐电梯，震动减弱后沿楼梯有序撤离。",
        "撤离后前往开阔地，避开玻璃幕墙、围墙和电线杆。",
    ]

    if felt_level >= 7:
        level_advice.insert(0, "震感较强，优先确认燃气、电源是否关闭，防范次生灾害。")
    elif felt_level <= 3:
        level_advice.append("震感较弱但可能有余震，保持通讯畅通并关注社区广播。")

    btype = building_type.lower()
    if "砖" in btype or "自建" in btype or "old" in btype:
        level_advice.append("老旧/砖混结构风险较高，优先远离外墙和承重薄弱区域。")
    if "高层" in btype or "high" in btype:
        level_advice.append("高层建筑内先就地避险，等待主震减弱后分批撤离。")
    if structure_notes.strip():
        level_advice.append("已记录现场建筑结构信息，建议由社区网格员二次核查后统一广播。")

    return level_advice[:6]


def build_policy_context() -> str:
    snippets = retrieve_policy("earthquake shelter building structure evacuation", k=3)
    if not snippets:
        return "暂无策略片段"
    return "\n".join(f"{idx}. {' '.join(item.split())}" for idx, item in enumerate(snippets, 1))


def run_vlm_analysis(
    *,
    lat: float,
    lng: float,
    felt_level: int,
    building_type: str,
    structure_notes: str,
    description: str,
    image_bytes: bytes | None,
    image_mime: str | None,
) -> dict[str, Any]:
    fallback = heuristic_shelter_advice(felt_level, building_type, structure_notes)
    if OpenAI is None or not settings.openai_api_key:
        return {"status": "mock", "advice": fallback}

    try:
        prompt = (
            "你是地震应急指挥系统中的视觉安全分析助手。"
            "请根据震感、建筑结构和现场画面给出3-6条中文躲避建议，"
            "必须强调可执行动作与风险点，不要给虚构街道导航。\n\n"
            f"城市基准: {settings.base_city}\n"
            f"坐标: ({lat:.5f}, {lng:.5f})\n"
            f"震感等级: {felt_level}\n"
            f"建筑/房屋结构: {building_type}\n"
            f"结构补充: {structure_notes or '无'}\n"
            f"现场描述: {description or '无'}\n"
            f"策略参考:\n{build_policy_context()}\n"
        )

        user_content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if image_bytes:
            encoded = base64.b64encode(image_bytes).decode("utf-8")
            mime = image_mime or "image/jpeg"
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{encoded}"},
                }
            )

        client_kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        client = OpenAI(**client_kwargs)
        completion = client.chat.completions.create(
            model=settings.openai_vlm_model or settings.openai_model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": "你是专业地震避险专家，只输出简洁可执行建议。",
                },
                {"role": "user", "content": user_content},
            ],
        )
        raw = completion.choices[0].message.content if completion.choices else ""
        advice = normalize_advice_text(raw or "")
        if not advice:
            advice = fallback
        return {
            "status": "ok",
            "advice": advice,
            "advice_text": raw,
        }
    except Exception as exc:
        return {
            "status": "degraded",
            "advice": fallback,
            "error": str(exc),
        }


def build_community_snapshot(community_id: str) -> str:
    summary = storage.get_summary(community_id=community_id)
    reports = storage.list_recent_earthquake_reports(limit=5, community_id=community_id)
    notifications = storage.list_notifications(community_id=community_id, limit=5)

    report_lines = [
        f"- 震感{item.get('felt_level', '未知')}级，建筑{item.get('building_type', '未知')}，描述：{item.get('description', '')}"
        for item in reports[-5:]
    ]
    notice_lines = [
        f"- {item.get('title', '通知')}: {item.get('content', '')}" for item in notifications[-5:]
    ]
    return (
        f"社区统计: 报告总数={summary.get('total_reports', 0)}, 执行中任务={summary.get('active_missions', 0)}\n"
        f"近期震情:\n{chr(10).join(report_lines) if report_lines else '- 暂无'}\n"
        f"近期通知:\n{chr(10).join(notice_lines) if notice_lines else '- 暂无'}"
    )


def heuristic_community_assistant_answer(question: str) -> str:
    q = question.strip()
    return (
        "### 社区AI管理助手建议\n"
        f"- 你提出的问题：{q or '未提供问题'}\n"
        "- 先确认社区内高风险点（老旧建筑、人员密集区、学校医院）并进行分级。\n"
        "- 在群聊发布统一通知模板：避险动作、集合点、联系人、物资点。\n"
        "- 每 15 分钟滚动更新震情摘要，确保居民收到同一版本指令。\n"
        "- 指定网格员负责老人、儿童、行动不便人群的一对一确认。"
    )


def run_community_assistant(
    *,
    community_id: str,
    user_display_name: str,
    question: str,
    recent_chat_messages: list[dict[str, Any]],
) -> dict[str, Any]:
    fallback = heuristic_community_assistant_answer(question)
    if OpenAI is None or not settings.openai_api_key:
        return {"status": "mock", "answer": fallback}

    try:
        chat_context = "\n".join(
            f"- [{item.get('role', 'user')}] {item.get('sender_name', 'unknown')}: {item.get('content', '')[:220]}"
            for item in recent_chat_messages[-12:]
        )
        snapshot = build_community_snapshot(community_id)
        prompt = (
            "你是社区AI管理助手，目标是帮助社区管理者做应急沟通与资源协调。\n"
            "输出要求：中文、结构清晰、可执行，优先用 Markdown 列表。\n\n"
            f"提问人: {user_display_name}\n"
            f"问题: {question}\n\n"
            f"社区状态:\n{snapshot}\n\n"
            f"近期群聊上下文:\n{chat_context or '- 暂无'}\n"
        )
        client_kwargs: dict[str, Any] = {
            "api_key": settings.openai_api_key,
            "timeout": 25.0,
        }
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        client = OpenAI(**client_kwargs)
        completion = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.3,
            timeout=25.0,
            messages=[
                {
                    "role": "system",
                    "content": "你是专业社区应急治理助手，给出简洁可执行建议，不输出无关内容。",
                },
                {"role": "user", "content": prompt},
            ],
        )
        answer = completion.choices[0].message.content if completion.choices else ""
        if not (answer or "").strip():
            answer = fallback
        return {"status": "ok", "answer": answer}
    except Exception as exc:
        return {"status": "degraded", "answer": fallback, "error": str(exc)}


def _pick_value(value: str, allowed: set[str], fallback: str) -> str:
    candidate = (value or "").strip().lower()
    if candidate in allowed:
        return candidate
    return fallback


def ensure_local_response_teams(community: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        base_lat = float(community.get("base_lat", settings.base_lat))
    except Exception:
        base_lat = float(settings.base_lat)
    try:
        base_lng = float(community.get("base_lng", settings.base_lng))
    except Exception:
        base_lng = float(settings.base_lng)
    return storage.ensure_default_response_teams(
        community_id=community["id"],
        base_lat=base_lat,
        base_lng=base_lng,
    )


async def execute_dispatch_agent_for_analysis(
    *,
    community: dict[str, Any],
    user: dict[str, Any],
    analysis_record: dict[str, Any],
    trigger_source: str,
) -> dict[str, Any]:
    idempotency_key = f"{analysis_record['id']}:v1"
    existing = storage.get_dispatch_agent_run_by_key(idempotency_key=idempotency_key)
    if existing:
        return existing

    incidents = storage.list_incidents(community_id=community["id"], limit=200)
    tasks = storage.list_tasks(community_id=community["id"], limit=300)
    teams = ensure_local_response_teams(community)
    dispatches = storage.list_dispatch_records(community_id=community["id"], limit=200)
    analysis_payload = analysis_record.get("analysis") if isinstance(analysis_record, dict) else {}
    if not isinstance(analysis_payload, dict):
        analysis_payload = {}
    analysis_for_plan = {
        **analysis_payload,
        "incident_lat": analysis_record.get("lat"),
        "incident_lng": analysis_record.get("lng"),
    }

    plan_result = dispatch_agent_planner.generate_plan(
        analysis=analysis_for_plan,
        incidents=incidents,
        tasks=tasks,
        teams=teams,
        dispatches=dispatches,
    )
    plan_payload = plan_result.get("plan") if isinstance(plan_result.get("plan"), dict) else {}
    run = storage.create_dispatch_agent_run(
        community_id=community["id"],
        analysis_id=analysis_record["id"],
        trigger_source=trigger_source,
        idempotency_key=idempotency_key,
        input_payload={
            "incidents": len(incidents),
            "tasks": len(tasks),
            "teams": len(teams),
            "dispatches": len(dispatches),
            "analysis_overview": analysis_payload.get("scene_overview"),
            "victim_count": len(analysis_payload.get("victims", []))
            if isinstance(analysis_payload.get("victims"), list)
            else 0,
        },
        plan_payload={
            **plan_payload,
            "source": plan_result.get("source"),
            "planner_status": plan_result.get("status"),
            "planner_error": plan_result.get("error"),
        },
        status="running",
        error=None,
    )

    created_incident_ids: list[str] = []
    updated_incident_ids: list[str] = []
    created_task_ids: list[str] = []
    updated_task_ids: list[str] = []
    created_dispatch_ids: list[str] = []
    execution_errors: list[str] = []

    active_incident = next((row for row in incidents if row.get("status") != "closed"), None)
    incident_for_tasks = active_incident["id"] if active_incident else None
    task_lookup = {row["id"]: row for row in tasks if row.get("id")}
    team_lookup = {row["id"]: row for row in teams if row.get("id")}

    incident_actions = plan_payload.get("incident_actions")
    if isinstance(incident_actions, list):
        for action in incident_actions[:2]:
            if not isinstance(action, dict):
                continue
            mode = str(action.get("action") or "create").lower()
            if mode == "update" and action.get("incident_id"):
                target_id = str(action.get("incident_id"))
                before = storage.get_incident(target_id, community["id"])
                if not before:
                    execution_errors.append(f"incident.update:{target_id}:not_found")
                    continue
                updated = storage.update_incident(
                    incident_id=target_id,
                    community_id=community["id"],
                    title=str(action.get("title") or before.get("title") or "地震事件"),
                    description=str(action.get("description") or before.get("description") or ""),
                    priority=_pick_value(
                        str(action.get("priority") or before.get("priority") or "high"),
                        {"low", "medium", "high", "critical"},
                        "high",
                    ),
                    status=_pick_value(
                        str(action.get("status") or before.get("status") or "responding"),
                        {"new", "verified", "responding", "stabilized", "closed"},
                        "responding",
                    ),
                )
                if updated:
                    updated_incident_ids.append(updated["id"])
                    incident_for_tasks = updated["id"]
                continue

            created = storage.create_incident(
                community_id=community["id"],
                created_by_user_id=user["id"],
                title=str(action.get("title") or "地震受灾搜救事件"),
                description=str(action.get("description") or analysis_payload.get("scene_overview") or ""),
                lat=analysis_record.get("lat"),
                lng=analysis_record.get("lng"),
                priority=_pick_value(
                    str(action.get("priority") or "high"),
                    {"low", "medium", "high", "critical"},
                    "high",
                ),
                source="agent_auto",
                status=_pick_value(
                    str(action.get("status") or "responding"),
                    {"new", "verified", "responding", "stabilized", "closed"},
                    "responding",
                ),
            )
            created_incident_ids.append(created["id"])
            incident_for_tasks = created["id"]

    if not incident_for_tasks:
        auto_incident = storage.create_incident(
            community_id=community["id"],
            created_by_user_id=user["id"],
            title="地震受灾搜救事件",
            description=str(analysis_payload.get("scene_overview") or "自动调度创建事件"),
            lat=analysis_record.get("lat"),
            lng=analysis_record.get("lng"),
            priority="high",
            source="agent_auto",
            status="responding",
        )
        created_incident_ids.append(auto_incident["id"])
        incident_for_tasks = auto_incident["id"]

    task_actions = plan_payload.get("task_actions")
    if isinstance(task_actions, list):
        for action in task_actions[:6]:
            if not isinstance(action, dict):
                continue
            mode = str(action.get("action") or "create").lower()
            if mode == "update" and action.get("task_id"):
                task_id = str(action.get("task_id"))
                before = task_lookup.get(task_id)
                if not before:
                    execution_errors.append(f"task.update:{task_id}:not_found")
                    continue
                if str(before.get("status")) == "completed":
                    continue
                updated = storage.update_task(
                    task_id=task_id,
                    community_id=community["id"],
                    status=_pick_value(
                        str(action.get("status") or before.get("status") or "in_progress"),
                        {"new", "assigned", "accepted", "in_progress", "blocked", "completed"},
                        "in_progress",
                    ),
                    priority=_pick_value(
                        str(action.get("priority") or before.get("priority") or "high"),
                        {"low", "medium", "high", "critical"},
                        "high",
                    ),
                    assignee_user_id=str(action.get("assignee_user_id") or "").strip() or None,
                    team_id=str(action.get("team_id") or "").strip() or None,
                    due_at=None,
                    title=str(action.get("title") or before.get("title") or "AI自动任务"),
                    description=str(action.get("description") or before.get("description") or ""),
                )
                if updated:
                    updated_task_ids.append(updated["id"])
                    task_lookup[updated["id"]] = updated
                continue

            team_id = str(action.get("team_id") or "").strip() or None
            if team_id and team_id not in team_lookup:
                team_id = None
            description = str(action.get("description") or "").strip()
            if not description:
                description = "AI-AUTO：依据地震图像识别结果执行现场搜救。"
            if "[AI-AUTO]" not in description:
                description = f"[AI-AUTO] {description}"
            created_task = storage.create_incident_task(
                incident_id=incident_for_tasks,
                community_id=community["id"],
                title=str(action.get("title") or "AI自动搜救任务")[:140],
                description=description[:3000],
                status=_pick_value(
                    str(action.get("status") or "assigned"),
                    {"new", "assigned", "accepted", "in_progress", "blocked", "completed"},
                    "assigned",
                ),
                priority=_pick_value(
                    str(action.get("priority") or "high"),
                    {"low", "medium", "high", "critical"},
                    "high",
                ),
                assignee_user_id=str(action.get("assignee_user_id") or "").strip() or None,
                team_id=team_id,
                due_at=None,
                created_by_user_id=user["id"],
            )
            created_task_ids.append(created_task["id"])
            detailed = storage.get_task(created_task["id"], community["id"]) or created_task
            task_lookup[detailed["id"]] = detailed

    dispatch_actions = plan_payload.get("dispatch_actions")
    if isinstance(dispatch_actions, list):
        for idx, action in enumerate(dispatch_actions[:6], 1):
            if not isinstance(action, dict):
                continue
            team_id = str(action.get("team_id") or "").strip() or None
            if team_id and team_id not in team_lookup:
                team_id = None
            linked_task_id = created_task_ids[idx - 1] if idx - 1 < len(created_task_ids) else None
            dispatch_record = storage.create_dispatch_record(
                community_id=community["id"],
                created_by_user_id=user["id"],
                incident_id=incident_for_tasks,
                task_id=linked_task_id,
                team_id=team_id,
                resource_type=str(action.get("resource_type") or "rescue_unit")[:64],
                resource_name=str(action.get("resource_name") or "机动搜救单元")[:120],
                quantity=max(1, int(action.get("quantity") or 1)),
                status=_pick_value(
                    str(action.get("status") or "allocated"),
                    {"allocated", "in_transit", "delivered", "consumed", "returned"},
                    "allocated",
                ),
                notes=str(action.get("notes") or "AI-AUTO 调度记录")[:1200],
            )
            created_dispatch_ids.append(dispatch_record["id"])

    execution_payload = {
        "incident": {"created": created_incident_ids, "updated": updated_incident_ids},
        "tasks": {"created": created_task_ids, "updated": updated_task_ids},
        "dispatches": {"created": created_dispatch_ids},
        "planner_status": plan_result.get("status"),
        "planner_source": plan_result.get("source"),
        "planner_error": plan_result.get("error"),
        "execution_errors": execution_errors,
    }
    final_status = "completed" if not execution_errors else "degraded"
    updated_run = storage.update_dispatch_agent_run_result(
        run_id=run["id"],
        status=final_status,
        execution_payload=execution_payload,
        error="; ".join(execution_errors) if execution_errors else None,
    )
    result = updated_run or run

    for incident_id in created_incident_ids:
        incident = storage.get_incident(incident_id, community["id"])
        if incident:
            await manager.broadcast_to_community(
                community["id"],
                {"type": "incident_created", "incident": incident},
            )
    for incident_id in updated_incident_ids:
        incident = storage.get_incident(incident_id, community["id"])
        if incident:
            await manager.broadcast_to_community(
                community["id"],
                {"type": "incident_updated", "incident": incident},
            )
    for task_id in created_task_ids:
        task = storage.get_task(task_id, community["id"])
        if task:
            await manager.broadcast_to_community(
                community["id"],
                {"type": "task_created", "task": task},
            )
    for task_id in updated_task_ids:
        task = storage.get_task(task_id, community["id"])
        if task:
            await manager.broadcast_to_community(
                community["id"],
                {"type": "task_updated", "task": task},
            )

    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="dispatch_agent.execute",
        target_type="dispatch_agent_run",
        target_id=result.get("id"),
        detail={
            "analysis_id": analysis_record.get("id"),
            "status": result.get("status"),
            "created_incident_count": len(created_incident_ids),
            "created_task_count": len(created_task_ids),
            "created_dispatch_count": len(created_dispatch_ids),
        },
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="dispatch_agent_executed",
        title="自动调度 Agent 已执行",
        content=(
            f"事件+{len(created_incident_ids)}，任务+{len(created_task_ids)}，"
            f"调度+{len(created_dispatch_ids)}，状态 {result.get('status')}"
        ),
        entity_type="dispatch_agent_run",
        entity_id=result.get("id"),
        payload={"dispatch_agent_run": result},
        created_by_user_id=user["id"],
        ws_type="dispatch_agent_executed",
    )
    return result


def sanitize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=400,
            detail="用户名仅支持 2-32 位中文、字母、数字和下划线",
        )
    return normalized


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "created_at": user.get("created_at"),
    }


def user_response_payload(user: dict[str, Any], community: dict[str, Any] | None) -> dict[str, Any]:
    return {
        **public_user(user),
        "community": community,
    }


def issue_token(user_id: str) -> str:
    return create_access_token(
        {"sub": user_id},
        secret=settings.auth_secret,
        expires_minutes=settings.auth_token_exp_minutes,
    )


def resolve_user_from_token(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    payload = decode_access_token(token, settings.auth_secret)
    if not payload:
        return None
    user_id = str(payload.get("sub", "")).strip()
    if not user_id:
        return None
    user = storage.get_user_by_id(user_id)
    if not user or not int(user.get("is_active", 0)):
        return None
    community = storage.get_user_primary_community(user_id)
    return user_response_payload(user, community)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="未登录或 token 缺失")
    user = resolve_user_from_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录")
    if not user.get("community"):
        raise HTTPException(status_code=403, detail="用户尚未加入社区")
    return user


async def process_mission(
    description: str,
    community_id: str | None = None,
) -> str:
    mission = storage.create_mission(description)
    mission_id = mission["id"]

    async def stream_callback(message: dict[str, Any]) -> None:
        source = str(message.get("source", "SYSTEM"))
        content = str(message.get("content", ""))
        msg_type = str(message.get("type", "TextMessage"))
        storage.add_mission_event(mission_id, source, msg_type, content)
        payload = {**message, "mission_id": mission_id}
        if community_id:
            await manager.broadcast_to_community(community_id, payload)
        else:
            await manager.broadcast(payload)

    try:
        mission_manager = MissionManager(callback=stream_callback)
        await mission_manager.run(description)
        storage.update_mission_status(mission_id, "completed")
    except Exception as exc:
        storage.update_mission_status(mission_id, "failed")
        payload = {
            "type": "status",
            "source": "SYSTEM",
            "content": f"Mission failed: {exc}",
            "mission_id": mission_id,
        }
        if community_id:
            await manager.broadcast_to_community(community_id, payload)
        else:
            await manager.broadcast(payload)
        raise

    return mission_id


async def create_earthquake_report_and_notify(
    *,
    user: dict[str, Any],
    lat: float,
    lng: float,
    felt_level: int,
    building_type: str,
    structure_notes: str,
    description: str,
    image_bytes: bytes | None,
    image_mime: str | None,
    image_url: str | None,
) -> dict[str, Any]:
    community = user.get("community")
    if not community:
        raise HTTPException(status_code=403, detail="用户尚未加入社区")

    analysis = run_vlm_analysis(
        lat=lat,
        lng=lng,
        felt_level=felt_level,
        building_type=building_type,
        structure_notes=structure_notes,
        description=description,
        image_bytes=image_bytes,
        image_mime=image_mime,
    )

    report = storage.add_earthquake_report(
        user_id=user["id"],
        community_id=community["id"],
        lat=lat,
        lng=lng,
        felt_level=felt_level,
        building_type=building_type,
        structure_notes=structure_notes,
        description=description,
        image_url=image_url,
        vlm_advice=analysis.get("advice") or [],
    )
    report.pop("vlm_advice_json", None)

    report_payload = {
        "type": "field_report",
        **report,
    }
    await manager.broadcast_to_community(community["id"], report_payload)

    summary_text = (
        f"[{community['name']}] 新地震上报：震感 {felt_level} 级，"
        f"建筑类型 {building_type}。请居民立即就近避险并确认家人安全。"
    )
    notification = storage.create_notification(
        community_id=community["id"],
        sender_user_id=user["id"],
        title="地震避险通知",
        content=summary_text,
        payload={
            "report_id": report["id"],
            "felt_level": felt_level,
            "building_type": building_type,
            "lat": lat,
            "lng": lng,
        },
    )
    notification.pop("payload_json", None)

    await manager.broadcast_to_community(
        community["id"],
        {
            "type": "community_alert",
            "source": "COMMUNITY_ALERT",
            "content": summary_text,
            "community_id": community["id"],
            "notification": notification,
        },
    )

    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="earthquake.report.create",
        target_type="earthquake_report",
        target_id=report["id"],
        detail={
            "felt_level": felt_level,
            "building_type": building_type,
            "lat": lat,
            "lng": lng,
        },
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="earthquake_reported",
        title=f"地震上报：{felt_level}级",
        content=f"{building_type}，坐标 {lat:.5f}, {lng:.5f}",
        entity_type="earthquake_report",
        entity_id=report["id"],
        payload={"report": report, "analysis_status": analysis.get("status", "mock")},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )

    return {
        "status": "success",
        "report": report,
        "shelter_advice": analysis.get("advice") or [],
        "analysis_status": analysis.get("status", "mock"),
        "analysis_error": analysis.get("error"),
        "community_notification": notification,
    }


async def create_and_broadcast_chat_message(
    *,
    community_id: str,
    sender_user_id: str | None,
    sender_name: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    message = storage.add_chat_message(
        community_id=community_id,
        sender_user_id=sender_user_id,
        sender_name=sender_name,
        role=role,
        content=content,
        metadata=metadata,
    )
    payload = {
        "type": "community_chat_message",
        "message": {**message, "metadata": message.get("metadata") or {}},
    }
    await manager.broadcast_to_community(community_id, payload)
    return message


def _incident_snapshot(incident: dict[str, Any] | None) -> dict[str, Any]:
    if not incident:
        return {"id": None, "title": "", "status": "", "priority": ""}
    return {
        "id": incident.get("id"),
        "title": incident.get("title"),
        "status": incident.get("status"),
        "priority": incident.get("priority"),
    }


async def record_ops_event(
    *,
    community_id: str,
    event_type: str,
    title: str,
    content: str,
    entity_type: str | None,
    entity_id: str | None,
    payload: dict[str, Any] | None,
    created_by_user_id: str | None,
    ws_type: str | None = None,
) -> dict[str, Any]:
    event = storage.add_ops_timeline_event(
        community_id=community_id,
        event_type=event_type,
        title=title,
        content=content,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        created_by_user_id=created_by_user_id,
    )
    if ws_type:
        await manager.broadcast_to_community(
            community_id,
            {
                "type": ws_type,
                "event": event,
                "payload": payload or {},
            },
        )
    return event


def record_audit(
    *,
    community_id: str,
    user_id: str | None,
    action: str,
    target_type: str,
    target_id: str | None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return storage.add_audit_log(
        community_id=community_id,
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail or {},
    )


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "message": f"{settings.app_name} is running",
        "status": "online",
        "version": settings.app_version,
        "mode": settings.app_mode,
        "base_city": settings.base_city,
        "base_location": {"lat": settings.base_lat, "lng": settings.base_lng},
        "server_time": utc_now(),
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    try:
        db_ok = storage.get_summary() is not None
    except Exception:
        db_ok = False

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "database": db_ok,
        "rag": True,
        "rag_checked": False,
        "time": utc_now(),
        "mode": settings.app_mode,
    }


@app.post("/auth/register")
async def auth_register(req: RegisterRequest) -> dict[str, Any]:
    username = sanitize_username(req.username)
    if storage.get_user_by_username(username):
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = storage.create_user(
        username=username,
        display_name=req.display_name.strip(),
        password_hash=hash_password(req.password),
    )

    community = storage.create_or_get_community(
        name=req.community_name.strip(),
        district=req.community_district.strip() or settings.base_city,
        base_lat=settings.base_lat,
        base_lng=settings.base_lng,
    )
    member_count = storage.get_community_member_count(community["id"])
    role = "owner" if member_count == 0 else "member"
    storage.add_user_to_community(user["id"], community["id"], role=role)
    ensure_local_response_teams(community)

    token = issue_token(user["id"])
    return {
        "status": "success",
        "token": token,
        "user": user_response_payload(user, {**community, "role": role}),
    }


@app.post("/auth/login")
async def auth_login(req: LoginRequest) -> dict[str, Any]:
    username = sanitize_username(req.username)
    user = storage.get_user_by_username(username)
    if not user or not verify_password(req.password, str(user.get("password_hash", ""))):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not int(user.get("is_active", 0)):
        raise HTTPException(status_code=403, detail="账户已停用")

    community = storage.get_user_primary_community(user["id"])
    if community:
        ensure_local_response_teams(community)
    token = issue_token(user["id"])
    return {
        "status": "success",
        "token": token,
        "user": user_response_payload(user, community),
    }


@app.get("/auth/me")
async def auth_me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"status": "success", "user": user}


@app.get("/community/me")
async def community_me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"status": "success", "community": user.get("community")}


@app.get("/community/notifications")
async def community_notifications(
    limit: int = Query(default=50, ge=1, le=500),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_notifications(community_id=community["id"], limit=limit)
    for item in items:
        item.pop("payload_json", None)
    return {"count": len(items), "items": items}


@app.post("/community/alerts")
async def community_alert_broadcast(
    req: CommunityAlertRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    notification = storage.create_notification(
        community_id=community["id"],
        sender_user_id=user["id"],
        title=req.title,
        content=req.content,
        payload={"manual": True},
    )
    notification.pop("payload_json", None)
    payload = {
        "type": "community_alert",
        "source": "COMMUNITY_ALERT",
        "content": req.content,
        "title": req.title,
        "community_id": community["id"],
        "notification": notification,
    }
    await manager.broadcast_to_community(community["id"], payload)
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="community.alert.create",
        target_type="notification",
        target_id=notification["id"],
        detail={"title": req.title},
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="community_alert_sent",
        title=f"社区通知：{req.title}",
        content=req.content,
        entity_type="notification",
        entity_id=notification["id"],
        payload={"notification": notification},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )
    return {"status": "success", "notification": notification}


@app.post("/community/alerts/one-click-warning")
async def one_click_warning(
    req: OneClickWarningRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    title = req.title.strip()
    content = req.content.strip()
    notification = storage.create_notification(
        community_id=community["id"],
        sender_user_id=user["id"],
        title=title,
        content=content,
        payload={
            "manual": True,
            "is_emergency": True,
            "warning_type": "earthquake",
            "warning_level": "critical",
            "trigger": "one_click_warning",
        },
    )
    notification.pop("payload_json", None)

    warning_payload = {
        "type": "community_warning",
        "source": "COMMUNITY_WARNING",
        "title": title,
        "content": content,
        "community_id": community["id"],
        "severity": "critical",
        "notification": notification,
    }
    await manager.broadcast_to_community(community["id"], warning_payload)
    await manager.broadcast_to_community(
        community["id"],
        {
            "type": "community_alert",
            "source": "COMMUNITY_ALERT",
            "title": title,
            "content": content,
            "community_id": community["id"],
            "notification": notification,
        },
    )

    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="community.warning.one_click",
        target_type="notification",
        target_id=notification["id"],
        detail={"title": title, "severity": "critical"},
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="community_warning_sent",
        title=f"一键预警：{title}",
        content=content,
        entity_type="notification",
        entity_id=notification["id"],
        payload={"notification": notification, "severity": "critical"},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )
    return {"status": "success", "notification": notification}


@app.get("/community/chat/messages")
async def community_chat_messages(
    limit: int = Query(default=100, ge=1, le=500),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_chat_messages(community_id=community["id"], limit=limit)
    for item in items:
        item.pop("metadata_json", None)
    return {"count": len(items), "items": items}


@app.post("/community/chat/send")
async def community_chat_send(
    req: CommunityChatRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    message = await create_and_broadcast_chat_message(
        community_id=community["id"],
        sender_user_id=user["id"],
        sender_name=user["display_name"],
        role="user",
        content=content,
    )
    message.pop("metadata_json", None)

    assistant_message: dict[str, Any] | None = None
    assistant_meta: dict[str, Any] | None = None
    if req.ask_ai:
        history = storage.list_chat_messages(community_id=community["id"], limit=40)
        ai_resp = run_community_assistant(
            community_id=community["id"],
            user_display_name=user["display_name"],
            question=content,
            recent_chat_messages=history,
        )
        assistant_meta = {"status": ai_resp.get("status"), "error": ai_resp.get("error")}
        assistant_message = await create_and_broadcast_chat_message(
            community_id=community["id"],
            sender_user_id=None,
            sender_name="社区AI助手",
            role="assistant",
            content=str(ai_resp.get("answer", "")),
            metadata=assistant_meta,
        )
        assistant_message.pop("metadata_json", None)

    return {
        "status": "success",
        "message": message,
        "assistant_message": assistant_message,
        "assistant_meta": assistant_meta,
    }


@app.post("/community/assistant/ask")
async def community_assistant_ask(
    req: CommunityAssistantRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    user_message = await create_and_broadcast_chat_message(
        community_id=community["id"],
        sender_user_id=user["id"],
        sender_name=user["display_name"],
        role="user",
        content=question,
    )
    history = storage.list_chat_messages(community_id=community["id"], limit=40)
    ai_resp = run_community_assistant(
        community_id=community["id"],
        user_display_name=user["display_name"],
        question=question,
        recent_chat_messages=history,
    )
    assistant_message = await create_and_broadcast_chat_message(
        community_id=community["id"],
        sender_user_id=None,
        sender_name="社区AI助手",
        role="assistant",
        content=str(ai_resp.get("answer", "")),
        metadata={"status": ai_resp.get("status"), "error": ai_resp.get("error")},
    )
    user_message.pop("metadata_json", None)
    assistant_message.pop("metadata_json", None)
    return {
        "status": "success",
        "user_message": user_message,
        "assistant_message": assistant_message,
        "assistant_status": ai_resp.get("status", "mock"),
        "assistant_error": ai_resp.get("error"),
    }


@app.post("/incidents")
async def create_incident(
    req: IncidentCreateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    incident = storage.create_incident(
        community_id=community["id"],
        created_by_user_id=user["id"],
        title=req.title,
        description=req.description,
        lat=req.lat,
        lng=req.lng,
        priority=req.priority,
        source=req.source,
        status="new",
    )
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="incident.create",
        target_type="incident",
        target_id=incident["id"],
        detail={"priority": req.priority, "source": req.source},
    )
    timeline_event = await record_ops_event(
        community_id=community["id"],
        event_type="incident_created",
        title=f"事件已创建：{incident['title']}",
        content=f"优先级 {incident['priority']}，状态 {incident['status']}",
        entity_type="incident",
        entity_id=incident["id"],
        payload={"incident": incident},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )
    await manager.broadcast_to_community(
        community["id"], {"type": "incident_created", "incident": incident}
    )
    return {"status": "success", "incident": incident, "timeline_event": timeline_event}


@app.get("/incidents")
async def list_incidents(
    limit: int = Query(default=80, ge=1, le=300),
    status: str | None = Query(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_incidents(community_id=community["id"], limit=limit)
    if status:
        items = [item for item in items if item.get("status") == status]
    return {"count": len(items), "items": items}


@app.patch("/incidents/{incident_id}")
async def patch_incident(
    incident_id: str,
    req: IncidentUpdateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    incident = storage.get_incident(incident_id, community["id"])
    if not incident:
        raise HTTPException(status_code=404, detail="事件不存在")
    updated = storage.update_incident(
        incident_id=incident_id,
        community_id=community["id"],
        title=req.title,
        description=req.description,
        priority=req.priority,
        status=req.status,
        lat=req.lat,
        lng=req.lng,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="事件不存在")
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="incident.update",
        target_type="incident",
        target_id=incident_id,
        detail={"before": _incident_snapshot(incident), "after": _incident_snapshot(updated)},
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="incident_updated",
        title=f"事件已更新：{updated['title']}",
        content=f"状态 {updated['status']}，优先级 {updated['priority']}",
        entity_type="incident",
        entity_id=updated["id"],
        payload={"incident": updated},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )
    await manager.broadcast_to_community(
        community["id"], {"type": "incident_updated", "incident": updated}
    )
    return {"status": "success", "incident": updated}


@app.post("/incidents/{incident_id}/tasks")
async def create_incident_task(
    incident_id: str,
    req: IncidentTaskCreateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    incident = storage.get_incident(incident_id, community["id"])
    if not incident:
        raise HTTPException(status_code=404, detail="事件不存在")
    task = storage.create_incident_task(
        incident_id=incident_id,
        community_id=community["id"],
        title=req.title,
        description=req.description,
        status=req.status,
        priority=req.priority,
        assignee_user_id=req.assignee_user_id,
        team_id=req.team_id,
        due_at=req.due_at,
        created_by_user_id=user["id"],
    )
    detailed = storage.get_task(task["id"], community["id"]) or task
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="task.create",
        target_type="incident_task",
        target_id=task["id"],
        detail={"incident_id": incident_id, "status": req.status, "priority": req.priority},
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="task_created",
        title=f"任务已创建：{detailed.get('title', '')}",
        content=f"事件 {incident.get('title', incident_id)}，状态 {detailed.get('status', 'new')}",
        entity_type="task",
        entity_id=task["id"],
        payload={"task": detailed},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )
    await manager.broadcast_to_community(community["id"], {"type": "task_created", "task": detailed})
    return {"status": "success", "task": detailed}


@app.get("/incidents/{incident_id}/tasks")
async def list_incident_tasks(
    incident_id: str,
    limit: int = Query(default=150, ge=1, le=500),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_tasks(
        community_id=community["id"],
        incident_id=incident_id,
        limit=limit,
    )
    return {"count": len(items), "items": items}


@app.get("/tasks")
async def list_tasks(
    limit: int = Query(default=150, ge=1, le=500),
    status: str | None = Query(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_tasks(community_id=community["id"], limit=limit)
    if status:
        items = [item for item in items if item.get("status") == status]
    return {"count": len(items), "items": items}


@app.patch("/tasks/{task_id}")
async def patch_task(
    task_id: str,
    req: IncidentTaskUpdateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    before = storage.get_task(task_id, community["id"])
    if not before:
        raise HTTPException(status_code=404, detail="任务不存在")
    task = storage.update_task(
        task_id=task_id,
        community_id=community["id"],
        status=req.status,
        priority=req.priority,
        assignee_user_id=req.assignee_user_id,
        team_id=req.team_id,
        due_at=req.due_at,
        title=req.title,
        description=req.description,
    )
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="task.update",
        target_type="incident_task",
        target_id=task_id,
        detail={
            "before": {
                "status": before.get("status"),
                "priority": before.get("priority"),
                "assignee_user_id": before.get("assignee_user_id"),
                "team_id": before.get("team_id"),
            },
            "after": {
                "status": task.get("status"),
                "priority": task.get("priority"),
                "assignee_user_id": task.get("assignee_user_id"),
                "team_id": task.get("team_id"),
            },
        },
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="task_updated",
        title=f"任务已更新：{task.get('title', '')}",
        content=f"状态 {task.get('status', '')}，优先级 {task.get('priority', '')}",
        entity_type="task",
        entity_id=task_id,
        payload={"task": task},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )
    await manager.broadcast_to_community(community["id"], {"type": "task_updated", "task": task})
    return {"status": "success", "task": task}


@app.post("/teams")
async def create_team(
    req: TeamCreateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    team = storage.create_response_team(
        community_id=community["id"],
        name=req.name,
        specialty=req.specialty,
        status=req.status,
        leader_user_id=req.leader_user_id,
        contact=req.contact,
        base_lat=req.base_lat,
        base_lng=req.base_lng,
        base_location_text=req.base_location_text,
        equipment=req.equipment,
        vehicles=req.vehicles,
        personnel_count=req.personnel_count,
        capacity=req.capacity,
        availability_score=req.availability_score,
        last_active_at=utc_now(),
    )
    if req.leader_user_id:
        storage.add_team_member(team_id=team["id"], user_id=req.leader_user_id, role="leader")
    for member_id in req.member_user_ids:
        storage.add_team_member(team_id=team["id"], user_id=member_id, role="member")
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="team.create",
        target_type="response_team",
        target_id=team["id"],
        detail={"specialty": team["specialty"], "status": team["status"]},
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="team_created",
        title=f"救援队已创建：{team['name']}",
        content=f"专业类型 {team['specialty']}，状态 {team['status']}",
        entity_type="team",
        entity_id=team["id"],
        payload={"team": team},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )
    return {"status": "success", "team": team}


@app.post("/teams/{team_id}/members")
async def add_team_member(
    team_id: str,
    req: TeamMemberAddRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    ensure_local_response_teams(community)
    teams = storage.list_response_teams(community_id=community["id"], limit=300)
    if not any(item.get("id") == team_id for item in teams):
        raise HTTPException(status_code=404, detail="救援队不存在")
    member = storage.add_team_member(team_id=team_id, user_id=req.user_id, role=req.role)
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="team.member.add",
        target_type="response_team",
        target_id=team_id,
        detail={"member_user_id": req.user_id, "role": req.role},
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="team_member_added",
        title="救援队成员已加入",
        content=f"队伍 {team_id} 新增成员 {req.user_id}",
        entity_type="team",
        entity_id=team_id,
        payload={"member": member, "team_id": team_id},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )
    return {"status": "success", "member": member}


@app.get("/teams")
async def list_teams(
    limit: int = Query(default=120, ge=1, le=300),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    ensure_local_response_teams(community)
    items = storage.list_response_teams(community_id=community["id"], limit=limit)
    return {"count": len(items), "items": items}


@app.post("/dispatches")
async def create_dispatch(
    req: DispatchCreateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    record = storage.create_dispatch_record(
        community_id=community["id"],
        created_by_user_id=user["id"],
        incident_id=req.incident_id,
        task_id=req.task_id,
        team_id=req.team_id,
        resource_type=req.resource_type,
        resource_name=req.resource_name,
        quantity=req.quantity,
        status=req.status,
        notes=req.notes,
    )
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="dispatch.create",
        target_type="dispatch_record",
        target_id=record["id"],
        detail={"resource_type": req.resource_type, "quantity": req.quantity},
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="dispatch_created",
        title=f"资源调度：{record['resource_name']}",
        content=f"{record['resource_type']} x{record['quantity']}，状态 {record['status']}",
        entity_type="dispatch",
        entity_id=record["id"],
        payload={"dispatch": record},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )
    return {"status": "success", "dispatch": record}


@app.get("/dispatches")
async def list_dispatches(
    limit: int = Query(default=150, ge=1, le=400),
    incident_id: str | None = Query(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_dispatch_records(
        community_id=community["id"], incident_id=incident_id, limit=limit
    )
    return {"count": len(items), "items": items}


@app.post("/residents/checkins")
async def create_resident_checkin(
    req: ResidentCheckinRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    checkin = storage.add_resident_checkin(
        community_id=community["id"],
        user_id=user["id"] if req.relation == "self" else None,
        incident_id=req.incident_id,
        subject_name=req.subject_name,
        relation=req.relation,
        status=req.status,
        lat=req.lat,
        lng=req.lng,
        notes=req.notes,
    )
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="resident.checkin",
        target_type="resident_checkin",
        target_id=checkin["id"],
        detail={"status": req.status, "relation": req.relation},
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="resident_checkin_updated",
        title=f"居民状态更新：{req.subject_name}",
        content=f"状态 {req.status}（关系 {req.relation}）",
        entity_type="resident_checkin",
        entity_id=checkin["id"],
        payload={"checkin": checkin},
        created_by_user_id=user["id"],
        ws_type="resident_checkin_updated",
    )
    return {"status": "success", "checkin": checkin}


@app.get("/residents/checkins")
async def list_resident_checkins(
    limit: int = Query(default=150, ge=1, le=500),
    incident_id: str | None = Query(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_resident_checkins(
        community_id=community["id"], incident_id=incident_id, limit=limit
    )
    return {"count": len(items), "items": items}


@app.get("/residents/checkins/summary")
async def resident_checkin_summary(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    return storage.summarize_resident_checkins(community_id=community["id"])


@app.post("/missing-persons")
async def create_missing_person(
    req: MissingPersonCreateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    report = storage.create_missing_person_report(
        community_id=community["id"],
        incident_id=req.incident_id,
        reporter_user_id=user["id"],
        name=req.name,
        age=req.age,
        contact=req.contact,
        last_seen_location=req.last_seen_location,
        priority=req.priority,
        status=req.status,
        notes=req.notes,
    )
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="missing_person.create",
        target_type="missing_person",
        target_id=report["id"],
        detail={"priority": req.priority, "status": req.status},
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="missing_person_reported",
        title=f"失联人员上报：{req.name}",
        content=f"优先级 {req.priority}，状态 {req.status}",
        entity_type="missing_person",
        entity_id=report["id"],
        payload={"missing_person": report},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )
    return {"status": "success", "report": report}


@app.get("/missing-persons")
async def list_missing_persons(
    limit: int = Query(default=150, ge=1, le=400),
    status: str | None = Query(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_missing_person_reports(
        community_id=community["id"], limit=limit, status=status
    )
    return {"count": len(items), "items": items}


@app.post("/shelters")
async def create_shelter(
    req: ShelterCreateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    shelter = storage.create_shelter(
        community_id=community["id"],
        name=req.name,
        address=req.address,
        lat=req.lat,
        lng=req.lng,
        capacity=req.capacity,
        current_occupancy=req.current_occupancy,
        status=req.status,
    )
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="shelter.create",
        target_type="shelter",
        target_id=shelter["id"],
        detail={"capacity": req.capacity, "status": req.status},
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="shelter_created",
        title=f"避难点已创建：{req.name}",
        content=f"容量 {req.capacity}，当前 {req.current_occupancy}",
        entity_type="shelter",
        entity_id=shelter["id"],
        payload={"shelter": shelter},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )
    return {"status": "success", "shelter": shelter}


@app.get("/shelters")
async def list_shelters(
    limit: int = Query(default=120, ge=1, le=300),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_shelters(community_id=community["id"], limit=limit)
    return {"count": len(items), "items": items}


@app.patch("/shelters/{shelter_id}/occupancy")
async def update_shelter_occupancy(
    shelter_id: str,
    req: ShelterOccupancyUpdateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    if req.delta is None and req.absolute_occupancy is None and req.status is None:
        raise HTTPException(status_code=400, detail="至少提供一个更新字段")
    shelter = storage.update_shelter_occupancy(
        shelter_id=shelter_id,
        community_id=community["id"],
        delta=req.delta,
        absolute_occupancy=req.absolute_occupancy,
        status=req.status,
        reason=req.reason,
        created_by_user_id=user["id"],
    )
    if not shelter:
        raise HTTPException(status_code=404, detail="避难点不存在")
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="shelter.occupancy.update",
        target_type="shelter",
        target_id=shelter_id,
        detail={
            "delta": req.delta,
            "absolute_occupancy": req.absolute_occupancy,
            "status": req.status,
        },
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="shelter_occupancy_updated",
        title=f"避难点人数更新：{shelter.get('name', shelter_id)}",
        content=f"当前收容 {shelter.get('current_occupancy', 0)}/{shelter.get('capacity', 0)}",
        entity_type="shelter",
        entity_id=shelter_id,
        payload={"shelter": shelter},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )
    return {"status": "success", "shelter": shelter}


@app.post("/hazards/zones")
async def create_hazard_zone(
    req: HazardZoneCreateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    polygon = [{"lat": point.lat, "lng": point.lng} for point in req.polygon]
    zone = storage.create_hazard_zone(
        community_id=community["id"],
        incident_id=req.incident_id,
        name=req.name,
        risk_level=req.risk_level,
        zone_type=req.zone_type,
        polygon=polygon,
        notes=req.notes,
        status=req.status,
        created_by_user_id=user["id"],
    )
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="hazard_zone.create",
        target_type="hazard_zone",
        target_id=zone["id"],
        detail={"risk_level": req.risk_level, "point_count": len(polygon)},
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="hazard_zone_updated",
        title=f"风险区已标绘：{req.name}",
        content=f"等级 {req.risk_level}，点位 {len(polygon)} 个",
        entity_type="hazard_zone",
        entity_id=zone["id"],
        payload={"hazard_zone": zone},
        created_by_user_id=user["id"],
        ws_type="hazard_zone_updated",
    )
    return {"status": "success", "hazard_zone": zone}


@app.get("/hazards/zones")
async def list_hazard_zones(
    limit: int = Query(default=120, ge=1, le=300),
    incident_id: str | None = Query(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_hazard_zones(
        community_id=community["id"], incident_id=incident_id, limit=limit
    )
    return {"count": len(items), "items": items}


@app.post("/roads/blocks")
async def create_road_block(
    req: RoadBlockCreateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    block = storage.create_road_block(
        community_id=community["id"],
        incident_id=req.incident_id,
        title=req.title,
        details=req.details,
        lat=req.lat,
        lng=req.lng,
        severity=req.severity,
        status=req.status,
        created_by_user_id=user["id"],
    )
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="road_block.create",
        target_type="road_block",
        target_id=block["id"],
        detail={"severity": req.severity, "status": req.status},
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="road_block_updated",
        title=f"道路阻断更新：{req.title}",
        content=f"等级 {req.severity}，状态 {req.status}",
        entity_type="road_block",
        entity_id=block["id"],
        payload={"road_block": block},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )
    return {"status": "success", "road_block": block}


@app.get("/roads/blocks")
async def list_road_blocks(
    limit: int = Query(default=120, ge=1, le=300),
    incident_id: str | None = Query(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_road_blocks(
        community_id=community["id"], incident_id=incident_id, limit=limit
    )
    return {"count": len(items), "items": items}


@app.post("/community/notification-templates")
async def create_notification_template(
    req: NotificationTemplateCreateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    template = storage.create_notification_template(
        community_id=community["id"],
        name=req.name,
        level=req.level,
        title_template=req.title_template,
        content_template=req.content_template,
        created_by_user_id=user["id"],
    )
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="notification_template.create",
        target_type="notification_template",
        target_id=template["id"],
        detail={"level": req.level, "name": req.name},
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="notification_template_created",
        title=f"通知模板新增：{req.name}",
        content=f"级别 {req.level}",
        entity_type="notification_template",
        entity_id=template["id"],
        payload={"template": template},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )
    return {"status": "success", "template": template}


@app.get("/community/notification-templates")
async def list_notification_templates(
    limit: int = Query(default=80, ge=1, le=200),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_notification_templates(community_id=community["id"], limit=limit)
    return {"count": len(items), "items": items}


@app.post("/community/notifications/receipt")
async def mark_notification_receipt(
    req: NotificationReceiptRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    receipt = storage.upsert_notification_receipt(
        notification_id=req.notification_id,
        community_id=community["id"],
        user_id=user["id"],
        status=req.status,
    )
    summary = storage.summarize_notification_receipts(
        community_id=community["id"],
        notification_id=req.notification_id,
    )
    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="notification.receipt.upsert",
        target_type="notification",
        target_id=req.notification_id,
        detail={"status": req.status},
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="notification_receipt_updated",
        title="通知回执更新",
        content=f"通知 {req.notification_id} 新增 {req.status} 回执",
        entity_type="notification",
        entity_id=req.notification_id,
        payload={"receipt": receipt, "summary": summary},
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )
    return {"status": "success", "receipt": receipt, "summary": summary}


@app.get("/community/notifications/{notification_id}/receipts/summary")
async def notification_receipt_summary(
    notification_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    return storage.summarize_notification_receipts(
        community_id=community["id"], notification_id=notification_id
    )


@app.get("/ops/timeline")
async def list_ops_timeline(
    limit: int = Query(default=200, ge=1, le=800),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_ops_timeline(community_id=community["id"], limit=limit)
    return {"count": len(items), "items": items}


@app.get("/ops/audit-logs")
async def list_audit_logs(
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_audit_logs(community_id=community["id"], limit=limit)
    return {"count": len(items), "items": items}


async def _perform_earthquake_rescue_analysis(
    *,
    description: str,
    lat: float | None,
    lng: float | None,
    images: list[UploadFile] | None,
    user: dict[str, Any],
    trigger_source: str,
    deprecated_endpoint: bool,
) -> dict[str, Any]:
    community = user["community"]
    image_files = images or []
    if not image_files:
        raise HTTPException(status_code=400, detail="请至少上传 1 张地震现场图")
    if len(image_files) > MAX_RESCUE_IMAGES:
        raise HTTPException(status_code=400, detail=f"最多上传 {MAX_RESCUE_IMAGES} 张现场图片")
    if lat is not None and not (-90 <= lat <= 90):
        raise HTTPException(status_code=400, detail="lat 越界")
    if lng is not None and not (-180 <= lng <= 180):
        raise HTTPException(status_code=400, detail="lng 越界")

    image_dir = settings.upload_dir / "earthquake_images"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_urls: list[str] = []
    image_payloads: list[dict[str, Any]] = []
    for image in image_files:
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="上传文件中包含非图片类型")
        if image.content_type.lower() in UNSUPPORTED_AERIAL_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail="暂不支持 HEIC/HEIF，请先转换为 JPG/PNG 后再上传",
            )
        raw = await image.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"图片过大，单张限制 {MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
            )
        try:
            with Image.open(io.BytesIO(raw)) as verified:
                verified.verify()
        except UnidentifiedImageError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"无法识别图片格式：{image.filename or '未命名文件'}，请使用 JPG/PNG/WebP",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"图片校验失败：{image.filename or '未命名文件'}",
            ) from exc

        ext = Path(image.filename or "").suffix.lower() or ".jpg"
        fname = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex}{ext}"
        fpath = image_dir / fname
        fpath.write_bytes(raw)
        url = f"/uploads/earthquake_images/{fname}"
        image_urls.append(url)
        image_payloads.append(
            {"name": image.filename or fname, "bytes": raw, "mime": image.content_type, "url": url}
        )

    ai_resp = earthquake_rescue_analyzer.analyze(
        community_id=community["id"],
        description=description.strip(),
        lat=lat,
        lng=lng,
        images=image_payloads,
    )
    analysis = ai_resp.get("analysis") if isinstance(ai_resp.get("analysis"), dict) else {}
    victims = analysis.get("victims") if isinstance(analysis.get("victims"), list) else []
    victim_count = len(victims)

    record = storage.add_earthquake_rescue_analysis(
        community_id=community["id"],
        requester_user_id=user["id"],
        description=description.strip(),
        lat=lat,
        lng=lng,
        image_urls=image_urls,
        analysis=analysis,
        status=str(ai_resp.get("status", "degraded")),
    )
    record.pop("image_urls_json", None)
    record.pop("analysis_json", None)

    dispatch_run = await execute_dispatch_agent_for_analysis(
        community=community,
        user=user,
        analysis_record=record,
        trigger_source=trigger_source,
    )

    notice_content = (
        f"[{community['name']}] 地震受灾搜救分析已更新：识别疑似受灾人员 {victim_count} 人。"
        "自动调度 Agent 已同步生成搜救任务，请救援小组按路线执行。"
    )
    notification = storage.create_notification(
        community_id=community["id"],
        sender_user_id=user["id"],
        title="地震受灾搜救分析更新",
        content=notice_content,
        payload={
            "analysis_id": record["id"],
            "victim_count": victim_count,
            "dispatch_agent_run_id": dispatch_run.get("id"),
        },
    )
    notification.pop("payload_json", None)

    ws_payload = {
        "analysis": record,
        "notification": notification,
        "dispatch_agent_run": dispatch_run,
        "deprecated_endpoint": deprecated_endpoint,
    }
    await manager.broadcast_to_community(
        community["id"],
        {
            "type": "earthquake_rescue_analysis",
            **ws_payload,
        },
    )
    await manager.broadcast_to_community(
        community["id"],
        {
            "type": "fire_rescue_analysis",
            **ws_payload,
        },
    )
    await manager.broadcast_to_community(
        community["id"],
        {
            "type": "community_alert",
            "source": "COMMUNITY_ALERT",
            "title": "地震受灾搜救分析更新",
            "content": notice_content,
            "community_id": community["id"],
            "notification": notification,
        },
    )

    record_audit(
        community_id=community["id"],
        user_id=user["id"],
        action="earthquake_rescue_analysis.create",
        target_type="earthquake_rescue_analysis",
        target_id=record["id"],
        detail={
            "victim_count": victim_count,
            "analysis_status": ai_resp.get("status", "degraded"),
            "deprecated_endpoint": deprecated_endpoint,
        },
    )
    await record_ops_event(
        community_id=community["id"],
        event_type="earthquake_rescue_analysis_updated",
        title="地震受灾搜救分析已更新",
        content=f"识别疑似受灾人员 {victim_count} 人，状态 {record['status']}",
        entity_type="earthquake_rescue_analysis",
        entity_id=record["id"],
        payload={
            "analysis": record,
            "notification": notification,
            "dispatch_agent_run": dispatch_run,
            "deprecated_endpoint": deprecated_endpoint,
        },
        created_by_user_id=user["id"],
        ws_type="ops_timeline_event",
    )

    return {
        "status": "success",
        "analysis_status": ai_resp.get("status", "degraded"),
        "analysis_error": ai_resp.get("error"),
        "result": record,
        "notification": notification,
        "dispatch_agent_run": dispatch_run,
        "deprecated_endpoint": deprecated_endpoint,
    }


@app.post("/rescue/earthquake/analyze")
async def earthquake_rescue_analyze(
    description: str = Form(""),
    lat: float | None = Form(default=None),
    lng: float | None = Form(default=None),
    images: list[UploadFile] | None = File(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return await _perform_earthquake_rescue_analysis(
        description=description,
        lat=lat,
        lng=lng,
        images=images,
        user=user,
        trigger_source="earthquake_rescue_endpoint",
        deprecated_endpoint=False,
    )


@app.post("/rescue/fire/analyze")
async def fire_rescue_analyze_legacy(
    description: str = Form(""),
    lat: float | None = Form(default=None),
    lng: float | None = Form(default=None),
    images: list[UploadFile] | None = File(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    payload = await _perform_earthquake_rescue_analysis(
        description=description,
        lat=lat,
        lng=lng,
        images=images,
        user=user,
        trigger_source="legacy_fire_proxy",
        deprecated_endpoint=True,
    )
    payload["deprecation_note"] = "请迁移至 /rescue/earthquake/analyze"
    return payload


@app.get("/rescue/earthquake/analyses")
async def list_earthquake_rescue_analyses(
    limit: int = Query(default=20, ge=1, le=200),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_earthquake_rescue_analyses(community_id=community["id"], limit=limit)
    for item in items:
        item.pop("image_urls_json", None)
        item.pop("analysis_json", None)
    return {"count": len(items), "items": items}


@app.get("/rescue/fire/analyses")
async def list_fire_rescue_analyses_legacy(
    limit: int = Query(default=20, ge=1, le=200),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    payload = await list_earthquake_rescue_analyses(limit=limit, user=user)
    payload["deprecated_endpoint"] = True
    payload["deprecation_note"] = "请迁移至 /rescue/earthquake/analyses"
    return payload


@app.get("/dispatch-agent/runs")
async def list_dispatch_agent_runs(
    limit: int = Query(default=20, ge=1, le=200),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    community = user["community"]
    items = storage.list_dispatch_agent_runs(community_id=community["id"], limit=limit)
    for item in items:
        item.pop("input_json", None)
        item.pop("plan_json", None)
        item.pop("execution_json", None)
    return {"count": len(items), "items": items}


@app.get("/reports/recent")
async def get_recent_reports(
    limit: int = Query(default=50, ge=1, le=500),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    reports = storage.list_recent_earthquake_reports(
        limit=limit,
        community_id=user["community"]["id"],
    )
    for item in reports:
        item.pop("vlm_advice_json", None)
    return {"count": len(reports), "items": reports}


@app.get("/system/summary")
async def system_summary(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    summary = storage.get_summary(community_id=user["community"]["id"])
    latest = summary.get("latest_report")
    if isinstance(latest, dict):
        latest.pop("vlm_advice_json", None)
    return summary


@app.get("/missions/{mission_id}")
async def get_mission(
    mission_id: str,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    mission = storage.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission


@app.post("/mission/start")
async def start_mission(
    req: MissionRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        mission_id = await process_mission(
            req.description,
            community_id=user["community"]["id"],
        )
        mission = storage.get_mission(mission_id)
        return {"status": "completed", "mission_id": mission_id, "mission": mission}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to run mission: {exc}") from exc


@app.post("/report/earthquake")
async def report_earthquake(
    req: EarthquakeReportRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return await create_earthquake_report_and_notify(
        user=user,
        lat=req.lat,
        lng=req.lng,
        felt_level=req.felt_level,
        building_type=req.building_type,
        structure_notes=req.structure_notes,
        description=req.description,
        image_bytes=None,
        image_mime=None,
        image_url=None,
    )


@app.post("/report/earthquake_with_media")
async def report_earthquake_with_media(
    lat: float = Form(..., ge=-90, le=90),
    lng: float = Form(..., ge=-180, le=180),
    felt_level: int = Form(..., ge=1, le=12),
    building_type: str = Form(...),
    structure_notes: str = Form(""),
    description: str = Form(""),
    image: UploadFile | None = File(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    image_url: str | None = None
    content: bytes | None = None
    content_type: str | None = None

    if image is not None:
        content, ext, content_type = await read_and_validate_image_upload(image)
        filename = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex}{ext}"
        file_path = settings.upload_dir / filename
        file_path.write_bytes(content)
        image_url = build_public_image_url(filename)

    return await create_earthquake_report_and_notify(
        user=user,
        lat=lat,
        lng=lng,
        felt_level=felt_level,
        building_type=building_type,
        structure_notes=structure_notes,
        description=description,
        image_bytes=content,
        image_mime=content_type,
        image_url=image_url,
    )


@app.post("/report/submit")
async def submit_report(
    report: LegacyReportRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return await create_earthquake_report_and_notify(
        user=user,
        lat=report.lat,
        lng=report.lng,
        felt_level=report.felt_level,
        building_type=report.building_type,
        structure_notes=report.structure_notes,
        description=report.description,
        image_bytes=None,
        image_mime=None,
        image_url=None,
    )


@app.post("/report/submit_with_media")
async def submit_report_with_media(
    lat: float = Form(..., ge=-90, le=90),
    lng: float = Form(..., ge=-180, le=180),
    type: str = Form("earthquake"),
    description: str = Form(""),
    felt_level: int = Form(5),
    building_type: str = Form("未知建筑"),
    structure_notes: str = Form(""),
    image: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    _ = type
    content, ext, content_type = await read_and_validate_image_upload(image)

    filename = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex}{ext}"
    file_path = settings.upload_dir / filename
    file_path.write_bytes(content)
    image_url = build_public_image_url(filename)

    return await create_earthquake_report_and_notify(
        user=user,
        lat=lat,
        lng=lng,
        felt_level=felt_level,
        building_type=building_type,
        structure_notes=structure_notes,
        description=description,
        image_bytes=content,
        image_mime=content_type,
        image_url=image_url,
    )


@app.post("/ai/route_advice")
async def ai_route_advice(
    req: RouteAdviceRequest,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    analysis = run_vlm_analysis(
        lat=req.lat,
        lng=req.lng,
        felt_level=req.felt_level,
        building_type=req.building_type,
        structure_notes=req.structure_notes,
        description=req.description,
        image_bytes=None,
        image_mime=None,
    )
    return {
        "status": analysis.get("status", "mock"),
        "advice": analysis.get("advice", []),
        "advice_text": analysis.get("advice_text"),
        "error": analysis.get("error"),
    }


@app.websocket("/ws/mission")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    user = resolve_user_from_token(token)
    await manager.connect(websocket, user)
    await websocket.send_json(
        {
            "type": "status",
            "source": "SYSTEM",
            "content": "WebSocket connected",
            "time": utc_now(),
            "authenticated": bool(user),
            "community": user.get("community") if user else None,
            "base_city": settings.base_city,
        }
    )
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "source": "SYSTEM",
                        "content": "Invalid message format, expected JSON.",
                    }
                )
                continue

            ptype = payload.get("type")
            if ptype == "start_mission":
                if not user or not user.get("community"):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "source": "SYSTEM",
                            "content": "请先登录社区账号再发送任务。",
                        }
                    )
                    continue
                description = str(payload.get("description", "")).strip()
                if len(description) < 2:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "source": "SYSTEM",
                            "content": "Mission description is too short.",
                        }
                    )
                    continue
                await process_mission(description, community_id=user["community"]["id"])
            elif ptype == "ping":
                await websocket.send_json({"type": "pong", "time": utc_now()})
            elif ptype == "fetch_recent_reports":
                if not user or not user.get("community"):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "source": "SYSTEM",
                            "content": "请先登录后再查看社区报告。",
                        }
                    )
                    continue
                limit = int(payload.get("limit", 50))
                reports = storage.list_recent_earthquake_reports(
                    limit=max(1, min(limit, 500)),
                    community_id=user["community"]["id"],
                )
                for item in reports:
                    item.pop("vlm_advice_json", None)
                await websocket.send_json({"type": "recent_reports", "items": reports})
            elif ptype == "fetch_notifications":
                if not user or not user.get("community"):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "source": "SYSTEM",
                            "content": "请先登录后再查看社区通知。",
                        }
                    )
                    continue
                limit = int(payload.get("limit", 30))
                items = storage.list_notifications(
                    community_id=user["community"]["id"],
                    limit=max(1, min(limit, 500)),
                )
                for item in items:
                    item.pop("payload_json", None)
                await websocket.send_json({"type": "community_notifications", "items": items})
            elif ptype == "fetch_chat_messages":
                if not user or not user.get("community"):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "source": "SYSTEM",
                            "content": "请先登录后再查看社区聊天。",
                        }
                    )
                    continue
                limit = int(payload.get("limit", 100))
                items = storage.list_chat_messages(
                    community_id=user["community"]["id"],
                    limit=max(1, min(limit, 500)),
                )
                for item in items:
                    item.pop("metadata_json", None)
                await websocket.send_json({"type": "community_chat_messages", "items": items})
            elif ptype == "community_chat_send":
                if not user or not user.get("community"):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "source": "SYSTEM",
                            "content": "请先登录后再发送社区聊天消息。",
                        }
                    )
                    continue
                content = str(payload.get("content", "")).strip()
                ask_ai = bool(payload.get("ask_ai", False))
                if not content:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "source": "SYSTEM",
                            "content": "消息内容不能为空。",
                        }
                    )
                    continue
                await create_and_broadcast_chat_message(
                    community_id=user["community"]["id"],
                    sender_user_id=user["id"],
                    sender_name=user["display_name"],
                    role="user",
                    content=content,
                )
                if ask_ai:
                    history = storage.list_chat_messages(
                        community_id=user["community"]["id"], limit=40
                    )
                    ai_resp = run_community_assistant(
                        community_id=user["community"]["id"],
                        user_display_name=user["display_name"],
                        question=content,
                        recent_chat_messages=history,
                    )
                    await create_and_broadcast_chat_message(
                        community_id=user["community"]["id"],
                        sender_user_id=None,
                        sender_name="社区AI助手",
                        role="assistant",
                        content=str(ai_resp.get("answer", "")),
                        metadata={
                            "status": ai_resp.get("status"),
                            "error": ai_resp.get("error"),
                        },
                    )
            elif ptype in {"fetch_fire_rescue_analyses", "fetch_earthquake_rescue_analyses"}:
                if not user or not user.get("community"):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "source": "SYSTEM",
                            "content": "请先登录后再查看地震搜救分析。",
                        }
                    )
                    continue
                limit = int(payload.get("limit", 20))
                items = storage.list_earthquake_rescue_analyses(
                    community_id=user["community"]["id"],
                    limit=max(1, min(limit, 200)),
                )
                for item in items:
                    item.pop("image_urls_json", None)
                    item.pop("analysis_json", None)
                await websocket.send_json({"type": "fire_rescue_analyses", "items": items})
                await websocket.send_json({"type": "earthquake_rescue_analyses", "items": items})
            elif ptype == "fetch_dispatch_agent_runs":
                if not user or not user.get("community"):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "source": "SYSTEM",
                            "content": "请先登录后再查看自动调度记录。",
                        }
                    )
                    continue
                limit = int(payload.get("limit", 20))
                items = storage.list_dispatch_agent_runs(
                    community_id=user["community"]["id"],
                    limit=max(1, min(limit, 200)),
                )
                for item in items:
                    item.pop("input_json", None)
                    item.pop("plan_json", None)
                    item.pop("execution_json", None)
                await websocket.send_json({"type": "dispatch_agent_runs", "items": items})
            elif ptype == "fetch_incidents":
                if not user or not user.get("community"):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "source": "SYSTEM",
                            "content": "请先登录后再查看事件列表。",
                        }
                    )
                    continue
                limit = int(payload.get("limit", 80))
                items = storage.list_incidents(
                    community_id=user["community"]["id"],
                    limit=max(1, min(limit, 300)),
                )
                await websocket.send_json({"type": "incidents", "items": items})
            elif ptype == "fetch_tasks":
                if not user or not user.get("community"):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "source": "SYSTEM",
                            "content": "请先登录后再查看任务列表。",
                        }
                    )
                    continue
                limit = int(payload.get("limit", 150))
                incident_id = payload.get("incident_id")
                items = storage.list_tasks(
                    community_id=user["community"]["id"],
                    incident_id=str(incident_id) if incident_id else None,
                    limit=max(1, min(limit, 500)),
                )
                await websocket.send_json({"type": "tasks", "items": items})
            elif ptype == "fetch_teams":
                if not user or not user.get("community"):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "source": "SYSTEM",
                            "content": "请先登录后再查看救援队。",
                        }
                    )
                    continue
                limit = int(payload.get("limit", 120))
                ensure_local_response_teams(user["community"])
                items = storage.list_response_teams(
                    community_id=user["community"]["id"],
                    limit=max(1, min(limit, 300)),
                )
                await websocket.send_json({"type": "teams", "items": items})
            elif ptype == "fetch_ops_timeline":
                if not user or not user.get("community"):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "source": "SYSTEM",
                            "content": "请先登录后再查看时间轴。",
                        }
                    )
                    continue
                limit = int(payload.get("limit", 200))
                items = storage.list_ops_timeline(
                    community_id=user["community"]["id"],
                    limit=max(1, min(limit, 800)),
                )
                await websocket.send_json({"type": "ops_timeline", "items": items})
            elif ptype == "fetch_resident_checkin_summary":
                if not user or not user.get("community"):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "source": "SYSTEM",
                            "content": "请先登录后再查看居民回执统计。",
                        }
                    )
                    continue
                summary = storage.summarize_resident_checkins(
                    community_id=user["community"]["id"]
                )
                await websocket.send_json({"type": "resident_checkin_summary", "summary": summary})
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "source": "SYSTEM",
                        "content": f"Unsupported command: {ptype}",
                    }
                )
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
