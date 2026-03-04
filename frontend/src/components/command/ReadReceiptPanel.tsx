import { useState } from "react";

import type { CommunityNotification, NotificationReceiptSummary } from "@/lib/api";

interface ReadReceiptPanelProps {
  notifications: CommunityNotification[];
  receiptSummaries: Record<string, NotificationReceiptSummary | undefined>;
  myReceiptStatus: Record<string, "read" | "confirmed" | undefined>;
  onMarkRead: (notificationId: string) => Promise<void>;
  onMarkConfirmed: (notificationId: string) => Promise<void>;
}

export default function ReadReceiptPanel({
  notifications,
  receiptSummaries,
  myReceiptStatus,
  onMarkRead,
  onMarkConfirmed,
}: ReadReceiptPanelProps) {
  const [pendingId, setPendingId] = useState<string | null>(null);

  const latest = notifications.slice(-6).reverse();

  const handle = async (notificationId: string, type: "read" | "confirmed") => {
    setPendingId(`${notificationId}:${type}`);
    try {
      if (type === "read") {
        await onMarkRead(notificationId);
      } else {
        await onMarkConfirmed(notificationId);
      }
    } finally {
      setPendingId(null);
    }
  };

  return (
    <section className="ui-panel rounded-2xl border p-3 shadow-[var(--shadow-panel)]">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-title text-base text-[var(--text-primary)]">通知回执</h3>
        <span className="text-[11px] text-[var(--text-secondary)]">最近 {latest.length} 条</span>
      </div>
      <div className="ui-scrollbar max-h-64 space-y-2 overflow-y-auto pr-1">
        {latest.length === 0 ? (
          <div className="rounded-lg border border-[var(--line-soft)] px-3 py-2 text-xs text-[var(--text-secondary)]">
            暂无可回执通知
          </div>
        ) : (
          latest.map((item) => (
            <article
              key={item.id}
              className="rounded-lg border border-[var(--line-soft)] bg-[rgba(255,255,255,0.015)] p-2"
            >
              {(() => {
                const summary = receiptSummaries[item.id];
                const status = myReceiptStatus[item.id];
                const readDone = status === "read" || status === "confirmed";
                const confirmedDone = status === "confirmed";
                return (
                  <>
                    <div className="mb-1.5 flex items-center justify-between gap-2">
                      <div className="inline-flex items-center gap-1 text-[10px] text-[var(--text-secondary)]">
                        <span className="rounded border border-[var(--line-soft)] px-1.5 py-0.5">
                          已读 {summary?.by_status.read ?? 0}
                        </span>
                        <span className="rounded border border-[var(--line-soft)] px-1.5 py-0.5">
                          确认 {summary?.by_status.confirmed ?? 0}
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
                    <p className="text-[11px] font-medium text-[var(--accent-strong)]">{item.title}</p>
                    <p className="mt-1 line-clamp-2 text-[11px] text-[var(--text-secondary)]">{item.content}</p>
                    <div className="mt-2 flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => handle(item.id, "read")}
                        disabled={pendingId === `${item.id}:read` || readDone}
                        className="rounded border border-[var(--line-soft)] px-2 py-1 text-[10px] text-[var(--text-secondary)] transition hover:text-[var(--text-primary)] disabled:opacity-55"
                      >
                        {pendingId === `${item.id}:read` ? "提交中" : readDone ? "已读" : "标记已读"}
                      </button>
                      <button
                        type="button"
                        onClick={() => handle(item.id, "confirmed")}
                        disabled={pendingId === `${item.id}:confirmed` || confirmedDone}
                        className="rounded border border-[rgba(200,165,106,0.45)] bg-[rgba(200,165,106,0.12)] px-2 py-1 text-[10px] text-[var(--accent-strong)] disabled:opacity-55"
                      >
                        {pendingId === `${item.id}:confirmed`
                          ? "提交中"
                          : confirmedDone
                            ? "已确认"
                            : "确认执行"}
                      </button>
                    </div>
                  </>
                );
              })()}
            </article>
          ))
        )}
      </div>
    </section>
  );
}
