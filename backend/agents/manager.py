from __future__ import annotations

import asyncio
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

try:
    from backend.utils.rag_engine import retrieve_policy
except ImportError:
    from utils.rag_engine import retrieve_policy

MessageCallback = Callable[[dict[str, Any]], Awaitable[None]]


def detect_hazard_type(text: str) -> str:
    # Earthquake-only mode for the Chengdu command system.
    _ = text
    return "earthquake"


def extract_coordinates(text: str) -> tuple[float, float] | None:
    patterns = [
        r"\[?\s*(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)\s*\]?",
        r"lat[:=]\s*(-?\d{1,2}\.\d+).*?lng[:=]\s*(-?\d{1,3}\.\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        lat, lng = float(match.group(1)), float(match.group(2))
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return lat, lng
    return None


def build_cv_assessment(hazard: str, mission_description: str) -> str:
    baseline = {
        "fire": "热源扩散风险高，建议优先判断火线方向、风向变化和可燃物密度。",
        "flood": "积水深度与流速存在不确定性，需优先确认低洼路段和排水节点。",
        "earthquake": "建筑结构稳定性未知，需重点标记疑似坍塌区与二次灾害风险点。",
        "unknown": "灾种信息不完整，建议先建立通用风险网格并补充现场影像。",
    }
    coords = extract_coordinates(mission_description)
    coord_hint = (
        f"检测到任务中包含坐标({coords[0]:.4f}, {coords[1]:.4f})，可作为第一观测中心。"
        if coords
        else "任务描述中未给出精确坐标，建议先通过前线回传确定核心受灾区域。"
    )
    return f"{baseline[hazard]} {coord_hint}"


def build_gis_advice(hazard: str) -> str:
    advice = {
        "fire": [
            "以风向反方向规划撤离走廊，避免穿越林地或狭窄峡谷。",
            "建立双层隔离圈：内圈救援、外圈交通管制。",
            "把医院、变电站、水厂列入优先防护节点。",
        ],
        "flood": [
            "主撤离路线指向高地，备用路线避开涵洞与下穿通道。",
            "对桥梁和隧道设置实时通行开关，基于水位动态调整。",
            "在 30-45 分钟内建立临时安置点与补给集散点。",
        ],
        "earthquake": [
            "优先绕行老旧高层、桥梁和地下空间出入口。",
            "按网格划分搜救区，先清点生命信号高概率区域。",
            "保持主干道至少一条救援单向通道畅通。",
        ],
        "unknown": [
            "先建立基础禁行区，再依据前线数据动态扩缩。",
            "设置统一坐标参考和回传频率，避免信息漂移。",
            "将交通、医疗、消防调度统一到单一战术图层。",
        ],
    }
    points = advice[hazard]
    return "\n".join(f"{idx}. {item}" for idx, item in enumerate(points, start=1))


def summarize_policy_snippets(hazard: str, snippets: list[str]) -> str:
    if not snippets:
        return "未检索到策略库条款，按照通用应急规范执行。"
    key = {
        "fire": "fire containment and evacuation",
        "flood": "flood evacuation and infrastructure protection",
        "earthquake": "structural collapse and USAR protocol",
        "unknown": "generic emergency operations",
    }[hazard]
    trimmed = []
    for raw in snippets[:2]:
        one_line = " ".join(raw.split())
        trimmed.append(one_line[:220])
    body = "\n".join(f"- {item}" for item in trimmed)
    return f"检索主题：{key}\n{body}"


class MissionManager:
    def __init__(self, callback: Optional[MessageCallback] = None):
        self.callback = callback

    async def _emit(self, source: str, content: str, message_type: str = "TextMessage") -> None:
        if not self.callback:
            return
        await self.callback({"type": message_type, "source": source, "content": content})

    async def run(self, mission_description: str) -> list[dict[str, Any]]:
        history: list[dict[str, Any]] = []

        async def push(source: str, content: str, message_type: str = "TextMessage") -> None:
            message = {"type": message_type, "source": source, "content": content}
            history.append(message)
            await self._emit(source, content, message_type=message_type)

        normalized_description = mission_description.strip() or "未知警情"
        hazard = detect_hazard_type(normalized_description)

        await push("SYSTEM", "Mission Started", "status")
        await asyncio.sleep(0.15)

        await push(
            "Commander_Agent",
            f"收到任务：{normalized_description}\n"
            f"判定灾种：{hazard}\n"
            "开始执行多智能体协同流程。",
        )
        await asyncio.sleep(0.15)

        await push("CV_Analyst_Agent", build_cv_assessment(hazard, normalized_description))
        await asyncio.sleep(0.15)

        snippets = retrieve_policy(f"{hazard} emergency protocol {normalized_description}", k=2)
        await push("Policy_RAG_Agent", summarize_policy_snippets(hazard, snippets))
        await asyncio.sleep(0.15)

        await push("GIS_Routing_Agent", build_gis_advice(hazard))
        await asyncio.sleep(0.15)

        await push(
            "Commander_Summary",
            "任务阶段性结论：\n"
            "1. 已完成灾种初判与风险区域定义。\n"
            "2. 已给出策略条款与路线建议。\n"
            "3. 建议继续接入前线报告更新态势图并滚动修正调度策略。",
        )
        await push("SYSTEM", "Mission Completed", "status")
        return history


async def run_mission(mission_description: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []

    async def collect(message: dict[str, Any]) -> None:
        events.append(message)

    mgr = MissionManager(callback=collect)
    await mgr.run(mission_description)
    return events
