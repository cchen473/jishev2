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

    def _table_columns(self, conn: sqlite3.Connection, table_name: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row["name"]) for row in rows}

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        *,
        table_name: str,
        column_name: str,
        definition: str,
    ) -> None:
        columns = self._table_columns(conn, table_name)
        if column_name in columns:
            return
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

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

                    CREATE TABLE IF NOT EXISTS community_chat_messages (
                        id TEXT PRIMARY KEY,
                        community_id TEXT NOT NULL,
                        sender_user_id TEXT,
                        sender_name TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata_json TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(sender_user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS fire_rescue_analyses (
                        id TEXT PRIMARY KEY,
                        community_id TEXT NOT NULL,
                        requester_user_id TEXT NOT NULL,
                        description TEXT NOT NULL,
                        lat REAL,
                        lng REAL,
                        scene_model_name TEXT,
                        scene_model_url TEXT,
                        image_urls_json TEXT,
                        analysis_json TEXT,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(requester_user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS earthquake_rescue_analyses (
                        id TEXT PRIMARY KEY,
                        community_id TEXT NOT NULL,
                        requester_user_id TEXT NOT NULL,
                        description TEXT NOT NULL,
                        lat REAL,
                        lng REAL,
                        image_urls_json TEXT,
                        analysis_json TEXT,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(requester_user_id) REFERENCES users(id)
                    );

                    CREATE INDEX IF NOT EXISTS idx_membership_user
                    ON community_memberships(user_id);

                    CREATE INDEX IF NOT EXISTS idx_membership_community
                    ON community_memberships(community_id);

                    CREATE INDEX IF NOT EXISTS idx_earthquake_reports_community_created
                    ON earthquake_reports(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_notifications_community_created
                    ON community_notifications(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_chat_messages_community_created
                    ON community_chat_messages(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_fire_rescue_community_created
                    ON fire_rescue_analyses(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_eq_rescue_community_created
                    ON earthquake_rescue_analyses(community_id, created_at);

                    CREATE TABLE IF NOT EXISTS incidents (
                        id TEXT PRIMARY KEY,
                        community_id TEXT NOT NULL,
                        created_by_user_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        lat REAL,
                        lng REAL,
                        priority TEXT NOT NULL DEFAULT 'medium',
                        status TEXT NOT NULL DEFAULT 'new',
                        source TEXT NOT NULL DEFAULT 'manual',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS incident_tasks (
                        id TEXT PRIMARY KEY,
                        incident_id TEXT NOT NULL,
                        community_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'new',
                        priority TEXT NOT NULL DEFAULT 'medium',
                        assignee_user_id TEXT,
                        team_id TEXT,
                        due_at TEXT,
                        accepted_at TEXT,
                        completed_at TEXT,
                        created_by_user_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(incident_id) REFERENCES incidents(id),
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(assignee_user_id) REFERENCES users(id),
                        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS response_teams (
                        id TEXT PRIMARY KEY,
                        community_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        specialty TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'standby',
                        leader_user_id TEXT,
                        contact TEXT,
                        base_lat REAL,
                        base_lng REAL,
                        base_location_text TEXT,
                        equipment_json TEXT,
                        vehicle_json TEXT,
                        personnel_count INTEGER NOT NULL DEFAULT 0,
                        capacity INTEGER NOT NULL DEFAULT 8,
                        availability_score REAL NOT NULL DEFAULT 1.0,
                        last_active_at TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(leader_user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS team_memberships (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        team_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'member',
                        created_at TEXT NOT NULL,
                        UNIQUE(team_id, user_id),
                        FOREIGN KEY(team_id) REFERENCES response_teams(id),
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS dispatch_records (
                        id TEXT PRIMARY KEY,
                        community_id TEXT NOT NULL,
                        incident_id TEXT,
                        task_id TEXT,
                        team_id TEXT,
                        resource_type TEXT NOT NULL,
                        resource_name TEXT NOT NULL,
                        quantity INTEGER NOT NULL DEFAULT 1,
                        status TEXT NOT NULL DEFAULT 'allocated',
                        notes TEXT,
                        created_by_user_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(incident_id) REFERENCES incidents(id),
                        FOREIGN KEY(task_id) REFERENCES incident_tasks(id),
                        FOREIGN KEY(team_id) REFERENCES response_teams(id),
                        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS resident_checkins (
                        id TEXT PRIMARY KEY,
                        community_id TEXT NOT NULL,
                        user_id TEXT,
                        incident_id TEXT,
                        subject_name TEXT NOT NULL,
                        relation TEXT NOT NULL DEFAULT 'self',
                        status TEXT NOT NULL,
                        lat REAL,
                        lng REAL,
                        notes TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(user_id) REFERENCES users(id),
                        FOREIGN KEY(incident_id) REFERENCES incidents(id)
                    );

                    CREATE TABLE IF NOT EXISTS missing_person_reports (
                        id TEXT PRIMARY KEY,
                        community_id TEXT NOT NULL,
                        incident_id TEXT,
                        reporter_user_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        age INTEGER,
                        contact TEXT,
                        last_seen_location TEXT,
                        priority TEXT NOT NULL DEFAULT 'medium',
                        status TEXT NOT NULL DEFAULT 'open',
                        notes TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(incident_id) REFERENCES incidents(id),
                        FOREIGN KEY(reporter_user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS shelters (
                        id TEXT PRIMARY KEY,
                        community_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        address TEXT NOT NULL,
                        lat REAL,
                        lng REAL,
                        capacity INTEGER NOT NULL,
                        current_occupancy INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'open',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id)
                    );

                    CREATE TABLE IF NOT EXISTS shelter_occupancy_events (
                        id TEXT PRIMARY KEY,
                        shelter_id TEXT NOT NULL,
                        community_id TEXT NOT NULL,
                        delta INTEGER NOT NULL,
                        occupancy INTEGER NOT NULL,
                        reason TEXT,
                        created_by_user_id TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(shelter_id) REFERENCES shelters(id),
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS hazard_zones (
                        id TEXT PRIMARY KEY,
                        community_id TEXT NOT NULL,
                        incident_id TEXT,
                        name TEXT NOT NULL,
                        risk_level TEXT NOT NULL DEFAULT 'medium',
                        zone_type TEXT NOT NULL DEFAULT 'hazard',
                        polygon_json TEXT NOT NULL,
                        notes TEXT,
                        status TEXT NOT NULL DEFAULT 'active',
                        created_by_user_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(incident_id) REFERENCES incidents(id),
                        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS road_blocks (
                        id TEXT PRIMARY KEY,
                        community_id TEXT NOT NULL,
                        incident_id TEXT,
                        title TEXT NOT NULL,
                        details TEXT,
                        lat REAL,
                        lng REAL,
                        severity TEXT NOT NULL DEFAULT 'medium',
                        status TEXT NOT NULL DEFAULT 'active',
                        created_by_user_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(incident_id) REFERENCES incidents(id),
                        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS community_notification_templates (
                        id TEXT PRIMARY KEY,
                        community_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        level TEXT NOT NULL DEFAULT 'info',
                        title_template TEXT NOT NULL,
                        content_template TEXT NOT NULL,
                        created_by_user_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS notification_receipts (
                        id TEXT PRIMARY KEY,
                        notification_id TEXT NOT NULL,
                        community_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'read',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(notification_id, user_id),
                        FOREIGN KEY(notification_id) REFERENCES community_notifications(id),
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        community_id TEXT NOT NULL,
                        user_id TEXT,
                        action TEXT NOT NULL,
                        target_type TEXT NOT NULL,
                        target_id TEXT,
                        detail_json TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS ops_timeline_events (
                        id TEXT PRIMARY KEY,
                        community_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        entity_type TEXT,
                        entity_id TEXT,
                        payload_json TEXT,
                        created_by_user_id TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id),
                        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS dispatch_agent_runs (
                        id TEXT PRIMARY KEY,
                        community_id TEXT NOT NULL,
                        analysis_id TEXT NOT NULL,
                        trigger_source TEXT NOT NULL,
                        idempotency_key TEXT NOT NULL UNIQUE,
                        input_json TEXT,
                        plan_json TEXT,
                        execution_json TEXT,
                        status TEXT NOT NULL,
                        error TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(community_id) REFERENCES communities(id)
                    );

                    CREATE INDEX IF NOT EXISTS idx_incidents_community_created
                    ON incidents(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_tasks_community_created
                    ON incident_tasks(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_tasks_incident_status_priority
                    ON incident_tasks(incident_id, status, priority);

                    CREATE INDEX IF NOT EXISTS idx_dispatch_community_created
                    ON dispatch_records(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_checkins_community_created
                    ON resident_checkins(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_checkins_user_created
                    ON resident_checkins(user_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_missing_community_created
                    ON missing_person_reports(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_shelters_community_created
                    ON shelters(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_shelter_events_shelter_created
                    ON shelter_occupancy_events(shelter_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_hazard_zones_community_created
                    ON hazard_zones(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_road_blocks_community_created
                    ON road_blocks(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_templates_community_created
                    ON community_notification_templates(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_receipts_notification_status
                    ON notification_receipts(notification_id, status);

                    CREATE INDEX IF NOT EXISTS idx_audit_community_created
                    ON audit_logs(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_timeline_community_created
                    ON ops_timeline_events(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_dispatch_agent_runs_community_created
                    ON dispatch_agent_runs(community_id, created_at);

                    CREATE INDEX IF NOT EXISTS idx_dispatch_agent_runs_analysis
                    ON dispatch_agent_runs(analysis_id, created_at);
                    """
                )
                self._ensure_column(
                    conn,
                    table_name="response_teams",
                    column_name="base_lat",
                    definition="REAL",
                )
                self._ensure_column(
                    conn,
                    table_name="response_teams",
                    column_name="base_lng",
                    definition="REAL",
                )
                self._ensure_column(
                    conn,
                    table_name="response_teams",
                    column_name="base_location_text",
                    definition="TEXT",
                )
                self._ensure_column(
                    conn,
                    table_name="response_teams",
                    column_name="equipment_json",
                    definition="TEXT",
                )
                self._ensure_column(
                    conn,
                    table_name="response_teams",
                    column_name="vehicle_json",
                    definition="TEXT",
                )
                self._ensure_column(
                    conn,
                    table_name="response_teams",
                    column_name="personnel_count",
                    definition="INTEGER NOT NULL DEFAULT 0",
                )
                self._ensure_column(
                    conn,
                    table_name="response_teams",
                    column_name="capacity",
                    definition="INTEGER NOT NULL DEFAULT 8",
                )
                self._ensure_column(
                    conn,
                    table_name="response_teams",
                    column_name="availability_score",
                    definition="REAL NOT NULL DEFAULT 1.0",
                )
                self._ensure_column(
                    conn,
                    table_name="response_teams",
                    column_name="last_active_at",
                    definition="TEXT",
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

    def add_chat_message(
        self,
        *,
        community_id: str,
        sender_name: str,
        role: str,
        content: str,
        sender_user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = {
            "id": uuid.uuid4().hex,
            "community_id": community_id,
            "sender_user_id": sender_user_id,
            "sender_name": sender_name.strip() or "unknown",
            "role": role.strip() or "user",
            "content": content.strip(),
            "metadata_json": json.dumps(metadata or {}, ensure_ascii=False),
            "created_at": utc_now(),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO community_chat_messages (
                        id, community_id, sender_user_id, sender_name, role, content, metadata_json, created_at
                    )
                    VALUES (
                        :id, :community_id, :sender_user_id, :sender_name, :role, :content, :metadata_json, :created_at
                    )
                    """,
                    record,
                )
                conn.commit()
        payload = {**record}
        payload["metadata"] = self._safe_load_json(record.get("metadata_json")) or {}
        return payload

    def list_chat_messages(
        self, *, community_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 500)
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        id, community_id, sender_user_id, sender_name, role,
                        content, metadata_json, created_at
                    FROM community_chat_messages
                    WHERE community_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (community_id, safe_limit),
                ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["metadata"] = self._safe_load_json(item.get("metadata_json")) or {}
            items.append(item)
        items.reverse()
        return items

    def add_fire_rescue_analysis(
        self,
        *,
        community_id: str,
        requester_user_id: str,
        description: str,
        lat: float | None,
        lng: float | None,
        scene_model_name: str | None,
        scene_model_url: str | None,
        image_urls: list[str] | None,
        analysis: dict[str, Any],
        status: str,
    ) -> dict[str, Any]:
        record = {
            "id": uuid.uuid4().hex,
            "community_id": community_id,
            "requester_user_id": requester_user_id,
            "description": description.strip(),
            "lat": lat,
            "lng": lng,
            "scene_model_name": scene_model_name,
            "scene_model_url": scene_model_url,
            "image_urls_json": json.dumps(image_urls or [], ensure_ascii=False),
            "analysis_json": json.dumps(analysis or {}, ensure_ascii=False),
            "status": status,
            "created_at": utc_now(),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO fire_rescue_analyses (
                        id, community_id, requester_user_id, description, lat, lng,
                        scene_model_name, scene_model_url, image_urls_json, analysis_json, status, created_at
                    )
                    VALUES (
                        :id, :community_id, :requester_user_id, :description, :lat, :lng,
                        :scene_model_name, :scene_model_url, :image_urls_json, :analysis_json, :status, :created_at
                    )
                    """,
                    record,
                )
                conn.commit()
        payload = {**record}
        payload["image_urls"] = self._safe_load_json(record.get("image_urls_json")) or []
        payload["analysis"] = self._safe_load_json(record.get("analysis_json")) or {}
        return payload

    def list_fire_rescue_analyses(
        self, *, community_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 200)
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        id, community_id, requester_user_id, description, lat, lng,
                        scene_model_name, scene_model_url, image_urls_json, analysis_json, status, created_at
                    FROM fire_rescue_analyses
                    WHERE community_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (community_id, safe_limit),
                ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["image_urls"] = self._safe_load_json(item.get("image_urls_json")) or []
            item["analysis"] = self._safe_load_json(item.get("analysis_json")) or {}
            items.append(item)
        items.reverse()
        return items

    def add_earthquake_rescue_analysis(
        self,
        *,
        community_id: str,
        requester_user_id: str,
        description: str,
        lat: float | None,
        lng: float | None,
        image_urls: list[str] | None,
        analysis: dict[str, Any],
        status: str,
    ) -> dict[str, Any]:
        record = {
            "id": uuid.uuid4().hex,
            "community_id": community_id,
            "requester_user_id": requester_user_id,
            "description": description.strip(),
            "lat": lat,
            "lng": lng,
            "image_urls_json": json.dumps(image_urls or [], ensure_ascii=False),
            "analysis_json": json.dumps(analysis or {}, ensure_ascii=False),
            "status": status,
            "created_at": utc_now(),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO earthquake_rescue_analyses (
                        id, community_id, requester_user_id, description, lat, lng,
                        image_urls_json, analysis_json, status, created_at
                    )
                    VALUES (
                        :id, :community_id, :requester_user_id, :description, :lat, :lng,
                        :image_urls_json, :analysis_json, :status, :created_at
                    )
                    """,
                    record,
                )
                conn.commit()
        payload = {**record}
        payload["image_urls"] = self._safe_load_json(record.get("image_urls_json")) or []
        payload["analysis"] = self._safe_load_json(record.get("analysis_json")) or {}
        return payload

    def list_earthquake_rescue_analyses(
        self, *, community_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 200)
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        id, community_id, requester_user_id, description, lat, lng,
                        image_urls_json, analysis_json, status, created_at
                    FROM earthquake_rescue_analyses
                    WHERE community_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (community_id, safe_limit),
                ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["image_urls"] = self._safe_load_json(item.get("image_urls_json")) or []
            item["analysis"] = self._safe_load_json(item.get("analysis_json")) or {}
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
                if community_id:
                    incident_total = conn.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM incidents
                        WHERE community_id = ?
                        """,
                        (community_id,),
                    ).fetchone()
                    task_running = conn.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM incident_tasks
                        WHERE community_id = ? AND status IN ('assigned', 'accepted', 'in_progress', 'blocked')
                        """,
                        (community_id,),
                    ).fetchone()
                    need_help = conn.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM resident_checkins
                        WHERE community_id = ? AND status = 'need_help'
                        """,
                        (community_id,),
                    ).fetchone()
                else:
                    incident_total = conn.execute(
                        "SELECT COUNT(*) as count FROM incidents"
                    ).fetchone()
                    task_running = conn.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM incident_tasks
                        WHERE status IN ('assigned', 'accepted', 'in_progress', 'blocked')
                        """
                    ).fetchone()
                    need_help = conn.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM resident_checkins
                        WHERE status = 'need_help'
                        """
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
            "total_incidents": int(incident_total["count"]) if incident_total else 0,
            "active_tasks": int(task_running["count"]) if task_running else 0,
            "residents_need_help": int(need_help["count"]) if need_help else 0,
        }

    def create_incident(
        self,
        *,
        community_id: str,
        created_by_user_id: str,
        title: str,
        description: str,
        lat: float | None,
        lng: float | None,
        priority: str,
        status: str = "new",
        source: str = "manual",
    ) -> dict[str, Any]:
        now = utc_now()
        record = {
            "id": uuid.uuid4().hex,
            "community_id": community_id,
            "created_by_user_id": created_by_user_id,
            "title": title.strip(),
            "description": description.strip(),
            "lat": lat,
            "lng": lng,
            "priority": priority,
            "status": status,
            "source": source,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO incidents (
                        id, community_id, created_by_user_id, title, description, lat, lng,
                        priority, status, source, created_at, updated_at
                    )
                    VALUES (
                        :id, :community_id, :created_by_user_id, :title, :description, :lat, :lng,
                        :priority, :status, :source, :created_at, :updated_at
                    )
                    """,
                    record,
                )
                conn.commit()
        return record

    def get_incident(self, incident_id: str, community_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT
                        i.id, i.community_id, i.created_by_user_id, i.title, i.description,
                        i.lat, i.lng, i.priority, i.status, i.source, i.created_at, i.updated_at,
                        u.display_name as created_by_name
                    FROM incidents i
                    LEFT JOIN users u ON u.id = i.created_by_user_id
                    WHERE i.id = ? AND i.community_id = ?
                    LIMIT 1
                    """,
                    (incident_id, community_id),
                ).fetchone()
        return dict(row) if row else None

    def list_incidents(self, *, community_id: str, limit: int = 80) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 300)
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        i.id, i.community_id, i.created_by_user_id, i.title, i.description,
                        i.lat, i.lng, i.priority, i.status, i.source, i.created_at, i.updated_at,
                        u.display_name as created_by_name
                    FROM incidents i
                    LEFT JOIN users u ON u.id = i.created_by_user_id
                    WHERE i.community_id = ?
                    ORDER BY i.created_at DESC
                    LIMIT ?
                    """,
                    (community_id, safe_limit),
                ).fetchall()
        items = [dict(row) for row in rows]
        items.reverse()
        return items

    def update_incident(
        self,
        *,
        incident_id: str,
        community_id: str,
        title: str | None = None,
        description: str | None = None,
        priority: str | None = None,
        status: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
    ) -> dict[str, Any] | None:
        updates: dict[str, Any] = {}
        if title is not None:
            updates["title"] = title.strip()
        if description is not None:
            updates["description"] = description.strip()
        if priority is not None:
            updates["priority"] = priority
        if status is not None:
            updates["status"] = status
        if lat is not None:
            updates["lat"] = lat
        if lng is not None:
            updates["lng"] = lng
        if not updates:
            return self.get_incident(incident_id, community_id)

        updates["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = :{key}" for key in updates.keys())
        payload = {"incident_id": incident_id, "community_id": community_id, **updates}
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    f"""
                    UPDATE incidents
                    SET {assignments}
                    WHERE id = :incident_id AND community_id = :community_id
                    """,
                    payload,
                )
                conn.commit()
        return self.get_incident(incident_id, community_id)

    def create_incident_task(
        self,
        *,
        incident_id: str,
        community_id: str,
        title: str,
        description: str,
        status: str,
        priority: str,
        assignee_user_id: str | None,
        team_id: str | None,
        due_at: str | None,
        created_by_user_id: str,
    ) -> dict[str, Any]:
        now = utc_now()
        record = {
            "id": uuid.uuid4().hex,
            "incident_id": incident_id,
            "community_id": community_id,
            "title": title.strip(),
            "description": description.strip(),
            "status": status,
            "priority": priority,
            "assignee_user_id": assignee_user_id,
            "team_id": team_id,
            "due_at": due_at,
            "accepted_at": None,
            "completed_at": None,
            "created_by_user_id": created_by_user_id,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO incident_tasks (
                        id, incident_id, community_id, title, description, status, priority,
                        assignee_user_id, team_id, due_at, accepted_at, completed_at,
                        created_by_user_id, created_at, updated_at
                    )
                    VALUES (
                        :id, :incident_id, :community_id, :title, :description, :status, :priority,
                        :assignee_user_id, :team_id, :due_at, :accepted_at, :completed_at,
                        :created_by_user_id, :created_at, :updated_at
                    )
                    """,
                    record,
                )
                conn.commit()
        return record

    def get_task(self, task_id: str, community_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT
                        t.id, t.incident_id, t.community_id, t.title, t.description, t.status, t.priority,
                        t.assignee_user_id, t.team_id, t.due_at, t.accepted_at, t.completed_at,
                        t.created_by_user_id, t.created_at, t.updated_at,
                        creator.display_name as created_by_name,
                        assignee.display_name as assignee_name,
                        team.name as team_name
                    FROM incident_tasks t
                    LEFT JOIN users creator ON creator.id = t.created_by_user_id
                    LEFT JOIN users assignee ON assignee.id = t.assignee_user_id
                    LEFT JOIN response_teams team ON team.id = t.team_id
                    WHERE t.id = ? AND t.community_id = ?
                    LIMIT 1
                    """,
                    (task_id, community_id),
                ).fetchone()
        return dict(row) if row else None

    def list_tasks(
        self,
        *,
        community_id: str,
        limit: int = 160,
        incident_id: str | None = None,
    ) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 500)
        with self._lock:
            with self._connect() as conn:
                if incident_id:
                    rows = conn.execute(
                        """
                        SELECT
                            t.id, t.incident_id, t.community_id, t.title, t.description, t.status, t.priority,
                            t.assignee_user_id, t.team_id, t.due_at, t.accepted_at, t.completed_at,
                            t.created_by_user_id, t.created_at, t.updated_at,
                            creator.display_name as created_by_name,
                            assignee.display_name as assignee_name,
                            team.name as team_name
                        FROM incident_tasks t
                        LEFT JOIN users creator ON creator.id = t.created_by_user_id
                        LEFT JOIN users assignee ON assignee.id = t.assignee_user_id
                        LEFT JOIN response_teams team ON team.id = t.team_id
                        WHERE t.community_id = ? AND t.incident_id = ?
                        ORDER BY t.created_at DESC
                        LIMIT ?
                        """,
                        (community_id, incident_id, safe_limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT
                            t.id, t.incident_id, t.community_id, t.title, t.description, t.status, t.priority,
                            t.assignee_user_id, t.team_id, t.due_at, t.accepted_at, t.completed_at,
                            t.created_by_user_id, t.created_at, t.updated_at,
                            creator.display_name as created_by_name,
                            assignee.display_name as assignee_name,
                            team.name as team_name
                        FROM incident_tasks t
                        LEFT JOIN users creator ON creator.id = t.created_by_user_id
                        LEFT JOIN users assignee ON assignee.id = t.assignee_user_id
                        LEFT JOIN response_teams team ON team.id = t.team_id
                        WHERE t.community_id = ?
                        ORDER BY t.created_at DESC
                        LIMIT ?
                        """,
                        (community_id, safe_limit),
                    ).fetchall()
        items = [dict(row) for row in rows]
        items.reverse()
        return items

    def update_task(
        self,
        *,
        task_id: str,
        community_id: str,
        status: str | None = None,
        priority: str | None = None,
        assignee_user_id: str | None = None,
        team_id: str | None = None,
        due_at: str | None = None,
        title: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any] | None:
        updates: dict[str, Any] = {}
        if status is not None:
            updates["status"] = status
            if status == "accepted":
                updates["accepted_at"] = utc_now()
            if status == "completed":
                updates["completed_at"] = utc_now()
        if priority is not None:
            updates["priority"] = priority
        if assignee_user_id is not None:
            updates["assignee_user_id"] = assignee_user_id
        if team_id is not None:
            updates["team_id"] = team_id
        if due_at is not None:
            updates["due_at"] = due_at
        if title is not None:
            updates["title"] = title.strip()
        if description is not None:
            updates["description"] = description.strip()
        if not updates:
            return self.get_task(task_id, community_id)
        updates["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = :{key}" for key in updates.keys())
        payload = {"task_id": task_id, "community_id": community_id, **updates}
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    f"""
                    UPDATE incident_tasks
                    SET {assignments}
                    WHERE id = :task_id AND community_id = :community_id
                    """,
                    payload,
                )
                conn.commit()
        return self.get_task(task_id, community_id)

    def create_response_team(
        self,
        *,
        community_id: str,
        name: str,
        specialty: str,
        status: str,
        leader_user_id: str | None,
        contact: str | None,
        base_lat: float | None = None,
        base_lng: float | None = None,
        base_location_text: str | None = None,
        equipment: list[str] | None = None,
        vehicles: list[str] | None = None,
        personnel_count: int = 0,
        capacity: int = 8,
        availability_score: float = 1.0,
        last_active_at: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        record = {
            "id": uuid.uuid4().hex,
            "community_id": community_id,
            "name": name.strip(),
            "specialty": specialty.strip(),
            "status": status,
            "leader_user_id": leader_user_id,
            "contact": (contact or "").strip() or None,
            "base_lat": float(base_lat) if base_lat is not None else None,
            "base_lng": float(base_lng) if base_lng is not None else None,
            "base_location_text": (base_location_text or "").strip() or None,
            "equipment_json": json.dumps(equipment or [], ensure_ascii=False),
            "vehicle_json": json.dumps(vehicles or [], ensure_ascii=False),
            "personnel_count": max(0, int(personnel_count)),
            "capacity": max(1, int(capacity)),
            "availability_score": max(0.0, min(float(availability_score), 1.0)),
            "last_active_at": (last_active_at or "").strip() or None,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO response_teams (
                        id, community_id, name, specialty, status, leader_user_id, contact,
                        base_lat, base_lng, base_location_text, equipment_json, vehicle_json,
                        personnel_count, capacity, availability_score, last_active_at, created_at, updated_at
                    )
                    VALUES (
                        :id, :community_id, :name, :specialty, :status, :leader_user_id, :contact,
                        :base_lat, :base_lng, :base_location_text, :equipment_json, :vehicle_json,
                        :personnel_count, :capacity, :availability_score, :last_active_at, :created_at, :updated_at
                    )
                    """,
                    record,
                )
                conn.commit()
        return {
            **record,
            "equipment": equipment or [],
            "vehicles": vehicles or [],
            "member_count": 0,
        }

    def add_team_member(self, *, team_id: str, user_id: str, role: str = "member") -> dict[str, Any]:
        record = {
            "team_id": team_id,
            "user_id": user_id,
            "role": role,
            "created_at": utc_now(),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO team_memberships (team_id, user_id, role, created_at)
                    VALUES (:team_id, :user_id, :role, :created_at)
                    """,
                    record,
                )
                conn.commit()
                row = conn.execute(
                    """
                    SELECT id, team_id, user_id, role, created_at
                    FROM team_memberships
                    WHERE team_id = ? AND user_id = ?
                    LIMIT 1
                    """,
                    (team_id, user_id),
                ).fetchone()
        return dict(row) if row else record

    def list_response_teams(self, *, community_id: str, limit: int = 120) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 300)
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        t.id, t.community_id, t.name, t.specialty, t.status,
                        t.leader_user_id, t.contact, t.base_lat, t.base_lng, t.base_location_text,
                        t.equipment_json, t.vehicle_json, t.personnel_count, t.capacity, t.availability_score, t.last_active_at,
                        t.created_at, t.updated_at,
                        u.display_name as leader_name,
                        (
                            SELECT COUNT(*)
                            FROM team_memberships m
                            WHERE m.team_id = t.id
                        ) as member_count
                    FROM response_teams t
                    LEFT JOIN users u ON u.id = t.leader_user_id
                    WHERE t.community_id = ?
                    ORDER BY t.created_at DESC
                    LIMIT ?
                    """,
                    (community_id, safe_limit),
                ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            equipment = self._safe_load_json(item.pop("equipment_json", None))
            vehicles = self._safe_load_json(item.pop("vehicle_json", None))
            item["equipment"] = equipment if isinstance(equipment, list) else []
            item["vehicles"] = vehicles if isinstance(vehicles, list) else []
            if item.get("capacity") is None:
                item["capacity"] = 8
            if item.get("personnel_count") is None:
                item["personnel_count"] = 0
            if item.get("availability_score") is None:
                item["availability_score"] = 1.0
            items.append(item)
        items.reverse()
        return items

    def ensure_default_response_teams(
        self,
        *,
        community_id: str,
        base_lat: float,
        base_lng: float,
    ) -> list[dict[str, Any]]:
        defaults = [
            {
                "name": "先遣搜索一队",
                "specialty": "搜索排查",
                "contact": "VHF-01",
                "base_lat_offset": 0.0022,
                "base_lng_offset": 0.0016,
                "base_location_text": "东侧前置点",
                "equipment": ["生命探测仪", "热成像无人机", "便携照明"],
                "vehicles": ["轻型救援车"],
                "personnel_count": 7,
                "capacity": 8,
            },
            {
                "name": "医疗转运组",
                "specialty": "医疗救护",
                "contact": "VHF-02",
                "base_lat_offset": -0.0018,
                "base_lng_offset": 0.0021,
                "base_location_text": "社区医疗站",
                "equipment": ["急救包", "AED", "折叠担架"],
                "vehicles": ["医疗转运车"],
                "personnel_count": 5,
                "capacity": 6,
            },
            {
                "name": "破拆救援组",
                "specialty": "破拆救援",
                "contact": "VHF-03",
                "base_lat_offset": 0.0013,
                "base_lng_offset": -0.0023,
                "base_location_text": "西南装备点",
                "equipment": ["液压破拆工具", "支撑套件", "防护头盔"],
                "vehicles": ["重型救援车"],
                "personnel_count": 9,
                "capacity": 10,
            },
        ]
        existing = self.list_response_teams(community_id=community_id, limit=300)
        existing_names = {str(item.get("name")) for item in existing}
        for item in defaults:
            if item["name"] in existing_names:
                continue
            self.create_response_team(
                community_id=community_id,
                name=item["name"],
                specialty=item["specialty"],
                status="standby",
                leader_user_id=None,
                contact=item["contact"],
                base_lat=base_lat + float(item["base_lat_offset"]),
                base_lng=base_lng + float(item["base_lng_offset"]),
                base_location_text=item["base_location_text"],
                equipment=list(item["equipment"]),
                vehicles=list(item["vehicles"]),
                personnel_count=int(item["personnel_count"]),
                capacity=int(item["capacity"]),
                availability_score=1.0,
                last_active_at=utc_now(),
            )
        return self.list_response_teams(community_id=community_id, limit=300)

    def create_dispatch_record(
        self,
        *,
        community_id: str,
        created_by_user_id: str,
        incident_id: str | None,
        task_id: str | None,
        team_id: str | None,
        resource_type: str,
        resource_name: str,
        quantity: int,
        status: str,
        notes: str | None,
    ) -> dict[str, Any]:
        now = utc_now()
        record = {
            "id": uuid.uuid4().hex,
            "community_id": community_id,
            "incident_id": incident_id,
            "task_id": task_id,
            "team_id": team_id,
            "resource_type": resource_type.strip(),
            "resource_name": resource_name.strip(),
            "quantity": max(1, int(quantity)),
            "status": status,
            "notes": (notes or "").strip() or None,
            "created_by_user_id": created_by_user_id,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO dispatch_records (
                        id, community_id, incident_id, task_id, team_id, resource_type, resource_name,
                        quantity, status, notes, created_by_user_id, created_at, updated_at
                    )
                    VALUES (
                        :id, :community_id, :incident_id, :task_id, :team_id, :resource_type, :resource_name,
                        :quantity, :status, :notes, :created_by_user_id, :created_at, :updated_at
                    )
                    """,
                    record,
                )
                conn.commit()
        return record

    def list_dispatch_records(
        self, *, community_id: str, limit: int = 150, incident_id: str | None = None
    ) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 400)
        with self._lock:
            with self._connect() as conn:
                if incident_id:
                    rows = conn.execute(
                        """
                        SELECT
                            d.id, d.community_id, d.incident_id, d.task_id, d.team_id, d.resource_type,
                            d.resource_name, d.quantity, d.status, d.notes, d.created_by_user_id,
                            d.created_at, d.updated_at, u.display_name as created_by_name,
                            t.name as team_name
                        FROM dispatch_records d
                        LEFT JOIN users u ON u.id = d.created_by_user_id
                        LEFT JOIN response_teams t ON t.id = d.team_id
                        WHERE d.community_id = ? AND d.incident_id = ?
                        ORDER BY d.created_at DESC
                        LIMIT ?
                        """,
                        (community_id, incident_id, safe_limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT
                            d.id, d.community_id, d.incident_id, d.task_id, d.team_id, d.resource_type,
                            d.resource_name, d.quantity, d.status, d.notes, d.created_by_user_id,
                            d.created_at, d.updated_at, u.display_name as created_by_name,
                            t.name as team_name
                        FROM dispatch_records d
                        LEFT JOIN users u ON u.id = d.created_by_user_id
                        LEFT JOIN response_teams t ON t.id = d.team_id
                        WHERE d.community_id = ?
                        ORDER BY d.created_at DESC
                        LIMIT ?
                        """,
                        (community_id, safe_limit),
                    ).fetchall()
        items = [dict(row) for row in rows]
        items.reverse()
        return items

    def add_resident_checkin(
        self,
        *,
        community_id: str,
        user_id: str | None,
        incident_id: str | None,
        subject_name: str,
        relation: str,
        status: str,
        lat: float | None,
        lng: float | None,
        notes: str | None,
    ) -> dict[str, Any]:
        record = {
            "id": uuid.uuid4().hex,
            "community_id": community_id,
            "user_id": user_id,
            "incident_id": incident_id,
            "subject_name": subject_name.strip(),
            "relation": relation.strip(),
            "status": status,
            "lat": lat,
            "lng": lng,
            "notes": (notes or "").strip() or None,
            "created_at": utc_now(),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO resident_checkins (
                        id, community_id, user_id, incident_id, subject_name, relation, status,
                        lat, lng, notes, created_at
                    )
                    VALUES (
                        :id, :community_id, :user_id, :incident_id, :subject_name, :relation, :status,
                        :lat, :lng, :notes, :created_at
                    )
                    """,
                    record,
                )
                conn.commit()
        return record

    def list_resident_checkins(
        self, *, community_id: str, limit: int = 150, incident_id: str | None = None
    ) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 500)
        with self._lock:
            with self._connect() as conn:
                if incident_id:
                    rows = conn.execute(
                        """
                        SELECT
                            c.id, c.community_id, c.user_id, c.incident_id, c.subject_name, c.relation, c.status,
                            c.lat, c.lng, c.notes, c.created_at, u.display_name as user_name
                        FROM resident_checkins c
                        LEFT JOIN users u ON u.id = c.user_id
                        WHERE c.community_id = ? AND c.incident_id = ?
                        ORDER BY c.created_at DESC
                        LIMIT ?
                        """,
                        (community_id, incident_id, safe_limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT
                            c.id, c.community_id, c.user_id, c.incident_id, c.subject_name, c.relation, c.status,
                            c.lat, c.lng, c.notes, c.created_at, u.display_name as user_name
                        FROM resident_checkins c
                        LEFT JOIN users u ON u.id = c.user_id
                        WHERE c.community_id = ?
                        ORDER BY c.created_at DESC
                        LIMIT ?
                        """,
                        (community_id, safe_limit),
                    ).fetchall()
        items = [dict(row) for row in rows]
        items.reverse()
        return items

    def summarize_resident_checkins(self, *, community_id: str) -> dict[str, Any]:
        with self._lock:
            with self._connect() as conn:
                total_row = conn.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM resident_checkins
                    WHERE community_id = ?
                    """,
                    (community_id,),
                ).fetchone()
                grouped = conn.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM resident_checkins
                    WHERE community_id = ?
                    GROUP BY status
                    """,
                    (community_id,),
                ).fetchall()
                latest_row = conn.execute(
                    """
                    SELECT created_at
                    FROM resident_checkins
                    WHERE community_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (community_id,),
                ).fetchone()
        by_status = {str(row["status"]): int(row["count"]) for row in grouped}
        return {
            "community_id": community_id,
            "total": int(total_row["count"]) if total_row else 0,
            "by_status": by_status,
            "latest_checkin_at": latest_row["created_at"] if latest_row else None,
        }

    def create_missing_person_report(
        self,
        *,
        community_id: str,
        incident_id: str | None,
        reporter_user_id: str,
        name: str,
        age: int | None,
        contact: str | None,
        last_seen_location: str | None,
        priority: str,
        status: str,
        notes: str | None,
    ) -> dict[str, Any]:
        now = utc_now()
        record = {
            "id": uuid.uuid4().hex,
            "community_id": community_id,
            "incident_id": incident_id,
            "reporter_user_id": reporter_user_id,
            "name": name.strip(),
            "age": age,
            "contact": (contact or "").strip() or None,
            "last_seen_location": (last_seen_location or "").strip() or None,
            "priority": priority,
            "status": status,
            "notes": (notes or "").strip() or None,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO missing_person_reports (
                        id, community_id, incident_id, reporter_user_id, name, age, contact,
                        last_seen_location, priority, status, notes, created_at, updated_at
                    )
                    VALUES (
                        :id, :community_id, :incident_id, :reporter_user_id, :name, :age, :contact,
                        :last_seen_location, :priority, :status, :notes, :created_at, :updated_at
                    )
                    """,
                    record,
                )
                conn.commit()
        return record

    def list_missing_person_reports(
        self, *, community_id: str, limit: int = 150, status: str | None = None
    ) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 400)
        with self._lock:
            with self._connect() as conn:
                if status:
                    rows = conn.execute(
                        """
                        SELECT
                            m.id, m.community_id, m.incident_id, m.reporter_user_id, m.name, m.age,
                            m.contact, m.last_seen_location, m.priority, m.status, m.notes,
                            m.created_at, m.updated_at, u.display_name as reporter_name
                        FROM missing_person_reports m
                        LEFT JOIN users u ON u.id = m.reporter_user_id
                        WHERE m.community_id = ? AND m.status = ?
                        ORDER BY m.created_at DESC
                        LIMIT ?
                        """,
                        (community_id, status, safe_limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT
                            m.id, m.community_id, m.incident_id, m.reporter_user_id, m.name, m.age,
                            m.contact, m.last_seen_location, m.priority, m.status, m.notes,
                            m.created_at, m.updated_at, u.display_name as reporter_name
                        FROM missing_person_reports m
                        LEFT JOIN users u ON u.id = m.reporter_user_id
                        WHERE m.community_id = ?
                        ORDER BY m.created_at DESC
                        LIMIT ?
                        """,
                        (community_id, safe_limit),
                    ).fetchall()
        items = [dict(row) for row in rows]
        items.reverse()
        return items

    def create_shelter(
        self,
        *,
        community_id: str,
        name: str,
        address: str,
        lat: float | None,
        lng: float | None,
        capacity: int,
        current_occupancy: int = 0,
        status: str = "open",
    ) -> dict[str, Any]:
        now = utc_now()
        normalized_capacity = max(1, int(capacity))
        normalized_occupancy = max(0, min(int(current_occupancy), normalized_capacity))
        record = {
            "id": uuid.uuid4().hex,
            "community_id": community_id,
            "name": name.strip(),
            "address": address.strip(),
            "lat": lat,
            "lng": lng,
            "capacity": normalized_capacity,
            "current_occupancy": normalized_occupancy,
            "status": status,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO shelters (
                        id, community_id, name, address, lat, lng, capacity, current_occupancy, status, created_at, updated_at
                    )
                    VALUES (
                        :id, :community_id, :name, :address, :lat, :lng, :capacity, :current_occupancy, :status, :created_at, :updated_at
                    )
                    """,
                    record,
                )
                conn.commit()
        return record

    def get_shelter(self, shelter_id: str, community_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT
                        id, community_id, name, address, lat, lng, capacity,
                        current_occupancy, status, created_at, updated_at
                    FROM shelters
                    WHERE id = ? AND community_id = ?
                    LIMIT 1
                    """,
                    (shelter_id, community_id),
                ).fetchone()
        return dict(row) if row else None

    def list_shelters(self, *, community_id: str, limit: int = 120) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 300)
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        id, community_id, name, address, lat, lng, capacity,
                        current_occupancy, status, created_at, updated_at
                    FROM shelters
                    WHERE community_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (community_id, safe_limit),
                ).fetchall()
        items = [dict(row) for row in rows]
        items.reverse()
        return items

    def add_shelter_occupancy_event(
        self,
        *,
        shelter_id: str,
        community_id: str,
        delta: int,
        occupancy: int,
        reason: str | None,
        created_by_user_id: str | None,
    ) -> dict[str, Any]:
        event = {
            "id": uuid.uuid4().hex,
            "shelter_id": shelter_id,
            "community_id": community_id,
            "delta": int(delta),
            "occupancy": int(occupancy),
            "reason": (reason or "").strip() or None,
            "created_by_user_id": created_by_user_id,
            "created_at": utc_now(),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO shelter_occupancy_events (
                        id, shelter_id, community_id, delta, occupancy, reason, created_by_user_id, created_at
                    )
                    VALUES (
                        :id, :shelter_id, :community_id, :delta, :occupancy, :reason, :created_by_user_id, :created_at
                    )
                    """,
                    event,
                )
                conn.commit()
        return event

    def update_shelter_occupancy(
        self,
        *,
        shelter_id: str,
        community_id: str,
        delta: int | None = None,
        absolute_occupancy: int | None = None,
        status: str | None = None,
        reason: str | None = None,
        created_by_user_id: str | None = None,
    ) -> dict[str, Any] | None:
        shelter = self.get_shelter(shelter_id, community_id)
        if shelter is None:
            return None
        capacity = int(shelter.get("capacity") or 0)
        current = int(shelter.get("current_occupancy") or 0)
        if absolute_occupancy is not None:
            next_occupancy = absolute_occupancy
            real_delta = absolute_occupancy - current
        else:
            real_delta = int(delta or 0)
            next_occupancy = current + real_delta
        next_occupancy = max(0, min(next_occupancy, capacity if capacity > 0 else next_occupancy))
        updates: dict[str, Any] = {"current_occupancy": next_occupancy, "updated_at": utc_now()}
        if status is not None:
            updates["status"] = status
        assignments = ", ".join(f"{key} = :{key}" for key in updates.keys())
        payload = {"shelter_id": shelter_id, "community_id": community_id, **updates}
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    f"""
                    UPDATE shelters
                    SET {assignments}
                    WHERE id = :shelter_id AND community_id = :community_id
                    """,
                    payload,
                )
                conn.commit()
        self.add_shelter_occupancy_event(
            shelter_id=shelter_id,
            community_id=community_id,
            delta=real_delta,
            occupancy=next_occupancy,
            reason=reason,
            created_by_user_id=created_by_user_id,
        )
        return self.get_shelter(shelter_id, community_id)

    def create_hazard_zone(
        self,
        *,
        community_id: str,
        incident_id: str | None,
        name: str,
        risk_level: str,
        zone_type: str,
        polygon: list[dict[str, float]],
        notes: str | None,
        status: str,
        created_by_user_id: str,
    ) -> dict[str, Any]:
        now = utc_now()
        record = {
            "id": uuid.uuid4().hex,
            "community_id": community_id,
            "incident_id": incident_id,
            "name": name.strip(),
            "risk_level": risk_level,
            "zone_type": zone_type,
            "polygon_json": json.dumps(polygon, ensure_ascii=False),
            "notes": (notes or "").strip() or None,
            "status": status,
            "created_by_user_id": created_by_user_id,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO hazard_zones (
                        id, community_id, incident_id, name, risk_level, zone_type, polygon_json,
                        notes, status, created_by_user_id, created_at, updated_at
                    )
                    VALUES (
                        :id, :community_id, :incident_id, :name, :risk_level, :zone_type, :polygon_json,
                        :notes, :status, :created_by_user_id, :created_at, :updated_at
                    )
                    """,
                    record,
                )
                conn.commit()
        payload = {**record}
        payload["polygon"] = polygon
        return payload

    def list_hazard_zones(
        self, *, community_id: str, limit: int = 120, incident_id: str | None = None
    ) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 300)
        with self._lock:
            with self._connect() as conn:
                if incident_id:
                    rows = conn.execute(
                        """
                        SELECT
                            id, community_id, incident_id, name, risk_level, zone_type, polygon_json, notes,
                            status, created_by_user_id, created_at, updated_at
                        FROM hazard_zones
                        WHERE community_id = ? AND incident_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                        """,
                        (community_id, incident_id, safe_limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT
                            id, community_id, incident_id, name, risk_level, zone_type, polygon_json, notes,
                            status, created_by_user_id, created_at, updated_at
                        FROM hazard_zones
                        WHERE community_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                        """,
                        (community_id, safe_limit),
                    ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["polygon"] = self._safe_load_json(item.get("polygon_json")) or []
            items.append(item)
        items.reverse()
        return items

    def create_road_block(
        self,
        *,
        community_id: str,
        incident_id: str | None,
        title: str,
        details: str | None,
        lat: float | None,
        lng: float | None,
        severity: str,
        status: str,
        created_by_user_id: str,
    ) -> dict[str, Any]:
        now = utc_now()
        record = {
            "id": uuid.uuid4().hex,
            "community_id": community_id,
            "incident_id": incident_id,
            "title": title.strip(),
            "details": (details or "").strip() or None,
            "lat": lat,
            "lng": lng,
            "severity": severity,
            "status": status,
            "created_by_user_id": created_by_user_id,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO road_blocks (
                        id, community_id, incident_id, title, details, lat, lng, severity, status,
                        created_by_user_id, created_at, updated_at
                    )
                    VALUES (
                        :id, :community_id, :incident_id, :title, :details, :lat, :lng, :severity, :status,
                        :created_by_user_id, :created_at, :updated_at
                    )
                    """,
                    record,
                )
                conn.commit()
        return record

    def list_road_blocks(
        self, *, community_id: str, limit: int = 120, incident_id: str | None = None
    ) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 300)
        with self._lock:
            with self._connect() as conn:
                if incident_id:
                    rows = conn.execute(
                        """
                        SELECT
                            id, community_id, incident_id, title, details, lat, lng, severity, status,
                            created_by_user_id, created_at, updated_at
                        FROM road_blocks
                        WHERE community_id = ? AND incident_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                        """,
                        (community_id, incident_id, safe_limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT
                            id, community_id, incident_id, title, details, lat, lng, severity, status,
                            created_by_user_id, created_at, updated_at
                        FROM road_blocks
                        WHERE community_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                        """,
                        (community_id, safe_limit),
                    ).fetchall()
        items = [dict(row) for row in rows]
        items.reverse()
        return items

    def create_notification_template(
        self,
        *,
        community_id: str,
        name: str,
        level: str,
        title_template: str,
        content_template: str,
        created_by_user_id: str,
    ) -> dict[str, Any]:
        now = utc_now()
        record = {
            "id": uuid.uuid4().hex,
            "community_id": community_id,
            "name": name.strip(),
            "level": level,
            "title_template": title_template.strip(),
            "content_template": content_template.strip(),
            "created_by_user_id": created_by_user_id,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO community_notification_templates (
                        id, community_id, name, level, title_template, content_template,
                        created_by_user_id, created_at, updated_at
                    )
                    VALUES (
                        :id, :community_id, :name, :level, :title_template, :content_template,
                        :created_by_user_id, :created_at, :updated_at
                    )
                    """,
                    record,
                )
                conn.commit()
        return record

    def list_notification_templates(
        self, *, community_id: str, limit: int = 80
    ) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 200)
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        id, community_id, name, level, title_template, content_template,
                        created_by_user_id, created_at, updated_at
                    FROM community_notification_templates
                    WHERE community_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (community_id, safe_limit),
                ).fetchall()
        items = [dict(row) for row in rows]
        items.reverse()
        return items

    def upsert_notification_receipt(
        self,
        *,
        notification_id: str,
        community_id: str,
        user_id: str,
        status: str,
    ) -> dict[str, Any]:
        now = utc_now()
        record = {
            "id": uuid.uuid4().hex,
            "notification_id": notification_id,
            "community_id": community_id,
            "user_id": user_id,
            "status": status,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO notification_receipts (
                        id, notification_id, community_id, user_id, status, created_at, updated_at
                    )
                    VALUES (
                        :id, :notification_id, :community_id, :user_id, :status, :created_at, :updated_at
                    )
                    ON CONFLICT(notification_id, user_id)
                    DO UPDATE SET
                        status = excluded.status,
                        updated_at = excluded.updated_at
                    """,
                    record,
                )
                conn.commit()
                row = conn.execute(
                    """
                    SELECT
                        id, notification_id, community_id, user_id, status, created_at, updated_at
                    FROM notification_receipts
                    WHERE notification_id = ? AND user_id = ?
                    LIMIT 1
                    """,
                    (notification_id, user_id),
                ).fetchone()
        return dict(row) if row else record

    def summarize_notification_receipts(
        self, *, community_id: str, notification_id: str
    ) -> dict[str, Any]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM notification_receipts
                    WHERE community_id = ? AND notification_id = ?
                    GROUP BY status
                    """,
                    (community_id, notification_id),
                ).fetchall()
        by_status = {str(row["status"]): int(row["count"]) for row in rows}
        return {
            "community_id": community_id,
            "notification_id": notification_id,
            "by_status": by_status,
            "total": sum(by_status.values()),
        }

    def add_audit_log(
        self,
        *,
        community_id: str,
        action: str,
        target_type: str,
        target_id: str | None,
        user_id: str | None,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = {
            "community_id": community_id,
            "user_id": user_id,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "detail_json": json.dumps(detail or {}, ensure_ascii=False),
            "created_at": utc_now(),
        }
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO audit_logs (
                        community_id, user_id, action, target_type, target_id, detail_json, created_at
                    )
                    VALUES (
                        :community_id, :user_id, :action, :target_type, :target_id, :detail_json, :created_at
                    )
                    """,
                    record,
                )
                conn.commit()
                record["id"] = cursor.lastrowid
        record["detail"] = self._safe_load_json(record.get("detail_json")) or {}
        return record

    def list_audit_logs(self, *, community_id: str, limit: int = 300) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 1000)
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, community_id, user_id, action, target_type, target_id, detail_json, created_at
                    FROM audit_logs
                    WHERE community_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (community_id, safe_limit),
                ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["detail"] = self._safe_load_json(item.get("detail_json")) or {}
            items.append(item)
        items.reverse()
        return items

    def add_ops_timeline_event(
        self,
        *,
        community_id: str,
        event_type: str,
        title: str,
        content: str,
        entity_type: str | None,
        entity_id: str | None,
        payload: dict[str, Any] | None,
        created_by_user_id: str | None,
    ) -> dict[str, Any]:
        record = {
            "id": uuid.uuid4().hex,
            "community_id": community_id,
            "event_type": event_type,
            "title": title.strip(),
            "content": content.strip(),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload_json": json.dumps(payload or {}, ensure_ascii=False),
            "created_by_user_id": created_by_user_id,
            "created_at": utc_now(),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO ops_timeline_events (
                        id, community_id, event_type, title, content, entity_type,
                        entity_id, payload_json, created_by_user_id, created_at
                    )
                    VALUES (
                        :id, :community_id, :event_type, :title, :content, :entity_type,
                        :entity_id, :payload_json, :created_by_user_id, :created_at
                    )
                    """,
                    record,
                )
                conn.commit()
        payload = {**record}
        payload["payload"] = self._safe_load_json(record.get("payload_json")) or {}
        return payload

    def list_ops_timeline(self, *, community_id: str, limit: int = 200) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 800)
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        id, community_id, event_type, title, content, entity_type,
                        entity_id, payload_json, created_by_user_id, created_at
                    FROM ops_timeline_events
                    WHERE community_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (community_id, safe_limit),
                ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = self._safe_load_json(item.get("payload_json")) or {}
            items.append(item)
        items.reverse()
        return items

    def get_dispatch_agent_run_by_key(
        self, *, idempotency_key: str
    ) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT
                        id, community_id, analysis_id, trigger_source, idempotency_key,
                        input_json, plan_json, execution_json, status, error, created_at
                    FROM dispatch_agent_runs
                    WHERE idempotency_key = ?
                    LIMIT 1
                    """,
                    (idempotency_key,),
                ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["input"] = self._safe_load_json(item.get("input_json")) or {}
        item["plan"] = self._safe_load_json(item.get("plan_json")) or {}
        item["execution"] = self._safe_load_json(item.get("execution_json")) or {}
        return item

    def create_dispatch_agent_run(
        self,
        *,
        community_id: str,
        analysis_id: str,
        trigger_source: str,
        idempotency_key: str,
        input_payload: dict[str, Any],
        plan_payload: dict[str, Any],
        status: str,
        error: str | None = None,
    ) -> dict[str, Any]:
        record = {
            "id": uuid.uuid4().hex,
            "community_id": community_id,
            "analysis_id": analysis_id,
            "trigger_source": trigger_source,
            "idempotency_key": idempotency_key,
            "input_json": json.dumps(input_payload or {}, ensure_ascii=False),
            "plan_json": json.dumps(plan_payload or {}, ensure_ascii=False),
            "execution_json": json.dumps({}, ensure_ascii=False),
            "status": status,
            "error": error,
            "created_at": utc_now(),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO dispatch_agent_runs (
                        id, community_id, analysis_id, trigger_source, idempotency_key,
                        input_json, plan_json, execution_json, status, error, created_at
                    )
                    VALUES (
                        :id, :community_id, :analysis_id, :trigger_source, :idempotency_key,
                        :input_json, :plan_json, :execution_json, :status, :error, :created_at
                    )
                    """,
                    record,
                )
                conn.commit()
        payload = {**record}
        payload["input"] = self._safe_load_json(record.get("input_json")) or {}
        payload["plan"] = self._safe_load_json(record.get("plan_json")) or {}
        payload["execution"] = self._safe_load_json(record.get("execution_json")) or {}
        return payload

    def update_dispatch_agent_run_result(
        self,
        *,
        run_id: str,
        status: str,
        execution_payload: dict[str, Any],
        error: str | None = None,
    ) -> dict[str, Any] | None:
        payload = {
            "run_id": run_id,
            "status": status,
            "execution_json": json.dumps(execution_payload or {}, ensure_ascii=False),
            "error": error,
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE dispatch_agent_runs
                    SET status = :status, execution_json = :execution_json, error = :error
                    WHERE id = :run_id
                    """,
                    payload,
                )
                conn.commit()
                row = conn.execute(
                    """
                    SELECT
                        id, community_id, analysis_id, trigger_source, idempotency_key,
                        input_json, plan_json, execution_json, status, error, created_at
                    FROM dispatch_agent_runs
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (run_id,),
                ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["input"] = self._safe_load_json(item.get("input_json")) or {}
        item["plan"] = self._safe_load_json(item.get("plan_json")) or {}
        item["execution"] = self._safe_load_json(item.get("execution_json")) or {}
        return item

    def list_dispatch_agent_runs(
        self, *, community_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 200)
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        id, community_id, analysis_id, trigger_source, idempotency_key,
                        input_json, plan_json, execution_json, status, error, created_at
                    FROM dispatch_agent_runs
                    WHERE community_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (community_id, safe_limit),
                ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["input"] = self._safe_load_json(item.get("input_json")) or {}
            item["plan"] = self._safe_load_json(item.get("plan_json")) or {}
            item["execution"] = self._safe_load_json(item.get("execution_json")) or {}
            items.append(item)
        items.reverse()
        return items
