from __future__ import annotations

import asyncio
import base64
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
from pydantic import BaseModel, Field

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    from backend.agents.manager import MissionManager
    from backend.config import settings
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

bearer_scheme = HTTPBearer(auto_error=False)


class MissionRequest(BaseModel):
    description: str = Field(..., min_length=2, max_length=500)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=32)
    display_name: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    community_name: str = Field(..., min_length=2, max_length=80)
    community_district: str = Field(default="成都市", max_length=80)


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


class RouteAdviceRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    type: str = Field(default="earthquake", min_length=2, max_length=64)
    description: str = Field(default="", max_length=1000)
    felt_level: int = Field(default=5, ge=1, le=12)
    building_type: str = Field(default="未知建筑", max_length=64)
    structure_notes: str = Field(default="", max_length=1000)


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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_public_image_url(filename: str) -> str:
    return f"/uploads/{filename}"


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

    return {
        "status": "success",
        "report": report,
        "shelter_advice": analysis.get("advice") or [],
        "analysis_status": analysis.get("status", "mock"),
        "analysis_error": analysis.get("error"),
        "community_notification": notification,
    }


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

    try:
        rag_snippets = retrieve_policy("earthquake shelter", k=1)
        rag_ok = isinstance(rag_snippets, list)
    except Exception:
        rag_ok = False

    status = "ok" if db_ok and rag_ok else "degraded"
    return {
        "status": status,
        "database": db_ok,
        "rag": rag_ok,
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
        district=req.community_district.strip() or "成都市",
        base_lat=settings.base_lat,
        base_lng=settings.base_lng,
    )
    member_count = storage.get_community_member_count(community["id"])
    role = "owner" if member_count == 0 else "member"
    storage.add_user_to_community(user["id"], community["id"], role=role)

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
    return {"status": "success", "notification": notification}


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
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Invalid file type. Image required.")

        ext = Path(image.filename or "").suffix.lower()
        if not ext:
            ext = ".jpg"
        content = await image.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Image too large. Limit is {MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
            )

        filename = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex}{ext}"
        file_path = settings.upload_dir / filename
        file_path.write_bytes(content)
        image_url = build_public_image_url(filename)
        content_type = image.content_type

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
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Image required.")

    ext = Path(image.filename or "").suffix.lower()
    if not ext:
        ext = ".jpg"

    content = await image.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large. Limit is {MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
        )

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
        image_mime=image.content_type,
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
