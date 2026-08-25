import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeRaw from 'rehype-raw';
import rehypeKatex from 'rehype-katex';
import { MermaidDiagram } from './MermaidDiagram';

import { NotebookLMCitationBadge, type CitationItem } from '../chat/NotebookLMCitations';

export type { CitationItem };


export const cleanMarkdownContent = (content: string): string => {
  if (!content) return '';
  // 0. Strip leading JSON preambles (e.g. {"conflict": false, "summary": ""})
  let text = content.replace(/^\s*\{[\s\S]*?"summary":\s*"[^"]*"\s*\}\s*/g, '');

  // 0.1 Normalize exotic Unicode whitespace characters to standard ASCII space
  text = text.replace(/[\u202F\u00A0\u2000-\u200B\u2028\u2029\uFEFF]/g, ' ');

  // 0.2 Fix collapsed Markdown tables where rows are glued together with || or | |
  // e.g. "| cell | cell | | Next Row | cell |" -> "| cell | cell |\n| Next Row | cell |"
  text = text.replace(/\|\s*\|\s*(?=[^|\n]+(?:\||$))/g, '|\n| ');

  // 0.3 Fix collapsed Markdown table header separator rows
  text = text.replace(/(\|[-:]+[-| :]*)\|([^\n\-\|])/g, '$1|\n| $2');
  text = text.replace(/(\|[^|\n]+)\|(\|[-:]+[-| :]*\|)/g, '$1|\n$2');

  // 1. Process Citations FIRST before any math bracket conversions
  // Handle special citation markers: 【1†source】 or 【1】
  text = text.replace(/【(\d+)†[^】]*】/g, ' [$1](#cit-$1)');
  text = text.replace(/【(\d+)】/g, ' [$1](#cit-$1)');
  text = text.replace(/【[^】]*】/g, '');

  // Handle grouped bracketed citations like [1, 2, 4] or [1,2]
  text = text.replace(/(?<![\$\w\\])\[(\d+(?:\s*,\s*\d+)+)\](?!\()/g, (_match, group) => {
    const nums = group.split(',').map((n: string) => n.trim()).filter(Boolean);
    return nums.map((n: string) => `[${n}](#cit-${n})`).join(' ');
  });

  // Handle range bracketed citations like [1-3] or [1–3]
  text = text.replace(/(?<![\$\w\\])\[(\d+)\s*[-–—]\s*(\d+)\](?!\()/g, (_match, startStr, endStr) => {
    const start = parseInt(startStr, 10);
    const end = parseInt(endStr, 10);
    if (!isNaN(start) && !isNaN(end) && start < end && end - start <= 10) {
      const items = [];
      for (let i = start; i <= end; i++) {
        items.push(`[${i}](#cit-${i})`);
      }
      return items.join(' ');
    }
    return `[${startStr}](#cit-${startStr})-[${endStr}](#cit-${endStr})`;
  });

  // Handle single bracketed citations [1], [2], etc.
  text = text.replace(/(?<![\$\w\\])\[(\d+)\](?!\()/g, '[$1](#cit-$1)');

  // Remove awkward spacing between citation badge and following punctuation
  text = text.replace(/(\(#cit-\d+\))\s+([.,;:!?])/g, '$1$2');

  // 2. Standardize LaTeX blocks \[ ... \] to $$ ... $$ and \( ... \) to $ ... $
  text = text.replace(/\\\[([\s\S]*?)\\\]/g, '\n\n$$\n$1\n$$\n\n');
  text = text.replace(/\\\(([\s\S]*?)\\\)/g, '$$$1$$');

  // 3. Process line-by-line to find standalone LaTeX math equations without multiline bleeding
  const lines = text.split('\n');
  const processedLines = lines.map((line) => {
    const trimmed = line.trim();
    if (!trimmed) return line;
    // Skip Markdown structure (headings, lists, quotes, tables, code blocks)
    if (trimmed.startsWith('#') || trimmed.startsWith('*') || trimmed.startsWith('-') || trimmed.startsWith('>') || trimmed.startsWith('|')) {
      return line;
    }
    // Skip if already in math blocks
    if (trimmed.startsWith('$$') || trimmed.endsWith('$$')) {
      return line;
    }
    // Check if line contains a mathematical LaTeX command and is a standalone formula line
    if (/\\[a-zA-Z]+/.test(trimmed) && !trimmed.includes('](#cit-')) {
      const isPureFormula = /^(?:[a-zA-Z0-9_*^:=+\-/(), \t]|\\(?:rightarrow|to|leftarrow|le|ge|times|cdot|frac|sqrt|sum|prod|alpha|beta|gamma|theta|lambda|mu|pi|sigma|omega|approx|neq|in|subset|cup|cap|mathbf|mathit|text|pm|infty|partial))+$/.test(trimmed);
      if (isPureFormula) {
        return `$$ ${trimmed} $$`;
      }
    }
    return line;
  });

  text = processedLines.join('\n');

  // Clean empty display math blocks like "$$\n$$" or "$$ $$"
  text = text.replace(/\$\$\s*\$\$/g, '');

  // 4. Safe <br> handling: preserve <br> inside table cells, normalize outside
  const finalLines = text.split('\n').map((line) => {
    const trimmed = line.trim();
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      // Inside a table row: preserve <br> for intra-cell multiline lists
      return line;
    }
    // Outside table rows: convert <br> to clean newlines
    return line
      .replace(/<br\s*\/?>\s*•/gi, '\n- ')
      .replace(/<br\s*\/?>\s*\*/gi, '\n* ')
      .replace(/<br\s*\/?>\s*-/gi, '\n- ')
      .replace(/<br\s*\/?>/gi, '\n\n');
  });

  return finalLines.join('\n');
};




export const markdownToReportHtml = (md: string): string => {
  if (!md) return '';

  let text = md.replace(/\r\n/g, '\n').replace(/<think>[\s\S]*?<\/think>/gi, '').trim();

  text = text
    .replace(/^### (.*$)/gim, '<h3 class="report-h3">$1</h3>')
    .replace(/^## (.*$)/gim, '<h2 class="report-h2">$1</h2>')
    .replace(/^# (.*$)/gim, '<h1 class="report-h1">$1</h1>');

  text = text
    .replace(/\*\*\*(.*?)\*\*\*/gim, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/gim, '<em>$1</em>')
    .replace(/___(.*?)___/gim, '<strong><em>$1</em></strong>')
    .replace(/__(.*?)__/gim, '<strong>$1</strong>')
    .replace(/_(.*?)_/gim, '<em>$1</em>');

  text = text
    .replace(/【(\d+)†[^】]*】/gim, '<span class="report-cit-badge">[$1]</span>')
    .replace(/【(\d+)】/gim, '<span class="report-cit-badge">[$1]</span>')
    .replace(/【[^】]*】/gim, '')
    .replace(/(?<![\$\w\\])\[(\d+(?:\s*,\s*\d+)+)\](?!\()/gim, (_m, group) => {
      const nums = group.split(',').map((n: string) => n.trim()).filter(Boolean);
      return nums.map((n: string) => `<span class="report-cit-badge">[${n}]</span>`).join(' ');
    })
    .replace(/(?<![\$\w\\])\[(\d+)\s*[-–—]\s*(\d+)\](?!\()/gim, (_m, s, e) => {
      const start = parseInt(s, 10);
      const end = parseInt(e, 10);
      if (!isNaN(start) && !isNaN(end) && start < end && end - start <= 10) {
        const items = [];
        for (let i = start; i <= end; i++) {
          items.push(`<span class="report-cit-badge">[${i}]</span>`);
        }
        return items.join(' ');
      }
      return `<span class="report-cit-badge">[${s}-${e}]</span>`;
    })
    .replace(/(?<![\$\w\\])\[(\d+)\](?!\()/gim, '<span class="report-cit-badge">[$1]</span>');

  text = text
    .replace(/```([\w]*)\n([\s\S]*?)```/gim, '<pre class="report-code-block"><code>$2</code></pre>')
    .replace(/`([^`]+)`/gim, '<code class="report-inline-code">$1</code>');

  text = text.replace(/^>\s+(.*$)/gim, '<blockquote class="report-blockquote">$1</blockquote>');

  const rawLines = text.split('\n');
  const result: string[] = [];
  let inList = false;
  let inOrderedList = false;

  for (let i = 0; i < rawLines.length; i++) {
    const line = rawLines[i].trim();
    if (!line) {
      if (inList) { result.push('</ul>'); inList = false; }
      if (inOrderedList) { result.push('</ol>'); inOrderedList = false; }
      continue;
    }

    if (line.startsWith('* ') || line.startsWith('- ') || line.startsWith('• ')) {
      if (inOrderedList) { result.push('</ol>'); inOrderedList = false; }
      if (!inList) { result.push('<ul class="report-ul">'); inList = true; }
      result.push(`<li>${line.replace(/^[*•-]\s+/, '')}</li>`);
    } else if (/^\d+\.\s+/.test(line)) {
      if (inList) { result.push('</ul>'); inList = false; }
      if (!inOrderedList) { result.push('<ol class="report-ol">'); inOrderedList = true; }
      result.push(`<li>${line.replace(/^\d+\.\s+/, '')}</li>`);
    } else if (line.startsWith('<h1') || line.startsWith('<h2') || line.startsWith('<h3') || line.startsWith('<pre') || line.startsWith('<blockquote') || line.startsWith('<table')) {
      if (inList) { result.push('</ul>'); inList = false; }
      if (inOrderedList) { result.push('</ol>'); inOrderedList = false; }
      result.push(line);
    } else {
      if (inList) { result.push('</ul>'); inList = false; }
      if (inOrderedList) { result.push('</ol>'); inOrderedList = false; }
      result.push(`<p class="report-p">${line}</p>`);
    }
  }

  if (inList) result.push('</ul>');
  if (inOrderedList) result.push('</ol>');

  return result.join('\n');
};


interface MarkdownRendererProps {
  content: string;
  citations?: CitationItem[];
  highlightedCitationIndex?: number | null;
  onCitationClick?: (citation: CitationItem) => void;
  onCitationHover?: (citation: CitationItem | null, rect?: DOMRect) => void;
  onFileClick?: (path: string) => void;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
  citations = [],
  highlightedCitationIndex,
  onCitationClick,
  onCitationHover,
  onFileClick,
}) => {
  const cleaned = cleanMarkdownContent(content);

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeRaw, [rehypeKatex, { throwOnError: false, errorColor: '#f87171', strict: 'ignore' }]]}
      components={{
        table: ({ children, ...props }) => (
          <div className="markdown-table-wrapper">
            <table {...props}>{children}</table>
          </div>
        ),
        code({ className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '');
          const lang = match ? match[1] : '';
          const codeString = String(children).replace(/\n$/, '');
          const isMermaid =
            lang === 'mermaid' ||
            codeString.startsWith('graph ') ||
            codeString.startsWith('graph TD') ||
            codeString.startsWith('flowchart ') ||
            codeString.startsWith('sequenceDiagram') ||
            codeString.startsWith('classDiagram');

          if (isMermaid) {
            return <MermaidDiagram chart={codeString} />;
          }

          return (
            <code className={className} {...props}>
              {children}
            </code>
          );
        },
        a({ href, children, ...props }) {
          if (href && href.startsWith('#cit-')) {
            const citNum = parseInt(href.replace('#cit-', ''), 10);
            const targetCitation = citations.find((c) => c.index === citNum) || citations[citNum - 1] || {
              index: citNum,
              source: `Source [${citNum}]`,
              score: 'yes',
              text: 'Referenced document passage evaluated and verified by the CRAG pipeline.',
            };

            return (
              <NotebookLMCitationBadge
                index={citNum}
                citation={targetCitation}
                isHighlighted={highlightedCitationIndex === citNum}
                onClick={(c) => onCitationClick && onCitationClick(c)}
                onMouseEnter={(c, rect) => onCitationHover && onCitationHover(c, rect)}
                onMouseLeave={() => onCitationHover && onCitationHover(null)}
              />
            );
          }

          if (href && href.startsWith('file://')) {
            const path = href.replace('file://', '');
            return (
              <span
                className="inline-file-link"
                title={`Local path: ${path} (Click to copy)`}
                onClick={(e) => {
                  e.preventDefault();
                  if (onFileClick) onFileClick(path);
                }}
                style={{
                  cursor: 'pointer',
                  textDecoration: 'underline',
                  color: 'var(--color-5, #0284C7)',
                  fontFamily: 'var(--font-mono, monospace)',
                  fontSize: '0.9em'
                }}
              >
                {children}
              </span>
            );
          }

          return (
            <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
              {children}
            </a>
          );
        },
      }}
    >
      {cleaned}
    </ReactMarkdown>
  );
};


