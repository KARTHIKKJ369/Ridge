import React, { useState } from 'react';
import {
  FileText,
  Globe,
  Check,
  X,
  Copy,
  ExternalLink,
  BookOpen,
  Sparkles,
  Layers,
  ChevronDown,
  ChevronUp,
  Search,
} from 'lucide-react';

export interface CitationItem {
  index: number;
  score?: 'yes' | 'no' | string;
  source?: string;
  breadcrumb?: string;
  rationale?: string;
  text?: string;
  relevance?: number;
  page?: number | string;
  type?: 'local' | 'web' | string;
  chunk_id?: string;
  parent_id?: string;
}

interface InlineCitationBadgeProps {
  index: number;
  citation?: CitationItem;
  onClick: (citation: CitationItem, e: React.MouseEvent) => void;
  onMouseEnter: (citation: CitationItem, rect: DOMRect) => void;
  onMouseLeave: () => void;
  isHighlighted?: boolean;
}

export const NotebookLMCitationBadge: React.FC<InlineCitationBadgeProps> = ({
  index,
  citation,
  onClick,
  onMouseEnter,
  onMouseLeave,
  isHighlighted,
}) => {
  const isWeb =
    citation?.breadcrumb === 'Web Search Fallback' ||
    citation?.source?.startsWith('http') ||
    citation?.type === 'web';

  const defaultCitation: CitationItem = citation || {
    index,
    source: `Document Source [${index}]`,
    score: 'yes',
    text: 'Referenced passage evaluated and verified by the CRAG pipeline.',
  };

  const handleMouseEnter = (e: React.MouseEvent<HTMLButtonElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    onMouseEnter(defaultCitation, rect);
  };

  return (
    <span className="notebooklm-inline-cit-wrapper">
      <button
        type="button"
        className={`notebooklm-citation-badge ${isWeb ? 'web-badge' : 'local-badge'} ${
          isHighlighted ? 'active-highlight' : ''
        }`}
        onClick={(e) => onClick(defaultCitation, e)}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={onMouseLeave}
        title={
          defaultCitation.source
            ? `[${index}] ${defaultCitation.source.split('/').pop()} (Click to inspect source)`
            : `Citation [${index}]`
        }
        aria-label={`Source citation ${index}`}
      >
        <span className="cit-badge-index">{index}</span>
      </button>
    </span>
  );
};

interface CitationPopoverProps {
  citation: CitationItem;
  rect: DOMRect;
  onClose: () => void;
  onInspect: (citation: CitationItem) => void;
}

export const NotebookLMCitationPopover: React.FC<CitationPopoverProps> = ({
  citation,
  rect,
  onClose,
  onInspect,
}) => {
  const [copied, setCopied] = useState(false);
  const isWeb =
    citation.breadcrumb === 'Web Search Fallback' ||
    citation.source?.startsWith('http') ||
    citation.type === 'web';

  const filename = citation.source ? citation.source.split('/').pop() : `Source [${citation.index}]`;
  const isRelevant = citation.score === 'yes';

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (citation.text) {
      navigator.clipboard.writeText(citation.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Clean excerpt text: remove raw [Context: ... > ...] prefix
  const cleanExcerpt = (raw?: string) => {
    if (!raw) return '';
    let t = raw.replace(/^\[Context:\s*[^\]]+\]\s*/gi, '');
    t = t.replace(/^tmp[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9]+)?\s*\n+/g, '');
    return t.trim();
  };

  const displayQuote = cleanExcerpt(citation.text);

  // Compute position relative to viewport
  const top = rect.top < 180 ? rect.bottom + 10 : Math.max(12, rect.top - 180);
  const left = Math.min(window.innerWidth - 380, Math.max(16, rect.left - 120));

  return (
    <div
      className="notebooklm-popover-container"
      style={{
        position: 'fixed',
        top: `${top}px`,
        left: `${left}px`,
        zIndex: 130,
      }}
      onMouseEnter={() => {}}
      onMouseLeave={onClose}
    >
      <div className="notebooklm-popover-card">
        {/* Header */}
        <div className="popover-header">
          <div className="popover-source-info">
            <span className={`source-type-icon ${isWeb ? 'web' : 'local'}`}>
              {isWeb ? <Globe size={13} /> : <FileText size={13} />}
            </span>
            <div className="source-title-group">
              <span className="source-index-pill">[{citation.index}]</span>
              <span className="source-filename" title={citation.source || filename}>
                {filename}
              </span>
            </div>
          </div>
          <span className={`popover-veracity-badge ${isRelevant ? 'verified' : 'filtered'}`}>
            {isRelevant ? <Check size={11} /> : <X size={11} />}
            <span>{isRelevant ? (isWeb ? 'Web Verified' : 'Verified') : 'Filtered Crux'}</span>
          </span>
        </div>

        {/* Section Breadcrumb */}
        {citation.breadcrumb && citation.breadcrumb !== 'Web Search Fallback' && (
          <div className="popover-breadcrumb" title={citation.breadcrumb}>
            <Layers size={11} className="text-muted" />
            <span className="popover-breadcrumb-text">{citation.breadcrumb}</span>
          </div>
        )}

        {/* Excerpt Body */}
        <div className="popover-quote-block">
          <div className="quote-accent-bar" />
          <p className="quote-text">
            {displayQuote
              ? `"${displayQuote.slice(0, 220).trim()}${displayQuote.length > 220 ? '...' : ''}"`
              : 'Verified grounded passage referenced by the synthesis pipeline.'}
          </p>
        </div>

        {/* Action Footer */}
        <div className="popover-footer">
          {citation.text && (
            <button type="button" className="popover-action-btn" onClick={handleCopy} title="Copy excerpt">
              {copied ? <Check size={12} className="text-moss" /> : <Copy size={12} />}
              <span>{copied ? 'Copied' : 'Copy Quote'}</span>
            </button>
          )}

          <button
            type="button"
            className="popover-action-btn primary"
            onClick={() => {
              onClose();
              onInspect(citation);
            }}
          >
            <span>Inspect Full Passage</span>
            <ExternalLink size={11} />
          </button>
        </div>
      </div>
    </div>
  );
};

