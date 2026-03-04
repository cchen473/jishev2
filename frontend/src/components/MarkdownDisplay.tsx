import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

export interface MarkdownDisplayProps {
  content: string;
  compact?: boolean;
  className?: string;
}

function normalizeMarkdown(raw: string): string {
  const normalized = raw.replace(/\r\n?/g, "\n").trimEnd();
  return normalized || "暂无内容";
}

export default function MarkdownDisplay({ content, compact = false, className = "" }: MarkdownDisplayProps) {
  const markdown = normalizeMarkdown(content);
  const containerClass = compact ? "markdown-body markdown-body-compact" : "markdown-body";

  return (
    <div className={`${containerClass} ${className}`.trim()}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        rehypePlugins={[rehypeSanitize]}
        components={{
          a: ({ href, children }) => (
            <a href={href ?? "#"} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
          pre: ({ children }) => <pre>{children}</pre>,
          code: ({ className: codeClassName, children, ...props }) => (
            <code className={codeClassName} {...props}>
              {children}
            </code>
          ),
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
