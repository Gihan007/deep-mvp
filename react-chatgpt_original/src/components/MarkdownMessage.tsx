import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Props {
  children: string;
  className?: string;
}

/**
 * Reusable component for rendering markdown messages
 */
export default function MarkdownMessage({ children, className = 'markdown' }: Props) {
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
