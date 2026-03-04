export type PanelTabValue = "terminal" | "chat" | "rescue";

interface PanelTabsProps {
  value: PanelTabValue;
  onChange: (value: PanelTabValue) => void;
}

const TABS: Array<{ id: PanelTabValue; label: string }> = [
  { id: "terminal", label: "指挥终端" },
  { id: "chat", label: "社区群聊" },
  { id: "rescue", label: "地震搜救" },
];

export default function PanelTabs({ value, onChange }: PanelTabsProps) {
  return (
    <div className="ui-elevated grid grid-cols-3 gap-1.5 rounded-xl border p-1">
      {TABS.map((tab) => {
        const active = value === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={`rounded-lg px-2 py-2 text-[11px] font-medium tracking-wide transition ${
              active
                ? "bg-[rgba(200,165,106,0.17)] text-[var(--accent-strong)]"
                : "text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.03)] hover:text-[var(--text-primary)]"
            }`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
