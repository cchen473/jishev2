"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  BellRing,
  Bot,
  Map,
  Send,
  Shield,
  Terminal,
} from "lucide-react";
import { AgentMessage } from "@/components/AgentMessage";
import DisasterMap from "@/components/DisasterMap";
import MarkdownDisplay from "@/components/MarkdownDisplay";
import AuthCard from "@/components/command/AuthCard";
import AutoDispatchPanel from "@/components/command/AutoDispatchPanel";
import CommandShell from "@/components/command/CommandShell";
import IncidentBoard from "@/components/command/IncidentBoard";
import MetricCard from "@/components/command/MetricCard";
import PanelTabs from "@/components/command/PanelTabs";
import ReadReceiptPanel from "@/components/command/ReadReceiptPanel";
import SectionFrame from "@/components/command/SectionFrame";
import TaskKanban from "@/components/command/TaskKanban";
import TimelineRail from "@/components/command/TimelineRail";
import {
  askCommunityAssistant,
  clearAuthToken,
  createIncident,
  createIncidentTask,
  fetchCommunityChatMessages,
  fetchCommunityNotifications,
  fetchDispatchAgentRuns,
  fetchEarthquakeRescueAnalyses,
  fetchIncidents,
  fetchMe,
  fetchNotificationReceiptSummary,
  fetchOpsTimeline,
  fetchRecentReports,
  fetchResidentCheckinSummary,
  fetchSystemSummary,
  fetchTasks,
  fetchTeams,
  getAuthToken,
  loginUser,
  markNotificationReceipt,
  registerUser,
  saveAuthToken,
  sendCommunityAlert,
  sendOneClickWarning,
  sendCommunityChatMessage,
  submitEarthquakeRescueAnalysis,
  updateIncident,
  updateTask,
  type AuthUser,
  type CommunityChatMessage,
  type CommunityNotification,
  type DispatchAgentRunSummary,
  type EarthquakeRescueAnalysisPayload,
  type EarthquakeRescueAnalysisRecord,
  type FieldReport,
  type Incident,
  type IncidentTask,
  type NotificationReceiptSummary,
  type OpsTimelineEvent,
  type ResidentCheckinSummary,
  type ResponseTeam,
  type SystemSummary,
} from "@/lib/api";
import { getBackendWsBase, toBackendAbsoluteUrl } from "@/lib/runtime-config";

interface Message {
  id: string;
  source: string;
  content: string;
  type: string;
}

const EMPTY_SUMMARY: SystemSummary = {
  total_reports: 0,
  active_missions: 0,
  report_counts: {},
  latest_report: null,
  total_incidents: 0,
  active_tasks: 0,
  residents_need_help: 0,
};

type ConnectionState = "connecting" | "connected" | "disconnected";
type AuthMode = "login" | "register";
type RightPanelTab = "terminal" | "chat" | "rescue";
type WorkspaceView = "overview" | "operations" | "community";

function createMessage(source: string, content: string, type = "TextMessage"): Message {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    source,
    content,
    type,
  };
}

function readErrorMessage(error: unknown, fallback: string): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    typeof (error as { response?: unknown }).response === "object"
  ) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (
        typeof first === "object" &&
        first !== null &&
        "msg" in first &&
        typeof (first as { msg?: unknown }).msg === "string"
      ) {
        return String((first as { msg: string }).msg);
      }
    }
  }
  return fallback;
}

function buildCommunityAlertMarkdown(title: string, content: string): string {
  return `### ${title}\n\n${content}`;
}

function buildFieldReportMarkdown(report: FieldReport): string {
  const lines = [
    "### 收到震情上报",
    `- **震感等级**：${report.felt_level} 级`,
    `- **建筑类型**：${report.building_type}`,
    `- **位置**：${report.lat.toFixed(5)}, ${report.lng.toFixed(5)}`,
    report.description ? `- **描述**：${report.description}` : "",
    report.image_url ? `- **现场图片**：[点击查看](${toBackendAbsoluteUrl(report.image_url)})` : "",
  ].filter(Boolean);

  const adviceSection =
    report.vlm_advice && report.vlm_advice.length
      ? `\n\n#### VLM 躲避建议\n${report.vlm_advice
          .map((item, index) => `${index + 1}. ${item}`)
          .join("\n")}`
      : "";

  return `${lines.join("\n")}${adviceSection}`;
}

function buildRescueAnalysisMarkdown(record: EarthquakeRescueAnalysisRecord): string {
  const analysis: EarthquakeRescueAnalysisPayload = record.analysis ?? {};
  const victims = Array.isArray(analysis.victims) ? analysis.victims : [];
  const routes = Array.isArray(analysis.routes) ? analysis.routes : [];
  const notes = Array.isArray(analysis.command_notes) ? analysis.command_notes : [];
  const imageFindings = Array.isArray(analysis.image_findings) ? analysis.image_findings : [];
  const metrics =
    analysis.algorithm_metrics && typeof analysis.algorithm_metrics === "object"
      ? analysis.algorithm_metrics
      : null;

  const victimSection = victims.length
    ? victims
        .map(
          (v, idx) =>
            `${idx + 1}. **${v.id || `V-${idx + 1}`}**\n   - 位置：${v.position_hint || "未知"}\n   - 风险：${v.risk_level || "未知"}\n   - 优先级：${v.priority ?? idx + 1}\n   - 优先分：${typeof v.priority_score === "number" ? v.priority_score.toFixed(3) : "N/A"}\n   - 状态：${v.condition || "待确认"}\n   - 证据：${v.evidence || "无"}${v.image_url ? `\n   - 原图： [查看](${toBackendAbsoluteUrl(v.image_url)})` : ""}${v.annotated_image_url ? `\n   - 标注图： [查看](${toBackendAbsoluteUrl(v.annotated_image_url)})` : ""}`,
        )
        .join("\n")
    : "- 暂无明确受困人员目标";

  const routeSection = routes.length
    ? routes
        .map((r, idx) => {
          const steps = Array.isArray(r.steps) && r.steps.length ? r.steps.map((s) => `     - ${s}`).join("\n") : "     - 无";
          return `${idx + 1}. **${r.name || `路线-${idx + 1}`}**\n   - 类型：${r.route_type === "search" ? "搜索" : r.route_type === "rescue" ? "救援" : "综合"}\n   - 风险：${r.risk || "未知"}\n   - 推荐队伍：${r.recommended_team || "待定"}\n   - 步骤：\n${steps}`;
        })
        .join("\n")
    : "- 暂无可执行路线";

  const noteSection = notes.length ? notes.map((n, i) => `${i + 1}. ${n}`).join("\n") : "- 无";
  const summarySection = imageFindings.length
    ? imageFindings
        .map(
          (item, idx) =>
            `${idx + 1}. **${item.image_name || `image-${idx + 1}`}**：识别到 ${item.detected_people ?? 0} 人${item.original_image_url ? `（[原图](${toBackendAbsoluteUrl(item.original_image_url)})` : ""}${item.annotated_image_url ? `${item.original_image_url ? " / " : "（"}[标注图](${toBackendAbsoluteUrl(item.annotated_image_url)})` : ""}${item.original_image_url || item.annotated_image_url ? "）" : ""}`,
        )
        .join("\n")
    : "- 无";
  const hotspotSection =
    metrics && Array.isArray(metrics.hotspots) && metrics.hotspots.length
      ? metrics.hotspots
          .slice(0, 6)
          .map(
            (spot, index) =>
              `${index + 1}. **${spot.id}**（${spot.level}）- 强度 ${spot.intensity.toFixed(
                3,
              )}，目标 ${spot.victim_ids.length} 个，中心 ${spot.center_norm
                .map((value) => value.toFixed(3))
                .join(", ")}`,
          )
          .join("\n")
      : "- 暂无热点聚类";
  const metricLine = metrics
    ? `- **复杂度指数**：${metrics.rescue_complexity_index.toFixed(1)} / 100\n- **搜索覆盖率**：${metrics.coverage_score.toFixed(
        1,
      )} / 100\n- **优先级模型**：${metrics.priority_model || "默认"}`
    : "- **复杂度指数**：N/A\n- **搜索覆盖率**：N/A";

  return [
    "### 地震受灾搜救分析结果（VLM）",
    `- **状态**：${record.status}`,
    `- **场景概览**：${analysis.scene_overview || "暂无"}`,
    "",
    "#### 图像识别摘要",
    summarySection,
    "",
    "#### 受灾人群识别",
    victimSection,
    "",
    "#### 建议搜索与救援路线",
    routeSection,
    "",
    "#### 算法评估",
    metricLine,
    "",
    "#### 热点聚类",
    hotspotSection,
    "",
    "#### 指挥备注",
    noteSection,
  ]
    .filter(Boolean)
    .join("\n");
}

