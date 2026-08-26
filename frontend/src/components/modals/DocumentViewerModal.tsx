import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  FileText,
  Globe,
  X,
  Search,
  Copy,
  Check,
  Layers,
  ExternalLink,
  BookOpen,
  Loader2,
  Sparkles,
  ChevronUp,
  ChevronDown,
  Download,
} from 'lucide-react';

interface DocumentChunkItem {
  id: string;
  index: number;
  text: string;
  metadata?: Record<string, any>;
}

interface DocumentData {
  id?: string;
  filename: string;
  source_type?: string;
  source_url?: string;
  is_shared?: boolean;
  chunk_count?: number;
  full_text?: string;
  chunks?: DocumentChunkItem[];
}

interface DocumentViewerModalProps {
  sourceName: string;
  docId?: string;
  highlightText?: string;
  initialChunkIndex?: number;
  onClose: () => void;
  fetchWithAuth: (url: string, options?: RequestInit) => Promise<Response>;
}

export const DocumentViewerModal: React.FC<DocumentViewerModalProps> = ({
  sourceName,
  docId,
  highlightText,
  initialChunkIndex,
  onClose,
  fetchWithAuth,
}) => {
  const [docData, setDocData] = useState<DocumentData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState<'reader' | 'chunks'>('reader');
  const [copied, setCopied] = useState(false);
  const [activeMatchIndex, setActiveMatchIndex] = useState(0);
  const [selectedChunkIdx, setSelectedChunkIdx] = useState<number | null>(
    initialChunkIndex ?? null
  );

  const readerContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let isMounted = true;
    const fetchDoc = async () => {
      setLoading(true);
      setError(null);
      try {
        const queryParams = new URLSearchParams();
        queryParams.set('source', sourceName);
        if (docId) queryParams.set('doc_id', docId);

        const res = await fetchWithAuth(`/api/v1/documents/content?${queryParams.toString()}`);
        if (!res.ok) {
          throw new Error(`Failed to load document (${res.status})`);
        }
        const data = await res.json();
        if (isMounted) {
          setDocData(data);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || 'Could not load document content');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchDoc();
    return () => {
      isMounted = false;
    };
  }, [sourceName, docId]);

  // Clean raw strings and temporary path prefixes
  const cleanDisplayContent = (rawText?: string) => {
    if (!rawText) return '';
    let t = rawText.replace(/^tmp[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9]+)?\s*\n+/g, '');
    t = t.replace(/\[Context:\s*tmp[a-zA-Z0-9_-]+\.[a-zA-Z0-9]+\]\s*\n*/gi, '');
    return t.trim();
  };

  const displayText = useMemo(() => {
    return cleanDisplayContent(docData?.full_text || '');
  }, [docData?.full_text]);

  const cleanHighlight = useMemo(() => {
    return cleanDisplayContent(highlightText || '');
  }, [highlightText]);

  // Count search occurrences in text
  const searchMatches = useMemo(() => {
    if (!searchTerm.trim() || !displayText) return [];
    const term = searchTerm.toLowerCase();
    const matches: number[] = [];
    let pos = 0;
    const lower = displayText.toLowerCase();
    while ((pos = lower.indexOf(term, pos)) !== -1) {
      matches.push(pos);
      pos += term.length;
    }
    return matches;
  }, [searchTerm, displayText]);

  // Scroll to active search match
  useEffect(() => {
    if (searchMatches.length > 0 && readerContainerRef.current) {
      const marks = readerContainerRef.current.querySelectorAll('.doc-search-mark');
      if (marks[activeMatchIndex]) {
        marks[activeMatchIndex].scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [activeMatchIndex, searchMatches]);

  const handleNextMatch = () => {
    if (searchMatches.length === 0) return;
    setActiveMatchIndex((prev) => (prev + 1) % searchMatches.length);
  };

  const handlePrevMatch = () => {
    if (searchMatches.length === 0) return;
    setActiveMatchIndex((prev) => (prev - 1 + searchMatches.length) % searchMatches.length);
  };

  const handleCopy = (textToCopy?: string) => {
    const text = textToCopy || displayText || cleanHighlight || '';
    if (text) {
      navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownload = () => {
    const text = displayText || cleanHighlight || '';
    if (!text) return;
    const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${sourceName.split('/').pop() || 'document'}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const isWeb =
    sourceName.startsWith('http') ||
    docData?.source_type === 'url' ||
    docData?.source_url?.startsWith('http');

  const filename = sourceName.split('/').pop() || sourceName;

  // Filter chunks if searching
  const filteredChunks = useMemo(() => {
    return (docData?.chunks || []).filter((c) =>
      !searchTerm.trim()
        ? true
        : c.text.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [docData?.chunks, searchTerm]);

  // Highlight matches inside reader pre block
  const renderHighlightedReaderText = () => {
    if (!searchTerm.trim()) {
      return displayText || 'No text content available.';
    }

    const term = searchTerm;
    const regex = new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    const parts = displayText.split(regex);
    let matchCounter = 0;

    return parts.map((part, i) => {
      if (part.toLowerCase() === term.toLowerCase()) {
        const isCurrent = matchCounter === activeMatchIndex;
        matchCounter++;
        return (
          <mark
            key={i}
            className={`doc-search-mark ${isCurrent ? 'current' : ''}`}
          >
            {part}
          </mark>
        );
      }
      return part;
    });
  };

  return (
    <div className="recall-modal-backdrop document-viewer-backdrop" onClick={onClose}>
      <div
        className="recall-modal-card document-viewer-modal-card"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header doc-viewer-header">
          <div className="modal-title-wrap">
            <div className={`modal-icon-badge ${isWeb ? 'web' : 'local'}`}>
              {isWeb ? <Globe size={18} /> : <FileText size={18} />}
            </div>
            <div className="modal-title-content">
              <div className="modal-title-row">
                <h3 className="modal-source-title" title={sourceName}>
                  {filename}
                </h3>
                {docData?.is_shared && <span className="shared-badge">Org Shared</span>}
              </div>
              <p className="modal-sub-label">
                {isWeb ? 'External Web Grounding Source' : 'Knowledge Base Document Preview'}
                {docData?.chunk_count ? ` · ${docData.chunk_count} indexed chunks` : ''}
              </p>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close document viewer">
            <X size={18} />
          </button>
        </div>

        {/* Toolbar & Search Bar */}
        <div className="doc-viewer-toolbar">
          <div className="doc-tab-buttons">
            <button
              type="button"
              className={`doc-tab-btn ${activeTab === 'reader' ? 'active' : ''}`}
              onClick={() => setActiveTab('reader')}
            >
              <BookOpen size={13} />
              <span>Full Document Reader</span>
            </button>
            <button
              type="button"
              className={`doc-tab-btn ${activeTab === 'chunks' ? 'active' : ''}`}
              onClick={() => setActiveTab('chunks')}
            >
              <Layers size={13} />
              <span>Indexed Chunks ({docData?.chunks?.length || 0})</span>
            </button>
          </div>

          <div className="doc-viewer-search-wrapper">
            <div className="doc-viewer-search">
              <Search size={13} className="text-muted search-icon" />
              <input
                type="text"
                placeholder="Search in document..."
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setActiveMatchIndex(0);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    if (e.shiftKey) handlePrevMatch();
                    else handleNextMatch();
                  }
                }}
                className="doc-search-input"
              />
              {searchTerm && (
                <div className="doc-search-actions">
                  <span className="doc-search-count">
                    {searchMatches.length > 0
                      ? `${activeMatchIndex + 1}/${searchMatches.length}`
                      : '0 found'}
                  </span>
                  <button
                    type="button"
                    className="doc-nav-btn"
                    onClick={handlePrevMatch}
                    title="Previous match (Shift+Enter)"
                    disabled={searchMatches.length === 0}
                  >
                    <ChevronUp size={12} />
                  </button>
                  <button
                    type="button"
                    className="doc-nav-btn"
                    onClick={handleNextMatch}
                    title="Next match (Enter)"
                    disabled={searchMatches.length === 0}
                  >
                    <ChevronDown size={12} />
                  </button>
                  <button
                    type="button"
                    className="doc-search-clear"
                    onClick={() => {
                      setSearchTerm('');
                      setActiveMatchIndex(0);
                    }}
                    title="Clear search"
                  >
                    <X size={11} />
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Body Content */}
        <div className="modal-body-area doc-viewer-body" ref={readerContainerRef}>
          {loading && (
            <div className="doc-viewer-loading">
              <Loader2 size={26} className="spin-slow text-accent" />
              <span>Loading document context & pgvector chunks...</span>
            </div>
          )}

          {!loading && error && (
            <div className="doc-viewer-error">
              <FileText size={24} className="text-rust" />
              <h4>Preview Note</h4>
              <p>{error}</p>
              {cleanHighlight && (
                <div className="fallback-excerpt-box">
                  <span className="fallback-excerpt-label">Referenced Citation Passage:</span>
                  <pre className="fallback-excerpt-text">{cleanHighlight}</pre>
                </div>
              )}
            </div>
          )}

          {!loading && !error && activeTab === 'reader' && (
            <div className="doc-reader-container">
              {cleanHighlight && (
                <div className="referenced-highlight-banner">
                  <div className="highlight-banner-header">
                    <Sparkles size={13} className="text-amber" />
                    <span>Active Grounded Passage referenced by Ridge synthesis:</span>
                  </div>
                  <pre className="highlight-banner-text">{cleanHighlight}</pre>
                </div>
              )}

              <div className="doc-reader-text-wrapper">
                <pre className="doc-full-text-content">
                  {renderHighlightedReaderText()}
                </pre>
              </div>
            </div>
          )}

          {!loading && !error && activeTab === 'chunks' && (
            <div className="doc-chunks-list">
              {filteredChunks.map((chunk) => (
                <div
                  key={chunk.id || chunk.index}
                  className={`doc-chunk-card ${
                    selectedChunkIdx === chunk.index ? 'active' : ''
                  }`}
                  onClick={() => setSelectedChunkIdx(chunk.index)}
                >
                  <div className="chunk-card-header">
                    <span className="chunk-index-badge">Chunk #{chunk.index + 1}</span>
                    <button
                      type="button"
                      className="chunk-copy-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCopy(chunk.text);
                      }}
                      title="Copy chunk"
                    >
                      <Copy size={12} />
                    </button>
                  </div>
                  <p className="chunk-card-text">{chunk.text}</p>
                </div>
              ))}
              {filteredChunks.length === 0 && (
                <div className="doc-chunks-empty">
                  <span>No chunks matched "{searchTerm}"</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer-area doc-viewer-footer">
          <div className="modal-footer-left">
            <button
              type="button"
              className="popover-action-btn primary"
              onClick={() => handleCopy()}
            >
              {copied ? <Check size={12} className="text-moss" /> : <Copy size={12} />}
              <span>{copied ? 'Copied to Clipboard' : 'Copy All Text'}</span>
            </button>
            <button
              type="button"
              className="popover-action-btn"
              onClick={handleDownload}
              title="Download full document as Markdown"
            >
              <Download size={12} />
              <span>Download (.md)</span>
            </button>
            {docData?.source_url && (
              <a
                href={docData.source_url}
                target="_blank"
                rel="noreferrer"
                className="popover-action-btn"
              >
                <span>Open URL</span>
                <ExternalLink size={11} />
              </a>
            )}
          </div>
          <button type="button" className="btn-secondary modal-done-btn" onClick={onClose}>
            Close Preview
          </button>
        </div>
      </div>
    </div>
  );
};
