const TONE_STYLES = {
  neutral: {
    border: "rgba(167, 175, 189, 0.25)",
    accent: "var(--text-secondary)",
  },
  primary: {
    border: "rgba(200, 165, 106, 0.4)",
    accent: "var(--accent-strong)",
  },
  warning: {
    border: "rgba(217, 165, 96, 0.4)",
    accent: "var(--warning)",
  },
  danger: {
    border: "rgba(201, 123, 115, 0.4)",
    accent: "var(--danger)",
  },
} as const;

export type MetricCardTone = keyof typeof TONE_STYLES;

interface MetricCardProps {
  label: string;
  value: string | number;
  tone?: MetricCardTone;
  hint?: string;
}

export default function MetricCard({ label, value, tone = "neutral", hint }: MetricCardProps) {
  const style = TONE_STYLES[tone];

  return (
    <article
      className="ui-elevated rounded-2xl border px-4 py-3.5"
      style={{ borderColor: style.border }}
    >
      <p className="text-[11px] font-medium tracking-[0.08em] text-[var(--text-secondary)]">{label}</p>
      <p
        className="mt-1 text-2xl font-semibold leading-none tracking-tight"
        style={{ color: style.accent }}
      >
        {value}
      </p>
      {hint ? <p className="mt-2 text-[11px] text-[var(--text-secondary)]">{hint}</p> : null}
    </article>
  );
}
