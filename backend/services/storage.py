from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.database_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS reports (
                        id TEXT PRIMARY KEY,
                        lat REAL NOT NULL,
                        lng REAL NOT NULL,
                        category TEXT NOT NULL,
                        description TEXT NOT NULL,
                        image_url TEXT,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS missions (
                        id TEXT PRIMARY KEY,
                        description TEXT NOT NULL,
                        status TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        completed_at TEXT
                    );

                    CREATE TABLE IF NOT EXISTS mission_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        mission_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(mission_id) REFERENCES missions(id)
                    );

                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        display_name TEXT NOT NULL,
                        password_hash TEXT NOT NULL,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS communities (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        district TEXT NOT NULL,
                        base_lat REAL NOT NULL,
                        base_lng REAL NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS community_memberships (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        community_id TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'member',
                        created_at TEXT NOT NULL,
                        UNIQUE(user_id, community_id),
                        FOREIGN KEY(user_id) REFERENCES users(id),
                        FOREIGN KEY(community_id) REFERENCES communities(id)
                    );

                    CREATE TABLE IF NOT EXISTS earthquake_reports (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        community_id TEXT NOT NULL,
                        lat REAL NOT NULL,
                        lng REAL NOT NULL,
                        felt_level INTEGER NOT NULL,
                        building_type TEXT NOT NULL,
                        structure_notes TEXT NOT NULL,
                        description TEXT NOT NULL,
                        image_url TEXT,
                        vlm_advice_json TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(id),
                        FOREIGN KEY(community_id) REFERENCES communities(id)
                    );

                    CREATE TABLE IF NOT EXISTS community_notifications (
                        id TEXT PRIMARY KEY,
                        community_id TEXT NOT NULL,
                        sender_user_id TEXT,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        payload_json TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(sender_user_id) REFERENCES users(id)
                    );
                    """
                )
                conn.commit()

    def _safe_load_json(self, raw: str | None) -> Any:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def create_user(
        self, username: str, display_name: str, password_hash: str
    ) -> dict[str, Any]:
        user = {
            "id": uuid.uuid4().hex,
            "username": username.strip().lower(),
            "display_name": display_name.strip(),
            "password_hash": password_hash,
            "is_active": 1,
            "created_at": utc_now(),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users (id, username, display_name, password_hash, is_active, created_at)
                    VALUES (:id, :username, :display_name, :password_hash, :is_active, :created_at)
                    """,
                    user,
                )
                conn.commit()
        return user

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT id, username, display_name, password_hash, is_active, created_at
                    FROM users
                    WHERE username = ?
                    LIMIT 1
                    """,
                    (username.strip().lower(),),
                ).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT id, username, display_name, password_hash, is_active, created_at
                    FROM users
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (user_id,),
                ).fetchone()
        return dict(row) if row else None

    def create_or_get_community(
        self, name: str, district: str, base_lat: float, base_lng: float
    ) -> dict[str, Any]:
        normalized = name.strip()
        with self._lock:
            with self._connect() as conn:
                existing = conn.execute(
                    """
                    SELECT id, name, district, base_lat, base_lng, created_at
                    FROM communities
                    WHERE name = ?
                    LIMIT 1
                    """,
                    (normalized,),
                ).fetchone()
                if existing is not None:
                    return dict(existing)

                community = {
                    "id": uuid.uuid4().hex,
                    "name": normalized,
                    "district": district.strip() or "成都",
                    "base_lat": float(base_lat),
                    "base_lng": float(base_lng),
                    "created_at": utc_now(),
                }
                conn.execute(
                    """
                    INSERT INTO communities (id, name, district, base_lat, base_lng, created_at)
                    VALUES (:id, :name, :district, :base_lat, :base_lng, :created_at)
                    """,
                    community,
                )
                conn.commit()
        return community

    def get_community_by_id(self, community_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT id, name, district, base_lat, base_lng, created_at
                    FROM communities
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (community_id,),
                ).fetchone()
        return dict(row) if row else None

    def get_community_member_count(self, community_id: str) -> int:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM community_memberships
                    WHERE community_id = ?
                    """,
                    (community_id,),
                ).fetchone()
        return int(row["count"]) if row else 0

    def add_user_to_community(
        self, user_id: str, community_id: str, role: str = "member"
    ) -> dict[str, Any]:
        membership = {
            "user_id": user_id,
            "community_id": community_id,
            "role": role,
            "created_at": utc_now(),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO community_memberships (user_id, community_id, role, created_at)
                    VALUES (:user_id, :community_id, :role, :created_at)
                    """,
                    membership,
                )
                conn.commit()
                row = conn.execute(
                    """
                    SELECT id, user_id, community_id, role, created_at
                    FROM community_memberships
                    WHERE user_id = ? AND community_id = ?
                    LIMIT 1
                    """,
                    (user_id, community_id),
                ).fetchone()
        return dict(row) if row else membership

    def get_user_primary_community(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT c.id, c.name, c.district, c.base_lat, c.base_lng, c.created_at, m.role
                    FROM community_memberships m
                    JOIN communities c ON c.id = m.community_id
                    WHERE m.user_id = ?
                    ORDER BY m.id ASC
                    LIMIT 1
                    """,
                    (user_id,),
                ).fetchone()
        return dict(row) if row else None

    def add_earthquake_report(
        self,
        user_id: str,
        community_id: str,
        lat: float,
        lng: float,
        felt_level: int,
        building_type: str,
        structure_notes: str,
        description: str,
        image_url: str | None = None,
        vlm_advice: list[str] | None = None,
    ) -> dict[str, Any]:
        record = {
            "id": uuid.uuid4().hex,
            "user_id": user_id,
            "community_id": community_id,
            "lat": float(lat),
            "lng": float(lng),
            "felt_level": int(felt_level),
            "building_type": building_type.strip(),
            "structure_notes": structure_notes.strip(),
            "description": description.strip(),
            "image_url": image_url,
            "vlm_advice_json": json.dumps(vlm_advice or [], ensure_ascii=False),
            "created_at": utc_now(),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO earthquake_reports (
                        id, user_id, community_id, lat, lng, felt_level, building_type,
                        structure_notes, description, image_url, vlm_advice_json, created_at
                    )
                    VALUES (
                        :id, :user_id, :community_id, :lat, :lng, :felt_level, :building_type,
                        :structure_notes, :description, :image_url, :vlm_advice_json, :created_at
                    )
                    """,
                    record,
                )
                conn.commit()
        payload = {**record}
        payload["category"] = "earthquake"
        payload["vlm_advice"] = self._safe_load_json(record.get("vlm_advice_json")) or []
        return payload

    def list_recent_earthquake_reports(
        self, limit: int = 50, community_id: str | None = None
    ) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 500)
        with self._lock:
            with self._connect() as conn:
                if community_id:
                    rows = conn.execute(
                        """
                        SELECT
                            id, user_id, community_id, lat, lng, felt_level, building_type,
                            structure_notes, description, image_url, vlm_advice_json, created_at
                        FROM earthquake_reports
                        WHERE community_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                        """,
                        (community_id, safe_limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT
                            id, user_id, community_id, lat, lng, felt_level, building_type,
                            structure_notes, description, image_url, vlm_advice_json, created_at
                        FROM earthquake_reports
                        ORDER BY created_at DESC
                        LIMIT ?
                        """,
                        (safe_limit,),
                    ).fetchall()
        records = []
        for row in rows:
            item = dict(row)
            item["category"] = "earthquake"
            item["vlm_advice"] = self._safe_load_json(item.get("vlm_advice_json")) or []
            records.append(item)
        records.reverse()
        return records

    def create_notification(
        self,
        community_id: str,
        title: str,
        content: str,
        sender_user_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = {
            "id": uuid.uuid4().hex,
            "community_id": community_id,
            "sender_user_id": sender_user_id,
            "title": title.strip(),
            "content": content.strip(),
            "payload_json": json.dumps(payload or {}, ensure_ascii=False),
            "created_at": utc_now(),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO community_notifications (
                        id, community_id, sender_user_id, title, content, payload_json, created_at
                    )
                    VALUES (
                        :id, :community_id, :sender_user_id, :title, :content, :payload_json, :created_at
                    )
                    """,
                    record,
                )
                conn.commit()
        payload = {**record}
        payload["payload"] = self._safe_load_json(record.get("payload_json")) or {}
        return payload

    def list_notifications(
        self, community_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 500)
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        n.id, n.community_id, n.sender_user_id, n.title, n.content,
                        n.payload_json, n.created_at,
                        u.display_name as sender_name
                    FROM community_notifications n
                    LEFT JOIN users u ON u.id = n.sender_user_id
                    WHERE n.community_id = ?
                    ORDER BY n.created_at DESC
                    LIMIT ?
                    """,
                    (community_id, safe_limit),
                ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["payload"] = self._safe_load_json(item.get("payload_json")) or {}
            items.append(item)
        items.reverse()
        return items

    def create_mission(self, description: str) -> dict[str, Any]:
        mission = {
            "id": uuid.uuid4().hex,
            "description": description.strip(),
            "status": "running",
            "started_at": utc_now(),
            "completed_at": None,
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO missions (id, description, status, started_at, completed_at)
                    VALUES (:id, :description, :status, :started_at, :completed_at)
                    """,
                    mission,
                )
                conn.commit()
        return mission

    def update_mission_status(self, mission_id: str, status: str) -> None:
        completed_at = utc_now() if status in {"completed", "failed"} else None
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE missions
                    SET status = ?, completed_at = COALESCE(?, completed_at)
                    WHERE id = ?
                    """,
                    (status, completed_at, mission_id),
                )
                conn.commit()

    def add_mission_event(
        self, mission_id: str, source: str, message_type: str, content: str
    ) -> dict[str, Any]:
        event = {
            "mission_id": mission_id,
            "source": source,
            "type": message_type,
            "content": content,
            "created_at": utc_now(),
        }
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO mission_events (mission_id, source, type, content, created_at)
                    VALUES (:mission_id, :source, :type, :content, :created_at)
                    """,
                    event,
                )
                conn.commit()
                event["id"] = cursor.lastrowid
        return event

    def get_mission(self, mission_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                mission_row = conn.execute(
                    """
                    SELECT id, description, status, started_at, completed_at
                    FROM missions
                    WHERE id = ?
                    """,
                    (mission_id,),
                ).fetchone()
                if mission_row is None:
                    return None
                event_rows = conn.execute(
                    """
                    SELECT id, source, type, content, created_at
                    FROM mission_events
                    WHERE mission_id = ?
                    ORDER BY id ASC
                    """,
                    (mission_id,),
                ).fetchall()
        mission = dict(mission_row)
        mission["events"] = [dict(row) for row in event_rows]
        return mission

    def get_summary(self, community_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            with self._connect() as conn:
                if community_id:
                    total_reports = conn.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM earthquake_reports
                        WHERE community_id = ?
                        """,
                        (community_id,),
                    ).fetchone()
                    latest_report = conn.execute(
                        """
                        SELECT
                            id, user_id, community_id, lat, lng, felt_level, building_type,
                            structure_notes, description, image_url, vlm_advice_json, created_at
                        FROM earthquake_reports
                        WHERE community_id = ?
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (community_id,),
                    ).fetchone()
                else:
                    total_reports = conn.execute(
                        "SELECT COUNT(*) as count FROM earthquake_reports"
                    ).fetchone()
                    latest_report = conn.execute(
                        """
                        SELECT
                            id, user_id, community_id, lat, lng, felt_level, building_type,
                            structure_notes, description, image_url, vlm_advice_json, created_at
                        FROM earthquake_reports
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    ).fetchone()
                running_missions = conn.execute(
                    "SELECT COUNT(*) as count FROM missions WHERE status = 'running'"
                ).fetchone()

        latest = dict(latest_report) if latest_report else None
        if latest:
            latest["category"] = "earthquake"
            latest["vlm_advice"] = self._safe_load_json(latest.get("vlm_advice_json")) or []
        return {
            "total_reports": int(total_reports["count"]) if total_reports else 0,
            "active_missions": int(running_missions["count"]) if running_missions else 0,
            "report_counts": {"earthquake": int(total_reports["count"]) if total_reports else 0},
            "latest_report": latest,
        }