export default function Home() {
  const [authReady, setAuthReady] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState("");
  const [authToken, setAuthToken] = useState("");
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);

  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  const [registerUsername, setRegisterUsername] = useState("");
  const [registerDisplayName, setRegisterDisplayName] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerCommunityName, setRegisterCommunityName] = useState("默认社区");
  const [registerCommunityDistrict, setRegisterCommunityDistrict] = useState("默认行政区");

  const [activePanel, setActivePanel] = useState<RightPanelTab>("terminal");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerPinned, setDrawerPinned] = useState(false);
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>("overview");

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<Message[]>([]);
  const [reports, setReports] = useState<FieldReport[]>([]);
  const [summary, setSummary] = useState<SystemSummary>(EMPTY_SUMMARY);
  const [notifications, setNotifications] = useState<CommunityNotification[]>([]);
  const [notificationReceiptSummaries, setNotificationReceiptSummaries] = useState<
    Record<string, NotificationReceiptSummary | undefined>
  >({});
  const [myNotificationReceiptStatus, setMyNotificationReceiptStatus] = useState<
    Record<string, "read" | "confirmed" | undefined>
  >({});
  const [connection, setConnection] = useState<ConnectionState>("connecting");

  const [alertTitle, setAlertTitle] = useState("余震避险提醒");
  const [alertContent, setAlertContent] = useState("");
  const [alertSending, setAlertSending] = useState(false);
  const [warningSending, setWarningSending] = useState(false);

  const [chatMessages, setChatMessages] = useState<CommunityChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const [chatAskAi, setChatAskAi] = useState(true);
  const [assistantQuestion, setAssistantQuestion] = useState("");
  const [assistantLoading, setAssistantLoading] = useState(false);

  const [rescueDescription, setRescueDescription] = useState("");
  const [rescueLat, setRescueLat] = useState("");
  const [rescueLng, setRescueLng] = useState("");
  const [rescueImageFiles, setRescueImageFiles] = useState<File[]>([]);
  const [rescueLoading, setRescueLoading] = useState(false);
  const [rescueError, setRescueError] = useState("");
  const [rescueAnalyses, setRescueAnalyses] = useState<EarthquakeRescueAnalysisRecord[]>([]);
  const [dispatchAgentRuns, setDispatchAgentRuns] = useState<DispatchAgentRunSummary[]>([]);

  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [incidentCreating, setIncidentCreating] = useState(false);
  const [incidentUpdatingId, setIncidentUpdatingId] = useState<string | null>(null);
  const [tasks, setTasks] = useState<IncidentTask[]>([]);
  const [taskCreating, setTaskCreating] = useState(false);
  const [taskUpdatingId, setTaskUpdatingId] = useState<string | null>(null);
  const [teams, setTeams] = useState<ResponseTeam[]>([]);
  const [timelineEvents, setTimelineEvents] = useState<OpsTimelineEvent[]>([]);
  const [checkinSummary, setCheckinSummary] = useState<ResidentCheckinSummary>({
    community_id: "",
    total: 0,
    by_status: {},
    latest_checkin_at: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reportIdsRef = useRef<Set<string>>(new Set());
  const loadedReceiptIdsRef = useRef<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);
  const drawerCloseTimerRef = useRef<number | null>(null);

  const appendMessage = (message: Message) => {
    setHistory((prev) => [...prev, message].slice(-500));
  };

  const upsertReport = (report: FieldReport) => {
    setReports((prev) => {
      const exists = prev.some((item) => item.id === report.id);
      if (exists) {
        return prev.map((item) => (item.id === report.id ? report : item));
      }
      return [...prev, report].slice(-300);
    });
  };

  const upsertChatMessage = (incoming: CommunityChatMessage) => {
    setChatMessages((prev) => {
      if (prev.some((item) => item.id === incoming.id)) {
        return prev;
      }
      return [...prev, incoming].slice(-300);
    });
  };

  const upsertRescueAnalysis = (incoming: EarthquakeRescueAnalysisRecord) => {
    setRescueAnalyses((prev) => {
      if (prev.some((item) => item.id === incoming.id)) {
        return prev;
      }
      return [...prev, incoming].slice(-80);
    });
  };

  const normalizeNotifications = (items: CommunityNotification[]) => {
    const unique = new globalThis.Map<string, CommunityNotification>();
    items.forEach((item) => {
      if (item?.id) {
        unique.set(item.id, item);
      }
    });
    return Array.from(unique.values()).slice(-200);
  };

  const upsertNotification = (incoming: CommunityNotification) => {
    if (!incoming?.id) {
      return;
    }
    setNotifications((prev) => {
      const index = prev.findIndex((item) => item.id === incoming.id);
      if (index >= 0) {
        const next = [...prev];
        next[index] = incoming;
        return next;
      }
      return [...prev, incoming].slice(-200);
    });
  };

  const upsertDispatchAgentRun = (incoming: DispatchAgentRunSummary) => {
    setDispatchAgentRuns((prev) => {
      const index = prev.findIndex((item) => item.id === incoming.id);
      if (index >= 0) {
        const next = [...prev];
        next[index] = incoming;
        return next;
      }
      return [...prev, incoming].slice(-120);
    });
  };

  const upsertIncident = (incoming: Incident) => {
    setIncidents((prev) => {
      const index = prev.findIndex((item) => item.id === incoming.id);
      if (index >= 0) {
        const next = [...prev];
        next[index] = incoming;
        return next;
      }
      return [...prev, incoming].slice(-200);
    });
  };

  const upsertTask = (incoming: IncidentTask) => {
    setTasks((prev) => {
      const index = prev.findIndex((item) => item.id === incoming.id);
      if (index >= 0) {
        const next = [...prev];
        next[index] = incoming;
        return next;
      }
      return [...prev, incoming].slice(-500);
    });
  };

  const upsertTimelineEvent = (incoming: OpsTimelineEvent) => {
    setTimelineEvents((prev) => {
      if (prev.some((item) => item.id === incoming.id)) {
        return prev;
      }
      return [...prev, incoming].slice(-600);
    });
  };

  const mapMarkers = useMemo(
    () =>
      reports.map((item) => ({
        lat: item.lat,
        lng: item.lng,
        type: "earthquake",
      })),
    [reports],
  );

  const communityCenterLat = currentUser?.community?.base_lat ?? 30.5728;
  const communityCenterLng = currentUser?.community?.base_lng ?? 104.0668;
  const latestReport = reports[reports.length - 1] ?? null;
  const mapCenterLat = latestReport?.lat ?? communityCenterLat;
  const mapCenterLng = latestReport?.lng ?? communityCenterLng;
  const latestNotifications = notifications.slice(-8).reverse();
  const latestRescueAnalysis = rescueAnalyses[rescueAnalyses.length - 1] ?? null;
  const workspaceTitle =
    workspaceView === "overview" ? "态势总览" : workspaceView === "operations" ? "调度作业" : "社区协同";

  useEffect(() => {
    let active = true;
    let settled = false;
    const token = getAuthToken();
    if (!token) {
      setAuthReady(true);
      return;
    }

    const bootstrapTimeout = window.setTimeout(() => {
      if (!active || settled) {
        return;
      }
      settled = true;
      clearAuthToken();
      setAuthToken("");
      setCurrentUser(null);
      setAuthError("自动登录超时，请重新登录。");
      setAuthReady(true);
    }, 7000);

    fetchMe(token)
      .then((user) => {
        if (!active || settled) return;
        settled = true;
        clearTimeout(bootstrapTimeout);
        setAuthError("");
        setAuthToken(token);
        setCurrentUser(user);
        setAuthReady(true);
      })
      .catch(() => {
        if (!active || settled) return;
        settled = true;
        clearTimeout(bootstrapTimeout);
        clearAuthToken();
        setAuthToken("");
        setCurrentUser(null);
        setAuthError("登录状态已失效，请重新登录。");
        setAuthReady(true);
      });
    return () => {
      active = false;
      clearTimeout(bootstrapTimeout);
    };
  }, []);

  useEffect(() => {
    if (!authToken || !currentUser?.community) {
      return;
    }
    const communityName = currentUser.community.name;
    let mounted = true;

    const bootstrap = async () => {
      try {
        const [
          initialReports,
          initialSummary,
          initialNotifications,
          initialChats,
          initialRescue,
          initialAgentRuns,
          initialIncidents,
          initialTasks,
          initialTeams,
          initialTimeline,
          initialCheckinSummary,
        ] = await Promise.all([
          fetchRecentReports(50, authToken),
          fetchSystemSummary(authToken),
          fetchCommunityNotifications(50, authToken),
          fetchCommunityChatMessages(100, authToken),
          fetchEarthquakeRescueAnalyses(20, authToken),
          fetchDispatchAgentRuns(20, authToken),
          fetchIncidents(80, authToken),
          fetchTasks(160, authToken),
          fetchTeams(120, authToken),
          fetchOpsTimeline(220, authToken),
          fetchResidentCheckinSummary(authToken),
        ]);
        if (!mounted) {
          return;
        }
        setReports(initialReports);
        reportIdsRef.current = new Set(initialReports.map((item) => item.id));
        setSummary(initialSummary);
        setNotifications(normalizeNotifications(initialNotifications));
        setNotificationReceiptSummaries({});
        setMyNotificationReceiptStatus({});
        loadedReceiptIdsRef.current.clear();
        setChatMessages(initialChats);
        setRescueAnalyses(initialRescue);
        setDispatchAgentRuns(initialAgentRuns);
        setIncidents(initialIncidents);
        setTasks(initialTasks);
        setTeams(initialTeams);
        setTimelineEvents(initialTimeline);
        setCheckinSummary(initialCheckinSummary);
        appendMessage(
          createMessage(
            "SYSTEM",
            [
              "### 系统初始化完成",
              `- **社区**：${communityName}`,
              `- **历史上报**：${initialReports.length} 条`,
              `- **社区通知**：${initialNotifications.length} 条`,
              `- **群聊消息**：${initialChats.length} 条`,
              `- **地震搜救分析**：${initialRescue.length} 条`,
              `- **自动调度记录**：${initialAgentRuns.length} 条`,
              `- **事件工单**：${initialIncidents.length} 事件 / ${initialTasks.length} 任务`,
            ].join("\n"),
            "status",
          ),
        );
      } catch {
        if (!mounted) {
          return;
        }
        appendMessage(createMessage("SYSTEM_ERROR", "初始化失败：无法拉取社区数据", "Error"));
      }
    };

    bootstrap();

    return () => {
      mounted = false;
    };
  }, [authToken, currentUser]);

  useEffect(() => {
    if (!authToken || !currentUser?.community) {
      return;
    }

    let active = true;

    const connect = () => {
      if (!active) {
        return;
      }
      setConnection("connecting");
      const ws = new WebSocket(`${getBackendWsBase()}/ws/mission?token=${encodeURIComponent(authToken)}`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!active) {
          return;
        }
        setConnection("connected");
        ws.send(JSON.stringify({ type: "fetch_recent_reports", limit: 50 }));
        ws.send(JSON.stringify({ type: "fetch_notifications", limit: 30 }));
        ws.send(JSON.stringify({ type: "fetch_chat_messages", limit: 100 }));
        ws.send(JSON.stringify({ type: "fetch_earthquake_rescue_analyses", limit: 20 }));
        ws.send(JSON.stringify({ type: "fetch_dispatch_agent_runs", limit: 20 }));
        ws.send(JSON.stringify({ type: "fetch_incidents", limit: 80 }));
        ws.send(JSON.stringify({ type: "fetch_tasks", limit: 200 }));
        ws.send(JSON.stringify({ type: "fetch_teams", limit: 120 }));
        ws.send(JSON.stringify({ type: "fetch_ops_timeline", limit: 240 }));
        ws.send(JSON.stringify({ type: "fetch_resident_checkin_summary" }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === "recent_reports" && Array.isArray(data.items)) {
            const incoming = data.items as FieldReport[];
            setReports(incoming);
            reportIdsRef.current = new Set(incoming.map((item) => item.id));
            return;
          }

          if (data.type === "community_notifications" && Array.isArray(data.items)) {
            setNotifications(normalizeNotifications(data.items as CommunityNotification[]));
            return;
          }

          if (data.type === "community_chat_messages" && Array.isArray(data.items)) {
            setChatMessages(data.items as CommunityChatMessage[]);
            return;
          }

          if (data.type === "community_chat_message" && data.message) {
            const msg = data.message as CommunityChatMessage;
            upsertChatMessage(msg);
            return;
          }

          if (
            (data.type === "earthquake_rescue_analyses" || data.type === "fire_rescue_analyses") &&
            Array.isArray(data.items)
          ) {
            setRescueAnalyses(data.items as EarthquakeRescueAnalysisRecord[]);
            return;
          }

          if (data.type === "dispatch_agent_runs" && Array.isArray(data.items)) {
            setDispatchAgentRuns(data.items as DispatchAgentRunSummary[]);
            return;
          }

          if (data.type === "incidents" && Array.isArray(data.items)) {
            setIncidents(data.items as Incident[]);
            return;
          }

          if (data.type === "incident_created" && data.incident) {
            upsertIncident(data.incident as Incident);
            return;
          }

          if (data.type === "incident_updated" && data.incident) {
            upsertIncident(data.incident as Incident);
            return;
          }

          if (data.type === "tasks" && Array.isArray(data.items)) {
            setTasks(data.items as IncidentTask[]);
            return;
          }

          if (data.type === "task_created" && data.task) {
            upsertTask(data.task as IncidentTask);
            return;
          }

          if (data.type === "task_updated" && data.task) {
            upsertTask(data.task as IncidentTask);
            return;
          }

          if (data.type === "teams" && Array.isArray(data.items)) {
            setTeams(data.items as ResponseTeam[]);
            return;
          }

          if (data.type === "ops_timeline" && Array.isArray(data.items)) {
            setTimelineEvents(data.items as OpsTimelineEvent[]);
            return;
          }

          if (data.type === "ops_timeline_event" && data.event) {
            const event = data.event as OpsTimelineEvent;
            upsertTimelineEvent(event);
            if (event.event_type === "notification_receipt_updated" && event.payload) {
              const payload = event.payload as {
                summary?: NotificationReceiptSummary;
                receipt?: {
                  notification_id?: string;
                  status?: string;
                  user_id?: string;
                };
              };
              const summaryPayload = payload.summary;
              const receiptPayload = payload.receipt;
              if (
                summaryPayload &&
                typeof summaryPayload === "object" &&
                summaryPayload.notification_id
              ) {
                setNotificationReceiptSummaries((prev) => ({
                  ...prev,
                  [summaryPayload.notification_id]: summaryPayload,
                }));
              }
              const receiptNotificationId = receiptPayload?.notification_id;
              if (receiptNotificationId && receiptPayload.user_id === currentUser?.id) {
                setMyNotificationReceiptStatus((prev) => ({
                  ...prev,
                  [receiptNotificationId]:
                    receiptPayload.status === "confirmed" ? "confirmed" : "read",
                }));
              }
            }
            return;
          }

          if (data.type === "resident_checkin_summary" && data.summary) {
            setCheckinSummary(data.summary as ResidentCheckinSummary);
            return;
          }

          if (data.type === "resident_checkin_updated" && data.event) {
            upsertTimelineEvent(data.event as OpsTimelineEvent);
            void fetchResidentCheckinSummary(authToken)
              .then((summaryData) => setCheckinSummary(summaryData))
              .catch(() => null);
            return;
          }

          if (data.type === "hazard_zone_updated" && data.event) {
            upsertTimelineEvent(data.event as OpsTimelineEvent);
            return;
          }

          if (
            (data.type === "earthquake_rescue_analysis" || data.type === "fire_rescue_analysis") &&
            data.analysis
          ) {
            const analysis = data.analysis as EarthquakeRescueAnalysisRecord;
            upsertRescueAnalysis(analysis);
            if (data.dispatch_agent_run) {
              upsertDispatchAgentRun(data.dispatch_agent_run as DispatchAgentRunSummary);
            }
            appendMessage(
              createMessage(
                "RESCUE_AI",
                buildRescueAnalysisMarkdown(analysis),
                "Alert",
              ),
            );
            return;
          }

          if (data.type === "dispatch_agent_executed" && data.payload?.dispatch_agent_run) {
            upsertDispatchAgentRun(data.payload.dispatch_agent_run as DispatchAgentRunSummary);
            return;
          }

          if (data.type === "community_alert") {
            const title = String(data.title || "社区通知");
            const content = String(data.content || "收到新的社区避险通知");
            appendMessage(
              createMessage("COMMUNITY_ALERT", buildCommunityAlertMarkdown(title, content), "Alert"),
            );
            if (data.notification) {
              const notification = data.notification as CommunityNotification;
              upsertNotification(notification);
            }
            return;
          }

          if (data.type === "community_warning") {
            const title = String(data.title || "地震紧急预警");
            const content = String(data.content || "收到紧急预警，请立即执行避险动作。");
            appendMessage(
              createMessage("COMMUNITY_WARNING", buildCommunityAlertMarkdown(title, content), "Alert"),
            );
            if (data.notification) {
              const notification = data.notification as CommunityNotification;
              upsertNotification(notification);
            }
            return;
          }

          if (data.type === "field_report") {
            const report: FieldReport = {
              id: data.id ?? `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
              user_id: data.user_id ?? "",
              community_id: data.community_id ?? "",
              lat: data.lat,
              lng: data.lng,
              category: "earthquake",
              felt_level: Number(data.felt_level ?? 5),
              building_type: String(data.building_type ?? "未知建筑"),
              structure_notes: String(data.structure_notes ?? ""),
              description: String(data.description ?? ""),
              image_url: data.image_url ?? null,
              vlm_advice: Array.isArray(data.vlm_advice) ? data.vlm_advice : [],
              created_at: data.created_at ?? new Date().toISOString(),
            };

            const isNewReport = !reportIdsRef.current.has(report.id);
            reportIdsRef.current.add(report.id);
            upsertReport(report);
            if (isNewReport) {
              setSummary((prev) => ({
                ...prev,
                total_reports: prev.total_reports + 1,
                report_counts: {
                  ...prev.report_counts,
                  earthquake: (prev.report_counts.earthquake ?? 0) + 1,
                },
                latest_report: report,
              }));
            } else {
              setSummary((prev) => ({ ...prev, latest_report: report }));
            }

            appendMessage(createMessage("SYSTEM_ALERT", buildFieldReportMarkdown(report), "Alert"));
            return;
          }

          if (data.source && data.content) {
            appendMessage(
              createMessage(String(data.source), String(data.content), String(data.type || "TextMessage")),
            );
            const content = String(data.content);
            if (content.includes("Mission Completed") || content.includes("Mission failed")) {
              setLoading(false);
              void fetchSystemSummary(authToken).then((s) => setSummary(s)).catch(() => null);
            } else if (content.includes("Mission Started")) {
              setLoading(true);
            }
          }
        } catch {
          appendMessage(createMessage("SYSTEM_ERROR", "收到无法解析的消息", "Error"));
        }
      };

      ws.onerror = () => {
        if (!active) {
          return;
        }
        setConnection("disconnected");
      };

      ws.onclose = () => {
        if (!active) {
          return;
        }
        setConnection("disconnected");
        reconnectTimerRef.current = window.setTimeout(() => connect(), 1800);
      };
    };

    connect();

    return () => {
      active = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [authToken, currentUser]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history]);

  useEffect(() => {
    const community = currentUser?.community;
    if (!community) {
      return;
    }
    setRescueLat((prev) => (prev.trim() ? prev : community.base_lat.toFixed(5)));
    setRescueLng((prev) => (prev.trim() ? prev : community.base_lng.toFixed(5)));
  }, [currentUser?.community]);

  useEffect(() => {
    return () => {
      if (drawerCloseTimerRef.current) {
        clearTimeout(drawerCloseTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!authToken || notifications.length === 0) {
      return;
    }
    let active = true;
    const targets = notifications.slice(-12);
    const pending = targets.filter((item) => !loadedReceiptIdsRef.current.has(item.id));
    if (pending.length === 0) {
      return;
    }
    pending.forEach((item) => loadedReceiptIdsRef.current.add(item.id));

    Promise.all(
      pending.map(async (item) => {
        try {
          const summary = await fetchNotificationReceiptSummary(item.id, authToken);
          return [item.id, summary] as const;
        } catch {
          return [item.id, null] as const;
        }
      }),
    )
      .then((entries) => {
        if (!active) {
          return;
        }
        setNotificationReceiptSummaries((prev) => {
          const next = { ...prev };
          entries.forEach(([id, summary]) => {
            if (summary) {
              next[id] = summary;
            }
          });
          return next;
        });
      })
      .catch(() => {
        pending.forEach((item) => loadedReceiptIdsRef.current.delete(item.id));
      });

    return () => {
      active = false;
    };
  }, [authToken, notifications]);

  const openDrawer = () => {
    if (drawerCloseTimerRef.current) {
      clearTimeout(drawerCloseTimerRef.current);
      drawerCloseTimerRef.current = null;
    }
    setDrawerOpen(true);
  };

  const scheduleDrawerClose = () => {
    if (drawerPinned) {
      return;
    }
    if (drawerCloseTimerRef.current) {
      clearTimeout(drawerCloseTimerRef.current);
    }
    drawerCloseTimerRef.current = window.setTimeout(() => {
      setDrawerOpen(false);
      drawerCloseTimerRef.current = null;
    }, 180);
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginUsername.trim() || !loginPassword.trim()) {
      return;
    }
    setAuthLoading(true);
    setAuthError("");
    try {
      const resp = await loginUser({
        username: loginUsername.trim(),
        password: loginPassword,
      });
      saveAuthToken(resp.token);
      setAuthToken(resp.token);
      setCurrentUser(resp.user);
      setHistory([]);
    } catch (error: unknown) {
      setAuthError(readErrorMessage(error, "登录失败，请检查用户名和密码"));
    } finally {
      setAuthLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!registerUsername.trim() || !registerPassword.trim() || !registerDisplayName.trim()) {
      return;
    }
    setAuthLoading(true);
    setAuthError("");
    try {
      const resp = await registerUser({
        username: registerUsername.trim(),
        display_name: registerDisplayName.trim(),
        password: registerPassword,
        community_name: registerCommunityName.trim(),
        community_district: registerCommunityDistrict.trim() || "默认行政区",
      });
      saveAuthToken(resp.token);
      setAuthToken(resp.token);
      setCurrentUser(resp.user);
      setHistory([]);
    } catch (error: unknown) {
      setAuthError(readErrorMessage(error, "注册失败，请调整信息后重试"));
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    clearAuthToken();
    setAuthToken("");
    setCurrentUser(null);
    setHistory([]);
    setReports([]);
    setNotifications([]);
    setNotificationReceiptSummaries({});
    setMyNotificationReceiptStatus({});
    loadedReceiptIdsRef.current.clear();
    setChatMessages([]);
    setRescueAnalyses([]);
    setDispatchAgentRuns([]);
    setIncidents([]);
    setTasks([]);
    setTeams([]);
    setTimelineEvents([]);
    setCheckinSummary({
      community_id: "",
      total: 0,
      by_status: {},
      latest_checkin_at: null,
    });
    wsRef.current?.close();
    wsRef.current = null;
  };

  const handleSubmitMission = (e: React.FormEvent) => {
    e.preventDefault();
    const description = input.trim();
    if (!description || loading) {
      return;
    }

    appendMessage(createMessage("COMMANDER_INPUT", description));
    setInput("");

    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      appendMessage(createMessage("SYSTEM_ERROR", "连接未就绪，无法发送任务", "Error"));
      return;
    }

    ws.send(JSON.stringify({ type: "start_mission", description }));
    setLoading(true);
  };

  const handleSendCommunityAlert = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!authToken || !alertTitle.trim() || !alertContent.trim()) {
      return;
    }
    setAlertSending(true);
    try {
      const notification = await sendCommunityAlert(
        {
          title: alertTitle.trim(),
          content: alertContent.trim(),
        },
        authToken,
      );
      upsertNotification(notification);
      setAlertContent("");
      appendMessage(
        createMessage(
          "COMMUNITY_BROADCAST",
          buildCommunityAlertMarkdown(notification.title, notification.content),
          "status",
        ),
      );
    } catch (error: unknown) {
      appendMessage(createMessage("SYSTEM_ERROR", readErrorMessage(error, "社区通知发送失败"), "Error"));
    } finally {
      setAlertSending(false);
    }
  };

  const handleOneClickWarning = async () => {
    if (!authToken || warningSending) {
      return;
    }
    setWarningSending(true);
    try {
      const notification = await sendOneClickWarning(
        {
          title: "地震紧急预警",
          content:
            "请立即远离玻璃和外墙，按社区避险路线前往最近集合点，保持手机畅通并等待后续调度。",
        },
        authToken,
      );
      upsertNotification(notification);
      appendMessage(
        createMessage(
          "COMMUNITY_WARNING",
          buildCommunityAlertMarkdown(notification.title, notification.content),
          "Alert",
        ),
      );
    } catch (error: unknown) {
      appendMessage(createMessage("SYSTEM_ERROR", readErrorMessage(error, "一键预警发送失败"), "Error"));
    } finally {
      setWarningSending(false);
    }
  };

  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!authToken || !chatInput.trim()) {
      return;
    }
    setChatSending(true);
    try {
      await sendCommunityChatMessage(
        {
          content: chatInput.trim(),
          ask_ai: chatAskAi,
        },
        authToken,
      );
      setChatInput("");
    } catch (error: unknown) {
      appendMessage(createMessage("SYSTEM_ERROR", readErrorMessage(error, "社区聊天发送失败"), "Error"));
    } finally {
      setChatSending(false);
    }
  };

  const handleAskAssistant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!authToken || !assistantQuestion.trim()) {
      return;
    }
    setAssistantLoading(true);
    try {
      await askCommunityAssistant(assistantQuestion.trim(), authToken);
      setAssistantQuestion("");
    } catch (error: unknown) {
      appendMessage(createMessage("SYSTEM_ERROR", readErrorMessage(error, "AI 助手请求失败"), "Error"));
    } finally {
      setAssistantLoading(false);
    }
  };

  const handleRunEarthquakeRescue = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!authToken) {
      return;
    }
    if (rescueImageFiles.length === 0) {
      setRescueError("请至少上传 1 张地震现场图");
      return;
    }

    setRescueLoading(true);
    setRescueError("");
    try {
      const form = new FormData();
      form.append("description", rescueDescription.trim());
      if (rescueLat.trim()) {
        form.append("lat", rescueLat.trim());
      }
      if (rescueLng.trim()) {
        form.append("lng", rescueLng.trim());
      }
      rescueImageFiles.forEach((file) => form.append("images", file));

      const result = await submitEarthquakeRescueAnalysis(form, authToken);
      upsertRescueAnalysis(result.result);
      if (result.dispatch_agent_run) {
        upsertDispatchAgentRun(result.dispatch_agent_run);
        const [latestIncidents, latestTasks] = await Promise.all([
          fetchIncidents(80, authToken),
          fetchTasks(200, authToken),
        ]);
        setIncidents(latestIncidents);
        setTasks(latestTasks);
      }
      appendMessage(createMessage("RESCUE_AI", buildRescueAnalysisMarkdown(result.result), "Alert"));
      if (result.analysis_status !== "ok") {
        const warningText = result.analysis_error || "部分图片未完成 VLM 检测，请检查图片格式后重试。";
        setRescueError(warningText);
        appendMessage(createMessage("SYSTEM_ERROR", warningText, "Error"));
      }
      if (result.deprecated_endpoint) {
        appendMessage(createMessage("SYSTEM", "当前使用的是兼容接口，请迁移到地震搜救新接口。", "status"));
      }
      setRescueDescription("");
    } catch (error: unknown) {
      const text = readErrorMessage(error, "地震受灾搜救分析失败");
      setRescueError(text);
      appendMessage(createMessage("SYSTEM_ERROR", text, "Error"));
    } finally {
      setRescueLoading(false);
    }
  };

  const handleCreateIncident = async (payload: {
    title: string;
    description: string;
    priority: "low" | "medium" | "high" | "critical";
  }) => {
    if (!authToken) {
      return;
    }
    setIncidentCreating(true);
    try {
      const incident = await createIncident(
        {
          title: payload.title,
          description: payload.description,
          priority: payload.priority,
          source: "manual",
          lat: latestReport?.lat ?? communityCenterLat,
          lng: latestReport?.lng ?? communityCenterLng,
        },
        authToken,
      );
      upsertIncident(incident);
    } catch (error: unknown) {
      appendMessage(createMessage("SYSTEM_ERROR", readErrorMessage(error, "事件创建失败"), "Error"));
    } finally {
      setIncidentCreating(false);
    }
  };

  const handleUpdateIncidentStatus = async (
    incidentId: string,
    status: "new" | "verified" | "responding" | "stabilized" | "closed",
  ) => {
    if (!authToken) {
      return;
    }
    setIncidentUpdatingId(incidentId);
    try {
      const incident = await updateIncident(incidentId, { status }, authToken);
      upsertIncident(incident);
    } catch (error: unknown) {
      appendMessage(createMessage("SYSTEM_ERROR", readErrorMessage(error, "事件状态更新失败"), "Error"));
    } finally {
      setIncidentUpdatingId(null);
    }
  };

  const handleCreateTask = async (payload: {
    incident_id: string;
    title: string;
    description: string;
    priority: "low" | "medium" | "high" | "critical";
    team_id?: string;
  }) => {
    if (!authToken) {
      return;
    }
    setTaskCreating(true);
    try {
      const task = await createIncidentTask(
        payload.incident_id,
        {
          title: payload.title,
          description: payload.description,
          priority: payload.priority,
          status: "assigned",
          team_id: payload.team_id,
        },
        authToken,
      );
      upsertTask(task);
    } catch (error: unknown) {
      appendMessage(createMessage("SYSTEM_ERROR", readErrorMessage(error, "任务创建失败"), "Error"));
    } finally {
      setTaskCreating(false);
    }
  };

  const handleAdvanceTask = async (
    task: IncidentTask,
    nextStatus: "assigned" | "accepted" | "in_progress" | "completed",
  ) => {
    if (!authToken) {
      return;
    }
    setTaskUpdatingId(task.id);
    try {
      const updated = await updateTask(task.id, { status: nextStatus }, authToken);
      upsertTask(updated);
    } catch (error: unknown) {
      appendMessage(createMessage("SYSTEM_ERROR", readErrorMessage(error, "任务流转失败"), "Error"));
    } finally {
      setTaskUpdatingId(null);
    }
  };

  const handleMarkNotificationReceipt = async (
    notificationId: string,
    status: "read" | "confirmed",
  ) => {
    if (!authToken) {
      return;
    }
    try {
      const result = await markNotificationReceipt({ notification_id: notificationId, status }, authToken);
      setNotificationReceiptSummaries((prev) => ({
        ...prev,
        [notificationId]: result.summary,
      }));
      setMyNotificationReceiptStatus((prev) => ({
        ...prev,
        [notificationId]: result.receipt.status === "confirmed" ? "confirmed" : "read",
      }));
    } catch (error: unknown) {
      appendMessage(createMessage("SYSTEM_ERROR", readErrorMessage(error, "通知回执提交失败"), "Error"));
    }
  };

  const commandWorkbench = (
    <div className="ui-panel flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border shadow-[var(--shadow-panel)]">
      <div className="border-b border-[var(--line-soft)] p-3">
        <PanelTabs value={activePanel} onChange={setActivePanel} />
      </div>

      <div className="min-h-0 flex-1 p-3">
        {activePanel === "terminal" && (
          <SectionFrame
            title="指挥终端"
            subtitle="任务流"
            actions={
              <span className="rounded-lg border border-[var(--line-soft)] px-2 py-1 text-[10px] text-[var(--text-secondary)]">
                {loading ? "执行中" : "就绪"}
              </span>
            }
            className="flex h-full min-h-0 flex-col overflow-hidden"
          >
            <div ref={scrollRef} className="ui-scrollbar min-h-0 flex-1 space-y-2 overflow-y-auto px-4 py-3">
              {history.length === 0 ? (
                <div className="flex h-full min-h-[180px] flex-col items-center justify-center gap-2 text-[var(--text-secondary)] opacity-70">
                  <Terminal size={24} />
                  <p className="text-xs">等待社区任务与震情流...</p>
                </div>
              ) : (
                history.map((msg) => (
                  <AgentMessage key={msg.id} source={msg.source} content={msg.content} type={msg.type} />
                ))
              )}
              {loading ? (
                <div className="rounded-lg border border-[rgba(200,165,106,0.3)] bg-[rgba(200,165,106,0.12)] px-3 py-2 text-xs text-[var(--accent-strong)]">
                  调度任务执行中...
                </div>
              ) : null}
            </div>

            <div className="space-y-3 border-t border-[var(--line-soft)] px-4 py-3">
              <form onSubmit={handleSubmitMission} className="relative">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="输入地震调度任务..."
                  className="ui-input ui-focus pr-20"
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="ui-btn ui-btn-primary ui-focus absolute right-1.5 top-1.5 px-3 py-1.5 text-[11px]"
                >
                  <span className="inline-flex items-center gap-1">
                    <Send size={12} />
                    发送
                  </span>
                </button>
              </form>

              <form onSubmit={handleSendCommunityAlert} className="space-y-2">
                <button
                  type="button"
                  onClick={handleOneClickWarning}
                  disabled={warningSending}
                  className="ui-btn ui-focus w-full border border-[rgba(201,123,115,0.45)] bg-[rgba(201,123,115,0.16)] px-3 py-2 text-[var(--danger)] transition hover:bg-[rgba(201,123,115,0.22)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {warningSending ? "一键预警发送中..." : "一键预警（全社区弹窗）"}
                </button>
                <input
                  value={alertTitle}
                  onChange={(e) => setAlertTitle(e.target.value)}
                  className="ui-input ui-focus"
                  placeholder="通知标题"
                />
                <textarea
                  value={alertContent}
                  onChange={(e) => setAlertContent(e.target.value)}
                  className="ui-input ui-focus min-h-20 resize-none"
                  placeholder="输入要广播给社区住户的避险通知"
                />
                <button
                  type="submit"
                  disabled={alertSending || !alertTitle.trim() || !alertContent.trim()}
                  className="ui-btn ui-btn-primary ui-focus w-full px-3 py-2"
                >
                  {alertSending ? "发送中..." : "广播社区通知"}
                </button>
              </form>

              <div className="ui-elevated rounded-xl border p-2">
                <p className="mb-2 text-[11px] tracking-[0.07em] text-[var(--text-secondary)]">最近通知</p>
                <div className="ui-scrollbar max-h-28 space-y-2 overflow-y-auto pr-1">
                  {latestNotifications.length === 0 ? (
                    <div className="rounded-lg border border-[var(--line-soft)] px-2 py-2 text-[11px] text-[var(--text-secondary)]">
                      暂无通知
                    </div>
                  ) : (
                    latestNotifications.map((item) => (
                      <div
                        key={item.id}
                        className="rounded-lg border border-[var(--line-soft)] bg-[rgba(255,255,255,0.02)] p-2"
                      >
                        <p className="mb-1 text-[11px] font-medium text-[var(--accent-strong)]">{item.title}</p>
                        <MarkdownDisplay
                          content={item.content}
                          compact
                          className="max-h-14 overflow-y-auto pr-1 text-[var(--text-secondary)]"
                        />
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </SectionFrame>
        )}

        {activePanel === "chat" && (
          <SectionFrame
            title="社区群聊"
            subtitle="实时沟通"
            actions={
              <span className="rounded-lg border border-[var(--line-soft)] px-2 py-1 text-[10px] text-[var(--text-secondary)]">
                {chatMessages.length} 条
              </span>
            }
            className="flex h-full min-h-0 flex-col overflow-hidden"
          >
            <div className="grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)_auto]">
              <div className="ui-scrollbar min-h-0 space-y-2 overflow-y-auto px-4 py-3">
                {chatMessages.length === 0 ? (
                  <div className="rounded-lg border border-[var(--line-soft)] px-3 py-2 text-xs text-[var(--text-secondary)]">
                    暂无群聊消息
                  </div>
                ) : (
                  chatMessages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`rounded-lg border p-2.5 ${
                        msg.role === "assistant"
                          ? "border-[rgba(200,165,106,0.35)] bg-[rgba(200,165,106,0.08)]"
                          : "border-[var(--line-soft)] bg-[rgba(255,255,255,0.02)]"
                      }`}
                    >
                      <div className="mb-1 flex items-center justify-between text-[10px]">
                        <span className="text-[var(--text-secondary)]">
                          {msg.role === "assistant" ? "社区AI助手" : msg.sender_name}
                        </span>
                        <span className="font-mono text-[var(--text-secondary)]">
                          {new Date(msg.created_at).toLocaleTimeString()}
                        </span>
                      </div>
                      <MarkdownDisplay
                        content={msg.content}
                        compact
                        className="max-h-40 overflow-y-auto pr-1 text-[var(--text-primary)]"
                      />
                    </div>
                  ))
                )}
              </div>

              <div className="space-y-3 border-t border-[var(--line-soft)] px-4 py-3">
                <form onSubmit={handleSendChat} className="space-y-2">
                  <textarea
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="输入社区群聊消息..."
                    className="ui-input ui-focus min-h-16 resize-none"
                  />
                  <div className="flex items-center justify-between gap-3">
                    <label className="inline-flex items-center gap-2 text-[11px] text-[var(--text-secondary)]">
                      <input
                        type="checkbox"
                        checked={chatAskAi}
                        onChange={(e) => setChatAskAi(e.target.checked)}
                        className="accent-[var(--accent-primary)]"
                      />
                      发送后让 AI 跟进
                    </label>
                    <button
                      type="submit"
                      disabled={chatSending || !chatInput.trim()}
                      className="ui-btn ui-btn-primary ui-focus px-3 py-1.5"
                    >
                      {chatSending ? "发送中" : "发送"}
                    </button>
                  </div>
                </form>

                <form onSubmit={handleAskAssistant} className="space-y-2 border-t border-[var(--line-soft)] pt-3">
                  <div className="inline-flex items-center gap-1 text-[11px] text-[var(--text-secondary)]">
                    <Bot size={12} />
                    单独提问社区 AI 助手
                  </div>
                  <input
                    value={assistantQuestion}
                    onChange={(e) => setAssistantQuestion(e.target.value)}
                    placeholder="例如：如何组织楼栋长进行夜间巡查？"
                    className="ui-input ui-focus"
                  />
                  <button
                    type="submit"
                    disabled={assistantLoading || !assistantQuestion.trim()}
                    className="ui-btn ui-btn-ghost ui-focus w-full px-3 py-2"
                  >
                    {assistantLoading ? "AI思考中..." : "提问 AI 助手"}
                  </button>
                </form>
              </div>
            </div>
          </SectionFrame>
        )}

        {activePanel === "rescue" && (
          <SectionFrame
            title="地震受灾搜救分析"
            subtitle="图像分析"
            actions={
              <span className="rounded-lg border border-[var(--line-soft)] px-2 py-1 text-[10px] text-[var(--text-secondary)]">
                {rescueAnalyses.length} 批
              </span>
            }
            className="flex h-full min-h-0 flex-col overflow-hidden"
          >
            <div className="ui-scrollbar min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3">
              <form onSubmit={handleRunEarthquakeRescue} className="space-y-2.5">
                <textarea
                  value={rescueDescription}
                  onChange={(e) => setRescueDescription(e.target.value)}
                  placeholder="地震现场描述（建筑受损、障碍物、可通行区域等）"
                  className="ui-input ui-focus min-h-20 resize-none"
                />

                <div className="grid grid-cols-2 gap-2">
                  <input
                    value={rescueLat}
                    onChange={(e) => setRescueLat(e.target.value)}
                    placeholder="纬度"
                    className="ui-input ui-focus"
                  />
                  <input
                    value={rescueLng}
                    onChange={(e) => setRescueLng(e.target.value)}
                    placeholder="经度"
                    className="ui-input ui-focus"
                  />
                </div>

                <label className="block text-[11px] text-[var(--text-secondary)]">
                  鸟瞰图（最多 6 张）
                  <input
                    type="file"
                    accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                    multiple
                    onChange={(e) => {
                      const files = Array.from(e.target.files ?? []);
                      setRescueImageFiles(files.slice(0, 6));
                    }}
                    className="mt-1 block w-full text-[11px] text-[var(--text-secondary)] file:mr-2 file:rounded-md file:border file:border-[var(--line-soft)] file:bg-[rgba(255,255,255,0.03)] file:px-2 file:py-1.5 file:text-[11px] file:text-[var(--text-primary)]"
                  />
                </label>

                {rescueError ? (
                  <div className="rounded-lg border border-[rgba(201,123,115,0.4)] bg-[rgba(201,123,115,0.1)] px-3 py-2 text-[11px] text-[var(--danger)]">
                    {rescueError}
                  </div>
                ) : null}

                <button
                  type="submit"
                  disabled={rescueLoading}
                  className="ui-btn ui-btn-danger ui-focus w-full px-3 py-2"
                >
                  {rescueLoading ? "分析中..." : "执行地震搜救分析"}
                </button>
              </form>

              {latestRescueAnalysis ? (
                <div className="rounded-xl border border-[var(--line-soft)] bg-[rgba(255,255,255,0.02)] p-3">
                  <MarkdownDisplay
                    content={buildRescueAnalysisMarkdown(latestRescueAnalysis)}
                    compact
                    className="text-[var(--text-primary)]"
                  />
                </div>
              ) : (
                <div className="rounded-lg border border-[var(--line-soft)] px-3 py-2 text-[11px] text-[var(--text-secondary)]">
                  暂无救援分析结果
                </div>
              )}
            </div>
          </SectionFrame>
        )}
      </div>
    </div>
  );

  if (!authReady) {
    return (
      <div className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)] flex items-center justify-center px-6">
        <div className="ui-panel rounded-2xl border px-6 py-4 text-sm text-[var(--text-secondary)] shadow-[var(--shadow-panel)] animate-pulse">
          正在同步社区工作台...
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <div className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)] px-6 py-12">
        <div className="mx-auto flex min-h-[84vh] w-full max-w-5xl items-center justify-center">
          <AuthCard mode={authMode} onModeChange={setAuthMode}>
            {authMode === "login" ? (
              <form className="grid grid-cols-1 gap-4 lg:grid-cols-2" onSubmit={handleLogin}>
                <div className="space-y-1.5 lg:col-span-2">
                  <label className="text-[11px] tracking-[0.08em] text-[var(--text-secondary)]">用户名</label>
                  <input
                    value={loginUsername}
                    onChange={(e) => setLoginUsername(e.target.value)}
                    placeholder="字母 / 数字 / 下划线"
                    className="ui-input ui-focus"
                  />
                </div>
                <div className="space-y-1.5 lg:col-span-2">
                  <label className="text-[11px] tracking-[0.08em] text-[var(--text-secondary)]">密码</label>
                  <input
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="输入密码"
                    type="password"
                    className="ui-input ui-focus"
                  />
                </div>
                <button
                  disabled={authLoading}
                  className="ui-btn ui-btn-primary ui-focus lg:col-span-2 px-4 py-2.5 text-sm"
                  type="submit"
                >
                  {authLoading ? "登录中..." : "进入社区指挥台"}
                </button>
              </form>
            ) : (
              <form className="grid grid-cols-1 gap-3 lg:grid-cols-2" onSubmit={handleRegister}>
                <div className="space-y-1.5">
                  <label className="text-[11px] tracking-[0.08em] text-[var(--text-secondary)]">用户名</label>
                  <input
                    value={registerUsername}
                    onChange={(e) => setRegisterUsername(e.target.value)}
                    placeholder="字母 / 数字 / 下划线"
                    className="ui-input ui-focus"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[11px] tracking-[0.08em] text-[var(--text-secondary)]">显示名称</label>
                  <input
                    value={registerDisplayName}
                    onChange={(e) => setRegisterDisplayName(e.target.value)}
                    placeholder="用于社区展示"
                    className="ui-input ui-focus"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[11px] tracking-[0.08em] text-[var(--text-secondary)]">密码</label>
                  <input
                    value={registerPassword}
                    onChange={(e) => setRegisterPassword(e.target.value)}
                    placeholder="至少 6 位"
                    type="password"
                    className="ui-input ui-focus"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[11px] tracking-[0.08em] text-[var(--text-secondary)]">行政区</label>
                  <input
                    value={registerCommunityDistrict}
                    onChange={(e) => setRegisterCommunityDistrict(e.target.value)}
                    placeholder="例如：高新区 / 浦东新区"
                    className="ui-input ui-focus"
                  />
                </div>
                <div className="space-y-1.5 lg:col-span-2">
                  <label className="text-[11px] tracking-[0.08em] text-[var(--text-secondary)]">社区名称</label>
                  <input
                    value={registerCommunityName}
                    onChange={(e) => setRegisterCommunityName(e.target.value)}
                    placeholder="会自动创建或加入"
                    className="ui-input ui-focus"
                  />
                </div>
                <button
                  disabled={authLoading}
                  className="ui-btn ui-btn-primary ui-focus lg:col-span-2 px-4 py-2.5 text-sm"
                  type="submit"
                >
                  {authLoading ? "注册中..." : "注册并进入指挥台"}
                </button>
              </form>
            )}

            {authError ? (
              <div className="mt-4 rounded-xl border border-[rgba(201,123,115,0.4)] bg-[rgba(201,123,115,0.12)] px-3 py-2 text-sm text-[var(--danger)]">
                {authError}
              </div>
            ) : null}
          </AuthCard>
        </div>
      </div>
    );
  }

  return (
    <CommandShell
      sidebar={
        <div className="ui-panel flex h-full w-full flex-col items-center rounded-2xl border py-4 shadow-[var(--shadow-panel)]">
          <div className="mb-6 flex h-10 w-10 items-center justify-center rounded-xl border border-[rgba(200,165,106,0.4)] bg-[rgba(200,165,106,0.14)] text-[var(--accent-strong)]">
            <Shield size={19} />
          </div>
          <nav className="flex flex-1 flex-col items-center gap-3">
            {[
              { id: "overview" as const, label: "总览", icon: Map },
              { id: "operations" as const, label: "调度", icon: Activity },
              { id: "community" as const, label: "社区", icon: BellRing },
            ].map((item) => {
              const active = workspaceView === item.id;
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => setWorkspaceView(item.id)}
                  className={`ui-focus inline-flex w-12 flex-col items-center gap-1 rounded-xl border p-2 transition ${
                    active
                      ? "border-[rgba(200,165,106,0.42)] bg-[rgba(200,165,106,0.14)] text-[var(--accent-strong)]"
                      : "border-transparent text-[var(--text-secondary)] hover:border-[var(--line-soft)] hover:bg-[rgba(255,255,255,0.04)] hover:text-[var(--text-primary)]"
                  }`}
                  type="button"
                >
                  <Icon size={16} />
                  <span className="text-[9px] tracking-[0.08em]">{item.label}</span>
                </button>
              );
            })}
          </nav>
          <div className="mt-3 text-[9px] font-semibold tracking-[0.18em] text-[var(--text-secondary)]">NG</div>
        </div>
      }
      header={
        <header className="ui-panel flex h-[72px] items-center justify-between rounded-2xl border px-5 shadow-[var(--shadow-panel)]">
          <div className="min-w-0 space-y-1">
            <h1 className="font-title truncate text-2xl leading-none tracking-[0.02em] text-[var(--text-primary)]">
              NebulaGuard 地震指挥系统
            </h1>
            <p className="truncate text-[11px] tracking-[0.08em] text-[var(--text-secondary)]">
              COMMUNITY {currentUser.community?.name ?? "未加入社区"} · {workspaceTitle} · COMMAND CENTER
            </p>
          </div>
          <div className="ml-4 flex items-center gap-2.5">
            <div className="ui-elevated inline-flex items-center gap-2 rounded-lg border px-2.5 py-1 text-[11px] text-[var(--text-secondary)]">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  connection === "connected"
                    ? "bg-[var(--success)]"
                    : connection === "connecting"
                    ? "bg-[var(--warning)]"
                    : "bg-[var(--danger)]"
                }`}
              />
              {connection === "connected" ? "在线" : connection === "connecting" ? "连接中" : "离线"}
            </div>
            <span className="hidden text-xs text-[var(--text-secondary)] md:inline">{currentUser.display_name}</span>
            <button
              className="ui-btn ui-btn-ghost ui-focus px-3 py-1.5 text-[11px]"
              onClick={handleLogout}
              type="button"
            >
              退出
            </button>
          </div>
        </header>
      }
      main={
        <div className="flex min-h-full flex-col gap-4 pb-4">
          <section className="ui-panel flex items-center justify-between rounded-2xl border px-4 py-2.5 shadow-[var(--shadow-panel)]">
            <div>
              <p className="text-[11px] tracking-[0.08em] text-[var(--text-secondary)]">当前工作区</p>
              <p className="font-title text-base text-[var(--text-primary)]">{workspaceTitle}</p>
            </div>
          </section>

          {workspaceView === "overview" && (
            <section className="ui-panel relative min-h-[820px] overflow-hidden rounded-2xl border shadow-[var(--shadow-panel)]">
              <div className="absolute inset-0">
                <DisasterMap
                  markers={mapMarkers}
                  centerLat={mapCenterLat}
                  centerLng={mapCenterLng}
                  initialZoom={16.2}
                  minZoom={14.8}
                />
              </div>
              <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(15,17,20,0.1),rgba(15,17,20,0.32))]" />
              <div className="pointer-events-none absolute left-4 right-4 top-4 z-10 flex items-start justify-between gap-4">
                <div className="ui-elevated rounded-xl border px-3 py-2">
                  <p className="text-[11px] tracking-[0.08em] text-[var(--text-secondary)]">态势总览</p>
                  <p className="font-title mt-1 text-lg tracking-[0.02em] text-[var(--text-primary)]">
                    地震与社区协同指挥
                  </p>
                </div>
                <div className="ui-elevated rounded-xl border px-3 py-2 font-mono text-[11px] text-[var(--text-secondary)]">
                  LAT {mapCenterLat.toFixed(4)} | LNG {mapCenterLng.toFixed(4)}
                </div>
              </div>
            </section>
          )}

          {workspaceView === "operations" && (
            <div className="grid gap-4 xl:grid-cols-[1.05fr_1.35fr]">
              <IncidentBoard
                incidents={incidents}
                creating={incidentCreating}
                updatingId={incidentUpdatingId}
                onCreate={handleCreateIncident}
                onUpdateStatus={handleUpdateIncidentStatus}
              />
              <div className="grid gap-4">
                <TaskKanban
                  incidents={incidents}
                  teams={teams}
                  tasks={tasks}
                  creating={taskCreating}
                  updatingId={taskUpdatingId}
                  onCreate={handleCreateTask}
                  onAdvance={handleAdvanceTask}
                />
                <SectionFrame
                  title="Agent 执行轨迹"
                  className="min-h-0"
                >
                  <div className="ui-scrollbar max-h-52 space-y-2 overflow-y-auto p-4">
                    {dispatchAgentRuns.length === 0 ? (
                      <div className="rounded-lg border border-[var(--line-soft)] px-3 py-2 text-xs text-[var(--text-secondary)]">
                        暂无自动调度执行记录
                      </div>
                    ) : (
                      dispatchAgentRuns.slice(-12).reverse().map((run) => {
                        const execution = run.execution && typeof run.execution === "object" ? run.execution : {};
                        const incidentsCreated = Array.isArray(
                          (execution as { incident?: { created?: unknown[] } }).incident?.created,
                        )
                          ? ((execution as { incident?: { created?: unknown[] } }).incident?.created?.length ?? 0)
                          : 0;
                        const tasksCreated = Array.isArray(
                          (execution as { tasks?: { created?: unknown[] } }).tasks?.created,
                        )
                          ? ((execution as { tasks?: { created?: unknown[] } }).tasks?.created?.length ?? 0)
                          : 0;
                        const dispatchCreated = Array.isArray(
                          (execution as { dispatches?: { created?: unknown[] } }).dispatches?.created,
                        )
                          ? ((execution as { dispatches?: { created?: unknown[] } }).dispatches?.created?.length ?? 0)
                          : 0;
                        return (
                          <article
                            key={run.id}
                            className="rounded-xl border border-[var(--line-soft)] bg-[rgba(255,255,255,0.015)] p-3"
                          >
                            <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
                              <span>{run.trigger_source}</span>
                              <span>{new Date(run.created_at).toLocaleString()}</span>
                            </div>
                            <p className="mt-1 text-xs text-[var(--text-primary)]">
                              状态 {run.status} · 事件 +{incidentsCreated} · 任务 +{tasksCreated} · 调度 +{dispatchCreated}
                            </p>
                            {run.error ? <p className="mt-1 text-xs text-[var(--warning)]">{run.error}</p> : null}
                          </article>
                        );
                      })
                    )}
                  </div>
                </SectionFrame>
              </div>
            </div>
          )}

          {workspaceView === "community" && (
            <div className="grid gap-4 xl:grid-cols-[1.06fr_1.34fr]">
              <SectionFrame title="社区通知与回执" className="min-h-0 overflow-hidden">
                <div className="ui-scrollbar max-h-[62vh] space-y-2 overflow-y-auto p-4">
                  {latestNotifications.length === 0 ? (
                    <div className="rounded-lg border border-[var(--line-soft)] px-3 py-2 text-xs text-[var(--text-secondary)]">
                      暂无通知
                    </div>
                  ) : (
                    latestNotifications.map((item) => (
                      <article key={item.id} className="rounded-xl border border-[var(--line-soft)] p-3">
                        {(() => {
                          const summaryData = notificationReceiptSummaries[item.id];
                          const receiptStatus = myNotificationReceiptStatus[item.id];
                          const readDone = receiptStatus === "read" || receiptStatus === "confirmed";
                          const confirmedDone = receiptStatus === "confirmed";
                          return (
                            <>
                              <div className="mb-1.5 flex items-center justify-between gap-2">
                                <div className="inline-flex items-center gap-1 text-[10px] text-[var(--text-secondary)]">
                                  <span className="rounded border border-[var(--line-soft)] px-1.5 py-0.5">
                                    已读 {summaryData?.by_status.read ?? 0}
                                  </span>
                                  <span className="rounded border border-[var(--line-soft)] px-1.5 py-0.5">
                                    确认 {summaryData?.by_status.confirmed ?? 0}
                                  </span>
                                </div>
                                <span
                                  className={`rounded border px-1.5 py-0.5 text-[10px] ${
                                    confirmedDone
                                      ? "border-[rgba(111,191,143,0.35)] text-[var(--success)]"
                                      : readDone
                                        ? "border-[rgba(217,165,96,0.35)] text-[var(--warning)]"
                                        : "border-[var(--line-soft)] text-[var(--text-secondary)]"
                                  }`}
                                >
                                  {confirmedDone ? "已确认" : readDone ? "已读" : "未回执"}
                                </span>
                              </div>
                              <div className="mb-1 flex items-center justify-between gap-2">
                                <p className="text-sm font-medium text-[var(--accent-strong)]">{item.title}</p>
                                <span className="font-mono text-[10px] text-[var(--text-secondary)]">
                                  {new Date(item.created_at).toLocaleTimeString()}
                                </span>
                              </div>
                              <MarkdownDisplay content={item.content} compact className="text-[var(--text-primary)]" />
                              <div className="mt-2 flex gap-2">
                                <button
                                  type="button"
                                  disabled={readDone}
                                  onClick={() => void handleMarkNotificationReceipt(item.id, "read")}
                                  className="ui-btn ui-btn-ghost ui-focus px-2.5 py-1 text-[11px] disabled:opacity-55"
                                >
                                  {readDone ? "已读" : "标记已读"}
                                </button>
                                <button
                                  type="button"
                                  disabled={confirmedDone}
                                  onClick={() => void handleMarkNotificationReceipt(item.id, "confirmed")}
                                  className="ui-btn ui-btn-primary ui-focus px-2.5 py-1 text-[11px] disabled:opacity-55"
                                >
                                  {confirmedDone ? "已确认" : "确认执行"}
                                </button>
                              </div>
                            </>
                          );
                        })()}
                      </article>
                    ))
                  )}
                </div>
              </SectionFrame>

              <SectionFrame title="社区群聊摘录" className="min-h-0 overflow-hidden">
                <div className="ui-scrollbar max-h-[62vh] space-y-2 overflow-y-auto p-4">
                  {chatMessages.length === 0 ? (
                    <div className="rounded-lg border border-[var(--line-soft)] px-3 py-2 text-xs text-[var(--text-secondary)]">
                      暂无群聊记录
                    </div>
                  ) : (
                    chatMessages.slice(-30).reverse().map((msg) => (
                      <div
                        key={msg.id}
                        className={`rounded-lg border p-2.5 ${
                          msg.role === "assistant"
                            ? "border-[rgba(200,165,106,0.35)] bg-[rgba(200,165,106,0.08)]"
                            : "border-[var(--line-soft)] bg-[rgba(255,255,255,0.02)]"
                        }`}
                      >
                        <div className="mb-1 flex items-center justify-between text-[10px] text-[var(--text-secondary)]">
                          <span>{msg.role === "assistant" ? "社区AI助手" : msg.sender_name}</span>
                          <span className="font-mono">{new Date(msg.created_at).toLocaleTimeString()}</span>
                        </div>
                        <MarkdownDisplay content={msg.content} compact className="text-[var(--text-primary)]" />
                      </div>
                    ))
                  )}
                </div>
              </SectionFrame>
            </div>
          )}
        </div>
      }
      aside={
        <div className="ui-scrollbar flex flex-col gap-4 lg:sticky lg:top-5 lg:max-h-[calc(100vh-2.5rem)] lg:overflow-y-auto lg:pr-1">
          {(workspaceView === "overview" || workspaceView === "operations") && (
            <div className="shrink-0">
              <AutoDispatchPanel runs={dispatchAgentRuns} />
            </div>
          )}
          {workspaceView === "overview" && (
            <>
              <section className="grid shrink-0 grid-cols-1 gap-3">
                <MetricCard
                  label="累计地震上报"
                  value={summary.total_reports}
                  tone="primary"
                  hint="社区上报总量"
                />
                <MetricCard
                  label="事件总数"
                  value={summary.total_incidents ?? incidents.length}
                  tone="warning"
                  hint="事件闭环池"
                />
                <MetricCard
                  label="活跃任务"
                  value={summary.active_tasks ?? tasks.filter((item) => item.status !== "completed").length}
                  tone="danger"
                  hint="工单推进中"
                />
                <MetricCard
                  label="居民待救援"
                  value={summary.residents_need_help ?? checkinSummary.by_status.need_help ?? 0}
                  tone="danger"
                  hint="来源于报平安回执"
                />
              </section>
              <SectionFrame title="调度动态" className="shrink-0 min-h-0 overflow-hidden">
                <div className="ui-scrollbar max-h-[280px] space-y-2 overflow-y-auto p-3">
                  {dispatchAgentRuns.length === 0 ? (
                    <div className="rounded-lg border border-[var(--line-soft)] px-3 py-2 text-xs text-[var(--text-secondary)]">
                      暂无记录
                    </div>
                  ) : (
                    dispatchAgentRuns.slice(-10).reverse().map((run) => {
                      const execution = run.execution && typeof run.execution === "object" ? run.execution : {};
                      const tasksCreated = Array.isArray(
                        (execution as { tasks?: { created?: unknown[] } }).tasks?.created,
                      )
                        ? ((execution as { tasks?: { created?: unknown[] } }).tasks?.created?.length ?? 0)
                        : 0;
                      const dispatchCreated = Array.isArray(
                        (execution as { dispatches?: { created?: unknown[] } }).dispatches?.created,
                      )
                        ? ((execution as { dispatches?: { created?: unknown[] } }).dispatches?.created?.length ?? 0)
                        : 0;
                      return (
                        <article
                          key={run.id}
                          className="rounded-xl border border-[var(--line-soft)] bg-[rgba(255,255,255,0.015)] p-3"
                        >
                          <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
                            <span>{run.status}</span>
                            <span className="font-mono">{new Date(run.created_at).toLocaleTimeString()}</span>
                          </div>
                          <p className="mt-1 text-xs text-[var(--text-primary)]">
                            任务 +{tasksCreated} · 调度 +{dispatchCreated}
                          </p>
                        </article>
                      );
                    })
                  )}
                </div>
              </SectionFrame>
              <SectionFrame title="现场时间轴" className="shrink-0 min-h-0 overflow-hidden">
                <div className="ui-scrollbar max-h-[280px] space-y-2 overflow-y-auto p-3">
                  {timelineEvents.length === 0 ? (
                    <div className="rounded-lg border border-[var(--line-soft)] px-3 py-2 text-xs text-[var(--text-secondary)]">
                      暂无事件
                    </div>
                  ) : (
                    timelineEvents.slice(-8).reverse().map((event) => (
                      <article
                        key={event.id}
                        className="rounded-xl border border-[var(--line-soft)] bg-[rgba(255,255,255,0.015)] p-3"
                      >
                        <div className="flex items-center justify-between gap-2 text-[10px] text-[var(--text-secondary)]">
                          <span className="truncate">{event.event_type}</span>
                          <span className="font-mono">{new Date(event.created_at).toLocaleTimeString()}</span>
                        </div>
                        <p className="mt-1 text-xs text-[var(--text-primary)]">{event.title}</p>
                      </article>
                    ))
                  )}
                </div>
              </SectionFrame>
            </>
          )}
          {workspaceView === "operations" && (
            <div className="shrink-0 lg:h-[46vh] lg:min-h-[360px]">
              <TimelineRail events={timelineEvents} />
            </div>
          )}
          {workspaceView === "community" && (
            <div className="shrink-0">
              <ReadReceiptPanel
                notifications={notifications}
                receiptSummaries={notificationReceiptSummaries}
                myReceiptStatus={myNotificationReceiptStatus}
                onMarkRead={(notificationId) => handleMarkNotificationReceipt(notificationId, "read")}
                onMarkConfirmed={(notificationId) => handleMarkNotificationReceipt(notificationId, "confirmed")}
              />
            </div>
          )}
          <div className="lg:hidden">{commandWorkbench}</div>
        </div>
      }
      overlay={
        <div className="hidden lg:block">
          {!drawerOpen ? (
            <div
              className="fixed right-0 top-1/2 z-40 h-56 w-6 -translate-y-1/2 cursor-ew-resize rounded-l-md border border-r-0 border-[var(--line-soft)] bg-[rgba(26,31,39,0.96)]"
              onMouseEnter={openDrawer}
            />
          ) : null}
          <div
            className={`fixed right-3 top-1/2 z-50 h-[88vh] w-[620px] max-w-[calc(100vw-1rem)] -translate-y-1/2 transition-transform duration-300 ${
              drawerOpen ? "translate-x-0" : "translate-x-[680px]"
            }`}
            onMouseEnter={openDrawer}
            onMouseLeave={scheduleDrawerClose}
          >
            <button
              type="button"
              className="ui-btn ui-btn-ghost ui-focus absolute -left-9 top-4 z-10 rounded-l-lg rounded-r-none border-r-0 px-2 py-1 text-[10px]"
              onClick={() => {
                setDrawerPinned((prev) => {
                  const next = !prev;
                  if (!next) {
                    scheduleDrawerClose();
                  } else {
                    openDrawer();
                  }
                  return next;
                });
              }}
              onMouseEnter={openDrawer}
            >
              {drawerPinned ? "固定" : "展开"}
            </button>
            {commandWorkbench}
          </div>
        </div>
      }
    />
  );
}
