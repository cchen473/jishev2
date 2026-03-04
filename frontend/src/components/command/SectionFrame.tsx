import type { ReactNode } from "react";

interface SectionFrameProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export default function SectionFrame({
  title,
  subtitle,
  actions,
  children,
  className = "",
}: SectionFrameProps) {
  return (
    <section className={`ui-panel rounded-2xl border ${className}`.trim()}>
      <header className="flex items-start justify-between gap-3 border-b border-[var(--line-soft)] px-4 py-3.5">
        <div className="space-y-1">
          <h3 className="font-title text-base tracking-[0.02em] text-[var(--text-primary)]">{title}</h3>
          {subtitle ? (
            <p className="text-[11px] leading-relaxed tracking-[0.06em] text-[var(--text-secondary)]">
              {subtitle}
            </p>
          ) : null}
        </div>
        {actions ? <div className="shrink-0">{actions}</div> : null}
      </header>
      {children}
    </section>
  );
}
