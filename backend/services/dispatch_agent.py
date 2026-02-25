from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None


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
        if start < 0 or end <= start:
            continue
        chunk = candidate[start : end + 1]
        try:
            payload = json.loads(chunk)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _normalize_plan(
    raw_plan: dict[str, Any],
    *,
    teams: list[dict[str, Any]],
    max_tasks: int,
) -> dict[str, Any]:
    team_ids = {str(item.get("id")) for item in teams if item.get("id")}
    incident_actions = raw_plan.get("incident_actions")
    task_actions = raw_plan.get("task_actions")
    dispatch_actions = raw_plan.get("dispatch_actions")
    notes = raw_plan.get("notes")

    normalized_incident_actions: list[dict[str, Any]] = []
    if isinstance(incident_actions, list):
        for item in incident_actions[:2]:
            if not isinstance(item, dict):
                continue
            action = str(item.get("action") or "create").strip().lower()
            if action not in {"create", "update"}:
                action = "create"
            normalized_incident_actions.append(
                {
                    "action": action,
                    "incident_id": str(item.get("incident_id") or "").strip() or None,
                    "title": str(item.get("title") or "地震受灾搜救事件").strip()[:120],
                    "description": str(item.get("description") or "").strip()[:1200],
                    "priority": str(item.get("priority") or "high").strip().lower(),
                    "status": str(item.get("status") or "responding").strip().lower(),
                }
            )

    normalized_task_actions: list[dict[str, Any]] = []
    if isinstance(task_actions, list):
        for idx, item in enumerate(task_actions[:max_tasks], 1):
            if not isinstance(item, dict):
                continue
            team_id = str(item.get("team_id") or "").strip() or None
            if team_id and team_id not in team_ids:
                team_id = None
            normalized_task_actions.append(
                {
                    "action": str(item.get("action") or "create").strip().lower(),
                    "task_id": str(item.get("task_id") or "").strip() or None,
                    "title": str(item.get("title") or f"AI搜救任务-{idx}").strip()[:140],
                    "description": str(item.get("description") or "").strip()[:1400],
                    "priority": str(item.get("priority") or "high").strip().lower(),
                    "status": str(item.get("status") or "assigned").strip().lower(),
                    "team_id": team_id,
                    "assignee_user_id": str(item.get("assignee_user_id") or "").strip() or None,
                }
            )

    normalized_dispatch_actions: list[dict[str, Any]] = []
    if isinstance(dispatch_actions, list):
        for item in dispatch_actions[:max_tasks]:
            if not isinstance(item, dict):
                continue
            team_id = str(item.get("team_id") or "").strip() or None
            if team_id and team_id not in team_ids:
                team_id = None
            try:
                quantity = int(item.get("quantity") or 1)
            except Exception:
                quantity = 1
            quantity = max(1, min(quantity, 10000))
            normalized_dispatch_actions.append(
                {
                    "resource_type": str(item.get("resource_type") or "rescue_unit").strip()[:64],
                    "resource_name": str(item.get("resource_name") or "机动搜救单元").strip()[:120],
                    "quantity": quantity,
                    "status": str(item.get("status") or "allocated").strip().lower(),
                    "team_id": team_id,
                    "notes": str(item.get("notes") or "").strip()[:600] or None,
                }
            )

    normalized_notes: list[str] = []
    if isinstance(notes, list):
        normalized_notes = [str(item).strip()[:280] for item in notes if str(item).strip()]

    return {
        "incident_actions": normalized_incident_actions,
        "task_actions": normalized_task_actions,
        "dispatch_actions": normalized_dispatch_actions,
        "notes": normalized_notes[:6],
    }


