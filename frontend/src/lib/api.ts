import axios from "axios";

import { getBackendHttpBase } from "@/lib/runtime-config";

let volatileAuthToken = "";

const api = axios.create({
  baseURL: getBackendHttpBase(),
  timeout: 15000,
});

export interface CommunityInfo {
  id: string;
  name: string;
  district: string;
  base_lat: number;
  base_lng: number;
  role?: string;
}

export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
  created_at?: string;
  community?: CommunityInfo | null;
}

export interface AuthResponse {
  status: string;
  token: string;
  user: AuthUser;
}

export interface FieldReport {
  id: string;
  user_id: string;
  community_id: string;
  lat: number;
  lng: number;
  category: "earthquake";
  felt_level: number;
  building_type: string;
  structure_notes: string;
  description: string;
  image_url?: string | null;
  vlm_advice?: string[];
  created_at: string;
}

export interface SystemSummary {
  total_reports: number;
  active_missions: number;
  report_counts: Record<string, number>;
  latest_report?: FieldReport | null;
  total_incidents?: number;
  active_tasks?: number;
  residents_need_help?: number;
}

export interface CommunityNotification {
  id: string;
  community_id: string;
  sender_user_id?: string | null;
  sender_name?: string | null;
  title: string;
  content: string;
  payload?: Record<string, unknown>;
  created_at: string;
}

export interface NotificationReceiptSummary {
  community_id: string;
  notification_id: string;
  by_status: Record<string, number>;
  total: number;
}

export interface NotificationReceiptRecord {
  id: string;
  notification_id: string;
  community_id: string;
  user_id: string;
  status: "read" | "confirmed" | string;
  created_at: string;
  updated_at: string;
}