interface SourcesDeckProps {
  msgId: string;
  citations: CitationItem[];
  activeHighlightId: string | null;
  onSelectSource: (citation: CitationItem) => void;
  onHoverSource: (index: number | null) => void;
}

export const NotebookLMSourcesDeck: React.FC<SourcesDeckProps> = ({
  msgId,
  citations,
  activeHighlightId,
  onSelectSource,
  onHoverSource,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  if (!citations || citations.length === 0) return null;

  const relevantCitations = citations.filter((c) => c.score === 'yes');
  const filteredCitations = citations.filter(
    (c) =>
      !searchTerm.trim() ||
      c.source?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.text?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.breadcrumb?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const hasWeb = citations.some(
    (c) => c.breadcrumb === 'Web Search Fallback' || c.source?.startsWith('http') || c.type === 'web'
  );

  return (
    <div className="notebooklm-sources-deck">
      {/* Tray Header */}
      <div className="sources-deck-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="deck-title-group">
          <div className={`deck-icon-badge ${hasWeb ? 'web' : 'local'}`}>
            {hasWeb ? <Globe size={13} /> : <BookOpen size={13} />}
          </div>
          <div className="deck-text-group">
            <span className="deck-main-title">
              {hasWeb ? 'Grounding Web Sources' : 'Verified Knowledge Grounding'}
            </span>
            <span className="deck-count-badge">
              {relevantCitations.length} of {citations.length} cited
            </span>
          </div>
        </div>
        <div className="deck-header-actions" onClick={(e) => e.stopPropagation()}>
          {isExpanded && citations.length > 3 && (
            <div className="deck-search-wrap">
              <Search size={11} className="text-muted" />
              <input
                type="text"
                placeholder="Filter sources..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="deck-search-input"
              />
            </div>
          )}
          <button
            type="button"
            className="deck-toggle-btn"
            onClick={() => setIsExpanded(!isExpanded)}
            title={isExpanded ? 'Collapse sources' : 'Expand sources'}
          >
            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {/* Tray Grid Cards */}
      {isExpanded && (
        <div className="sources-deck-grid">
          {filteredCitations.map((c, idx) => {
            const citNum = c.index || idx + 1;
            const cardId = `doc-card-${msgId}-${citNum}`;
            const isHighlighted = activeHighlightId === `${msgId}-${citNum}`;
            const isWeb =
              c.breadcrumb === 'Web Search Fallback' ||
              c.source?.startsWith('http') ||
              c.type === 'web';
            const filename = c.source ? c.source.split('/').pop() || c.source : `Chunk #${citNum}`;
            const isRelevant = c.score === 'yes';

            return (
              <div
                id={cardId}
                key={idx}
                className={`notebooklm-source-card ${isRelevant ? 'verified' : 'filtered'} ${
                  isHighlighted ? 'pulse-highlight' : ''
                }`}
                onClick={() => onSelectSource(c)}
                onMouseEnter={() => onHoverSource(citNum)}
                onMouseLeave={() => onHoverSource(null)}
              >
                <div className="card-top-row">
                  <div className="card-source-identity">
                    <span className="card-index-badge">[{citNum}]</span>
                    <span className="card-doc-name" title={c.source || filename}>
                      {filename}
                    </span>
                  </div>
                  <span className={`card-status-pill ${isRelevant ? 'pass' : 'fail'}`}>
                    {isRelevant ? <Check size={10} /> : <X size={10} />}
                    <span>{isRelevant ? (isWeb ? 'Web' : 'Verified') : 'Filtered'}</span>
                  </span>
                </div>

                {c.breadcrumb && c.breadcrumb !== 'Web Search Fallback' && (
                  <div className="card-breadcrumb" title={c.breadcrumb}>
                    {c.breadcrumb}
                  </div>
                )}

                {c.text && (
                  <p className="card-snippet-text">
                    {c.text.slice(0, 140).trim()}
                    {c.text.length > 140 ? '...' : ''}
                  </p>
                )}

                <div className="card-footer-action">
                  <span className="action-hint">Click to inspect excerpt & metadata</span>
                  <ExternalLink size={10} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

interface SourceModalProps {
  citation: CitationItem;
  onClose: () => void;
  onOpenViewer?: (source: string, text?: string) => void;
}

export const NotebookLMSourceModal: React.FC<SourceModalProps> = ({
  citation,
  onClose,
  onOpenViewer,
}) => {
  const [copied, setCopied] = useState(false);

  const isWeb =
    citation.breadcrumb === 'Web Search Fallback' ||
    citation.source?.startsWith('http') ||
    citation.type === 'web';
  const filename = citation.source ? citation.source.split('/').pop() || citation.source : 'Source Document';
  const isRelevant = citation.score === 'yes';

  const handleCopy = () => {
    if (citation.text) {
      navigator.clipboard.writeText(citation.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const cleanPassageText = (raw?: string) => {
    if (!raw) return '';
    let t = raw.replace(/^tmp[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9]+)?\s*\n+/g, '');
    t = t.replace(/(Slide\s+\d+:[^\n]+)\n+##\s+\1\n+/gi, '$1\n\n');
    return t.trim();
  };

  const displayText = cleanPassageText(citation.text);

  return (
    <div className="recall-modal-backdrop notebooklm-modal-backdrop" onClick={onClose}>
      <div
        className="recall-modal-card notebooklm-source-modal-card"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className={`modal-icon-badge ${isWeb ? 'web' : 'local'}`}>
              {isWeb ? <Globe size={18} /> : <FileText size={18} />}
            </div>
            <div className="modal-title-content">
              <div className="modal-title-row">
                <span className="modal-cit-index">[{citation.index || 1}]</span>
                <h3 className="modal-source-title" title={filename}>{filename}</h3>
              </div>
              <p className="modal-sub-label">
                {isWeb ? 'External Web Search Grounding' : 'Verified Knowledge Base Passage'}
              </p>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close modal">
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body-area">
          {/* Status & Metadata Badges */}
          <div className="source-meta-bar">
            <span className={`modal-status-badge ${isRelevant ? 'pass' : 'fail'}`}>
              {isRelevant ? <Check size={12} /> : <X size={12} />}
              <span>{isRelevant ? 'Used in Answer Synthesis' : 'Filtered as Crux / Low Relevance'}</span>
            </span>
            {citation.breadcrumb && (
              <span className="modal-meta-chip">
                <Layers size={11} />
                <span>{citation.breadcrumb}</span>
              </span>
            )}
            {citation.chunk_id && (
              <span className="modal-meta-chip font-mono">
                <span>ID: {citation.chunk_id.slice(0, 8)}</span>
              </span>
            )}
          </div>

          {/* Grader Rationale */}
          {citation.rationale && (
            <div className="modal-section-card rationale-card">
              <div className="section-card-header">
                <div className="section-header-left">
                  <Sparkles size={13} className="text-amber" />
                  <h4>Relevance & Faithfulness Evaluation:</h4>
                </div>
              </div>
              <p className="rationale-content">{citation.rationale}</p>
            </div>
          )}

          {/* Full Verified Passage */}
          {displayText && (
            <div className="modal-section-card passage-card">
              <div className="section-card-header">
                <div className="section-header-left">
                  <FileText size={13} className="text-teal" />
                  <h4>Grounded Document Passage:</h4>
                </div>
                <button type="button" className="copy-passage-btn" onClick={handleCopy}>
                  {copied ? <Check size={12} className="text-moss" /> : <Copy size={12} />}
                  <span>{copied ? 'Copied to Clipboard' : 'Copy Passage'}</span>
                </button>
              </div>
              <div className="passage-scroll-body">
                <pre className="passage-full-text">{displayText}</pre>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="modal-footer-area">
          <div className="modal-footer-left">
            {citation.source && onOpenViewer && !isWeb && (
              <button
                type="button"
                className="popover-action-btn primary"
                onClick={() => {
                  onClose();
                  onOpenViewer(citation.source!, citation.text);
                }}
              >
                <BookOpen size={12} />
                <span>Open Full Document Preview</span>
              </button>
            )}
            {isWeb && citation.source && (
              <a
                href={citation.source}
                target="_blank"
                rel="noreferrer"
                className="popover-action-btn"
              >
                <span>Visit Web Source</span>
                <ExternalLink size={11} />
              </a>
            )}
          </div>
          <button type="button" className="btn-secondary modal-done-btn" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
