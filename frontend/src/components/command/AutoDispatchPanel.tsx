import type { DispatchAgentRunSummary } from "@/lib/api";

interface AutoDispatchPanelProps {
  runs: DispatchAgentRunSummary[];
}

function parseCount(data: unknown, topKey: string, nestedKey: string): number {
  if (!data || typeof data !== "object") {
    return 0;
  }
  const section = (data as Record<string, unknown>)[topKey];
  if (!section || typeof section !== "object") {
    return 0;
  }
  const value = (section as Record<string, unknown>)[nestedKey];
  if (Array.isArray(value)) {
    return value.length;
  }
  if (typeof value === "number") {
    return value;
  }
  return 0;
}

export default function AutoDispatchPanel({ runs }: AutoDispatchPanelProps) {
  const latest = runs[runs.length - 1] ?? null;
  const latestExecution = latest?.execution ?? {};
  const incidentCount = parseCount(latestExecution, "incident", "created");
  const taskCount = parseCount(latestExecution, "tasks", "created");
  const dispatchCount = parseCount(latestExecution, "dispatches", "created");
  const plannerSource =
    latest?.plan && typeof latest.plan === "object" && "source" in latest.plan
      ? String((latest.plan as { source?: unknown }).source ?? "unknown")
      : "unknown";
  const plannerStatus =
    latest?.plan && typeof latest.plan === "object" && "planner_status" in latest.plan
      ? String((latest.plan as { planner_status?: unknown }).planner_status ?? "unknown")
      : "unknown";
  const latestErrors =
    latestExecution &&
    typeof latestExecution === "object" &&
    Array.isArray((latestExecution as { execution_errors?: unknown }).execution_errors)
      ? ((latestExecution as { execution_errors: string[] }).execution_errors as string[])
      : [];

  return (
    <section className="ui-panel rounded-2xl border p-3 shadow-[var(--shadow-panel)]">
      <div className="mb-2.5 flex items-center justify-between">
        <h3 className="font-title text-sm tracking-[0.03em] text-[var(--text-primary)]">自动调度 Agent</h3>
        <span className="rounded-md border border-[var(--line-soft)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]">
          {runs.length} 次
        </span>
      </div>

      {latest ? (
        <div className="rounded-xl border border-[var(--line-soft)] bg-[rgba(255,255,255,0.02)] p-2.5">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] text-[var(--text-secondary)]">最近执行</span>
            <span
              className={`rounded-md border px-1.5 py-0.5 text-[10px] ${
                latest.status === "completed"
                  ? "border-[rgba(111,191,143,0.35)] text-[var(--success)]"
                  : latest.status === "degraded"
                  ? "border-[rgba(217,165,96,0.35)] text-[var(--warning)]"
                  : "border-[rgba(201,123,115,0.35)] text-[var(--danger)]"
              }`}
            >
              {latest.status}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-1.5">
            <div className="rounded-md border border-[var(--line-soft)] px-2 py-1">
              <p className="text-[9px] text-[var(--text-secondary)]">事件</p>
              <p className="font-mono text-xs text-[var(--text-primary)]">+{incidentCount}</p>
            </div>
            <div className="rounded-md border border-[var(--line-soft)] px-2 py-1">
              <p className="text-[9px] text-[var(--text-secondary)]">任务</p>
              <p className="font-mono text-xs text-[var(--text-primary)]">+{taskCount}</p>
            </div>
            <div className="rounded-md border border-[var(--line-soft)] px-2 py-1">
              <p className="text-[9px] text-[var(--text-secondary)]">调度</p>
              <p className="font-mono text-xs text-[var(--text-primary)]">+{dispatchCount}</p>
            </div>
          </div>
          <div className="mt-2 rounded-md border border-[var(--line-soft)] bg-[rgba(255,255,255,0.015)] px-2 py-1.5 text-[10px] text-[var(--text-secondary)]">
            规划器：{plannerSource} · 状态：{plannerStatus}
          </div>
          {latestErrors.length > 0 ? (
            <div className="mt-2 rounded-md border border-[rgba(201,123,115,0.4)] bg-[rgba(201,123,115,0.08)] px-2 py-1.5 text-[10px] text-[var(--danger)]">
              {latestErrors.slice(0, 2).join("；")}
            </div>
          ) : null}
          {latest.error ? (
            <p className="mt-2 text-[10px] text-[var(--warning)]">
              {latest.error}
            </p>
          ) : null}
        </div>
      ) : (
        <div className="rounded-lg border border-[var(--line-soft)] px-2.5 py-2 text-[11px] text-[var(--text-secondary)]">
          暂无自动调度执行记录
        </div>
      )}

      <div className="ui-scrollbar mt-2 max-h-32 space-y-1.5 overflow-y-auto pr-1">
        {runs.slice(-6).reverse().map((run) => (
          <div
            key={run.id}
            className="rounded-md border border-[var(--line-soft)] bg-[rgba(255,255,255,0.015)] px-2 py-1.5"
          >
            <div className="flex items-center justify-between gap-2">
              <p className="truncate text-[10px] text-[var(--text-secondary)]">{run.trigger_source}</p>
              <span className="font-mono text-[10px] text-[var(--text-secondary)]">
                {new Date(run.created_at).toLocaleTimeString()}
              </span>
            </div>
            <p className="mt-1 text-[10px] text-[var(--text-primary)]">{run.status}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
