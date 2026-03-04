import type { ReactNode } from "react";

type AuthMode = "login" | "register";

interface AuthCardProps {
  mode: AuthMode;
  onModeChange: (mode: AuthMode) => void;
  children: ReactNode;
}

export default function AuthCard({ mode, onModeChange, children }: AuthCardProps) {
  return (
    <article className="ui-panel w-full max-w-4xl rounded-3xl border p-6 shadow-[var(--shadow-panel)] lg:p-8">
      <header className="mb-7 flex items-start justify-between gap-4">
        <div>
          <p className="font-title text-3xl tracking-[0.02em] text-[var(--text-primary)]">
            NebulaGuard 地震指挥系统
          </p>
          <p className="mt-1 text-xs tracking-[0.08em] text-[var(--text-secondary)]">
            COMMUNITY COMMAND CONSOLE
          </p>
        </div>

        <div className="ui-elevated inline-flex rounded-xl border p-1.5">
          <button
            type="button"
            onClick={() => onModeChange("login")}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              mode === "login"
                ? "bg-[rgba(200,165,106,0.17)] text-[var(--accent-strong)]"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            登录
          </button>
          <button
            type="button"
            onClick={() => onModeChange("register")}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              mode === "register"
                ? "bg-[rgba(200,165,106,0.17)] text-[var(--accent-strong)]"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            注册
          </button>
        </div>
      </header>

      {children}
    </article>
  );
}
