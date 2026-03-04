import { useMemo, useState } from "react";

import type { Incident, IncidentTask, ResponseTeam } from "@/lib/api";

interface TaskKanbanProps {
  incidents: Incident[];
  teams: ResponseTeam[];
  tasks: IncidentTask[];
  creating: boolean;
  updatingId: string | null;
  onCreate: (payload: {
    incident_id: string;
    title: string;
    description: string;
    priority: "low" | "medium" | "high" | "critical";
    team_id?: string;
  }) => Promise<void>;
  onAdvance: (
    task: IncidentTask,
    nextStatus: "assigned" | "accepted" | "in_progress" | "completed",
  ) => Promise<void>;
}

const KANBAN_COLUMNS: Array<{ id: IncidentTask["status"]; label: string }> = [
  { id: "assigned", label: "待接单" },
  { id: "accepted", label: "已接单" },
  { id: "in_progress", label: "处理中" },
  { id: "completed", label: "已完成" },
];

const COLUMN_TONE: Record<IncidentTask["status"], string> = {
  assigned: "border-[rgba(167,175,189,0.35)] text-[var(--text-secondary)]",
  accepted: "border-[rgba(200,165,106,0.42)] text-[var(--accent-primary)]",
  in_progress: "border-[rgba(217,165,96,0.38)] text-[var(--warning)]",
  completed: "border-[rgba(111,191,143,0.38)] text-[var(--success)]",
};

const NEXT_STATUS: Record<string, "assigned" | "accepted" | "in_progress" | "completed" | null> = {
  new: "assigned",
  assigned: "accepted",
  accepted: "in_progress",
  in_progress: "completed",
  blocked: "in_progress",
  completed: null,
};

const STATUS_TEXT: Record<string, string> = {
  assigned: "待接单",
  accepted: "已接单",
  in_progress: "处理中",
  completed: "已完成",
};

const PRIORITY_STYLE: Record<string, string> = {
  low: "border-[var(--line-soft)] text-[var(--text-secondary)]",
  medium: "border-[rgba(200,165,106,0.35)] text-[var(--accent-primary)]",
  high: "border-[rgba(217,165,96,0.4)] text-[var(--warning)]",
  critical: "border-[rgba(201,123,115,0.4)] text-[var(--danger)]",
};

