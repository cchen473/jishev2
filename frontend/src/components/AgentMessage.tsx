import React from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import MarkdownDisplay from '@/components/MarkdownDisplay';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface AgentMessageProps {
  source: string;
  content: string;
  type: string;
}

export const AgentMessage: React.FC<AgentMessageProps> = ({ source, content, type }) => {
  const sourceUpper = source.toUpperCase();
  let borderColor = 'border-[rgba(167,175,189,0.26)]';
  let textColor = 'text-[var(--text-primary)]';
  let titleColor = 'text-[var(--text-secondary)]';
  let badgeClass = 'border-[rgba(167,175,189,0.22)] text-[var(--text-secondary)]';

  if (sourceUpper.includes('COMMANDER')) {
    borderColor = 'border-[rgba(200,165,106,0.45)]';
    textColor = 'text-[var(--accent-strong)]';
    titleColor = 'text-[var(--accent-strong)]';
    badgeClass = 'border-[rgba(200,165,106,0.35)] text-[var(--accent-strong)]';
  } else if (sourceUpper.includes('CV')) {
    borderColor = 'border-[rgba(167,175,189,0.34)]';
  } else if (sourceUpper.includes('POLICY')) {
    borderColor = 'border-[rgba(217,165,96,0.45)]';
    titleColor = 'text-[var(--warning)]';
    badgeClass = 'border-[rgba(217,165,96,0.32)] text-[var(--warning)]';
  } else if (sourceUpper.includes('GIS')) {
    borderColor = 'border-[rgba(111,191,143,0.45)]';
    titleColor = 'text-[var(--success)]';
    badgeClass = 'border-[rgba(111,191,143,0.35)] text-[var(--success)]';
  } else if (sourceUpper.includes('ROUTE')) {
    borderColor = 'border-[rgba(200,165,106,0.38)]';
    titleColor = 'text-[var(--accent-primary)]';
  } else if (sourceUpper.includes('SYSTEM')) {
    if (type.toLowerCase() === 'error') {
      borderColor = 'border-[rgba(201,123,115,0.52)]';
      textColor = 'text-[var(--danger)]';
      titleColor = 'text-[var(--danger)]';
      badgeClass = 'border-[rgba(201,123,115,0.38)] text-[var(--danger)]';
    } else {
      borderColor = 'border-[rgba(217,165,96,0.5)]';
      titleColor = 'text-[var(--warning)]';
      badgeClass = 'border-[rgba(217,165,96,0.35)] text-[var(--warning)]';
    }
  }

  return (
    <article
      className={cn(
        "mb-2 rounded-xl border bg-[rgba(17,21,28,0.86)] p-3 shadow-[var(--shadow-floating)] animate-in fade-in slide-in-from-left-4 duration-300",
        borderColor,
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className={cn("font-mono text-[10px] font-semibold uppercase tracking-[0.12em]", titleColor)}>
          {source}
        </div>
        <span className={cn("rounded-md border px-1.5 py-0.5 text-[9px] uppercase tracking-[0.12em]", badgeClass)}>
          {type}
        </span>
      </div>
      <MarkdownDisplay content={content} compact className={cn("text-[13px]", textColor)} />
    </article>
  );
};
