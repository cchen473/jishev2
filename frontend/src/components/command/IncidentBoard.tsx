import { useMemo, useState } from "react";

import type { Incident } from "@/lib/api";

interface IncidentBoardProps {
  incidents: Incident[];
  creating: boolean;
  updatingId: string | null;
  onCreate: (payload: {
    title: string;
    description: string;
    priority: "low" | "medium" | "high" | "critical";
  }) => Promise<void>;
  onUpdateStatus: (
    incidentId: string,
    status: "new" | "verified" | "responding" | "stabilized" | "closed",
  ) => Promise<void>;
}

const STATUS_LABELS: Array<Incident["status"]> = ["new", "verified", "responding", "stabilized", "closed"];

const PRIORITY_COLORS: Record<string, string> = {
  low: "text-[var(--success)] border-[rgba(111,191,143,0.35)]",
  medium: "text-[var(--warning)] border-[rgba(217,165,96,0.35)]",
  high: "text-[var(--accent-strong)] border-[rgba(200,165,106,0.4)]",
  critical: "text-[var(--danger)] border-[rgba(201,123,115,0.42)]",
};

export default function IncidentBoard({
  incidents,
  creating,
  updatingId,
  onCreate,
  onUpdateStatus,
}: IncidentBoardProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<"low" | "medium" | "high" | "critical">("medium");
  const [submitting, setSubmitting] = useState(false);

  const sorted = useMemo(() => {
    return [...incidents].sort((a, b) => {
      const level = { critical: 3, high: 2, medium: 1, low: 0 } as Record<string, number>;
      const diff = (level[b.priority] ?? 0) - (level[a.priority] ?? 0);
      if (diff !== 0) {
        return diff;
      }
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
  }, [incidents]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      return;
    }
    setSubmitting(true);
    try {
      await onCreate({
        title: title.trim(),
        description: description.trim(),
        priority,
      });
      setTitle("");
      setDescription("");
      setPriority("medium");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="ui-panel rounded-2xl border p-3 shadow-[var(--shadow-panel)]">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-title text-base text-[var(--text-primary)]">事件中心</h3>
        <span className="text-[11px] text-[var(--text-secondary)]">{incidents.length} 条</span>
      </div>

      <form onSubmit={submit} className="space-y-2 rounded-xl border border-[var(--line-soft)] bg-[rgba(255,255,255,0.02)] p-2.5">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="ui-input ui-focus"
          placeholder="新增事件标题（如：3号楼外墙裂缝扩展）"
        />
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="ui-input ui-focus min-h-16 resize-none"
          placeholder="补充描述（可选）"
        />
        <div className="flex items-center gap-2">
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as "low" | "medium" | "high" | "critical")}
            className="ui-input ui-focus max-w-40"
          >
            <option value="low">低</option>
            <option value="medium">中</option>
            <option value="high">高</option>
            <option value="critical">紧急</option>
          </select>
          <button
            type="submit"
            disabled={submitting || creating || !title.trim()}
            className="ui-btn ui-btn-primary ui-focus ml-auto px-3 py-2"
          >
            {submitting || creating ? "创建中..." : "创建事件"}
          </button>
        </div>
      </form>

      <div className="ui-scrollbar mt-3 max-h-[380px] space-y-2 overflow-y-auto pr-1">
        {sorted.length === 0 ? (
          <div className="rounded-lg border border-[var(--line-soft)] px-3 py-2 text-xs text-[var(--text-secondary)]">
            暂无事件
          </div>
        ) : (
          sorted.map((item) => (
            <article
              key={item.id}
              className="rounded-xl border border-[var(--line-soft)] bg-[rgba(255,255,255,0.015)] p-2.5"
            >
              <div className="mb-1.5 flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-[var(--text-primary)]">{item.title}</p>
                  {item.source === "agent_auto" ? (
                    <span className="mt-1 inline-flex rounded-md border border-[rgba(200,165,106,0.45)] bg-[rgba(200,165,106,0.12)] px-1.5 py-0.5 text-[10px] tracking-wide text-[var(--accent-strong)]">
                      AI-AUTO
                    </span>
                  ) : null}
                </div>
                <span
                  className={`rounded-md border px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${PRIORITY_COLORS[item.priority] ?? "text-[var(--text-secondary)] border-[var(--line-soft)]"}`}
                >
                  {item.priority}
                </span>
              </div>
              {item.description ? (
                <p className="line-clamp-2 text-xs text-[var(--text-secondary)]">{item.description}</p>
              ) : null}
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                {STATUS_LABELS.map((status) => (
                  <button
                    key={status}
                    type="button"
                    disabled={updatingId === item.id}
                    onClick={() => onUpdateStatus(item.id, status as "new" | "verified" | "responding" | "stabilized" | "closed")}
                    className={`rounded-md border px-1.5 py-0.5 text-[10px] transition ${item.status === status
                      ? "border-[rgba(200,165,106,0.45)] bg-[rgba(200,165,106,0.12)] text-[var(--accent-strong)]"
                      : "border-[var(--line-soft)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    {status}
                  </button>
                ))}
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
