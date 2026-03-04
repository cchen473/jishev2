import type { ReactNode } from "react";

interface CommandShellProps {
  header: ReactNode;
  sidebar: ReactNode;
  main: ReactNode;
  aside: ReactNode;
  overlay?: ReactNode;
}

export default function CommandShell({ header, sidebar, main, aside, overlay }: CommandShellProps) {
  return (
    <div className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      <div className="mx-auto min-h-screen max-w-[1880px] p-4 lg:p-5">
        <div className="grid min-h-[calc(100vh-2.5rem)] gap-4 lg:grid-cols-[62px_minmax(0,1fr)_320px] lg:gap-5">
          <aside className="hidden min-h-0 lg:flex">{sidebar}</aside>

          <section className="min-h-0 flex flex-col gap-4">
            {header}
            <div className="min-h-0 flex-1">{main}</div>
          </section>

          <aside className="min-h-0">{aside}</aside>
        </div>
      </div>
      {overlay}
    </div>
  );
}