export interface CommunityChatMessage {
  id: string;
  community_id: string;
  sender_user_id?: string | null;
  sender_name: string;
  role: "user" | "assistant" | "system" | string;
  content: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface EarthquakeVictimDetection {
  id: string;
  bbox_norm: number[];
  confidence: number;
  condition: string;
  position_hint: string;
  priority: number;
}

export interface EarthquakeRescueVictim {
  id: string;
  position_hint: string;
  risk_level: string;
  priority: number;
  evidence: string;
  condition?: string;
  image_name?: string;
  image_url?: string;
  annotated_image_url?: string;
  bbox_norm?: number[];
  confidence?: number;
  priority_score?: number;
  bbox_area?: number;
}

export interface EarthquakeRescueRoute {
  name: string;
  steps: string[];
  risk: string;
  recommended_team: string;
  route_type?: "search" | "rescue" | string;
}

export interface EarthquakeImageFinding {
  image_name: string;
  original_image_url?: string;
  annotated_image_url?: string;
  detections?: EarthquakeVictimDetection[];
  detected_people: number;
}

export interface EarthquakeHotspot {
  id: string;
  center_norm: number[];
  victim_ids: string[];
  intensity: number;
  level: "high" | "medium" | "low" | string;
}

export interface EarthquakeAlgorithmMetrics {
  rescue_complexity_index: number;
  coverage_score: number;
  avg_priority_score?: number;
  victim_dispersion?: number;
  hotspots?: EarthquakeHotspot[];
  priority_model?: string;
}

export interface EarthquakeRescueAnalysisPayload {
  scene_overview?: string;
  victims?: EarthquakeRescueVictim[];
  routes?: EarthquakeRescueRoute[];
  command_notes?: string[];
  image_findings?: EarthquakeImageFinding[];
  algorithm_metrics?: EarthquakeAlgorithmMetrics;
}

export interface DispatchAgentRunSummary {
  id: string;
  community_id: string;
  analysis_id: string;
  trigger_source: string;
  idempotency_key: string;
  status: string;
  error?: string | null;
  created_at: string;
  input?: Record<string, unknown>;
  plan?: Record<string, unknown>;
  execution?: Record<string, unknown>;
}

export interface EarthquakeRescueAnalysisRecord {
  id: string;
  community_id: string;
  requester_user_id: string;
  description: string;
  lat?: number | null;
  lng?: number | null;
  image_urls?: string[];
  analysis?: EarthquakeRescueAnalysisPayload;
  status: string;
  created_at: string;
}

/** @deprecated use EarthquakeRescue* types */
export type FireRescueVictim = EarthquakeRescueVictim;
/** @deprecated use EarthquakeRescue* types */
export type FireRescueRoute = EarthquakeRescueRoute;
/** @deprecated use EarthquakeRescue* types */
export type FireRescueDetectionSummary = EarthquakeImageFinding;
/** @deprecated use EarthquakeRescue* types */
export type FireRescueAnalysisPayload = EarthquakeRescueAnalysisPayload;
/** @deprecated use EarthquakeRescue* types */
export type FireRescueAnalysisRecord = EarthquakeRescueAnalysisRecord;

export interface Incident {
  id: string;
  community_id: string;
  created_by_user_id: string;
  created_by_name?: string;
  title: string;
  description: string;
  lat?: number | null;
  lng?: number | null;
  priority: "low" | "medium" | "high" | "critical" | string;
  status: "new" | "verified" | "responding" | "stabilized" | "closed" | string;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface IncidentTask {
  id: string;
  incident_id: string;
  community_id: string;
  title: string;
  description: string;
  status: "new" | "assigned" | "accepted" | "in_progress" | "blocked" | "completed" | string;
  priority: "low" | "medium" | "high" | "critical" | string;
  assignee_user_id?: string | null;
  assignee_name?: string | null;
  team_id?: string | null;
  team_name?: string | null;
  due_at?: string | null;
  accepted_at?: string | null;
  completed_at?: string | null;
  created_by_user_id: string;
  created_by_name?: string | null;
  created_at: string;
  updated_at: string;
}

export interface OpsTimelineEvent {
  id: string;
  community_id: string;
  event_type: string;
  title: string;
  content: string;
  entity_type?: string | null;
  entity_id?: string | null;
  payload?: Record<string, unknown>;
  created_by_user_id?: string | null;
  created_at: string;
}

export interface ResponseTeam {
  id: string;
  community_id: string;
  name: string;
  specialty: string;
  status: "standby" | "deployed" | "offline" | string;
  leader_user_id?: string | null;
  leader_name?: string | null;
  contact?: string | null;
  base_lat?: number | null;
  base_lng?: number | null;
  base_location_text?: string | null;
  equipment?: string[];
  vehicles?: string[];
  personnel_count?: number;
  capacity?: number;
  availability_score?: number;
  last_active_at?: string | null;
  member_count?: number;
  created_at: string;
  updated_at: string;
}

export interface ResidentCheckinSummary {
  community_id: string;
  total: number;
  by_status: Record<string, number>;
  latest_checkin_at?: string | null;
}

export interface Shelter {
  id: string;
  community_id: string;
  name: string;
  address: string;
  lat?: number | null;
  lng?: number | null;
  capacity: number;
  current_occupancy: number;
  status: "open" | "limited" | "full" | "closed" | string;
  created_at: string;
  updated_at: string;
}

export interface NotificationTemplate {
  id: string;
  community_id: string;
  name: string;
  level: "info" | "warning" | "danger" | string;
  title_template: string;
  content_template: string;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
}

function authHeaders(token?: string): Record<string, string> {
  const current = token || getAuthToken();
  if (!current) {
    return {};
  }
  return { Authorization: `Bearer ${current}` };
}

export function saveAuthToken(token: string): void {
  volatileAuthToken = token.trim();
}

export function getAuthToken(): string {
  return volatileAuthToken;
}

export function clearAuthToken(): void {
  volatileAuthToken = "";
}

export async function registerUser(input: {
  username: string;
  display_name: string;
  password: string;
  community_name: string;
  community_district?: string;
}): Promise<AuthResponse> {
  const resp = await api.post<AuthResponse>("/auth/register", input);
  return resp.data;
}

export async function loginUser(input: {
  username: string;
  password: string;
}): Promise<AuthResponse> {
  const resp = await api.post<AuthResponse>("/auth/login", input);
  return resp.data;
}

export async function fetchMe(token?: string): Promise<AuthUser> {
  const resp = await api.get<{ status: string; user: AuthUser }>("/auth/me", {
    headers: authHeaders(token),
  });
  return resp.data.user;
}

export async function fetchRecentReports(limit = 50, token?: string): Promise<FieldReport[]> {
  const resp = await api.get<{ count: number; items: FieldReport[] }>("/reports/recent", {
    params: { limit },
    headers: authHeaders(token),
  });
  return resp.data.items;
}

export async function fetchSystemSummary(token?: string): Promise<SystemSummary> {
  const resp = await api.get<SystemSummary>("/system/summary", {
    headers: authHeaders(token),
  });
  return resp.data;
}

export async function requestRouteAdvice(
  input: {
    lat: number;
    lng: number;
    type?: string;
    description?: string;
    felt_level?: number;
    building_type?: string;
    structure_notes?: string;
  },
  token?: string,
): Promise<string[]> {
  const resp = await api.post<{ advice?: string[]; advice_text?: string }>("/ai/route_advice", input, {
    headers: authHeaders(token),
  });
  if (Array.isArray(resp.data.advice) && resp.data.advice.length > 0) {
    return resp.data.advice;
  }
  if (resp.data.advice_text?.trim()) {
    return [resp.data.advice_text.trim()];
  }
  return [];
}

export async function submitMission(description: string, token?: string): Promise<void> {
  await api.post(
    "/mission/start",
    { description },
    {
      headers: authHeaders(token),
    },
  );
}

export async function submitEarthquakeReportWithMedia(
  formData: FormData,
  token?: string,
): Promise<{
  status: string;
  report: FieldReport;
  shelter_advice: string[];
  analysis_status: string;
}> {
  const resp = await api.post("/report/earthquake_with_media", formData, {
    headers: {
      ...authHeaders(token),
      "Content-Type": "multipart/form-data",
    },
  });
  return resp.data;
}

export async function submitEarthquakeReport(
  payload: {
    lat: number;
    lng: number;
    felt_level: number;
    building_type: string;
    structure_notes?: string;
    description?: string;
  },
  token?: string,
): Promise<{
  status: string;
  report: FieldReport;
  shelter_advice: string[];
  analysis_status: string;
}> {
  const resp = await api.post("/report/earthquake", payload, {
    headers: authHeaders(token),
  });
  return resp.data;
}

export async function fetchCommunityNotifications(
  limit = 50,
  token?: string,
): Promise<CommunityNotification[]> {
  const resp = await api.get<{ count: number; items: CommunityNotification[] }>(
    "/community/notifications",
    {
      params: { limit },
      headers: authHeaders(token),
    },
  );
  return resp.data.items;
}

export async function sendCommunityAlert(
  payload: { title: string; content: string },
  token?: string,
): Promise<CommunityNotification> {
  const resp = await api.post<{ status: string; notification: CommunityNotification }>(
    "/community/alerts",
    payload,
    {
      headers: authHeaders(token),
    },
  );
  return resp.data.notification;
}

export async function sendOneClickWarning(
  payload?: { title?: string; content?: string },
  token?: string,
): Promise<CommunityNotification> {
  const resp = await api.post<{ status: string; notification: CommunityNotification }>(
    "/community/alerts/one-click-warning",
    payload ?? {},
    {
      headers: authHeaders(token),
    },
  );
  return resp.data.notification;
}

export async function fetchCommunityChatMessages(
  limit = 100,
  token?: string,
): Promise<CommunityChatMessage[]> {
  const resp = await api.get<{ count: number; items: CommunityChatMessage[] }>(
    "/community/chat/messages",
    {
      params: { limit },
      headers: authHeaders(token),
    },
  );
  return resp.data.items;
}

export async function sendCommunityChatMessage(
  payload: { content: string; ask_ai?: boolean },
  token?: string,
): Promise<{
  status: string;
  message: CommunityChatMessage;
  assistant_message?: CommunityChatMessage | null;
}> {
  const resp = await api.post(
    "/community/chat/send",
    payload,
    {
      headers: authHeaders(token),
    },
  );
  return resp.data;
}

export async function askCommunityAssistant(
  question: string,
  token?: string,
): Promise<{
  status: string;
  user_message: CommunityChatMessage;
  assistant_message: CommunityChatMessage;
  assistant_status: string;
}> {
  const resp = await api.post(
    "/community/assistant/ask",
    { question },
    {
      headers: authHeaders(token),
    },
  );
  return resp.data;
}

export async function submitEarthquakeRescueAnalysis(
  formData: FormData,
  token?: string,
): Promise<{
  status: string;
  analysis_status: string;
  analysis_error?: string | null;
  result: EarthquakeRescueAnalysisRecord;
  dispatch_agent_run?: DispatchAgentRunSummary;
  deprecated_endpoint?: boolean;
}> {
  const resp = await api.post("/rescue/earthquake/analyze", formData, {
    headers: {
      ...authHeaders(token),
      "Content-Type": "multipart/form-data",
    },
    timeout: 120000,
  });
  return resp.data;
}

export async function fetchEarthquakeRescueAnalyses(
  limit = 20,
  token?: string,
): Promise<EarthquakeRescueAnalysisRecord[]> {
  const resp = await api.get<{ count: number; items: EarthquakeRescueAnalysisRecord[] }>(
    "/rescue/earthquake/analyses",
    {
      params: { limit },
      headers: authHeaders(token),
    },
  );
  return resp.data.items;
}

export async function fetchDispatchAgentRuns(
  limit = 20,
  token?: string,
): Promise<DispatchAgentRunSummary[]> {
  const resp = await api.get<{ count: number; items: DispatchAgentRunSummary[] }>(
    "/dispatch-agent/runs",
    {
      params: { limit },
      headers: authHeaders(token),
    },
  );
  return resp.data.items;
}

/** @deprecated use submitEarthquakeRescueAnalysis */
export async function submitFireRescueAnalysis(
  formData: FormData,
  token?: string,
) {
  return submitEarthquakeRescueAnalysis(formData, token);
}

/** @deprecated use fetchEarthquakeRescueAnalyses */
export async function fetchFireRescueAnalyses(
  limit = 20,
  token?: string,
) {
  return fetchEarthquakeRescueAnalyses(limit, token);
}

export async function createIncident(
  payload: {
    title: string;
    description?: string;
    lat?: number;
    lng?: number;
    priority?: "low" | "medium" | "high" | "critical";
    source?: string;
  },
  token?: string,
): Promise<Incident> {
  const resp = await api.post<{ status: string; incident: Incident }>(
    "/incidents",
    payload,
    { headers: authHeaders(token) },
  );
  return resp.data.incident;
}

export async function fetchIncidents(
  limit = 80,
  token?: string,
  status?: string,
): Promise<Incident[]> {
  const resp = await api.get<{ count: number; items: Incident[] }>("/incidents", {
    params: { limit, status },
    headers: authHeaders(token),
  });
  return resp.data.items;
}

export async function updateIncident(
  incidentId: string,
  payload: {
    title?: string;
    description?: string;
    lat?: number;
    lng?: number;
    priority?: "low" | "medium" | "high" | "critical";
    status?: "new" | "verified" | "responding" | "stabilized" | "closed";
  },
  token?: string,
): Promise<Incident> {
  const resp = await api.patch<{ status: string; incident: Incident }>(
    `/incidents/${incidentId}`,
    payload,
    { headers: authHeaders(token) },
  );
  return resp.data.incident;
}

export async function createIncidentTask(
  incidentId: string,
  payload: {
    title: string;
    description?: string;
    status?: "new" | "assigned" | "accepted" | "in_progress" | "blocked" | "completed";
    priority?: "low" | "medium" | "high" | "critical";
    assignee_user_id?: string;
    team_id?: string;
    due_at?: string;
  },
  token?: string,
): Promise<IncidentTask> {
  const resp = await api.post<{ status: string; task: IncidentTask }>(
    `/incidents/${incidentId}/tasks`,
    payload,
    { headers: authHeaders(token) },
  );
  return resp.data.task;
}

export async function fetchTasks(
  limit = 150,
  token?: string,
  status?: string,
): Promise<IncidentTask[]> {
  const resp = await api.get<{ count: number; items: IncidentTask[] }>("/tasks", {
    params: { limit, status },
    headers: authHeaders(token),
  });
  return resp.data.items;
}

export async function updateTask(
  taskId: string,
  payload: {
    title?: string;
    description?: string;
    status?: "new" | "assigned" | "accepted" | "in_progress" | "blocked" | "completed";
    priority?: "low" | "medium" | "high" | "critical";
    assignee_user_id?: string;
    team_id?: string;
    due_at?: string;
  },
  token?: string,
): Promise<IncidentTask> {
  const resp = await api.patch<{ status: string; task: IncidentTask }>(
    `/tasks/${taskId}`,
    payload,
    { headers: authHeaders(token) },
  );
  return resp.data.task;
}

export async function createTeam(
  payload: {
    name: string;
    specialty: string;
    status?: "standby" | "deployed" | "offline";
    leader_user_id?: string;
    contact?: string;
    base_lat?: number;
    base_lng?: number;
    base_location_text?: string;
    equipment?: string[];
    vehicles?: string[];
    personnel_count?: number;
    capacity?: number;
    availability_score?: number;
    member_user_ids?: string[];
  },
  token?: string,
): Promise<ResponseTeam> {
  const resp = await api.post<{ status: string; team: ResponseTeam }>(
    "/teams",
    payload,
    { headers: authHeaders(token) },
  );
  return resp.data.team;
}

export async function fetchTeams(
  limit = 120,
  token?: string,
): Promise<ResponseTeam[]> {
  const resp = await api.get<{ count: number; items: ResponseTeam[] }>("/teams", {
    params: { limit },
    headers: authHeaders(token),
  });
  return resp.data.items;
}

export async function createResidentCheckin(
  payload: {
    incident_id?: string;
    subject_name: string;
    relation?: "self" | "family" | "neighbor" | "other";
    status?: "safe" | "need_help" | "missing_proxy";
    lat?: number;
    lng?: number;
    notes?: string;
  },
  token?: string,
): Promise<Record<string, unknown>> {
  const resp = await api.post<{ status: string; checkin: Record<string, unknown> }>(
    "/residents/checkins",
    payload,
    { headers: authHeaders(token) },
  );
  return resp.data.checkin;
}

export async function fetchResidentCheckinSummary(token?: string): Promise<ResidentCheckinSummary> {
  const resp = await api.get<ResidentCheckinSummary>("/residents/checkins/summary", {
    headers: authHeaders(token),
  });
  return resp.data;
}

export async function createShelter(
  payload: {
    name: string;
    address: string;
    lat?: number;
    lng?: number;
    capacity: number;
    current_occupancy?: number;
    status?: "open" | "limited" | "full" | "closed";
  },
  token?: string,
): Promise<Shelter> {
  const resp = await api.post<{ status: string; shelter: Shelter }>("/shelters", payload, {
    headers: authHeaders(token),
  });
  return resp.data.shelter;
}

export async function fetchShelters(limit = 120, token?: string): Promise<Shelter[]> {
  const resp = await api.get<{ count: number; items: Shelter[] }>("/shelters", {
    params: { limit },
    headers: authHeaders(token),
  });
  return resp.data.items;
}

export async function updateShelterOccupancy(
  shelterId: string,
  payload: {
    delta?: number;
    absolute_occupancy?: number;
    status?: "open" | "limited" | "full" | "closed";
    reason?: string;
  },
  token?: string,
): Promise<Shelter> {
  const resp = await api.patch<{ status: string; shelter: Shelter }>(
    `/shelters/${shelterId}/occupancy`,
    payload,
    { headers: authHeaders(token) },
  );
  return resp.data.shelter;
}

export async function createHazardZone(
  payload: {
    incident_id?: string;
    name: string;
    risk_level?: "low" | "medium" | "high" | "critical";
    zone_type?: "hazard" | "block" | "safe_corridor";
    polygon: Array<{ lat: number; lng: number }>;
    notes?: string;
    status?: "active" | "resolved" | "archived";
  },
  token?: string,
): Promise<Record<string, unknown>> {
  const resp = await api.post<{ status: string; hazard_zone: Record<string, unknown> }>(
    "/hazards/zones",
    payload,
    { headers: authHeaders(token) },
  );
  return resp.data.hazard_zone;
}

export async function createNotificationTemplate(
  payload: {
    name: string;
    level?: "info" | "warning" | "danger";
    title_template: string;
    content_template: string;
  },
  token?: string,
): Promise<NotificationTemplate> {
  const resp = await api.post<{ status: string; template: NotificationTemplate }>(
    "/community/notification-templates",
    payload,
    { headers: authHeaders(token) },
  );
  return resp.data.template;
}

export async function fetchNotificationTemplates(
  limit = 80,
  token?: string,
): Promise<NotificationTemplate[]> {
  const resp = await api.get<{ count: number; items: NotificationTemplate[] }>(
    "/community/notification-templates",
    {
      params: { limit },
      headers: authHeaders(token),
    },
  );
  return resp.data.items;
}

export async function markNotificationReceipt(
  payload: { notification_id: string; status: "read" | "confirmed" },
  token?: string,
): Promise<{ receipt: NotificationReceiptRecord; summary: NotificationReceiptSummary }> {
  const resp = await api.post<{
    status: string;
    receipt: NotificationReceiptRecord;
    summary: NotificationReceiptSummary;
  }>(
    "/community/notifications/receipt",
    payload,
    { headers: authHeaders(token) },
  );
  return {
    receipt: resp.data.receipt,
    summary: resp.data.summary,
  };
}

export async function fetchNotificationReceiptSummary(
  notificationId: string,
  token?: string,
): Promise<NotificationReceiptSummary> {
  const resp = await api.get<NotificationReceiptSummary>(
    `/community/notifications/${notificationId}/receipts/summary`,
    { headers: authHeaders(token) },
  );
  return resp.data;
}

export async function fetchOpsTimeline(
  limit = 200,
  token?: string,
): Promise<OpsTimelineEvent[]> {
  const resp = await api.get<{ count: number; items: OpsTimelineEvent[] }>("/ops/timeline", {
    params: { limit },
    headers: authHeaders(token),
  });
  return resp.data.items;
}

export default api;