@dataclass
class DispatchAgentPlanner:
    api_key: str
    model: str
    base_url: str | None
    max_tasks: int = 6

    def _heuristic_plan(
        self,
        *,
        analysis: dict[str, Any],
        incidents: list[dict[str, Any]],
        teams: list[dict[str, Any]],
    ) -> dict[str, Any]:
        victims = analysis.get("victims")
        if not isinstance(victims, list):
            victims = []
        active_incidents = [item for item in incidents if str(item.get("status")) != "closed"]
        primary_team_ids = [str(item.get("id")) for item in teams if item.get("id")]
        incident_title = "地震受灾搜救事件"
        incident_desc = str(analysis.get("scene_overview") or "地震现场自动调度事件")

        incident_actions = [
            {
                "action": "create" if not active_incidents else "update",
                "incident_id": active_incidents[0]["id"] if active_incidents else None,
                "title": active_incidents[0]["title"] if active_incidents else incident_title,
                "description": incident_desc,
                "priority": "high",
                "status": "responding",
            }
        ]

        task_actions: list[dict[str, Any]] = []
        dispatch_actions: list[dict[str, Any]] = []
        victim_count = min(len(victims), self.max_tasks)
        if victim_count == 0:
            victim_count = 1
        for idx in range(victim_count):
            victim = victims[idx] if idx < len(victims) else {}
            team_id = primary_team_ids[idx % len(primary_team_ids)] if primary_team_ids else None
            position = str(victim.get("position_hint") or f"疑似点位-{idx + 1}")
            confidence = float(victim.get("confidence", 0.0) or 0.0)
            task_actions.append(
                {
                    "action": "create",
                    "title": f"AI搜救任务-{idx + 1}",
                    "description": (
                        f"[AI-AUTO] 前往 {position} 执行搜索与转运，"
                        f"参考置信度 {confidence:.2f}。"
                    ),
                    "priority": "critical" if confidence >= 0.72 else "high",
                    "status": "assigned",
                    "team_id": team_id,
                    "assignee_user_id": None,
                }
            )
        for idx, team_id in enumerate(primary_team_ids[: max(1, min(3, len(primary_team_ids)))], 1):
            dispatch_actions.append(
                {
                    "resource_type": "rescue_team",
                    "resource_name": f"搜救队-{idx}",
                    "quantity": 1,
                    "status": "allocated",
                    "team_id": team_id,
                    "notes": "AI-AUTO：按地震图像识别结果优先出动。",
                }
            )
        return {
            "incident_actions": incident_actions,
            "task_actions": task_actions,
            "dispatch_actions": dispatch_actions,
            "notes": [
                "自动调度已执行，请人工复核路线与安全边界。",
                "若余震增强，请将任务状态切换为 blocked 并重规划。"
            ],
        }

    def _llm_plan(
        self,
        *,
        analysis: dict[str, Any],
        incidents: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        teams: list[dict[str, Any]],
        dispatches: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if OpenAI is None:
            return {"status": "mock", "error": "OpenAI SDK 不可用"}
        if not (self.api_key or "").strip():
            return {"status": "mock", "error": "未配置模型 API Key"}

        prompt = (
            "你是地震指挥系统自动调度 Agent。"
            "根据输入生成 JSON 调度计划。"
            "仅返回 JSON，不要额外文本。"
            "JSON 结构："
            "{"
            '"incident_actions":[{"action":"create|update","incident_id":"可选","title":"...","description":"...","priority":"low|medium|high|critical","status":"new|verified|responding|stabilized|closed"}],'
            '"task_actions":[{"action":"create|update","task_id":"可选","title":"...","description":"...","priority":"low|medium|high|critical","status":"new|assigned|accepted|in_progress|blocked|completed","team_id":"可选","assignee_user_id":"可选"}],'
            '"dispatch_actions":[{"resource_type":"...","resource_name":"...","quantity":1,"status":"allocated|in_transit|delivered|consumed|returned","team_id":"可选","notes":"..."}],'
            '"notes":[string]'
            "}。"
            f"最大 task_actions 数量为 {self.max_tasks}。"
            f"analysis={json.dumps(analysis, ensure_ascii=False)}\n"
            f"incidents={json.dumps(incidents, ensure_ascii=False)}\n"
            f"tasks={json.dumps(tasks, ensure_ascii=False)}\n"
            f"teams={json.dumps(teams, ensure_ascii=False)}\n"
            f"dispatches={json.dumps(dispatches, ensure_ascii=False)}\n"
        )

        client_kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        client = OpenAI(**client_kwargs)
        completion = client.chat.completions.create(
            model=self.model,
            temperature=0.15,
            messages=[
                {
                    "role": "system",
                    "content": "你是专业地震调度 Agent，输出必须是 JSON。",
                },
                {"role": "user", "content": prompt},
            ],
        )
        raw = completion.choices[0].message.content if completion.choices else ""
        payload = _extract_json_block(raw if isinstance(raw, str) else "")
        if not payload:
            return {"status": "degraded", "error": "模型输出不可解析 JSON", "raw": raw}
        return {"status": "ok", "payload": payload, "raw": raw}

    def generate_plan(
        self,
        *,
        analysis: dict[str, Any],
        incidents: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        teams: list[dict[str, Any]],
        dispatches: list[dict[str, Any]],
    ) -> dict[str, Any]:
        llm_result = self._llm_plan(
            analysis=analysis,
            incidents=incidents,
            tasks=tasks,
            teams=teams,
            dispatches=dispatches,
        )
        if llm_result.get("status") == "ok":
            plan = _normalize_plan(
                llm_result.get("payload") or {},
                teams=teams,
                max_tasks=self.max_tasks,
            )
            return {
                "status": "ok",
                "source": "llm",
                "plan": plan,
                "raw": llm_result.get("raw"),
            }

        heuristic_plan = self._heuristic_plan(
            analysis=analysis,
            incidents=incidents,
            teams=teams,
        )
        plan = _normalize_plan(heuristic_plan, teams=teams, max_tasks=self.max_tasks)
        return {
            "status": "degraded" if llm_result.get("error") else "mock",
            "source": "heuristic",
            "plan": plan,
            "error": llm_result.get("error"),
            "raw": llm_result.get("raw"),
        }
