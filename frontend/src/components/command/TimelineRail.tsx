import type { OpsTimelineEvent } from "@/lib/api";

interface TimelineRailProps {
  events: OpsTimelineEvent[];
}

export default function TimelineRail({ events }: TimelineRailProps) {
  return (
    <section className="ui-panel flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border p-3 shadow-[var(--shadow-panel)]">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-title text-base text-[var(--text-primary)]">复盘时间轴</h3>
        <span className="text-[11px] text-[var(--text-secondary)]">{events.length} 条</span>
      </div>
      <div className="ui-scrollbar min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
        {events.length === 0 ? (
          <div className="rounded-lg border border-[var(--line-soft)] px-3 py-2 text-xs text-[var(--text-secondary)]">
            暂无复盘事件
          </div>
        ) : (
          events
            .slice()
            .reverse()
            .map((event) => (
              <article
                key={event.id}
                className="relative rounded-xl border border-[var(--line-soft)] bg-[rgba(255,255,255,0.015)] p-2.5"
              >
                <span className="absolute left-2 top-2 h-1.5 w-1.5 rounded-full bg-[var(--accent-primary)]" />
                <div className="ml-3">
                  <p className="text-xs font-medium text-[var(--text-primary)]">{event.title}</p>
                  <p className="mt-0.5 text-[11px] text-[var(--text-secondary)]">{event.content}</p>
                  <div className="mt-1.5 flex items-center justify-between text-[10px] text-[var(--text-secondary)]">
                    <span>{event.event_type}</span>
                    <span>{new Date(event.created_at).toLocaleString()}</span>
                  </div>
                </div>
              </article>
            ))
        )}
      </div>
    </section>
  );
}