export default function TaskKanban({
  incidents,
  teams,
  tasks,
  creating,
  updatingId,
  onCreate,
  onAdvance,
}: TaskKanbanProps) {
  const [incidentId, setIncidentId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<"low" | "medium" | "high" | "critical">("medium");
  const [teamId, setTeamId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const grouped = useMemo(() => {
    const dict: Record<string, IncidentTask[]> = {};
    KANBAN_COLUMNS.forEach((col) => {
      dict[col.id] = [];
    });
    const priorityRank: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 };
    tasks.forEach((task) => {
      const key = KANBAN_COLUMNS.some((col) => col.id === task.status) ? task.status : "assigned";
      dict[key] = [...(dict[key] ?? []), task];
    });
    KANBAN_COLUMNS.forEach((col) => {
      dict[col.id] = (dict[col.id] ?? []).sort((a, b) => {
        const levelDiff = (priorityRank[b.priority] ?? 0) - (priorityRank[a.priority] ?? 0);
        if (levelDiff !== 0) {
          return levelDiff;
        }
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      });
    });
    return dict;
  }, [tasks]);

  const incidentNameById = useMemo(() => {
    const mapping: Record<string, string> = {};
    incidents.forEach((incident) => {
      mapping[incident.id] = incident.title;
    });
    return mapping;
  }, [incidents]);

  const teamLabelById = useMemo(() => {
    const mapping: Record<string, string> = {};
    teams.forEach((team) => {
      const people =
        typeof team.personnel_count === "number" && team.personnel_count > 0
          ? `${team.personnel_count}人`
          : `${team.member_count ?? 0}人`;
      const location = team.base_location_text || "未标注";
      mapping[team.id] = `${team.name} · ${people} · ${location}`;
    });
    return mapping;
  }, [teams]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!incidentId || !title.trim()) {
      return;
    }
    setSubmitting(true);
    try {
      await onCreate({
        incident_id: incidentId,
        title: title.trim(),
        description: description.trim(),
        priority,
        team_id: teamId || undefined,
      });
      setTitle("");
      setDescription("");
      setPriority("medium");
      setTeamId("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="ui-panel rounded-2xl border p-3 shadow-[var(--shadow-panel)]">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-title text-base text-[var(--text-primary)]">任务看板</h3>
        <span className="text-[11px] text-[var(--text-secondary)]">{tasks.length} 条</span>
      </div>

      <form
        onSubmit={submit}
        className="space-y-2 rounded-xl border border-[var(--line-soft)] bg-[rgba(255,255,255,0.02)] p-2.5"
      >
        <div className="grid gap-2 md:grid-cols-2">
          <select value={incidentId} onChange={(e) => setIncidentId(e.target.value)} className="ui-input ui-focus">
            <option value="">选择所属事件</option>
            {incidents.map((incident) => (
              <option key={incident.id} value={incident.id}>
                {incident.title}
              </option>
            ))}
          </select>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="ui-input ui-focus"
            placeholder="任务标题"
          />
        </div>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="ui-input ui-focus min-h-14 resize-none"
          placeholder="任务描述（可选）"
        />
        <div className="grid gap-2 md:grid-cols-3">
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as "low" | "medium" | "high" | "critical")}
            className="ui-input ui-focus"
          >
            <option value="low">低优先</option>
            <option value="medium">中优先</option>
            <option value="high">高优先</option>
            <option value="critical">紧急</option>
          </select>
          <select value={teamId} onChange={(e) => setTeamId(e.target.value)} className="ui-input ui-focus">
            <option value="">选择救援队（可选）</option>
            {teams.map((team) => (
              <option key={team.id} value={team.id}>
                {teamLabelById[team.id] || team.name}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={submitting || creating || !incidentId || !title.trim()}
            className="ui-btn ui-btn-primary ui-focus px-3 py-2"
          >
            {submitting || creating ? "创建中..." : "创建任务"}
          </button>
        </div>
      </form>

      <div className="mt-3 grid gap-3 lg:grid-cols-2 2xl:grid-cols-4">
        {KANBAN_COLUMNS.map((col) => (
          <div
            key={col.id}
            className="min-h-[240px] rounded-xl border border-[var(--line-soft)] bg-[rgba(255,255,255,0.015)] p-2.5"
          >
            <div className="mb-2 flex items-center justify-between">
              <p className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-[0.04em] ${COLUMN_TONE[col.id]}`}>
                {col.label}
              </p>
              <span className="rounded bg-[rgba(255,255,255,0.04)] px-1.5 py-0.5 text-[10px] font-mono text-[var(--text-secondary)]">
                {(grouped[col.id] ?? []).length}
              </span>
            </div>
            <div className="ui-scrollbar max-h-[420px] space-y-2 overflow-y-auto pr-0.5">
              {(grouped[col.id] ?? []).length === 0 ? (
                <p className="px-1 text-[10px] text-[var(--text-secondary)]">暂无任务</p>
              ) : (
                (grouped[col.id] ?? []).map((task) => {
                  const next = NEXT_STATUS[task.status] ?? null;
                  const aiAuto = (task.description || "").includes("[AI-AUTO]");
                  const desc = (task.description || "").replace("[AI-AUTO]", "").trim();
                  const priorityClass = PRIORITY_STYLE[task.priority] || PRIORITY_STYLE.medium;
                  return (
                    <article
                      key={task.id}
                      className="rounded-lg border border-[var(--line-soft)] bg-[rgba(255,255,255,0.02)] p-2.5"
                    >
                      <p className="truncate text-xs font-medium text-[var(--text-primary)]">{task.title}</p>
                      <p className="mt-0.5 truncate text-[10px] text-[var(--text-secondary)]">
                        {incidentNameById[task.incident_id] || "未关联事件"}
                      </p>
                      <p className="mt-1 line-clamp-2 text-[10px] text-[var(--text-secondary)]">
                        {desc || "暂无补充描述"}
                      </p>

                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        <span className={`rounded border px-1.5 py-0.5 text-[9px] uppercase ${priorityClass}`}>
                          {task.priority}
                        </span>
                        <span className="rounded border border-[var(--line-soft)] px-1.5 py-0.5 text-[9px] text-[var(--text-secondary)]">
                          {task.team_name || "未分队"}
                        </span>
                        {aiAuto ? (
                          <span className="rounded border border-[rgba(200,165,106,0.45)] bg-[rgba(200,165,106,0.12)] px-1.5 py-0.5 text-[9px] text-[var(--accent-strong)]">
                            AI-AUTO
                          </span>
                        ) : null}
                      </div>

                      <div className="mt-2 flex items-center justify-between">
                        <span className="text-[10px] text-[var(--text-secondary)]">
                          {STATUS_TEXT[task.status] || task.status}
                        </span>
                        {next ? (
                          <button
                            type="button"
                            disabled={updatingId === task.id}
                            onClick={() => onAdvance(task, next)}
                            className="rounded border border-[var(--line-soft)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)] transition hover:text-[var(--text-primary)]"
                          >
                            {updatingId === task.id ? "处理中" : `推进至${STATUS_TEXT[next]}`}
                          </button>
                        ) : (
                          <span className="text-[10px] text-[var(--success)]">已闭环</span>
                        )}
                      </div>
                    </article>
                  );
                })
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
