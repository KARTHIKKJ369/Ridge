import React, { useState, useRef, useEffect, useImperativeHandle } from 'react';
import { useNavigate } from 'react-router-dom';
import { FeedbackModal, type FeedbackTargetContext } from './components/FeedbackModal';
import { 
  User, 
  Activity, 
  CheckCircle, 
  RotateCw, 
  X, 
  Plus, 
  Upload, 
  FileText, 
  Globe, 
  Copy, 
  Check, 
  Trash2, 
  Database, 
  Sparkles, 
  ChevronRight, 
  ChevronDown, 
  BookOpen, 
  PanelLeft, 
  PanelLeftClose, 
  ThumbsUp, 
  ThumbsDown, 
  Download, 
  Search, 
  MessageSquare, 
  AlertCircle,

  Command, 
  Zap, 
  ShieldCheck, 
  Shield,
  Users,
  Sliders,
  UserCheck,
  UserX,
  Crown,
  Edit3,
  Paperclip,
  ArrowUp,
  LogOut,
  LogIn,
  Mail,
  Key,
  Square,
  Video,
  Image,
  Code,
  AlertTriangle,
  Layers,
  Building2,
  UserPlus,
  Eye,
  EyeOff
} from 'lucide-react';


import { AuthModal } from './components/AuthModal';
import { MarkdownRenderer, markdownToReportHtml } from './components/markdown/MarkdownRenderer';
import {
  NotebookLMCitationPopover,
  NotebookLMSourcesDeck,
  NotebookLMSourceModal,
} from './components/chat/NotebookLMCitations';
import './App.css';


// Symmetrical Mountain Summit & Neural Ridge Emblem
const RidgeLogo = ({ size = 22, className = '' }: { size?: number; className?: string }) => (
  <svg 
    width={size} 
    height={size} 
    viewBox="0 0 32 32" 
    fill="none" 
    xmlns="http://www.w3.org/2000/svg"
    className={`recall-emblem ${className}`}
  >
    <defs>
      <linearGradient id="crag-logo-bg" x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#1E293B" />
        <stop offset="100%" stopColor="#0F172A" />
      </linearGradient>
      <linearGradient id="summit-left-slope" x1="6" y1="24" x2="16" y2="8" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0284C7" />
        <stop offset="100%" stopColor="#38BDF8" />
      </linearGradient>
      <linearGradient id="summit-right-slope" x1="16" y1="8" x2="26" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#F97316" />
        <stop offset="100%" stopColor="#EA580C" />
      </linearGradient>
    </defs>
    {/* Outer Rounded Squircle Frame */}
    <rect x="2" y="2" width="28" height="28" rx="8" fill="url(#crag-logo-bg)" stroke="#334155" strokeWidth="1" />
    
    {/* Symmetrical Mountain Peak: Left (Summit Blue) & Right (Terracotta Rust) */}
    <polygon points="16,8 6,24 16,24" fill="url(#summit-left-slope)" />
    <polygon points="16,8 16,24 26,24" fill="url(#summit-right-slope)" />
    
    {/* Center Summit Ridge Line */}
    <line x1="16" y1="8" x2="16" y2="24" stroke="#FFFFFF" strokeWidth="1" strokeLinecap="round" />
    
    {/* Snowcap Top Triangle */}
    <polygon points="16,8 12.5,14 16,12.5 19.5,14" fill="#FFFFFF" />
    
    {/* High Altitude Beacon */}
    <circle cx="16" cy="6" r="1.5" fill="#38BDF8" stroke="#FFFFFF" strokeWidth="0.75" />
  </svg>
);

type ConfidenceMetric = {
  score: number;
  level: 'HIGH' | 'MEDIUM' | 'LOW';
  breakdown: {
    grader_consensus: number;
    source_trust: string;
    relevant_chunks: number;
    reformulation_loops: number;
    faithfulness?: string;
  };
};

type ConflictPassage = {
  source: string;
  name: string;
  text: string;
  rationale?: string;
};

type ConflictData = {
  detected: boolean;
  summary: string;
  sources: string[];
  passages?: ConflictPassage[];
};

type UploadQueueItem = {
  file: File;
  id: string;
  status: 'waiting' | 'uploading' | 'completed' | 'error';
  error?: string;
  chunksAdded?: number;
};

type TraceEvent = {
  node: string;
  message: string;
  timestamp?: string;
  documents?: string[];
  doc_grades?: any[];
  answer?: string;
  confidence?: ConfidenceMetric;
  conflict_data?: ConflictData;
  latency_ms?: number;
  sub_queries?: string[];
  expanded_count?: number;
};

type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  traces?: TraceEvent[];
  confidence?: ConfidenceMetric;
  conflict_data?: ConflictData;
  isStreaming?: boolean;
  timestamp?: string;
  liked?: boolean | null;
};

type GlossaryItem = {
  term: string;
  expansion: string;
  source: string;
};

type ChatSession = {
  id: string;
  title: string;
  createdAt: number;
  messages: Message[];
};

type ThemeMode = 'void' | 'stone' | 'rust';

type UserProfile = {
  id: string;
  username?: string;
  name: string;
  email: string;
  avatar_url?: string;
  provider?: string;
  is_guest?: boolean;
  role?: string;
  tenant_id?: string;
  tenant_name?: string;
  tenant_slug?: string;
  is_active?: boolean;
  daily_request_limit?: number;
  requests_today?: number;
};


type AdminUser = {
  id: string;
  username: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  daily_request_limit: number;
  created_at: number;
  requests_today: number;
  tenant_id?: string;
  tenant_name?: string;
  tenant_slug?: string;
};

type AdminStats = {
  total_users: number;
  active_users: number;
  total_requests_today: number;
  total_documents: number;
  total_chunks: number;
  tenant_id?: string;
  tenant_name?: string;
  tenant_slug?: string;
  is_superadmin?: boolean;
};

type TenantItem = {
  id: string;
  name: string;
  slug: string;
  is_active?: boolean;
  max_users?: number;
  user_count?: number;
  doc_count?: number;
  member_count?: number;
  document_count?: number;
};



// ---------------------------------------------------------------------------
// Per-User Scoped Session Helpers
// ---------------------------------------------------------------------------

const getUserSessionStorageKey = (u: UserProfile | null) => {
  if (!u || u.is_guest) return 'ridge_sessions_guest';
  return `ridge_sessions_${u.id || u.username || 'user'}`;
};

const createFreshSession = (): ChatSession => ({


  id: Date.now().toString(),
  title: 'New Research Ascent',
  createdAt: Date.now(),
  messages: []
});

const loadUserSessions = (u: UserProfile | null): ChatSession[] => {
  const key = getUserSessionStorageKey(u);
  try {
    const saved = localStorage.getItem(key);
    if (saved) {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed;
      }
    }
    // Migration from legacy global key if present
    const legacy = localStorage.getItem('recall_crag_sessions');
    if (legacy && (!u || u.is_guest)) {
      try {
        const parsedLegacy = JSON.parse(legacy);
        if (Array.isArray(parsedLegacy) && parsedLegacy.length > 0) {
          localStorage.removeItem('recall_crag_sessions');
          localStorage.setItem(key, JSON.stringify(parsedLegacy));
          return parsedLegacy;
        }
      } catch {}
    }
  } catch (e) {
    console.error('Failed to load user sessions:', e);
  }
  return [createFreshSession()];
};

type AuthConfig = {
  enabled: boolean;
  providers: {
    github: boolean;
    google: boolean;
  };
};

export interface KBSource {
  source: string;
  name: string;
  type: string;
  h1: string;
  chunk_count: number;
  sample: string;
  ids: string[];
}

const DEFAULT_SUGGESTIONS = [
  "Summarize the key findings and core concepts across the indexed documents.",
  "What are the main methodologies and step-by-step implementations described?",
  "Audit the knowledge base for contradictory claims or edge cases."
];

const getNodeDetails = (nodeName: string): { title: string; desc: string; icon: React.ReactNode; color: string } => {
  switch (nodeName) {
    case 'cache_hit_node':
      return {
        title: 'Semantic Query Cache',
        desc: 'Direct sub-millisecond retrieval from verified vector cache',
        icon: <Zap size={13} />,
        color: 'moss'
      };
    case 'decompose_node':
      return {
        title: 'Query Decomposition',
        desc: 'Multi-hop compound question splitter with parallel retrieval',
        icon: <Layers size={13} />,
        color: 'indigo'
      };
    case 'retrieve_node':
      return { 
        title: 'Hybrid Retrieval', 
        desc: 'Dense Chroma HNSW + Sparse BM25 with RRF & FlashRank', 
        icon: <Search size={13} />, 
        color: 'teal' 
      };
    case 'grade_node':
      return { 
        title: 'Relevance Grading', 
        desc: 'Strict Groq LLM hallucination and veracity evaluation', 
        icon: <ShieldCheck size={13} />, 
        color: 'rust' 
      };
    case 'web_search_node':
      return { 
        title: 'Web Search Fallback', 
        desc: 'DuckDuckGo knowledge search and retrieval', 
        icon: <Globe size={13} />, 
        color: 'amber' 
      };
    case 'rewrite_node':
      return { 
        title: 'Query Reformulation', 
        desc: 'Adaptive query rewriting for high-precision recall', 
        icon: <Edit3 size={13} />, 
        color: 'moss' 
      };
    case 'generate_node':
      return { 
        title: 'Answer Synthesis', 
        desc: 'Grounded generation from verified context', 
        icon: <Sparkles size={13} />, 
        color: 'summit' 
      };
    case 'check_hallucination_node':
      return { 
        title: 'Hallucination Auditor', 
        desc: 'Post-generation grounding and veracity verification', 
        icon: <ShieldCheck size={13} />, 
        color: 'moss' 
      };
    default:
      return { 
        title: nodeName, 
        desc: 'Pipeline state executed', 
        icon: <Zap size={13} />, 
        color: 'slate' 
      };
  }
};

interface ChatMessageItemProps {
  msg: Message;
  isExpanded: boolean;
  activeCitationHighlight: string | null;
  copiedId: string | null;
  onToggleThinking: (id: string) => void;
  onSelectConflict: (conflict: ConflictData) => void;
  onSelectSource: (source: any) => void;
  onCopy: (content: string, id: string) => void;
  onReaction: (id: string, liked: boolean) => void;
  onHoverCitation: (hover: { msgId: string; index: number; target?: any; rect: DOMRect } | null) => void;
  onHighlightCitation: (highlight: string | null) => void;
  onFileClick: (path: string) => void;
  onOpenFeedback?: (msg: Message) => void;
}


const ChatMessageItem = React.memo(({
  msg,
  isExpanded,
  activeCitationHighlight,
  copiedId,
  onToggleThinking,
  onSelectConflict,
  onSelectSource,
  onCopy,
  onReaction,
  onHoverCitation,
  onHighlightCitation,
  onFileClick,
  onOpenFeedback,
}: ChatMessageItemProps) => {

  const isAssistant = msg.role === 'assistant';
  const msgTraces = msg.traces || [];
  const latestTraceWithGrades = [...msgTraces].reverse().find(t => t.doc_grades && t.doc_grades.length > 0);
  const msgGrades: any[] = latestTraceWithGrades?.doc_grades || [];
  const totalPipelineLatency = msgTraces.reduce((sum, t) => sum + (t.latency_ms || 0), 0);

  return (
    <div className={`message-container ${msg.role}`}>
      <div className="message-inner">
        {/* Avatar */}
        <div className="message-avatar-wrap">
          {isAssistant ? (
            <div className={`assistant-avatar ${msg.isStreaming ? 'streaming-spin' : ''}`}>
              <RidgeLogo size={22} />
            </div>
          ) : (
            <div className="user-avatar">
              <User size={16} />
            </div>
          )}
        </div>

        {/* Content Body */}
        <div className="message-content-box">
          <div className="message-meta-row">
            <span className="author-name">{isAssistant ? 'Ridge' : 'You'}</span>
            {msg.timestamp && <span className="message-time">{msg.timestamp}</span>}
          </div>

          {/* State Machine Thinking Accordion */}
          {isAssistant && msgTraces.length > 0 && (
            <div className="recall-thinking-block">
              <button 
                className="thinking-toggle-bar"
                onClick={() => onToggleThinking(msg.id)}
                aria-expanded={isExpanded}
              >
                <div className="thinking-left">
                  <RotateCw size={13} className={msg.isStreaming ? 'spin-slow text-teal' : 'text-muted'} />
                  <span className="thinking-title">
                    {msg.isStreaming ? 'Synthesizing with CRAG state machine...' : `Pipeline Ascent (${msgTraces.length} steps executed)`}
                  </span>
                </div>
                <div className="thinking-right">
                  {totalPipelineLatency > 0 && !msg.isStreaming && (
                    <span className="latency-badge">{totalPipelineLatency}ms</span>
                  )}
                  {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </div>
              </button>

              {isExpanded && (
                <div className="thinking-content-tree">
                  {msgTraces.map((trace, idx) => {
                    const nodeDetails = getNodeDetails(trace.node);
                    return (
                      <div key={idx} className="thinking-node-item">
                        <div className="node-marker-col">
                          <div className={`node-dot ${nodeDetails.color}`} />
                          {idx < msgTraces.length - 1 && <div className="node-connector-line" />}
                        </div>
                        <div className="node-info-col">
                          <div className="node-header-line">
                            <span className="node-tag-name">
                              <span className="node-icon-inline">{nodeDetails.icon}</span>
                              {nodeDetails.title}
                            </span>
                            {trace.latency_ms != null && (
                              <span className="node-lat">{trace.latency_ms}ms</span>
                            )}
                          </div>
                          <p className="node-msg-text">{trace.message}</p>
                          {trace.node === 'decompose_node' && trace.sub_queries && trace.sub_queries.length > 1 && (
                            <div className="sub-query-pills">
                              {trace.sub_queries.map((sq: string, qi: number) => (
                                <span key={qi} className="sub-query-pill">
                                  <span className="sub-query-pill-num">{qi + 1}</span>
                                  {sq}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Multi-Document Conflict Alert Banner */}
          {isAssistant && msg.conflict_data?.detected && (
            <div className="conflict-alert-banner">
              <div className="conflict-banner-header">
                <div className="conflict-banner-title-group">
                  <AlertTriangle size={15} className="text-rust" />
                  <span className="conflict-banner-title">Document Conflict Detected</span>
                </div>
                <button
                  type="button"
                  className="conflict-compare-btn"
                  onClick={() => onSelectConflict(msg.conflict_data!)}
                >
                  <Layers size={13} />
                  <span>Compare Sources</span>
                </button>
              </div>
              <p className="conflict-banner-desc">
                {msg.conflict_data.summary || 'Multiple indexed documents present conflicting statements or policies on this question.'}
              </p>
              {msg.conflict_data.sources && msg.conflict_data.sources.length > 0 && (
                <div className="conflict-sources-row">
                  <span className="conflict-sources-label">Conflicting Sources:</span>
                  {msg.conflict_data.sources.map((src, i) => (
                    <span key={i} className="conflict-source-tag">{src}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Markdown Text */}
          {msg.content ? (
            <div className="recall-markdown-body">
              <MarkdownRenderer
                content={msg.content}
                citations={msgGrades}
                highlightedCitationIndex={activeCitationHighlight ? parseInt(activeCitationHighlight.split('-')[1], 10) : null}
                onCitationClick={(c) => onSelectSource(c)}
                onFileClick={onFileClick}
                onCitationHover={(c, rect) => {
                  if (c && rect) {
                    onHoverCitation({
                      msgId: msg.id,
                      index: c.index,
                      target: c,
                      rect,
                    });
                  } else {
                    onHoverCitation(null);
                  }
                }}
              />

            </div>
          ) : (
            msg.isStreaming && (
              <div className="recall-shimmer-loader">
                <div className="shimmer-pulse-dot" />
                <div className="shimmer-pulse-dot" />
                <div className="shimmer-pulse-dot" />
                <span>Evaluating context and generating verified answer...</span>
              </div>
            )
          )}

          {/* NotebookLM Grounding Sources Deck */}
          {isAssistant && msgGrades.length > 0 && (
            <NotebookLMSourcesDeck
              msgId={msg.id}
              citations={msgGrades}
              activeHighlightId={activeCitationHighlight}
              onSelectSource={(c) => onSelectSource(c)}
              onHoverSource={(idx) => {
                if (idx !== null) {
                  onHighlightCitation(`${msg.id}-${idx}`);
                } else {
                  onHighlightCitation(null);
                }
              }}
            />
          )}


          {/* Grounded Confidence Scorecard & Badge */}
          {isAssistant && msg.confidence && (
            <div className="confidence-metric-container">
              <div className={`confidence-badge-pill ${msg.confidence.level.toLowerCase()}`}>
                <span className="confidence-dot" />
                <span className="confidence-percent">{msg.confidence.score}%</span>
                <span className="confidence-text">
                  {msg.confidence.level === 'HIGH' ? 'High Grounded Confidence' : (msg.confidence.level === 'MEDIUM' ? 'Moderate Confidence' : 'Low Context Confidence')}
                </span>
              </div>
              <div className="confidence-meta-chips">
                <span className="meta-chip">
                  <span className="chip-label">Source:</span> {msg.confidence.breakdown.source_trust}
                </span>
                <span className="meta-chip">
                  <span className="chip-label">Grader Pass:</span> {msg.confidence.breakdown.grader_consensus}%
                </span>
                {msg.confidence.breakdown.faithfulness && (
                  <span className="meta-chip">
                    <span className="chip-label">Faithfulness:</span> {msg.confidence.breakdown.faithfulness}
                  </span>
                )}
                {msg.confidence.breakdown.reformulation_loops > 0 && (
                  <span className="meta-chip">
                    <span className="chip-label">Query Rewrites:</span> {msg.confidence.breakdown.reformulation_loops}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Assistant Message Action Bar in Grouped Pill Container */}
          {isAssistant && msg.content && (
            <div className="message-action-footer">
              <div className="action-pill-container">
                <button 
                  className="msg-action-btn"
                  onClick={() => onCopy(msg.content, msg.id)}
                  title="Copy response"
                  aria-label="Copy response"
                >
                  {copiedId === msg.id ? <Check size={14} className="text-moss" /> : <Copy size={14} />}
                  <span>{copiedId === msg.id ? 'Copied' : 'Copy'}</span>
                </button>

                <button 
                  className={`msg-action-btn ${msg.liked === true ? 'active-like' : ''}`}
                  onClick={() => onReaction(msg.id, true)}
                  title="Helpful ascent"
                  aria-label="Helpful response"
                >
                  <ThumbsUp size={14} />
                </button>

                <button 
                  className={`msg-action-btn ${msg.liked === false ? 'active-dislike' : ''}`}
                  onClick={() => onReaction(msg.id, false)}
                  title="Crux or inaccuracy encountered"
                  aria-label="Crux or inaccuracy encountered"
                >
                  <ThumbsDown size={14} />
                </button>
              </div>

              {/* Inline Feedback Suggestion Card when Thumbs Down is clicked */}
              {msg.liked === false && (
                <div className="feedback-inline-suggestion">
                  <div className="feedback-inline-info">
                    <AlertCircle size={13} className="feedback-inline-icon" />
                    <span>Report inaccuracy or issue with this answer?</span>
                  </div>
                  <button
                    className="feedback-inline-btn"
                    onClick={() => onOpenFeedback?.(msg)}
                    type="button"
                    title="Send specific feedback on this answer to administrators"
                  >
                    <MessageSquare size={12} />
                    <span>Send Feedback to Admin</span>
                  </button>
                </div>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
});

export interface ChatInputDeckRef {
  setValue: (val: string) => void;
  focus: () => void;
}

interface ChatInputDeckProps {
  isLoading: boolean;
  onSend: (query: string) => void;
  onStop: () => void;
  onAttachFile: (e: React.ChangeEvent<HTMLInputElement>) => void;
  selectedSourceFilter: string;
  onSelectSourceFilter: (source: string) => void;
  kbSources: KBSource[];
  onFetchKBSources: () => void;
  webSearchEnabled: boolean;
  onToggleWebSearch: () => void;
}

const ChatInputDeck = React.forwardRef<ChatInputDeckRef, ChatInputDeckProps>(({
  isLoading,
  onSend,
  onStop,
  onAttachFile,
  selectedSourceFilter,
  onSelectSourceFilter,
  kbSources,
  onFetchKBSources,
  webSearchEnabled,
  onToggleWebSearch,
}, ref) => {
  const [localInput, setLocalInput] = useState('');
  const [showSlashMenu, setShowSlashMenu] = useState(false);
  const [showSourceFilterMenu, setShowSourceFilterMenu] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const chatAttachRef = useRef<HTMLInputElement>(null);

  useImperativeHandle(ref, () => ({
    setValue: (val: string) => {
      setLocalInput(val);
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
        if (val) {
          textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
        }
      }
    },
    focus: () => {
      textareaRef.current?.focus();
    }
  }), []);

  // Click-outside listener for menus inside deck
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.source-scope-filter-container')) {
        setShowSourceFilterMenu(false);
      }
      if (!target.closest('.prompts-trigger-btn') && !target.closest('.slash-menu-popover')) {
        setShowSlashMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setLocalInput(val);
    const target = e.target;
    target.style.height = 'auto';
    target.style.height = `${Math.min(target.scrollHeight, 180)}px`;
    if (val.startsWith('/')) {
      setShowSlashMenu(true);
    } else if (showSlashMenu) {
      setShowSlashMenu(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (localInput.trim() && !isLoading) {
        const query = localInput.trim();
        setLocalInput('');
        if (textareaRef.current) {
          textareaRef.current.style.height = 'auto';
        }
        setShowSlashMenu(false);
        onSend(query);
      }
    }
  };

  const handleSendClick = () => {
    if (localInput.trim() && !isLoading) {
      const query = localInput.trim();
      setLocalInput('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
      setShowSlashMenu(false);
      onSend(query);
    }
  };

  return (
    <div className="recall-input-deck">
      {/* Slash Commands Dropup */}
      {showSlashMenu && (
        <div className="slash-menu-popover">
          <div className="slash-menu-header">
            <Command size={13} />
            <span>Quick Inquiries and Actions</span>
          </div>
          <button 
            type="button"
            className="slash-menu-item"
            onClick={() => {
              setLocalInput("Summarize the key findings across all indexed documents.");
              setShowSlashMenu(false);
              textareaRef.current?.focus();
            }}
          >
            <Sparkles size={14} className="text-teal" />
            <div className="slash-item-meta">
              <span className="slash-label">/summarize</span>
              <span className="slash-desc">Generate comprehensive summary across indexed chunks</span>
            </div>
          </button>

          <button 
            type="button"
            className="slash-menu-item"
            onClick={() => {
              setLocalInput("Audit all sources for contradictory claims or hallucinations.");
              setShowSlashMenu(false);
              textareaRef.current?.focus();
            }}
          >
            <ShieldCheck size={14} className="text-moss" />
            <div className="slash-item-meta">
              <span className="slash-label">/verify</span>
              <span className="slash-desc">Check veracity and contrast retrieved documents</span>
            </div>
          </button>

          <button 
            type="button"
            className="slash-menu-item"
            onClick={() => {
              setLocalInput("Extract all step-by-step methodologies mentioned in the knowledge base.");
              setShowSlashMenu(false);
              textareaRef.current?.focus();
            }}
          >
            <BookOpen size={14} className="text-rust" />
            <div className="slash-item-meta">
              <span className="slash-label">/methodology</span>
              <span className="slash-desc">Synthesize actionable implementation steps</span>
            </div>
          </button>
        </div>
      )}

      <div className={`recall-input-card ${isLoading ? 'is-loading' : ''}`}>
        <textarea
          ref={textareaRef}
          className="recall-textarea"
          placeholder="Ask anything about your documents, or type / for prompts..."
          value={localInput}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={isLoading}
        />

        <div className="input-toolbar-row">
          <div className="toolbar-left">
            {/* File Attachment Button */}
            <input 
              type="file" 
              ref={chatAttachRef} 
              onChange={onAttachFile}
              accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.pptx,.xlsx,.csv,.md,.txt,.py,.js,.ts,.json"
              style={{ display: 'none' }}
            />
            <button 
              type="button"
              className="toolbar-btn attach-btn"
              onClick={() => chatAttachRef.current?.click()}
              title="Attach document or media to index into Crag"
              aria-label="Attach file"
            >
              <Paperclip size={14} />
              <span>Attach</span>
            </button>

            {/* Source Scoped Metadata Filter Dropdown */}
            <div className="source-scope-filter-container">
              <button
                type="button"
                className={`toolbar-btn source-scope-btn ${selectedSourceFilter !== 'all' ? 'active' : ''}`}
                onClick={() => {
                  setShowSourceFilterMenu(!showSourceFilterMenu);
                  if (kbSources.length === 0) onFetchKBSources();
                }}
                title={selectedSourceFilter === 'all' ? "Filtering across all indexed documents (click to scope to a specific document)" : `Scoped strictly to: ${selectedSourceFilter}`}
                aria-label="Scope retrieval to specific document"
              >
                <Database size={13} className="source-scope-icon" />
                <span className="source-scope-label">
                  {selectedSourceFilter === 'all'
                    ? 'All Sources'
                    : (kbSources.find(s => s.source === selectedSourceFilter)?.name || selectedSourceFilter.split('/').pop())}
                </span>
                <ChevronDown size={11} className="source-scope-chevron" />
              </button>

              {showSourceFilterMenu && (
                <div className="source-scope-menu-dropdown">
                  <div className="source-scope-menu-header">Scope Retrieval</div>
                  <button
                    type="button"
                    className={`source-scope-menu-item ${selectedSourceFilter === 'all' ? 'selected' : ''}`}
                    onClick={() => {
                      onSelectSourceFilter('all');
                      setShowSourceFilterMenu(false);
                    }}
                  >
                    <span className="source-scope-radio-check">{selectedSourceFilter === 'all' ? '✓' : ''}</span>
                    <span className="source-scope-item-title">All Sources (Global Corpus)</span>
                    <span className="source-scope-item-meta">{kbSources.reduce((sum, s) => sum + s.chunk_count, 0)} chunks</span>
                  </button>

                  <div className="source-scope-menu-divider" />

                  {kbSources.length === 0 ? (
                    <div className="source-scope-menu-empty">No indexed documents found</div>
                  ) : (
                    kbSources.map((s, idx) => (
                      <button
                        key={idx}
                        type="button"
                        className={`source-scope-menu-item ${selectedSourceFilter === s.source ? 'selected' : ''}`}
                        onClick={() => {
                          onSelectSourceFilter(s.source);
                          setShowSourceFilterMenu(false);
                        }}
                      >
                        <span className="source-scope-radio-check">{selectedSourceFilter === s.source ? '✓' : ''}</span>
                        <span className="source-scope-item-title" title={s.source}>{s.name}</span>
                        <span className="source-scope-item-meta">{s.chunk_count} chunks</span>
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>

            {/* Web Search Fallback Mode Toggle */}
            <button 
              type="button"
              className={`toolbar-btn fallback-toggle-chip ${webSearchEnabled ? 'active' : ''}`}
              onClick={onToggleWebSearch}
              title={webSearchEnabled ? "Web fallback enabled when knowledge base recall is low (click to disable)" : "Web fallback disabled — queries will strictly stay within local documents (click to enable)"}
              aria-label="Toggle web search fallback"
            >
              <Globe size={13} className="fallback-chip-icon" />
              <span>Web Search</span>
              <span className={`fallback-status-dot ${webSearchEnabled ? 'on' : 'off'}`} />
            </button>

            {/* Quick Inquiries Popover Trigger */}
            <button 
              type="button"
              className="toolbar-btn prompts-trigger-btn"
              onClick={() => setShowSlashMenu(!showSlashMenu)}
              title="Quick Prompts and Inquiries (Type / to open)"
              aria-label="Quick prompts menu"
            >
              <Sparkles size={13} />
              <span>Prompts</span>
            </button>
          </div>

          {/* Right Action: Send Button or Stop Button */}
          <div className="toolbar-right">
            {isLoading ? (
              <button 
                type="button"
                className="recall-send-btn stop-active"
                onClick={onStop}
                title="Stop Ascent Generation (Esc)"
                aria-label="Stop generation"
              >
                <Square size={13} className="stop-square-icon" />
              </button>
            ) : (
              <button 
                type="button"
                className={`recall-send-btn ${localInput.trim() ? 'can-send' : ''}`}
                onClick={handleSendClick}
                disabled={!localInput.trim()}
                title="Send query (Enter)"
                aria-label="Send query"
              >
                <ArrowUp size={16} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

export default function App() {
  const navigate = useNavigate();

  // Authentication & User State

  const [user, setUser] = useState<UserProfile | null>(() => {
    try {
      const saved = localStorage.getItem('ridge_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isUserDropdownOpen, setIsUserDropdownOpen] = useState(false);

  // Admin Management State
  const [isAdminModalOpen, setIsAdminModalOpen] = useState(false);
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
  const [adminStats, setAdminStats] = useState<AdminStats | null>(null);
  const [isLoadingAdmin, setIsLoadingAdmin] = useState(false);
  const [adminSearch, setAdminSearch] = useState('');
  const [editingLimitUserId, setEditingLimitUserId] = useState<string | null>(null);
  const [tempLimitValue, setTempLimitValue] = useState<number>(50);

  // Multi-select & Confirm Dialog State
  const [selectedUserIds, setSelectedUserIds] = useState<Set<string>>(new Set());
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    title: string;
    message: string;
    danger?: boolean;
    onConfirm: () => void;
  }>({ open: false, title: '', message: '', onConfirm: () => {} });


  // New Add Member & SuperAdmin Filter State
  const [adminActiveTab, setAdminActiveTab] = useState<'users' | 'tenants'>('users');
  const [isAddUserModalOpen, setIsAddUserModalOpen] = useState(false);
  const [isCreateTenantModalOpen, setIsCreateTenantModalOpen] = useState(false);
  const [adminTenantFilter, setAdminTenantFilter] = useState('');
  const [adminTenantsList, setAdminTenantsList] = useState<TenantItem[]>([]);
  const [newUsername, setNewUsername] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newName, setNewName] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState<'user' | 'admin'>('user');
  const [newLimit, setNewLimit] = useState<number>(50);
  const [newTenantId, setNewTenantId] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [isCreatingUser, setIsCreatingUser] = useState(false);

  // New Tenant Provisioning State
  const [newTenantName, setNewTenantName] = useState('');
  const [newTenantSlug, setNewTenantSlug] = useState('');
  const [newTenantMaxUsers, setNewTenantMaxUsers] = useState<number>(50);
  const [isCreatingTenant, setIsCreatingTenant] = useState(false);



  // Theme Management: Defaults to 'stone' (Stone & Summit)
  const [theme, setTheme] = useState<ThemeMode>(() => {
    return (localStorage.getItem('recall_theme') as ThemeMode) || 'stone';
  });

  // Sidebar & Layout: Defaults to collapsed on refresh so the Hero is front and center
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isArtifactsOpen, setIsArtifactsOpen] = useState(false);
  const [activeArtifactTab, setActiveArtifactTab] = useState<'trace' | 'knowledge' | 'grader'>('trace');
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);
  const [feedbackTargetContext, setFeedbackTargetContext] = useState<FeedbackTargetContext | null>(null);



  // Multi-Session Chat State (User-scoped and persistent across reloads)
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    const initialUser = (() => {
      try {
        const saved = localStorage.getItem('ridge_user');
        return saved ? JSON.parse(saved) : null;
      } catch { return null; }
    })();
    const userSessions = loadUserSessions(initialUser);
    const hasEmpty = userSessions.some(s => s.messages.length === 0);
    if (!hasEmpty) {
      return [createFreshSession(), ...userSessions];
    }
    return userSessions;
  });

  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    const initialUser = (() => {
      try {
        const saved = localStorage.getItem('ridge_user');
        return saved ? JSON.parse(saved) : null;
      } catch { return null; }
    })();
    const userSessions = loadUserSessions(initialUser);

    // Tab-isolated active session: preserved on refresh within same tab, fresh on new tab
    const tabActiveId = sessionStorage.getItem('ridge_tab_active_session');
    if (tabActiveId && userSessions.some(s => s.id === tabActiveId)) {
      return tabActiveId;
    }

    // Fresh start on new tab: select or create an empty chat
    const emptySession = userSessions.find(s => s.messages.length === 0);
    if (emptySession) return emptySession.id;
    return userSessions[0]?.id || 'default-session';
  });

  const activeSessionIdRef = useRef<string>(activeSessionId);
  useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
    if (activeSessionId) {
      sessionStorage.setItem('ridge_tab_active_session', activeSessionId);
    }
  }, [activeSessionId]);

  const currentUserIdRef = useRef<string>(user?.id || 'guest');


  // Synchronize and isolate sessions when user account changes (login, logout, switch)
  useEffect(() => {
    const activeId = user?.id || 'guest';
    if (currentUserIdRef.current !== activeId) {
      currentUserIdRef.current = activeId;
      const loaded = loadUserSessions(user);
      const tabActiveId = sessionStorage.getItem('ridge_tab_active_session');
      const targetSession = tabActiveId ? loaded.find(s => s.id === tabActiveId) : null;
      
      if (targetSession) {
        setSessions(loaded);
        setActiveSessionId(targetSession.id);
      } else {
        const emptySession = loaded.find(s => s.messages.length === 0);
        if (emptySession) {
          setSessions(loaded);
          setActiveSessionId(emptySession.id);
        } else {
          const fresh = createFreshSession();
          setSessions([fresh, ...loaded]);
          setActiveSessionId(fresh.id);
        }
      }
      chatInputRef.current?.setValue('');
    }
  }, [user]);

  // Fetch persistent PostgreSQL conversations on login or initial mount
  useEffect(() => {
    if (!user || user.is_guest) return;

    let isMounted = true;
    const fetchServerConversations = async () => {
      try {
        const res = await fetchWithAuth('/api/conversations?limit=50');
        if (res.ok && isMounted) {
          const data = await res.json();
            setSessions(prev => {
              const serverSessions: ChatSession[] = data.conversations.map((c: any) => {
                const existing = prev.find(p => p.id === c.id);
                return {
                  id: c.id,
                  title: c.title || 'Research Ascent',
                  createdAt: c.created_at || Date.now(),
                  messages: existing?.messages || []
                };
              });
              const localDrafts = prev.filter(p => !p.id.includes('-') && p.messages.length === 0);
              const nonServerSessions = prev.filter(p => !data.conversations.some((c: any) => c.id === p.id) && p.messages.length > 0);
              const draftList = localDrafts.length > 0 ? localDrafts : [createFreshSession()];
              return [...draftList, ...nonServerSessions, ...serverSessions];
            });

            setActiveSessionId(curr => {
              const tabActiveId = sessionStorage.getItem('ridge_tab_active_session') || curr;
              const isServerConv = data.conversations.some((c: any) => c.id === tabActiveId);
              if (isServerConv) {
                // Preload active messages from server if user is viewing this conversation in this tab
                fetchWithAuth(`/api/conversations/${tabActiveId}/messages`).then(async (mRes) => {
                  if (mRes.ok && isMounted) {
                    const mData = await mRes.json();
                    if (mData.messages && mData.messages.length > 0) {
                      setSessions(sPrev => sPrev.map(s => s.id === tabActiveId ? { ...s, messages: mData.messages } : s));
                    }
                  }
                }).catch(() => {});
              }
              return tabActiveId;
            });

        }
      } catch (err) {
        console.warn('Could not fetch server conversations:', err);
      }
    };

    fetchServerConversations();
    return () => { isMounted = false; };
  }, [user]);

  // Persist sessions only for the currently active user's storage key
  useEffect(() => {
    const currentKey = getUserSessionStorageKey(user);
    if (currentUserIdRef.current === (user?.id || 'guest')) {
      localStorage.setItem(currentKey, JSON.stringify(sessions));
    }
  }, [sessions, user]);




  const activeSession = sessions.find(s => s.id === activeSessionId) || sessions[0];
  const messages = activeSession?.messages || [];

  // Input & Streaming States
  const [isLoading, setIsLoading] = useState(false);
  const [expandedThinking, setExpandedThinking] = useState<{ [msgId: string]: boolean }>({});
  const [webSearchEnabled, setWebSearchEnabled] = useState(true);
  const [selectedSourceFilter, setSelectedSourceFilter] = useState<string>('all');

  // Modals & Tools
  const [isIngestOpen, setIsIngestOpen] = useState(false);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [isGlossaryOpen, setIsGlossaryOpen] = useState(false);
  const [isGlossaryLoading, setIsGlossaryLoading] = useState(false);
  const [glossary, setGlossary] = useState<GlossaryItem[]>([]);
  const [selectedConflictDiff, setSelectedConflictDiff] = useState<ConflictData | null>(null);
  const [selectedSourceModal, setSelectedSourceModal] = useState<any | null>(null);
  const [activeCitationHighlight, setActiveCitationHighlight] = useState<string | null>(null);
  const [hoveredCitation, setHoveredCitation] = useState<{
    msgId: string;
    index: number;
    target?: any;
    rect: DOMRect;
  } | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' | 'info' } | null>(null);

  const fetchGlossary = async () => {
    setIsGlossaryLoading(true);
    try {
      const res = await fetchWithAuth('/api/glossary');
      if (res.ok) {
        const data = await res.json();
        setGlossary(data.glossary || []);
      }
    } catch (e) {
      console.error('Error fetching glossary:', e);
    } finally {
      setIsGlossaryLoading(false);
    }
  };

  // Ingestion States
  const [ingestMode, setIngestMode] = useState<'file' | 'url'>('file');
  const [ingestInput, setIngestInput] = useState('');
  const [isIngesting, setIsIngesting] = useState(false);
  const [isIngestSuccess, setIsIngestSuccess] = useState(false);
  const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>([]);
  const [uploadProgress, setUploadProgress] = useState<{ current: number; total: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  // Knowledge Stats & Grounded Suggestions (Instant 0ms hydration)
  const [suggestions, setSuggestions] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem('ridge_cached_suggestions');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {}
    return DEFAULT_SUGGESTIONS;
  });
  const [stats, setStats] = useState(() => {
    try {
      const saved = localStorage.getItem('ridge_cached_stats');
      return saved ? JSON.parse(saved) : { doc_count: 0, chunk_count: 0 };
    } catch {
      return { doc_count: 0, chunk_count: 0 };
    }
  });

  // Knowledge Base State
  const [kbSources, setKbSources] = useState<KBSource[]>([]);
  const [isLoadingKBSources, setIsLoadingKBSources] = useState(false);
  const [deletingSource, setDeletingSource] = useState<string | null>(null);
  const [isClearingKB, setIsClearingKB] = useState(false);
  const [searchDocFilter, setSearchDocFilter] = useState('');

  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<ChatInputDeckRef>(null);
  const userDropdownRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Stop Generation Handler
  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsLoading(false);
    updateCurrentMessages(prev => prev.map(msg => msg.isStreaming ? { ...msg, isStreaming: false } : msg));
    showToast('Ascent generation stopped', 'info');
  };

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userDropdownRef.current && !userDropdownRef.current.contains(e.target as Node)) {
        setIsUserDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Helper for relative timestamps on recent sessions
  const getRelativeTime = (timestamp: number) => {
    const diff = Math.floor((Date.now() - timestamp) / 1000);
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  // Close sidebar on mobile resize
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 768 && isSidebarOpen) {
        setIsSidebarOpen(false);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [isSidebarOpen]);

  // Dynamic document title
  useEffect(() => {
    document.title = activeSession?.title 
      ? `${activeSession.title} · Ridge`
      : 'Ridge · Corrective RAG Intelligence';
  }, [activeSession?.title]);

  // Apply Theme Mode
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('recall_theme', theme);
  }, [theme]);

  // Toast Notification Helper
  const showToast = (msg: string, type: 'success' | 'error' | 'info' = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  // Keyboard Shortcuts (Command+K for new ascent, Esc to stop/close)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        handleNewChat();
      }
      if (e.key === 'Escape') {
        if (isLoading) {
          handleStopGeneration();
        }
        setIsIngestOpen(false);
        setIsExportOpen(false);
        setIsAdminModalOpen(false);
        setSelectedSourceModal(null);
        if (window.innerWidth < 768) {
          setIsSidebarOpen(false);
          setIsArtifactsOpen(false);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [sessions, isLoading]);


  // Authenticated API request wrapper
  const fetchWithAuth = async (url: string, options: RequestInit = {}) => {
    const token = localStorage.getItem('ridge_token');
    const headers = new Headers(options.headers || {});
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    const signal = options.signal || abortControllerRef.current?.signal;
    const res = await fetch(url, { ...options, headers, signal });
    if (res.status === 401 && authConfig?.enabled) {
      setUser(null);
      localStorage.removeItem('ridge_token');
      localStorage.removeItem('ridge_user');
      setIsAuthModalOpen(true);
    }
    return res;
  };

  // Authentication Initialization & OAuth Callback Handler
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tokenParam = params.get('token');
    const authErr = params.get('auth_error');

    if (tokenParam) {
      localStorage.setItem('ridge_token', tokenParam);
      window.history.replaceState({}, document.title, window.location.pathname);
      showToast('Welcome back, Climber', 'success');
    } else if (authErr) {
      window.history.replaceState({}, document.title, window.location.pathname);
      showToast(`Authentication failed: ${authErr}`, 'error');
    }

    // Fetch Auth Configuration and Profile
    fetch('/api/auth/config')
      .then(res => res.json())
      .then(config => {
        setAuthConfig(config);
        return fetchWithAuth('/api/auth/me');
      })
      .then(async res => {
        if (res && res.ok) {
          const userData = await res.json();
          setUser(userData);
          localStorage.setItem('ridge_user', JSON.stringify(userData));
        } else if (res && res.status === 401) {
          setUser(null);
          localStorage.removeItem('ridge_user');
        }
      })
      .catch(err => {
        console.warn('Auth check error:', err);
      });
  }, []);

  const handleLogout = async () => {
    try {
      await fetchWithAuth('/api/auth/logout', { method: 'POST' });
    } catch (e) {}
    localStorage.removeItem('ridge_token');
    localStorage.removeItem('ridge_user');
    setUser(null);
    setIsUserDropdownOpen(false);
    setIsAdminModalOpen(false);
    showToast('Signed out of Ridge', 'info');
    if (authConfig?.enabled) {
      setIsAuthModalOpen(true);
    }
  };

  // Admin Management Functions
  const fetchAdminData = async (tenantFilter?: string) => {
    setIsLoadingAdmin(true);
    try {
      const activeFilter = tenantFilter !== undefined ? tenantFilter : adminTenantFilter;
      const url = activeFilter ? `/api/admin/users?tenant_id=${encodeURIComponent(activeFilter)}` : '/api/admin/users';
      
      const reqs: Promise<Response>[] = [
        fetchWithAuth(url),
        fetchWithAuth('/api/admin/stats'),
        fetchWithAuth('/api/admin/tenants')
      ];

      const [usersRes, statsRes, tenantsRes] = await Promise.all(reqs);

      if (usersRes.ok) {
        const uData = await usersRes.json();
        setAdminUsers(uData.users || []);
      }
      if (statsRes.ok) {
        const sData = await statsRes.json();
        setAdminStats(sData);
        if (sData.is_superadmin && user && user.role !== 'superadmin') {
          const updatedUser = { ...user, role: 'superadmin' };
          setUser(updatedUser);
          localStorage.setItem('ridge_user', JSON.stringify(updatedUser));
        }
      }
      if (tenantsRes && tenantsRes.ok) {
        const tData = await tenantsRes.json();
        setAdminTenantsList(tData.tenants || []);
      }
    } catch (e) {
      console.error('Failed to fetch admin data:', e);
      showToast('Failed to load admin data', 'error');
    } finally {
      setIsLoadingAdmin(false);
    }
  };

  const handleToggleTenantStatus = async (tenantId: string, currentStatus: boolean) => {
    const newStatus = !currentStatus;
    try {
      const res = await fetchWithAuth(`/api/admin/tenants/${tenantId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: newStatus })
      });
      if (res.ok) {
        showToast(`Institution ${newStatus ? 'activated' : 'suspended'}`, 'success');
        setAdminTenantsList(prev => prev.map(t => t.id === tenantId ? { ...t, is_active: newStatus } : t));
      } else {
        const err = await res.json();
        showToast(err.detail || 'Failed to update institution status', 'error');
      }
    } catch (e) {
      showToast('Error updating institution status', 'error');
    }
  };

  const handleDeleteTenant = (tenantId: string, tenantName: string) => {
    setConfirmDialog({
      open: true,
      title: 'Delete Institution',
      message: `Permanently delete "${tenantName}" and ALL its members, uploaded documents, and indexed knowledge? This cannot be undone.`,
      danger: true,
      onConfirm: async () => {
        setConfirmDialog(d => ({ ...d, open: false }));
        try {
          const res = await fetchWithAuth(`/api/admin/tenants/${tenantId}`, { method: 'DELETE' });
          if (res.ok) {
            showToast(`Institution '${tenantName}' deleted`, 'success');
            setAdminTenantsList(prev => prev.filter(t => t.id !== tenantId));
            if (adminTenantFilter === tenantId) setAdminTenantFilter('');
            fetchAdminData();
          } else {
            const err = await res.json();
            showToast(err.detail || 'Failed to delete institution', 'error');
          }
        } catch (e) {
          showToast('Error deleting institution', 'error');
        }
      },
    });
  };


  const handleCreateTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTenantName.trim() || !newTenantSlug.trim()) {
      showToast('Institution name and slug code are required', 'error');
      return;
    }
    setIsCreatingTenant(true);
    try {
      const res = await fetchWithAuth('/api/admin/tenants', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newTenantName.trim(),
          slug: newTenantSlug.trim().toLowerCase().replace(/[^a-z0-9-_]/g, ''),
          max_users: Number(newTenantMaxUsers) || 50
        })
      });
      if (res.ok) {
        showToast(`Institution '${newTenantName}' created successfully!`, 'success');
        setIsCreateTenantModalOpen(false);
        setNewTenantName('');
        setNewTenantSlug('');
        setNewTenantMaxUsers(50);
        fetchAdminData();
      } else {
        const err = await res.json();
        showToast(err.detail || 'Failed to create institution', 'error');
      }
    } catch (e) {
      showToast('Error creating institution', 'error');
    } finally {
      setIsCreatingTenant(false);
    }
  };


  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUsername.trim() || !newEmail.trim() || !newPassword.trim()) {
      showToast('Please fill in all required user fields', 'error');
      return;
    }

    if (newPassword.length < 6) {
      showToast('Password must be at least 6 characters', 'error');
      return;
    }

    setIsCreatingUser(true);
    try {
      const payload: any = {
        username: newUsername.trim(),
        name: newName.trim() || newUsername.trim(),
        email: newEmail.trim(),
        password: newPassword,
        role: newRole,
        daily_request_limit: newRole === 'admin' ? 999999 : Number(newLimit) || 50,
      };
      if (user?.role === 'superadmin' && newTenantId) {
        payload.tenant_id = newTenantId;
      }

      const res = await fetchWithAuth('/api/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        showToast(`Climber '@${newUsername.trim()}' created successfully!`, 'success');
        setIsAddUserModalOpen(false);
        setNewUsername('');
        setNewEmail('');
        setNewName('');
        setNewPassword('');
        setNewRole('user');
        setNewLimit(50);
        fetchAdminData();
      } else {
        const err = await res.json();
        showToast(err.detail || 'Failed to create user', 'error');
      }
    } catch (e) {
      showToast('Error creating user account', 'error');
    } finally {
      setIsCreatingUser(false);
    }
  };


  const handleUpdateRole = async (targetId: string, currentRole: string) => {
    const newRole = currentRole === 'admin' ? 'user' : 'admin';
    try {
      const res = await fetchWithAuth(`/api/admin/users/${targetId}/role`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: newRole })
      });
      if (res.ok) {
        showToast(`User role updated to ${newRole}`, 'success');
        setAdminUsers(prev => prev.map(u => u.id === targetId ? { ...u, role: newRole } : u));
      } else {
        const err = await res.json();
        showToast(err.detail || 'Failed to update role', 'error');
      }
    } catch (e) {
      showToast('Error updating role', 'error');
    }
  };

  const handleUpdateStatus = async (targetId: string, currentStatus: boolean) => {
    const newStatus = !currentStatus;
    try {
      const res = await fetchWithAuth(`/api/admin/users/${targetId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: newStatus })
      });
      if (res.ok) {
        showToast(`User account ${newStatus ? 'activated' : 'suspended'}`, 'success');
        setAdminUsers(prev => prev.map(u => u.id === targetId ? { ...u, is_active: newStatus } : u));
      } else {
        const err = await res.json();
        showToast(err.detail || 'Failed to update status', 'error');
      }
    } catch (e) {
      showToast('Error updating status', 'error');
    }
  };

  const handleSaveLimit = async (targetId: string, newLimit: number) => {
    try {
      const res = await fetchWithAuth(`/api/admin/users/${targetId}/limit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: newLimit })
      });
      if (res.ok) {
        showToast('Daily request quota updated', 'success');
        setAdminUsers(prev => prev.map(u => u.id === targetId ? { ...u, daily_request_limit: newLimit } : u));
        setEditingLimitUserId(null);
      } else {
        const err = await res.json();
        showToast(err.detail || 'Failed to update quota', 'error');
      }
    } catch (e) {
      showToast('Error updating quota', 'error');
    }
  };

  const handleDeleteUser = (targetId: string, username: string) => {
    setConfirmDialog({
      open: true,
      title: 'Delete Member Account',
      message: `Permanently delete @${username} and all their uploaded documents? This cannot be undone.`,
      danger: true,
      onConfirm: async () => {
        setConfirmDialog(d => ({ ...d, open: false }));
        try {
          const res = await fetchWithAuth(`/api/admin/users/${targetId}`, { method: 'DELETE' });
          if (res.ok) {
            showToast(`User '${username}' deleted`, 'success');
            setAdminUsers(prev => prev.filter(u => u.id !== targetId));
            setSelectedUserIds(prev => { const n = new Set(prev); n.delete(targetId); return n; });
          } else {
            const err = await res.json();
            showToast(err.detail || 'Failed to delete user', 'error');
          }
        } catch (e) {
          showToast('Error deleting user', 'error');
        }
      },
    });
  };

  const handleBulkDeleteUsers = () => {
    const ids = Array.from(selectedUserIds);
    const deletable = adminUsers.filter(u => ids.includes(u.id) && u.role !== 'superadmin' && u.id !== user?.id);
    if (deletable.length === 0) {
      showToast('No deletable users selected (SuperAdmin and your own account are protected)', 'error');
      return;
    }
    setConfirmDialog({
      open: true,
      title: `Delete ${deletable.length} Member${deletable.length > 1 ? 's' : ''}`,
      message: `Permanently delete ${deletable.length} selected member account${deletable.length > 1 ? 's' : ''} and all their data? This cannot be undone.`,
      danger: true,
      onConfirm: async () => {
        setConfirmDialog(d => ({ ...d, open: false }));
        setIsBulkDeleting(true);
        try {
          await Promise.all(
            deletable.map(u => fetchWithAuth(`/api/admin/users/${u.id}`, { method: 'DELETE' }))
          );
          showToast(`${deletable.length} member${deletable.length > 1 ? 's' : ''} deleted`, 'success');
          setSelectedUserIds(new Set());
          fetchAdminData();
        } catch (e) {
          showToast('Error during bulk delete', 'error');
        } finally {
          setIsBulkDeleting(false);
        }
      },
    });
  };



  // Fetch Suggestions & Knowledge Stats (Only hits API/cache; updates local storage)
  const fetchSuggestionsAndStats = async (forceRefresh = false) => {
    try {
      const [sugRes, statRes] = await Promise.all([
        fetchWithAuth(`/api/suggestions${forceRefresh ? '?force=true' : ''}`),
        fetchWithAuth('/api/stats')
      ]);
      if (sugRes.ok) {
        const sugData = await sugRes.json();
        if (!sugData.empty && sugData.suggestions?.length > 0) {
          setSuggestions(sugData.suggestions);
          localStorage.setItem('ridge_cached_suggestions', JSON.stringify(sugData.suggestions));
        }
      }
      if (statRes.ok) {
        const statData = await statRes.json();
        setStats(statData);
        localStorage.setItem('ridge_cached_stats', JSON.stringify(statData));
      }
    } catch (e) {
      console.error('Failed to fetch stats/suggestions:', e);
    }
  };

  // Fetch Knowledge Base Sources
  const fetchKBSources = async () => {
    setIsLoadingKBSources(true);
    try {
      const res = await fetchWithAuth('/api/kb/sources');
      if (res.ok) {
        const data = await res.json();
        setKbSources(data.sources || []);
        setStats({
          doc_count: data.total_sources || 0,
          chunk_count: data.total_chunks || 0
        });
      }
    } catch (e) {
      console.error('Failed to fetch KB sources:', e);
    } finally {
      setIsLoadingKBSources(false);
    }
  };

  const handleDeleteKBSource = async (source: string, name: string, ids?: string[]) => {
    if (!window.confirm(`Are you sure you want to delete '${name}' and all its indexed chunks from the knowledge base?`)) {
      return;
    }
    setDeletingSource(source);
    try {
      const res = await fetchWithAuth('/api/kb/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, ids })
      });
      if (res.ok) {
        showToast(`Deleted '${name}' from knowledge base`, 'success');
        setKbSources(prev => prev.filter(s => s.source !== source));
        await fetchKBSources();
        fetchSuggestionsAndStats(true);
      } else {
        showToast('Failed to delete source', 'error');
      }
    } catch (e) {
      showToast('Error deleting source', 'error');
    } finally {
      setDeletingSource(null);
    }
  };

  const handleClearAllKB = async () => {
    if (!window.confirm('Are you sure you want to CLEAR the entire knowledge base? All indexed documents and chunks will be permanently removed.')) {
      return;
    }
    setIsClearingKB(true);
    try {
      const res = await fetchWithAuth('/api/kb/clear', { method: 'POST' });
      if (res.ok) {
        showToast('Knowledge base completely cleared', 'success');
        setKbSources([]);
        setStats({ doc_count: 0, chunk_count: 0 });
        fetchSuggestionsAndStats(true);
      } else {
        showToast('Failed to clear knowledge base', 'error');
      }
    } catch (e) {
      showToast('Error clearing knowledge base', 'error');
    } finally {
      setIsClearingKB(false);
    }
  };

  const getSourceIcon = (source: string, type: string) => {
    const s = source.toLowerCase();
    if (type === 'youtube' || s.includes('youtube.com') || s.includes('youtu.be')) return <Video size={16} />;
    if (s.endsWith('.pdf')) return <FileText size={16} />;
    if (s.endsWith('.docx') || s.endsWith('.doc')) return <FileText size={16} />;
    if (s.endsWith('.pptx') || s.endsWith('.ppt')) return <FileText size={16} />;
    if (s.endsWith('.xlsx') || s.endsWith('.xls') || s.endsWith('.csv') || s.endsWith('.tsv')) return <Database size={16} />;
    if (s.endsWith('.png') || s.endsWith('.jpg') || s.endsWith('.jpeg') || s.endsWith('.webp')) return <Image size={16} />;
    if (s.endsWith('.py') || s.endsWith('.ts') || s.endsWith('.js') || s.endsWith('.tsx') || s.endsWith('.cpp') || s.endsWith('.json')) return <Code size={16} />;
    if (s.startsWith('http')) return <Globe size={16} />;
    return <FileText size={16} />;
  };

  useEffect(() => {
    fetchSuggestionsAndStats();
  }, []);

  useEffect(() => {
    if (isArtifactsOpen && activeArtifactTab === 'knowledge') {
      fetchKBSources();
    }
  }, [isArtifactsOpen, activeArtifactTab]);

  // Auto-scroll handler: instant auto during live streaming, smooth when completed
  useEffect(() => {
    if (isLoading) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading]);

  // Session Management Helpers
  const handleGoHome = () => {
    if (activeSession && activeSession.messages.length === 0) {
      if (window.innerWidth < 768) setIsSidebarOpen(false);
      return;
    }
    const emptySession = sessions.find(s => s.messages.length === 0);
    if (emptySession) {
      setActiveSessionId(emptySession.id);
    } else {
      const fresh = createFreshSession();
      setSessions(prev => [fresh, ...prev]);
      setActiveSessionId(fresh.id);
    }
    chatInputRef.current?.setValue('');
    if (window.innerWidth < 768) setIsSidebarOpen(false);
  };

  const handleNewChat = () => {
    if (activeSession && activeSession.messages.length === 0) {
      if (window.innerWidth < 768) setIsSidebarOpen(false);
      return;
    }
    const emptySession = sessions.find(s => s.messages.length === 0);
    if (emptySession) {
      setActiveSessionId(emptySession.id);
    } else {
      const fresh = createFreshSession();
      setSessions(prev => [fresh, ...prev]);
      setActiveSessionId(fresh.id);
    }
    chatInputRef.current?.setValue('');
    if (window.innerWidth < 768) setIsSidebarOpen(false);
    showToast('Started new research ascent', 'info');
  };

  const handleSelectSession = async (sid: string) => {
    setActiveSessionId(sid);
    const target = sessions.find(s => s.id === sid);
    if (target && target.messages.length === 0 && user && !user.is_guest && sid.includes('-')) {
      try {
        const res = await fetchWithAuth(`/api/conversations/${sid}/messages`);
        if (res.ok) {
          const data = await res.json();
          if (data.messages && data.messages.length > 0) {
            setSessions(prev => prev.map(s => s.id === sid ? { ...s, messages: data.messages } : s));
          }
        }
      } catch (err) {
        console.warn('Could not load conversation messages:', err);
      }
    }
    if (window.innerWidth < 768) setIsSidebarOpen(false);
  };

  const handleDeleteSession = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (user && !user.is_guest && id.includes('-')) {
      fetchWithAuth(`/api/conversations/${id}`, { method: 'DELETE' }).catch(err => console.warn(err));
    }
    if (sessions.length <= 1) {
      const fresh: ChatSession = {
        id: Date.now().toString(),
        title: 'New Research Ascent',
        createdAt: Date.now(),
        messages: []
      };
      setSessions([fresh]);
      setActiveSessionId(fresh.id);
      return;
    }
    const filtered = sessions.filter(s => s.id !== id);
    setSessions(filtered);
    if (activeSessionId === id) {
      setActiveSessionId(filtered[0].id);
    }
    showToast('Ascent deleted', 'info');
  };


  const updateCurrentMessages = (
    updater: (prevMsgs: Message[]) => Message[],
    targetSessionId?: string,
    targetMsgId?: string
  ) => {
    setSessions(prev => prev.map(s => {
      const targetId = targetSessionId || activeSessionIdRef.current;
      const isTarget = s.id === targetId || (targetMsgId ? s.messages.some(m => m.id === targetMsgId) : false);
      if (isTarget) {
        const updated = updater(s.messages);
        let newTitle = s.title;
        if ((s.title === 'New Research Ascent' || s.title === 'Initial Ascent') && updated.length > 0 && updated[0].role === 'user') {
          newTitle = updated[0].content.slice(0, 32) + (updated[0].content.length > 32 ? '...' : '');
        }
        return { ...s, messages: updated, title: newTitle };
      }
      return s;
    }));
  };

  // Chat Execution Stream
  const handleSend = async (customQuery?: string) => {
    if (!customQuery || !customQuery.trim() || isLoading) return;

    let currentTargetSessionId = activeSessionIdRef.current;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: customQuery.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    const assistantId = (Date.now() + 1).toString();
    const assistantMessage: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      traces: [],
      isStreaming: true,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    updateCurrentMessages(prev => [...prev, userMessage, assistantMessage], currentTargetSessionId, assistantId);
    setIsLoading(true);
    setExpandedThinking(prev => ({ ...prev, [assistantId]: true }));

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const response = await fetchWithAuth('/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          question: userMessage.content,
          web_search_enabled: webSearchEnabled,
          source_filter: selectedSourceFilter !== 'all' ? selectedSourceFilter : undefined,
          conversation_id: currentTargetSessionId && currentTargetSessionId.includes('-') ? currentTargetSessionId : undefined,
        }),
        signal: abortController.signal,
      });

      if (!response.ok) throw new Error('Failed to query assistant');

      const reader = response.body?.getReader();
      if (!reader) throw new Error('Streaming not supported');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            if (dataStr === '[DONE]') continue;

            try {
              const data = JSON.parse(dataStr);

              if (data.type === 'conversation_info' && data.conversation_id) {
                const oldId = currentTargetSessionId;
                const newServerConvId = data.conversation_id;
                currentTargetSessionId = newServerConvId;
                activeSessionIdRef.current = newServerConvId;
                setActiveSessionId(newServerConvId);
                setSessions(prev => prev.map(s => (s.id === oldId || s.messages.some(m => m.id === assistantId)) ? { ...s, id: newServerConvId } : s));
              } else if (data.type === 'token' && typeof data.token === 'string') {
                updateCurrentMessages(prev => prev.map(msg => {
                  if (msg.id === assistantId) {
                    return {
                      ...msg,
                      content: (msg.content || '') + data.token
                    };
                  }
                  return msg;
                }), currentTargetSessionId, assistantId);
              } else {
                updateCurrentMessages(prev => prev.map(msg => {
                  if (msg.id === assistantId) {
                    const newMsg = { ...msg };
                    newMsg.traces = [...(newMsg.traces || []), data];
                    if (data.answer) {
                      newMsg.content = data.answer;
                    }
                    if (data.confidence) {
                      newMsg.confidence = data.confidence;
                    }
                    if (data.conflict_data) {
                      newMsg.conflict_data = data.conflict_data;
                    }
                    return newMsg;
                  }
                  return msg;
                }), currentTargetSessionId, assistantId);
              }
            } catch (e) {
              console.error('Failed to parse SSE payload:', dataStr);
            }
          }
        }
      }

    } catch (error: any) {
      if (error.name === 'AbortError' || error.message?.includes('aborted')) {
        console.log('Ascent streaming aborted by user');
        return;
      }
      console.error(error);
      updateCurrentMessages(prev => prev.map(msg =>
        msg.id === assistantId
          ? { ...msg, content: `Error: ${error.message || 'Could not complete ascent.'}` }
          : msg
      ), currentTargetSessionId, assistantId);
      showToast('Error during pipeline ascent', 'error');
    } finally {
      abortControllerRef.current = null;
      updateCurrentMessages(prev => prev.map(msg =>
        msg.id === assistantId ? { ...msg, isStreaming: false } : msg
      ), currentTargetSessionId, assistantId);
      setIsLoading(false);
    }
  };



  // Multi-File Ingestion Queue Handlers
  const handleAddFilesToQueue = (files: FileList | File[]) => {
    const newItems: UploadQueueItem[] = Array.from(files).map(f => ({
      file: f,
      id: `${f.name}-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
      status: 'waiting'
    }));
    setUploadQueue(prev => [...prev, ...newItems]);
    setIngestInput('');
  };

  const handleRemoveQueueItem = (id: string) => {
    setUploadQueue(prev => prev.filter(item => item.id !== id));
  };

  const handleClearQueue = () => {
    setUploadQueue([]);
  };

  const handleIngest = async () => {
    if (ingestMode === 'url') {
      if (!ingestInput.trim()) return;
      setIsIngesting(true);
      try {
        const response = await fetchWithAuth('/ingest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text_or_url: ingestInput.trim() })
        });
        if (!response.ok) throw new Error('Server returned an error');
        const data = await response.json();
        showToast(`Anchored ${data.chunks_added} chunks into knowledge crag`);
        setIsIngestSuccess(true);
        setTimeout(() => {
          setIsIngestSuccess(false);
          setIsIngestOpen(false);
          setIngestInput('');
        }, 1200);
      } catch (e: any) {
        showToast('Ingestion failed: ' + (e.message || 'Unknown error'), 'error');
      } finally {
        setIsIngesting(false);
        fetchSuggestionsAndStats(true);
        fetchKBSources();
      }
      return;
    }

    // Batch File Ingestion Queue
    if (uploadQueue.length === 0) return;
    setIsIngesting(true);
    let totalAdded = 0;
    setUploadProgress({ current: 0, total: uploadQueue.length });

    for (let i = 0; i < uploadQueue.length; i++) {
      const item = uploadQueue[i];
      if (item.status === 'completed') continue;

      setUploadQueue(prev => prev.map((q, idx) => idx === i ? { ...q, status: 'uploading' } : q));
      setUploadProgress({ current: i + 1, total: uploadQueue.length });

      try {
        const formData = new FormData();
        formData.append('file', item.file);
        const res = await fetchWithAuth('/upload', {
          method: 'POST',
          body: formData
        });
        if (!res.ok) throw new Error('Server returned an error');
        const data = await res.json();
        const added = data.chunks_added || 0;
        totalAdded += added;
        setUploadQueue(prev => prev.map((q, idx) => idx === i ? { ...q, status: 'completed', chunksAdded: added } : q));
      } catch (err: any) {
        setUploadQueue(prev => prev.map((q, idx) => idx === i ? { ...q, status: 'error', error: err.message || 'Upload failed' } : q));
      }
    }

    setIsIngesting(false);
    setUploadProgress(null);
    showToast(`Batch complete: indexed ${totalAdded} chunks across ${uploadQueue.length} files`, 'success');
    setIsIngestSuccess(true);
    fetchSuggestionsAndStats(true);
    fetchKBSources();

    setTimeout(() => {
      setIsIngestSuccess(false);
      setIsIngestOpen(false);
      setUploadQueue([]);
    }, 1400);
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleAddFilesToQueue(e.dataTransfer.files);
    }
  };

  const handleChatFileAttach = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleAddFilesToQueue(e.target.files);
      setIsIngestOpen(true);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    showToast('Copied to clipboard');
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleReaction = (msgId: string, liked: boolean) => {
    updateCurrentMessages(prev => prev.map(msg => {
      if (msg.id === msgId) {
        const nextLiked = msg.liked === liked ? null : liked;
        if (nextLiked === true) showToast('Ascent marked helpful', 'success');
        if (nextLiked === false) showToast('Crux feedback noted', 'info');
        return { ...msg, liked: nextLiked };
      }
      return msg;
    }));
  };

  const handleOpenFeedbackForMessage = (msg: Message) => {

    const msgIdx = messages.findIndex(m => m.id === msg.id);
    let userQuery = '';
    if (msgIdx > 0) {
      for (let i = msgIdx - 1; i >= 0; i--) {
        if (messages[i].role === 'user') {
          userQuery = messages[i].content;
          break;
        }
      }
    }
    setFeedbackTargetContext({
      query: userQuery,
      answerSnippet: msg.content.slice(0, 300),
      messageId: msg.id,
    });
    setIsFeedbackOpen(true);
  };

  const clearCurrentChat = () => {

    updateCurrentMessages(() => []);
    showToast('Conversation cleared');
  };

  const exportConversation = (format: 'md' | 'json' | 'pdf') => {
    setIsExportOpen(false);

    if (format === 'pdf') {
      const printDoc = `
        <!DOCTYPE html>
        <html>
          <head>
            <meta charset="utf-8">
            <title>Ridge Ascent - ${activeSession.title}</title>
            <style>
              @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
              @page {
                size: A4 portrait;
                margin: 16mm 14mm;
              }
              * { box-sizing: border-box; }
              body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                color: #0F172A;
                background: #FFFFFF;
                padding: 0;
                max-width: 820px;
                margin: 0 auto;
                line-height: 1.6;
              }
              .header-banner {
                border-bottom: 2px solid #E2E8F0;
                padding-bottom: 14px;
                margin-bottom: 24px;
                display: flex;
                justify-content: space-between;
                align-items: flex-end;
              }
              .brand-title {
                font-size: 22px;
                font-weight: 700;
                color: #0F172A;
                margin: 0;
                letter-spacing: -0.02em;
              }
              .report-title {
                font-size: 14px;
                color: #64748B;
                margin: 4px 0 0 0;
                font-weight: 500;
              }
              .report-date {
                font-size: 11px;
                color: #94A3B8;
                font-family: monospace;
              }
              .message-block {
                margin-bottom: 28px;
              }
              .user-msg {
                background: #F8FAFC;
                border-left: 4px solid #0284C7;
                padding: 12px 16px;
                border-radius: 0 8px 8px 0;
                margin-bottom: 16px;
                page-break-inside: avoid;
              }
              .user-label {
                font-size: 10.5px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                color: #0284C7;
                margin-bottom: 4px;
              }
              .user-content {
                font-size: 14.5px;
                font-weight: 600;
                color: #0F172A;
              }
              .assistant-msg {
                padding: 0 4px 22px 4px;
                border-bottom: 1px solid #E2E8F0;
              }
              .assistant-label {
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: #0F172A;
                margin-bottom: 12px;
                page-break-inside: avoid;
              }
              .confidence-pill {
                font-size: 10px;
                padding: 2px 8px;
                border-radius: 10px;
                font-weight: 600;
                background: #ECFDF5;
                color: #059669;
                border: 1px solid #A7F3D0;
                text-transform: none;
                letter-spacing: normal;
              }
              .confidence-pill.medium {
                background: #EFF6FF;
                color: #0284C7;
                border-color: #BAE6FD;
              }
              .confidence-pill.low {
                background: #FFFBEB;
                color: #D97706;
                border-color: #FDE68A;
              }
              .assistant-content {
                font-size: 13.5px;
                color: #1E293B;
                line-height: 1.65;
              }
              .report-h1 {
                font-size: 17px;
                font-weight: 700;
                color: #0F172A;
                margin: 18px 0 8px 0;
                letter-spacing: -0.01em;
              }
              .report-h2 {
                font-size: 14.5px;
                font-weight: 700;
                color: #0F172A;
                margin: 16px 0 6px 0;
                border-bottom: 1px solid #F1F5F9;
                padding-bottom: 4px;
              }
              .report-h3 {
                font-size: 13.5px;
                font-weight: 600;
                color: #1E293B;
                margin: 12px 0 4px 0;
              }
              .report-p {
                margin: 0 0 10px 0;
                font-size: 13.5px;
                line-height: 1.65;
                color: #1E293B;
              }
              .report-ul, .report-ol {
                margin: 6px 0 12px 0;
                padding-left: 22px;
              }
              .report-li {
                margin-bottom: 5px;
                font-size: 13.5px;
                line-height: 1.55;
                color: #1E293B;
              }
              strong {
                color: #0F172A;
                font-weight: 600;
              }
              .report-cit-badge {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                background: #E0F2FE;
                color: #0369A1;
                font-family: monospace;
                font-size: 10.5px;
                font-weight: 700;
                padding: 0 4px;
                border-radius: 3px;
                border: 1px solid #BAE6FD;
                margin: 0 2px;
                line-height: 1.3;
              }
              .report-inline-code {
                font-family: monospace;
                font-size: 12px;
                background: #F1F5F9;
                padding: 1px 4px;
                border-radius: 3px;
                color: #0F172A;
              }
              .report-code-block {
                font-family: monospace;
                font-size: 12px;
                background: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 10px 14px;
                overflow-x: auto;
                margin: 10px 0;
                color: #0F172A;
              }
              .report-blockquote {
                border-left: 3px solid #CBD5E1;
                padding-left: 12px;
                margin: 10px 0;
                color: #475569;
                font-style: italic;
              }
              .citations-summary {
                margin-top: 16px;
                padding: 12px 14px;
                background: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                font-size: 12px;
                page-break-inside: avoid;
              }
              .citations-title {
                font-weight: 700;
                margin-bottom: 6px;
                color: #334155;
                font-size: 12px;
              }
              .citation-item {
                margin-bottom: 4px;
                color: #475569;
                font-size: 12px;
                line-height: 1.4;
              }
              .cit-status-pass {
                color: #059669;
                font-weight: 600;
              }
              .cit-status-fail {
                color: #DC2626;
              }
              .footer-note {
                margin-top: 36px;
                text-align: center;
                font-size: 11px;
                color: #94A3B8;
                border-top: 1px solid #E2E8F0;
                padding-top: 14px;
                page-break-inside: avoid;
              }
            </style>
          </head>
          <body>
            <div class="header-banner">
              <div>
                <h1 class="brand-title">🏔️ Ridge Intelligence Report</h1>
                <p class="report-title">${activeSession.title}</p>
              </div>
              <div class="report-date">${new Date().toLocaleString()}</div>
            </div>
            ${messages.map(m => {
              if (m.role === 'user') {
                return `
                  <div class="message-block">
                    <div class="user-msg">
                      <div class="user-label">User Inquiry</div>
                      <div class="user-content">${m.content}</div>
                    </div>
                  </div>
                `;
              } else {
                const conf = m.confidence;
                const confHtml = conf ? `
                  <span class="confidence-pill ${conf.level.toLowerCase()}">
                    ${conf.score}% Grounded Confidence (${conf.level})
                  </span>
                ` : '';
                
                const webSearchTrace = (m.traces || []).find(t => t.node === 'web_search_node' && t.doc_grades && t.doc_grades.length > 0);
                const gradeTrace = [...(m.traces || [])].reverse().find(t => t.node === 'grade_node' && t.doc_grades && t.doc_grades.length > 0);
                const grades = webSearchTrace?.doc_grades || gradeTrace?.doc_grades || [];
                
                const citationsHtml = grades.length > 0 ? `
                  <div class="citations-summary">
                    <div class="citations-title">Verified Context & Citations (${grades.length} evaluated):</div>
                    ${grades.map((g: any, i: number) => `
                      <div class="citation-item">
                        [${i + 1}] <strong>${g.source ? g.source.split('/').pop() : 'Source Passage'}</strong>
                        ${g.score === 'yes' ? '<span class="cit-status-pass"> — (Verified Relevant)</span>' : '<span class="cit-status-fail"> — (Filtered Out)</span>'}
                      </div>
                    `).join('')}
                  </div>
                ` : '';

                return `
                  <div class="message-block">
                    <div class="assistant-msg">
                      <div class="assistant-label">
                        <span>Ridge CRAG Synthesis</span>
                        ${confHtml}
                      </div>
                      <div class="assistant-content">${markdownToReportHtml(m.content)}</div>
                      ${citationsHtml}
                    </div>
                  </div>
                `;
              }
            }).join('')}
            <div class="footer-note">
              Generated by Ridge: High-Performance Corrective RAG Platform
            </div>
          </body>
        </html>
      `;

      const printFrame = document.createElement('iframe');
      printFrame.style.position = 'fixed';
      printFrame.style.right = '0';
      printFrame.style.bottom = '0';
      printFrame.style.width = '0';
      printFrame.style.height = '0';
      printFrame.style.border = '0';
      document.body.appendChild(printFrame);

      const frameDoc = printFrame.contentWindow?.document || printFrame.contentDocument;
      if (frameDoc) {
        frameDoc.open();
        frameDoc.write(printDoc);
        frameDoc.close();
        setTimeout(() => {
          printFrame.contentWindow?.focus();
          printFrame.contentWindow?.print();
          setTimeout(() => {
            if (document.body.contains(printFrame)) {
              document.body.removeChild(printFrame);
            }
          }, 4000);
        }, 350);
      }
      showToast('Opening print dialog (Save as PDF)...', 'info');
      return;
    }

    let content = '';
    let mimeType = 'text/plain';
    let ext = format;

    if (format === 'json') {
      content = JSON.stringify(messages, null, 2);
      mimeType = 'application/json';
    } else {
      content = `# Ridge: ${activeSession.title}\nExported on ${new Date().toLocaleString()}\n\n---\n\n` +
        messages.map(m => {
          const confidenceText = m.confidence ? `\n> **Grounded Confidence:** ${m.confidence.score}% (${m.confidence.level})\n` : '';
          return `### ${m.role === 'user' ? 'User' : 'Ridge'}\n${confidenceText}\n${m.content}\n\n`;
        }).join('\n---\n\n');
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ridge-${activeSession.id}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
    showToast(`Exported as .${ext}`);
  };

  // Last assistant traces for Stepper & Artifacts
  const lastAssistantMessage = messages.filter(m => m.role === 'assistant').pop();
  const activeTraces = lastAssistantMessage?.traces || [];
  const isCurrentlyStreaming = lastAssistantMessage?.isStreaming;

  const lastWebTrace = activeTraces.find(t => t.node === 'web_search_node' && t.doc_grades && t.doc_grades.length > 0);
  const lastGradeTrace = [...activeTraces].reverse().find(t => t.node === 'grade_node' && t.doc_grades && t.doc_grades.length > 0);
  const allDocGrades: any[] = lastWebTrace?.doc_grades || lastGradeTrace?.doc_grades || [];

  const totalPipelineLatency = activeTraces.reduce((sum, t) => sum + (t.latency_ms || 0), 0);

  // Time-aware greeting for Recall hero
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  };

  return (
    <div className={`recall-app ${isArtifactsOpen ? 'artifacts-active' : ''}`}>
      {/* Mobile Sidebar Overlay Backdrop */}
      <div 
        className={`sidebar-mobile-backdrop ${isSidebarOpen ? 'visible' : ''}`}
        onClick={() => setIsSidebarOpen(false)}
      />

      {/* Left Navigation Sidebar */}
      <aside className={`recall-sidebar ${isSidebarOpen ? 'open' : 'collapsed'}`}>
        <div className="sidebar-header">
          <div 
            className="recall-brand interactive-brand" 
            onClick={handleGoHome} 
            role="button" 
            tabIndex={0}
            title="Ridge Home - New Research Ascent"
          >
            <div className="brand-logo-frame">
              <RidgeLogo size={26} />
            </div>
            <div className="brand-texts">
              <div className="brand-row">
                <span className="brand-name">Ridge<span className="brand-dot">.</span></span>
              </div>
              <span className="brand-subtitle">CRAG Intelligence</span>
            </div>
          </div>
          <button 
            className="sidebar-collapse-btn" 
            onClick={() => setIsSidebarOpen(false)}
            title="Collapse sidebar"
            aria-label="Collapse sidebar"
          >
            <PanelLeftClose size={18} />
          </button>
        </div>

        <div className="sidebar-action-wrap">
          <button className="new-chat-btn" onClick={handleNewChat} aria-label="Start new ascent">
            <div className="new-chat-label-group">
              <Plus size={16} />
              <span>New Ascent</span>
            </div>
            <kbd className="shortcut-kbd-chip">⌘K</kbd>
          </button>
        </div>

        {/* Knowledge Crag Status Card */}
        <div className="sidebar-section">
          <div className="sidebar-section-title">Knowledge crag</div>
          <div 
            className="kb-stats-card" 
            onClick={() => {
              setIsIngestOpen(true);
              if (window.innerWidth < 768) setIsSidebarOpen(false);
            }}
            title="Manage and upload knowledge topo sources"
            role="button"
            tabIndex={0}
          >
            <div className="kb-stats-icon">
              <Database size={16} className="text-teal" />
            </div>
            <div className="kb-stats-meta">
              <div className="kb-stats-num">{stats.chunk_count} Anchored chunks</div>
              <div className="kb-stats-sub">
                <span className="live-status-dot" />
                <span>{stats.doc_count > 0 ? `${stats.doc_count} Topo sources active` : 'No sources attached'}</span>
              </div>
            </div>
            <Plus size={14} className="kb-add-icon" />
          </div>
        </div>

        {/* Recent Ascents */}
        <div className="sidebar-section recents-section">
          <div className="sidebar-section-title">Recent inquiries</div>
          <div className="sessions-list">
            {sessions.map(s => (
              <div 
                key={s.id} 
                className={`session-item ${s.id === activeSessionId ? 'active' : ''}`}
                onClick={() => handleSelectSession(s.id)}
                title={s.title}
              >
                <MessageSquare size={14} className="session-icon" />
                <div className="session-text-stack">
                  <span className="session-title">{s.title}</span>
                  <span className="session-timestamp">{getRelativeTime(s.createdAt)}</span>
                </div>
                <button 
                  className="session-delete-btn" 
                  onClick={(e) => handleDeleteSession(s.id, e)}
                  title="Delete ascent"
                  aria-label="Delete ascent"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Sidebar Footer with 3 Handcrafted Climbing Palettes & Color Dots */}
        <div className="sidebar-footer">
          <div className="theme-header-row">
            <span className="theme-label-caption">Theme</span>
          </div>
          <div className="theme-toggle-group">
            <button 
              className={`theme-btn ${theme === 'void' ? 'active' : ''}`}
              onClick={() => setTheme('void')}
              title="Chalk & Void: Dark Basalt & Alpine Teal"
              aria-label="Select Chalk & Void theme"
            >
              <span className="theme-color-dot void-dot" />
              <span>Void</span>
            </button>
            <button 
              className={`theme-btn ${theme === 'stone' ? 'active' : ''}`}
              onClick={() => setTheme('stone')}
              title="Stone & Summit: Warm Sandstone & Summit Blue"
              aria-label="Select Stone & Summit theme"
            >
              <span className="theme-color-dot stone-dot" />
              <span>Summit</span>
            </button>
            <button 
              className={`theme-btn ${theme === 'rust' ? 'active' : ''}`}
              onClick={() => setTheme('rust')}
              title="Rust & Ridge: Desert Crag & Terracotta Rust"
              aria-label="Select Rust & Ridge theme"
            >
              <span className="theme-color-dot rust-dot" />
              <span>Ridge</span>
            </button>
          </div>

          <div className="footer-meta">
            <span>PostgreSQL & pgvector · FlashRank · LangGraph · Groq</span>
          </div>
        </div>

      </aside>

      {/* Main Chat Workspace */}
      <main className="recall-main">
        {/* Top Navigation Bar with Simplified Hierarchy */}
        <header className="recall-navbar">
          <div className="navbar-left">
            {!isSidebarOpen && (
              <button 
                className="nav-btn sidebar-open-btn" 
                onClick={() => setIsSidebarOpen(true)}
                title="Expand sidebar"
                aria-label="Expand sidebar"
              >
                <PanelLeft size={18} />
              </button>
            )}

            <button 
              className="navbar-brand-anchor interactive-brand"
              onClick={handleGoHome}
              title="Ridge Home - Start New Ascent"
              type="button"
            >
              <span className="navbar-title">Ridge</span>
              <div className="engine-status-tag">
                <span className="engine-live-dot" />
                <span className="engine-name">Groq LLM</span>
              </div>
            </button>
          </div>

          <div className="navbar-right">
            {/* Observability Cluster */}
            <div className="nav-group-observability">
              <button 
                className={`nav-action-pill trace-pill ${isArtifactsOpen ? 'active' : ''} ${isCurrentlyStreaming ? 'pulsing' : ''}`}
                onClick={() => setIsArtifactsOpen(!isArtifactsOpen)}
                title="Inspect real-time LangGraph execution trace and state machine"
                aria-label="Toggle pipeline trace"
              >
                <Activity size={15} />
                <span className="btn-label-desktop">
                  {activeTraces.length > 0 ? `Trace (${activeTraces.length} steps)` : 'Pipeline Trace'}
                </span>
                <span className="btn-label-mobile">
                  {activeTraces.length > 0 ? `Trace (${activeTraces.length})` : 'Trace'}
                </span>
              </button>
            </div>

            <div className="navbar-divider" />

            {/* Session Action Cluster */}
            <div className="nav-group-actions">
              {(user?.role === 'admin' || user?.role === 'superadmin') && (
                <button 
                  className="nav-action-pill admin-pill"
                  onClick={() => navigate('/admin')}
                  title="Open Ridge Administrator Portal"
                  aria-label="Admin console"
                  type="button"
                >
                  <ShieldCheck size={15} />
                  <span>{user?.role === 'superadmin' ? 'SuperAdmin' : 'Admin'}</span>
                </button>
              )}



              <button 
                className="nav-action-pill glossary-pill"
                onClick={() => {
                  setIsGlossaryOpen(true);
                  fetchGlossary();
                }}
                title="Inspect corpus acronym and domain entity glossary"
                aria-label="Inspect glossary"
              >
                <BookOpen size={15} />
                <span>Glossary</span>
              </button>

              <button 
                className="nav-action-pill ingest-pill"
                onClick={() => setIsIngestOpen(true)}
                title="Ingest documents and articles into Knowledge Crag"
                aria-label="Ingest documents"
              >
                <Upload size={15} />
                <span>Ingest</span>
              </button>

              <button 
                className="nav-action-pill feedback-pill"
                onClick={() => {
                  setFeedbackTargetContext(null);
                  setIsFeedbackOpen(true);
                }}
                title="Send accuracy feedback or request help from administrators"
                aria-label="Feedback"
                type="button"
              >
                <MessageSquare size={15} />
                <span>Feedback</span>
              </button>



              {messages.length > 0 && (
                <>
                  <button 
                    className="nav-icon-btn" 
                    onClick={() => setIsExportOpen(true)}
                    title="Export ascent logs (Markdown or JSON)"
                    aria-label="Export ascent"
                  >
                    <Download size={16} />
                  </button>
                  <button 
                    className="nav-icon-btn" 
                    onClick={clearCurrentChat}
                    title="Clear current ascent messages"
                    aria-label="Clear ascent"
                  >
                    <Trash2 size={16} />
                  </button>
                </>
              )}
            </div>

            {/* User Profile / Auth Action */}
            <div className="navbar-divider" />
            <div className="nav-group-user">
              {user && !user.is_guest ? (
                <div className="user-capsule-container" ref={userDropdownRef}>
                  <button 
                    className="user-profile-capsule"
                    onClick={(e) => {
                      e.stopPropagation();
                      setIsUserDropdownOpen(prev => !prev);
                    }}
                    title={user.name || user.username}
                    aria-label="User profile menu"
                    type="button"
                  >
                    {user.avatar_url ? (
                      <img src={user.avatar_url} alt={user.name || user.username} className="user-avatar-img" />
                    ) : (
                      <div className="user-avatar-placeholder">
                        {(user.name || user.username || 'C').charAt(0).toUpperCase()}
                      </div>
                    )}
                    <span className="user-capsule-name">{(user.name || user.username || 'Climber').split(' ')[0]}</span>
                    <ChevronDown size={13} className={`dropdown-caret ${isUserDropdownOpen ? 'open' : ''}`} />
                  </button>

                  {isUserDropdownOpen && (
                    <div className="user-dropdown-menu" onClick={e => e.stopPropagation()}>
                      <div className="user-dropdown-header">
                        <div className="dropdown-user-name">{user.name || user.username}</div>
                        <div className="dropdown-user-email">{user.email}</div>
                        <div className="dropdown-user-provider">
                          <span className={`provider-badge ${user.role === 'admin' ? 'admin' : (user.provider || 'local')}`}>
                            {user.role === 'admin' ? 'Administrator' : (user.provider === 'local' ? 'Local Account' : user.provider)}
                          </span>
                        </div>
                      </div>

                      {/* Daily Request Quota Tracker */}
                      <div className="dropdown-quota-box">
                        <div className="quota-row-label">
                          <span className="quota-title">Daily Ascent Quota</span>
                          <span className="quota-count">
                            {user.role === 'admin' ? 'Unlimited' : `${user.requests_today || 0} / ${user.daily_request_limit || 50}`}
                          </span>
                        </div>
                        {user.role !== 'admin' && (
                          <div className="quota-track">
                            <div 
                              className={`quota-fill ${((user.requests_today || 0) / (user.daily_request_limit || 50)) >= 0.85 ? 'warning' : ''}`} 
                              style={{ width: `${Math.min(100, (((user.requests_today || 0) / (user.daily_request_limit || 50)) * 100))}%` }}
                            />
                          </div>
                        )}
                      </div>

                      <div className="dropdown-divider" />

                      {(user.role === 'admin' || user.role === 'superadmin') && (
                        <button 
                          className="dropdown-action-btn admin-menu-btn" 
                          onClick={() => {
                            setIsUserDropdownOpen(false);
                            navigate('/admin');
                          }} 
                          type="button"
                        >
                          <Shield size={14} />
                          <span>Admin Console</span>
                        </button>
                      )}


                      <button className="dropdown-action-btn logout-btn" onClick={handleLogout} type="button">
                        <LogOut size={14} />
                        <span>Sign Out</span>
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <button 
                  className="nav-action-pill login-pill"
                  onClick={() => setIsAuthModalOpen(true)}
                  title="Sign in or Register"
                  aria-label="Sign in"
                  type="button"
                >
                  <LogIn size={15} />
                  <span>Sign In</span>
                </button>
              )}
            </div>
          </div>
        </header>

        {/* Chat Feed Area */}
        <div className="conversation-viewport">
          {messages.length === 0 ? (
            <div className="recall-hero">
              <div className="hero-salutation">
                <div className="hero-logo-frame">
                  <RidgeLogo size={52} />
                </div>
                <h1 className="hero-heading">{getGreeting()}, Climber</h1>
                <p className="hero-subtext">
                  Navigate complex knowledge bases with self-correcting RAG intelligence.
                </p>
              </div>

              {/* Dynamic Suggested Inquiries (Asymmetric Bento Grid) */}
              <div className="hero-suggestions-deck">
                <div className="deck-grid">
                  {suggestions.length > 0 ? (
                    suggestions.map((sug, i) => (
                      <button 
                        key={i} 
                        className={`recall-prompt-card ${i === 0 ? 'featured' : ''}`}
                        onClick={() => handleSend(sug)}
                      >
                        <div className="prompt-content-wrap">
                          <span className="prompt-text">{sug}</span>
                        </div>
                        <ChevronRight size={16} className="prompt-arrow" />
                      </button>
                    ))
                  ) : (
                    <>
                      <button 
                        className="recall-prompt-card featured"
                        onClick={() => handleSend("Summarize the primary topo knowledge anchored in the crag.")}
                      >
                        <div className="prompt-content-wrap">
                          <span className="prompt-title">Summarize Topo Sources</span>
                          <span className="prompt-desc">Synthesize key concepts across all indexed vectors</span>
                        </div>
                        <ChevronRight size={16} className="prompt-arrow" />
                      </button>

                      <button 
                        className="recall-prompt-card"
                        onClick={() => handleSend("Explain the architectural components and state machine graph.")}
                      >
                        <div className="prompt-content-wrap">
                          <span className="prompt-title">Architectural Route Synthesis</span>
                          <span className="prompt-desc">Cross-evaluate LangGraph node transitions</span>
                        </div>
                        <ChevronRight size={16} className="prompt-arrow" />
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* Feature Tags Strip */}
              <div className="hero-feature-tags">
                <div className="feature-tag">
                  <ShieldCheck size={13} className="text-moss" />
                  <span>Strict Hallucination Filter</span>
                </div>
                <div className="feature-tag">
                  <Zap size={13} className="text-teal" />
                  <span>FlashRank MMR Re-ranking</span>
                </div>
                <div className="feature-tag">
                  <Globe size={13} className="text-rust" />
                  <span>Dynamic Web Fallback</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="messages-thread">
              {messages.map((msg) => (
                <ChatMessageItem
                  key={msg.id}
                  msg={msg}
                  isExpanded={expandedThinking[msg.id] ?? false}
                  activeCitationHighlight={activeCitationHighlight}
                  copiedId={copiedId}
                  onToggleThinking={(id) => setExpandedThinking(prev => ({ ...prev, [id]: !prev[id] }))}
                  onSelectConflict={(c) => setSelectedConflictDiff(c)}
                  onSelectSource={(s) => {
                    setHoveredCitation(null);
                    setSelectedSourceModal(s);
                  }}
                  onCopy={(text, id) => copyToClipboard(text, id)}
                  onReaction={(id, liked) => handleReaction(id, liked)}
                  onOpenFeedback={handleOpenFeedbackForMessage}
                  onHoverCitation={(h) => setHoveredCitation(h)}

                  onHighlightCitation={(h) => setActiveCitationHighlight(h)}
                  onFileClick={(path) => {
                    navigator.clipboard.writeText(path);
                    showToast(`Copied path: ${path.split('/').pop() || path}`, 'info');
                  }}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Isolated Zero-Lag Chat Input Deck */}
        <ChatInputDeck
          ref={chatInputRef}
          isLoading={isLoading}
          onSend={(query) => handleSend(query)}
          onStop={handleStopGeneration}
          onAttachFile={handleChatFileAttach}
          selectedSourceFilter={selectedSourceFilter}
          onSelectSourceFilter={(s) => {
            setSelectedSourceFilter(s);
            showToast(s === 'all' ? 'Search scope set to All Sources' : `Scoped queries to: ${s.split('/').pop() || s}`, 'info');
          }}
          kbSources={kbSources}
          onFetchKBSources={fetchKBSources}
          webSearchEnabled={webSearchEnabled}
          onToggleWebSearch={() => {
            const nextVal = !webSearchEnabled;
            setWebSearchEnabled(nextVal);
            showToast(nextVal ? 'Web search fallback enabled' : 'Web search fallback disabled (Local KB only)', 'info');
          }}
        />

        <div className="input-deck-disclaimer">
          Ridge can make mistakes. Verify important information against indexed sources.
        </div>
      </main>

      {/* Mobile Artifacts Drawer Backdrop */}
      <div 
        className={`artifacts-mobile-backdrop ${isArtifactsOpen ? 'visible' : ''}`}
        onClick={() => setIsArtifactsOpen(false)}
      />

      {/* Pipeline Trace & Artifacts Split Panel */}
      {isArtifactsOpen && (
        <aside className="recall-artifacts-panel">
          <div className="artifacts-panel-header">
            <div className="artifacts-tab-group">
              <button 
                className={`tab-item ${activeArtifactTab === 'trace' ? 'active' : ''}`}
                onClick={() => setActiveArtifactTab('trace')}
              >
                <Activity size={14} />
                <span>Ascent Trace</span>
              </button>
              <button 
                className={`tab-item ${activeArtifactTab === 'knowledge' ? 'active' : ''}`}
                onClick={() => setActiveArtifactTab('knowledge')}
              >
                <Database size={14} />
                <span>Knowledge Crag</span>
              </button>
              <button 
                className={`tab-item ${activeArtifactTab === 'grader' ? 'active' : ''}`}
                onClick={() => setActiveArtifactTab('grader')}
              >
                <CheckCircle size={14} />
                <span>Grader Topo</span>
              </button>
            </div>

            <button 
              className="panel-close-btn" 
              onClick={() => setIsArtifactsOpen(false)}
              title="Close panel"
              aria-label="Close panel"
            >
              <X size={18} />
            </button>
          </div>

          <div className="artifacts-panel-body">
            {/* Tab 1: LangGraph Execution Stepper */}
            {activeArtifactTab === 'trace' && (
              <div className="tab-pane trace-pane">
                <div className="pane-summary-card">
                  <div className="summary-col">
                    <span className="summary-label">State Machine</span>
                    <span className="summary-val">LangGraph CRAG</span>
                  </div>
                  <div className="summary-col">
                    <span className="summary-label">Total Latency</span>
                    <span className="summary-val">{totalPipelineLatency} ms</span>
                  </div>
                  <div className="summary-col">
                    <span className="summary-label">Status</span>
                    <span className={`summary-badge ${isCurrentlyStreaming ? 'running' : 'idle'}`}>
                      {isCurrentlyStreaming ? 'Ascending' : 'Anchored'}
                    </span>
                  </div>
                </div>

                {activeTraces.length === 0 ? (
                  <div className="pane-empty-state">
                    <Activity size={32} className="text-muted" />
                    <h4>No active ascent trace</h4>
                    <p>Submit an inquiry in the chat to watch LangGraph node transitions and latencies in real time.</p>
                  </div>
                ) : (
                  <div className="trace-stepper-list">
                    {activeTraces.map((trace, i) => {
                      const nodeInfo = getNodeDetails(trace.node);
                      const isLast = i === activeTraces.length - 1;
                      const isActive = isCurrentlyStreaming && isLast;

                      return (
                        <div key={i} className={`stepper-node-card ${isActive ? 'in-progress' : 'finished'}`}>
                          <div className="card-top-row">
                            <div className="node-title-group">
                              <span className="node-icon">{nodeInfo.icon}</span>
                              <span className="node-title">{nodeInfo.title}</span>
                            </div>
                            {trace.latency_ms != null && (
                              <span className="latency-tag">{trace.latency_ms} ms</span>
                            )}
                          </div>
                          <p className="node-desc-text">{nodeInfo.desc}</p>
                          <div className="node-output-box">
                            <span className="output-label">Status:</span>
                            <span className="output-msg">{trace.message}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* Tab 2: Knowledge Base Manager */}
            {activeArtifactTab === 'knowledge' && (
              <div className="tab-pane kb-pane">
                <div className="kb-hero-card">
                  <div className="kb-stats-grid">
                    <div className="stat-box">
                      <span className="stat-number">{stats.chunk_count}</span>
                      <span className="stat-title">Anchored Chunks</span>
                    </div>
                    <div className="stat-box">
                      <span className="stat-number">{stats.doc_count}</span>
                      <span className="stat-title">Indexed Sources</span>
                    </div>
                  </div>
                  <div className="kb-actions-row">
                    <button 
                      className="kb-upload-trigger-btn"
                      onClick={() => setIsIngestOpen(true)}
                    >
                      <Plus size={15} />
                      <span>Anchor Source</span>
                    </button>
                    {stats.chunk_count > 0 && (
                      <button 
                        className="kb-clear-all-btn"
                        onClick={handleClearAllKB}
                        disabled={isClearingKB}
                        title="Clear entire knowledge base"
                      >
                        {isClearingKB ? <RotateCw size={13} className="spin-slow" /> : <Trash2 size={13} />}
                        <span>Wipe KB</span>
                      </button>
                    )}
                  </div>
                </div>

                <div className="kb-search-bar">
                  <Search size={14} className="text-muted" />
                  <input 
                    type="text" 
                    placeholder="Filter indexed sources & chunks..." 
                    value={searchDocFilter}
                    onChange={(e) => setSearchDocFilter(e.target.value)}
                  />
                  {searchDocFilter && (
                    <button className="kb-search-clear" onClick={() => setSearchDocFilter('')}>
                      <X size={12} />
                    </button>
                  )}
                </div>

                {/* Sources & Chunks List */}
                {isLoadingKBSources ? (
                  <div className="kb-loading-state">
                    <RotateCw size={20} className="spin-slow text-muted" />
                    <span>Loading knowledge base sources...</span>
                  </div>
                ) : kbSources.length === 0 ? (
                  <div className="pane-empty-state">
                    <Database size={32} className="text-muted" />
                    <h4>Knowledge Base Empty</h4>
                    <p>No documents or chunks are currently stored in PostgreSQL. Anchor a file, URL, or YouTube video to get started.</p>

                    <button 
                      className="recall-btn-primary"
                      style={{ marginTop: '12px', padding: '6px 14px', fontSize: '0.8rem' }}
                      onClick={() => setIsIngestOpen(true)}
                    >
                      <Plus size={14} />
                      <span>Anchor First Document</span>
                    </button>
                  </div>
                ) : (
                  <div className="kb-sources-list">
                    {kbSources
                      .filter(s => {
                        if (!searchDocFilter.trim()) return true;
                        const query = searchDocFilter.toLowerCase();
                        return (
                          s.name.toLowerCase().includes(query) ||
                          s.source.toLowerCase().includes(query) ||
                          s.sample.toLowerCase().includes(query) ||
                          (s.h1 && s.h1.toLowerCase().includes(query))
                        );
                      })
                      .map((src, i) => (
                        <div key={i} className="kb-source-card">
                          <div className="source-card-header">
                            <div className="source-icon-wrap">
                              {getSourceIcon(src.source, src.type)}
                            </div>
                            <div className="source-title-group">
                              <span className="source-card-name" title={src.source}>
                                {src.name}
                              </span>
                              <span className="source-chunk-badge">
                                {src.chunk_count} {src.chunk_count === 1 ? 'chunk' : 'chunks'}
                              </span>
                            </div>
                            <button 
                              className="source-delete-btn"
                              onClick={() => handleDeleteKBSource(src.source, src.name, src.ids)}
                              disabled={deletingSource === src.source}
                              title={`Delete ${src.name}`}
                              aria-label={`Delete ${src.name}`}
                            >
                              {deletingSource === src.source ? (
                                <RotateCw size={14} className="spin-slow" />
                              ) : (
                                <Trash2 size={14} />
                              )}
                            </button>
                          </div>

                          {src.sample && (
                            <p className="source-preview-snippet">
                              "{src.sample.replace(/\n+/g, ' ')}..."
                            </p>
                          )}
                        </div>
                      ))}
                  </div>
                )}
              </div>
            )}

            {/* Tab 3: Grader & Citation Inspector */}
            {activeArtifactTab === 'grader' && (() => {
              const latestConfMsg = [...messages].reverse().find(m => m.role === 'assistant' && m.confidence);
              const conf = latestConfMsg?.confidence;

              return (
                <div className="tab-pane grader-pane">
                  {conf && (
                    <div className={`grader-confidence-hero ${conf.level.toLowerCase()}`}>
                      <div className="conf-hero-top">
                        <div className="conf-big-score-group">
                          <span className="conf-big-score">{conf.score}%</span>
                          <div className="conf-hero-text">
                            <span className="conf-hero-title">Grounded Confidence</span>
                            <span className={`conf-hero-badge ${conf.level.toLowerCase()}`}>
                              {conf.level} VERACITY
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="conf-hero-metrics-grid">
                        <div className="conf-metric-tile">
                          <span className="tile-label">Source Provenance</span>
                          <span className="tile-value">{conf.breakdown.source_trust}</span>
                        </div>
                        <div className="conf-metric-tile">
                          <span className="tile-label">Grader Consensus</span>
                          <span className="tile-value">{conf.breakdown.grader_consensus}%</span>
                        </div>
                        <div className="conf-metric-tile">
                          <span className="tile-label">Verified Chunks</span>
                          <span className="tile-value">{conf.breakdown.relevant_chunks}</span>
                        </div>
                        <div className="conf-metric-tile">
                          <span className="tile-label">Reformulations</span>
                          <span className="tile-value">{conf.breakdown.reformulation_loops}</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {allDocGrades.length === 0 ? (
                    <div className="pane-empty-state">
                      <CheckCircle size={32} className="text-muted" />
                      <h4>No Graded Contexts</h4>
                      <p>Ask a question to see how Groq LLM evaluates each retrieved chunk for hallucinations.</p>
                    </div>
                  ) : (
                    <div className="grader-cards-list">
                    {allDocGrades.map((g: any, idx: number) => {
                      const isPass = g.score === 'yes';
                      return (
                        <div key={idx} className={`grader-detail-card ${isPass ? 'pass' : 'fail'}`}>
                          <div className="grader-card-header">
                            <span className={`grader-badge ${isPass ? 'pass' : 'fail'}`}>
                              <span className="badge-icon-inline">
                                {isPass ? <Check size={11} /> : <X size={11} />}
                              </span>
                              {isPass ? 'VERIFIED RELEVANT' : 'FILTERED OUT (CRUX)'}
                            </span>
                            <span className="grader-source-name">
                              {g.source ? g.source.split('/').pop() : `Chunk #${idx + 1}`}
                            </span>
                          </div>
                          {g.rationale && (
                            <div className="grader-rationale-box">
                              <span className="rationale-tag">Grader Rationale:</span>
                              <p>{g.rationale}</p>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })()}
          </div>
        </aside>
      )}

      {/* Ingestion Modal */}
      {isIngestOpen && (
        <div className="recall-modal-backdrop" onClick={() => setIsIngestOpen(false)}>
          <div className="recall-modal-card" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-wrap">
                <RidgeLogo size={22} />
                <h3>Anchor Knowledge Sources</h3>
              </div>
              <button className="modal-close-btn" onClick={() => setIsIngestOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-mode-tabs">
              <button 
                className={`mode-tab ${ingestMode === 'file' ? 'active' : ''}`}
                onClick={() => setIngestMode('file')}
              >
                <FileText size={15} />
                <span>Upload Topo Files</span>
              </button>
              <button 
                className={`mode-tab ${ingestMode === 'url' ? 'active' : ''}`}
                onClick={() => setIngestMode('url')}
              >
                <Globe size={15} />
                <span>Web URL / Text</span>
              </button>
            </div>

            <div className="modal-body-area">
              {ingestMode === 'file' ? (
                <div className="multi-file-ingest-container">
                  <div 
                    className={`recall-dropzone ${isDragging ? 'dragging' : ''} ${uploadQueue.length > 0 ? 'has-queue' : ''}`}
                    onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={handleFileDrop}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <input 
                      type="file" 
                      ref={fileInputRef} 
                      multiple
                      onChange={(e) => {
                        if (e.target.files && e.target.files.length > 0) {
                          handleAddFilesToQueue(e.target.files);
                        }
                      }}
                      accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tiff,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.csv,.tsv,.md,.markdown,.txt,.py,.js,.ts,.tsx,.jsx,.json,.yaml,.yml,.toml,.sql,.html,.css,.cpp,.c,.h,.java,.go,.rs,.sh,.srt,.vtt"
                      style={{ display: 'none' }}
                    />
                    <div className="dropzone-empty-prompt">
                      <Upload size={28} className="text-teal" />
                      <p>Drag and drop <strong>Multiple Documents, OCR Images, or Slides</strong></p>
                      <span className="dropzone-sub-formats">Select multiple PDFs, Word documents, PPTX, Images, or Code</span>
                      <span className="dropzone-tap-prompt">+ Tap to browse files</span>
                    </div>
                  </div>

                  {/* Upload Queue Progress & File List */}
                  {uploadQueue.length > 0 && (
                    <div className="upload-queue-card">
                      <div className="upload-queue-header">
                        <div className="queue-title-count">
                          <span>Upload Queue ({uploadQueue.length} files)</span>
                          {uploadProgress && (
                            <span className="queue-progress-tag">
                              Indexing {uploadProgress.current} of {uploadProgress.total} ({Math.round((uploadProgress.current / uploadProgress.total) * 100)}%)
                            </span>
                          )}
                        </div>
                        {!isIngesting && (
                          <button
                            type="button"
                            className="queue-clear-btn"
                            onClick={handleClearQueue}
                          >
                            Clear All
                          </button>
                        )}
                      </div>

                      {uploadProgress && (
                        <div className="queue-progress-bar-track">
                          <div 
                            className="queue-progress-bar-fill" 
                            style={{ width: `${(uploadProgress.current / uploadProgress.total) * 100}%` }}
                          />
                        </div>
                      )}

                      <div className="upload-queue-items-list">
                        {uploadQueue.map((item) => (
                          <div key={item.id} className={`upload-queue-row ${item.status}`}>
                            <div className="queue-item-main">
                              <FileText size={14} className="text-teal" />
                              <span className="queue-item-name" title={item.file.name}>{item.file.name}</span>
                              <span className="queue-item-size">{(item.file.size / 1024).toFixed(1)} KB</span>
                            </div>

                            <div className="queue-item-status-col">
                              {item.status === 'waiting' && <span className="queue-badge waiting">Waiting</span>}
                              {item.status === 'uploading' && (
                                <span className="queue-badge uploading">
                                  <RotateCw size={11} className="spin-slow" /> Indexing...
                                </span>
                              )}
                              {item.status === 'completed' && (
                                <span className="queue-badge completed">
                                  ✓ Anchored ({item.chunksAdded || 0} chunks)
                                </span>
                              )}
                              {item.status === 'error' && (
                                <span className="queue-badge error" title={item.error}>
                                  ✕ Error
                                </span>
                              )}
                              {!isIngesting && (
                                <button
                                  type="button"
                                  className="queue-remove-btn"
                                  onClick={() => handleRemoveQueueItem(item.id)}
                                  title="Remove from queue"
                                >
                                  <X size={12} />
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="url-scrape-area">
                  <label className="input-field-label">Web URL, YouTube Video, or Raw Text / Code:</label>
                  <textarea 
                    className="recall-modal-textarea"
                    placeholder="Enter Web URL, YouTube link (e.g. https://youtu.be/... for automatic transcript extraction), GitHub link, or paste raw text..."
                    value={ingestInput}
                    onChange={e => setIngestInput(e.target.value)}
                    rows={5}
                  />
                  <div className="url-hints-row">
                    <span className="url-hint-badge">✨ Auto-transcribes YouTube Videos</span>
                    <span className="url-hint-badge">🌐 Scrapes Web & ArXiv Papers</span>
                  </div>
                </div>
              )}
            </div>

            <div className="modal-footer-row">
              <button className="btn-ghost" onClick={() => setIsIngestOpen(false)}>
                Cancel
              </button>
              <button 
                className={`recall-btn-primary ${isIngestSuccess ? 'success' : ''}`} 
                onClick={handleIngest} 
                disabled={(ingestMode === 'file' ? uploadQueue.length === 0 : !ingestInput.trim()) || isIngesting || isIngestSuccess}
              >
                {isIngesting ? (
                  <>
                    <RotateCw size={15} className="spin-slow" />
                    <span>{uploadProgress ? `Indexing ${uploadProgress.current}/${uploadProgress.total}...` : 'Anchoring Chunks...'}</span>
                  </>
                ) : isIngestSuccess ? (
                  <>
                    <Check size={15} />
                    <span>Successfully Anchored</span>
                  </>
                ) : (
                  <>
                    <Plus size={15} />
                    <span>{uploadQueue.length > 1 ? `Anchor ${uploadQueue.length} Files` : 'Anchor to Crag'}</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Export Conversation Modal */}
      {isExportOpen && (
        <div className="recall-modal-backdrop" onClick={() => setIsExportOpen(false)}>
          <div className="recall-modal-card export-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-wrap">
                <Download size={18} className="text-teal" />
                <h3>Export Ascent Logs</h3>
              </div>
              <button className="modal-close-btn" onClick={() => setIsExportOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body-area">
              <p className="export-desc">Download this ascent thread with questions, traces, and answers:</p>
              <div className="export-options-grid">
                <button className="export-choice-card" onClick={() => exportConversation('md')}>
                  <FileText size={24} className="text-teal" />
                  <span className="choice-title">Markdown Topo (.md)</span>
                  <span className="choice-desc">Formatted document for Obsidian, Notion, or Github</span>
                </button>
                <button className="export-choice-card" onClick={() => exportConversation('pdf')}>
                  <Sparkles size={24} className="text-moss" />
                  <span className="choice-title">Print / PDF Report</span>
                  <span className="choice-desc">Formatted research brief ready for print or saving as PDF</span>
                </button>
                <button className="export-choice-card" onClick={() => exportConversation('json')}>
                  <Database size={24} className="text-rust" />
                  <span className="choice-title">JSON Ascent (.json)</span>
                  <span className="choice-desc">Structured conversation traces and metadata</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* NotebookLM Source Detail Modal */}
      {selectedSourceModal && (
        <NotebookLMSourceModal
          citation={selectedSourceModal}
          onClose={() => setSelectedSourceModal(null)}
        />
      )}


      {/* Side-by-Side Conflict Diff Viewer Modal */}
      {selectedConflictDiff && (
        <div className="recall-modal-backdrop" onClick={() => setSelectedConflictDiff(null)}>
          <div className="recall-modal-card conflict-diff-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-wrap">
                <AlertTriangle size={18} className="text-rust" />
                <div>
                  <h3>Document Contradiction & Version Diff</h3>
                  {selectedConflictDiff.summary && (
                    <p className="modal-subtitle-text">{selectedConflictDiff.summary}</p>
                  )}
                </div>
              </div>
              <button className="modal-close-btn" onClick={() => setSelectedConflictDiff(null)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body-area">
              <div className="conflict-diff-split-grid">
                {(selectedConflictDiff.passages && selectedConflictDiff.passages.length > 0
                  ? selectedConflictDiff.passages
                  : selectedConflictDiff.sources.map((src): ConflictPassage => ({
                      source: src,
                      name: src.split('/').pop() || src,
                      text: `Indexed content from ${src}`,
                      rationale: undefined
                    }))
                ).map((p, pIdx) => (
                  <div key={pIdx} className="conflict-diff-column">
                    <div className="conflict-diff-card-header">
                      <div className="conflict-diff-source-title">
                        <FileText size={14} className="text-indigo" />
                        <span title={p.source}>{p.name}</span>
                      </div>
                      <button
                        type="button"
                        className="conflict-diff-copy-btn"
                        onClick={() => {
                          navigator.clipboard.writeText(p.text);
                          showToast(`Copied excerpt from ${p.name}`, 'info');
                        }}
                        title="Copy excerpt"
                      >
                        <Copy size={12} />
                        <span>Copy</span>
                      </button>
                    </div>
                    <div className="conflict-diff-text-box">
                      {p.text}
                    </div>
                    {p.rationale && (
                      <div className="conflict-diff-rationale">
                        <strong>Relevance context:</strong> {p.rationale}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Glossary Modal */}
      {isGlossaryOpen && (
        <div className="recall-modal-backdrop" onClick={() => setIsGlossaryOpen(false)}>
          <div className="recall-modal-card glossary-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-wrap">
                <BookOpen size={18} className="text-teal" />
                <h3>Corpus Acronym & Entity Glossary</h3>
              </div>
              <button className="modal-close-btn" onClick={() => setIsGlossaryOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body-area">
              <p className="export-desc">
                Domain acronyms and terminology automatically indexed from your uploaded documents to power semantic query reformulation:
              </p>
              {isGlossaryLoading ? (
                <div className="empty-state-card" style={{ padding: '24px' }}>Loading indexed glossary terms...</div>
              ) : glossary.length === 0 ? (
                <div className="empty-state-card" style={{ padding: '24px' }}>
                  No domain acronyms indexed yet. Upload or ingest documents containing acronym definitions (e.g. <code>CRAG (Corrective Retrieval-Augmented Generation)</code>) to automatically build your domain glossary.
                </div>
              ) : (
                <div className="glossary-items-grid">
                  {glossary.map((item, idx) => (
                    <div key={idx} className="glossary-item-card">
                      <div className="glossary-term-badge">{item.term}</div>
                      <div className="glossary-term-expansion">{item.expansion}</div>
                      <div className="glossary-term-source">Source: {item.source}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* NotebookLM Citation Hover Preview Popover */}
      {hoveredCitation && !selectedSourceModal && !isGlossaryOpen && !isAdminModalOpen && !isExportOpen && !isIngestOpen && !isAuthModalOpen && (
        <NotebookLMCitationPopover
          citation={hoveredCitation.target || { index: hoveredCitation.index }}
          rect={hoveredCitation.rect}
          onClose={() => setHoveredCitation(null)}
          onInspect={(c) => setSelectedSourceModal(c)}
        />
      )}


      {/* Admin Management Console Modal */}
      {isAdminModalOpen && (
        <div className="recall-modal-backdrop" onClick={() => setIsAdminModalOpen(false)}>
          <div className="recall-modal-card admin-modal-card" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-wrap">
                <div className="admin-summit-badge">
                  <ShieldCheck size={18} />
                </div>
                <div>
                  <div className="admin-header-title-row">
                    <h3>Enterprise Command & User Portal</h3>
                    {adminStats?.tenant_name && (
                      <span className="admin-enterprise-badge">
                        <Building2 size={13} />
                        <span>{adminStats.tenant_name}</span>
                        {adminStats.tenant_slug && <span className="tenant-slug-tag">@{adminStats.tenant_slug}</span>}
                      </span>
                    )}
                    {(user?.role === 'superadmin' || adminStats?.is_superadmin) && (
                      <span className="superadmin-status-pill">
                        <Crown size={12} />
                        <span>SuperAdmin Global Mode</span>
                      </span>
                    )}
                  </div>
                  <p className="modal-subtitle-text">
                    {(user?.role === 'superadmin' || adminStats?.is_superadmin)
                      ? 'Global system management: provision institutions, assign roles, and inspect all tenant workspaces'
                      : `Manage members, permission roles, and inference quotas for ${adminStats?.tenant_name || 'your enterprise'}`}
                  </p>
                </div>
              </div>
              <button className="modal-close-btn" onClick={() => setIsAdminModalOpen(false)} aria-label="Close">
                <X size={18} />
              </button>
            </div>

            {/* SuperAdmin Navigation Tabs */}
            {(user?.role === 'superadmin' || adminStats?.is_superadmin) && (
              <div className="admin-subnav-tabs">
                <button
                  type="button"
                  className={`admin-subnav-btn ${adminActiveTab === 'users' ? 'active' : ''}`}
                  onClick={() => setAdminActiveTab('users')}
                >
                  <Users size={15} />
                  <span>Climbers & Members ({adminUsers.length})</span>
                </button>
                <button
                  type="button"
                  className={`admin-subnav-btn ${adminActiveTab === 'tenants' ? 'active' : ''}`}
                  onClick={() => setAdminActiveTab('tenants')}
                >
                  <Building2 size={15} />
                  <span>Institutions & Enterprises ({adminTenantsList.length})</span>
                </button>
              </div>
            )}

            <div className="admin-modal-body">
              {/* Aggregate Enterprise / System Metrics */}
              {adminStats && (
                <div className="admin-metrics-grid">
                  <div className="admin-metric-card">
                    <div className="metric-icon-wrap text-teal">
                      <Users size={18} />
                    </div>
                    <div className="metric-info">
                      <span className="metric-value">{adminStats.total_users}</span>
                      <span className="metric-label">
                        {(user?.role === 'superadmin' || adminStats?.is_superadmin) ? `${adminStats.active_users} Total Active Climbers` : `${adminStats.active_users} Active Climbers`}
                      </span>
                    </div>
                  </div>

                  <div className="admin-metric-card">
                    <div className="metric-icon-wrap text-moss">
                      <Activity size={18} />
                    </div>
                    <div className="metric-info">
                      <span className="metric-value">{adminStats.total_requests_today}</span>
                      <span className="metric-label">System Requests Today</span>
                    </div>
                  </div>

                  <div className="admin-metric-card">
                    <div className="metric-icon-wrap text-rust">
                      <Database size={18} />
                    </div>
                    <div className="metric-info">
                      <span className="metric-value">{adminStats.total_documents}</span>
                      <span className="metric-label">{adminStats.total_chunks} Anchored Chunks</span>
                    </div>
                  </div>
                </div>
              )}

              {/* VIEW 1: CLIMBERS & MEMBERS TAB */}
              {adminActiveTab === 'users' && (
                <>
                  {/* Controls bar: Search, Enterprise Switcher & Add User */}
                  <div className="admin-controls-bar">
                    <div className="admin-search-wrap">
                      <Search size={15} className="search-icon" />
                      <input
                        type="text"
                        placeholder="Filter by name, username, email, role, or enterprise..."
                        value={adminSearch}
                        onChange={e => setAdminSearch(e.target.value)}
                        className="admin-search-input"
                      />
                      {adminSearch && (
                        <button className="clear-search-btn" onClick={() => setAdminSearch('')}>
                          <X size={13} />
                        </button>
                      )}
                    </div>

                    {(user?.role === 'superadmin' || adminStats?.is_superadmin) && adminTenantsList.length > 0 && (
                      <div className="admin-tenant-switcher-wrap">
                        <Building2 size={14} className="tenant-switch-icon" />
                        <select
                          className="admin-tenant-switcher-select"
                          value={adminTenantFilter}
                          onChange={e => {
                            setAdminTenantFilter(e.target.value);
                            fetchAdminData(e.target.value);
                          }}
                        >
                          <option value="">All Enterprises (Global)</option>
                          {adminTenantsList.map(t => (
                            <option key={t.id} value={t.id}>
                              {t.name} (@{t.slug})
                            </option>
                          ))}
                        </select>
                      </div>
                    )}

                    <div className="admin-actions-group">
                      <button
                        className="admin-add-user-btn"
                        onClick={() => {
                          setIsAddUserModalOpen(true);
                          setNewUsername('');
                          setNewEmail('');
                          setNewName('');
                          setNewPassword('');
                          setNewRole('user');
                          setNewLimit(50);
                          setNewTenantId(adminTenantFilter || user?.tenant_id || '');
                        }}
                        title="Directly add a new member"
                      >
                        <UserPlus size={14} />
                        <span>Add Member</span>
                      </button>

                      <button
                        className="admin-refresh-btn"
                        onClick={() => fetchAdminData()}
                        disabled={isLoadingAdmin}
                        title="Refresh List"
                      >
                        <RotateCw size={14} className={isLoadingAdmin ? 'spin-slow' : ''} />
                        <span>Refresh</span>
                      </button>
                    </div>
                  </div>


              {/* Users Table */}
              <div className="admin-table-container">
                {/* Bulk Action Bar */}
                {selectedUserIds.size > 0 && (
                  <div className="bulk-action-bar">
                    <span className="bulk-count">{selectedUserIds.size} selected</span>
                    <button
                      className="bulk-delete-btn"
                      onClick={handleBulkDeleteUsers}
                      disabled={isBulkDeleting}
                    >
                      <Trash2 size={14} />
                      <span>{isBulkDeleting ? 'Deleting...' : `Delete ${selectedUserIds.size}`}</span>
                    </button>
                    <button
                      className="bulk-clear-btn"
                      onClick={() => setSelectedUserIds(new Set())}
                    >
                      <X size={13} />
                      <span>Clear</span>
                    </button>
                  </div>
                )}
                {isLoadingAdmin && adminUsers.length === 0 ? (
                  <div className="admin-loading-state">
                    <RotateCw size={24} className="spin-slow text-teal" />
                    <span>Loading climber accounts...</span>
                  </div>
                ) : (
                  <table className="admin-users-table">
                    <thead>
                      <tr>
                        <th className="checkbox-col">
                          <input
                            type="checkbox"
                            className="admin-checkbox"
                            title="Select all visible"
                            checked={(() => {
                              const visible = adminUsers.filter(u => {
                                const q = adminSearch.toLowerCase();
                                return (
                                  u.username.toLowerCase().includes(q) ||
                                  u.email.toLowerCase().includes(q) ||
                                  (u.name && u.name.toLowerCase().includes(q)) ||
                                  u.role.toLowerCase().includes(q)
                                ) && u.role !== 'superadmin' && u.id !== user?.id;
                              });
                              return visible.length > 0 && visible.every(u => selectedUserIds.has(u.id));
                            })()}
                            onChange={e => {
                              const visible = adminUsers.filter(u => {
                                const q = adminSearch.toLowerCase();
                                return (
                                  u.username.toLowerCase().includes(q) ||
                                  u.email.toLowerCase().includes(q) ||
                                  (u.name && u.name.toLowerCase().includes(q)) ||
                                  u.role.toLowerCase().includes(q)
                                ) && u.role !== 'superadmin' && u.id !== user?.id;
                              });
                              if (e.target.checked) {
                                setSelectedUserIds(prev => new Set([...prev, ...visible.map(u => u.id)]));
                              } else {
                                setSelectedUserIds(prev => {
                                  const n = new Set(prev);
                                  visible.forEach(u => n.delete(u.id));
                                  return n;
                                });
                              }
                            }}
                          />
                        </th>
                        <th>Climber</th>
                        {(user?.role === 'superadmin' || adminStats?.is_superadmin) && !adminTenantFilter && <th>Enterprise</th>}
                        <th>Email</th>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Daily Quota</th>
                        <th>Usage Today</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {adminUsers
                        .filter(u => {
                          const query = adminSearch.toLowerCase();
                          return (
                            u.username.toLowerCase().includes(query) ||
                            u.email.toLowerCase().includes(query) ||
                            (u.name && u.name.toLowerCase().includes(query)) ||
                            u.role.toLowerCase().includes(query) ||
                            (u.tenant_name && u.tenant_name.toLowerCase().includes(query)) ||
                            (u.tenant_slug && u.tenant_slug.toLowerCase().includes(query))
                          );
                        })
                        .map(u => (
                          <tr key={u.id} className={`${!u.is_active ? 'user-row-inactive' : ''} ${selectedUserIds.has(u.id) ? 'user-row-selected' : ''}`}>
                            <td className="checkbox-col">
                              {u.role !== 'superadmin' && u.id !== user?.id ? (
                                <input
                                  type="checkbox"
                                  className="admin-checkbox"
                                  checked={selectedUserIds.has(u.id)}
                                  onChange={e => {
                                    setSelectedUserIds(prev => {
                                      const n = new Set(prev);
                                      e.target.checked ? n.add(u.id) : n.delete(u.id);
                                      return n;
                                    });
                                  }}
                                />
                              ) : (
                                <span className="checkbox-placeholder" />
                              )}
                            </td>
                            <td className="user-profile-cell">
                              <div className="user-table-avatar">
                                {u.username.charAt(0).toUpperCase()}
                              </div>
                              <div className="user-name-stack">
                                <span className="u-name">{u.name || u.username}</span>
                                <span className="u-id">@{u.username}</span>
                              </div>
                            </td>

                            {user?.role === 'superadmin' && !adminTenantFilter && (
                              <td className="user-tenant-cell">
                                <span className="tenant-table-badge" title={`Tenant: ${u.tenant_name || 'Default'}`}>
                                  <Building2 size={12} />
                                  <span>{u.tenant_name || 'Default'}</span>
                                </span>
                              </td>
                            )}

                            <td className="user-email-cell">{u.email}</td>

                            <td>
                              {u.role === 'superadmin' ? (
                                <span className="role-chip-static superadmin" title="Platform SuperAdmin">
                                  <Crown size={12} />
                                  <span>SuperAdmin</span>
                                </span>
                              ) : (
                                <button
                                  className={`role-chip-btn ${u.role === 'admin' ? 'admin' : 'user'}`}
                                  onClick={() => handleUpdateRole(u.id, u.role)}
                                  title={`Click to promote/demote between Admin and Member`}
                                >
                                  {u.role === 'admin' ? <Crown size={12} /> : <User size={12} />}
                                  <span>{u.role === 'admin' ? 'Admin' : 'Member'}</span>
                                </button>
                              )}
                            </td>

                            <td>
                              {u.role === 'superadmin' ? (
                                <span className="status-chip-static active">
                                  <UserCheck size={12} />
                                  <span>Active</span>
                                </span>
                              ) : (
                                <button
                                  className={`status-chip-btn ${u.is_active ? 'active' : 'suspended'}`}
                                  onClick={() => handleUpdateStatus(u.id, u.is_active)}
                                  title={`Click to ${u.is_active ? 'suspend' : 'activate'} account`}
                                >
                                  {u.is_active ? <UserCheck size={12} /> : <UserX size={12} />}
                                  <span>{u.is_active ? 'Active' : 'Suspended'}</span>
                                </button>
                              )}
                            </td>

                            <td>
                              {editingLimitUserId === u.id ? (
                                <div className="quota-edit-form">
                                  <input
                                    type="number"
                                    value={tempLimitValue}
                                    onChange={e => setTempLimitValue(Math.max(1, parseInt(e.target.value) || 1))}
                                    min={1}
                                    max={1000000}
                                    className="quota-edit-input"
                                    autoFocus
                                  />
                                  <button
                                    className="quota-save-btn"
                                    onClick={() => handleSaveLimit(u.id, tempLimitValue)}
                                    title="Save quota limit"
                                  >
                                    <Check size={13} />
                                  </button>
                                  <button
                                    className="quota-cancel-btn"
                                    onClick={() => setEditingLimitUserId(null)}
                                    title="Cancel"
                                  >
                                    <X size={13} />
                                  </button>
                                </div>
                              ) : (
                                <div
                                  className="quota-display-badge"
                                  onClick={() => {
                                    if (u.role !== 'superadmin') {
                                      setEditingLimitUserId(u.id);
                                      setTempLimitValue(u.daily_request_limit || 50);
                                    }
                                  }}
                                  title={u.role === 'superadmin' ? 'Unlimited SuperAdmin quota' : 'Click to change daily quota limit'}
                                >
                                  <span>{u.role === 'superadmin' || u.role === 'admin' ? 'Unlimited' : `${u.daily_request_limit} / day`}</span>
                                  {u.role !== 'superadmin' && <Sliders size={12} className="quota-edit-icon" />}
                                </div>
                              )}
                            </td>

                            <td className="usage-cell">
                              <span className="usage-number">{u.requests_today}</span>
                              <span className="usage-sub">requests</span>
                            </td>

                            <td className="actions-cell">
                              <button
                                className="user-delete-action-btn"
                                onClick={() => handleDeleteUser(u.id, u.username)}
                                disabled={u.id === user?.id || u.role === 'superadmin'}
                                title={
                                  u.id === user?.id
                                    ? 'Cannot delete your own account'
                                    : u.role === 'superadmin'
                                    ? 'Cannot delete SuperAdmin'
                                    : 'Delete user and purge data'
                                }
                              >
                                <Trash2 size={14} />
                              </button>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                )}
              </div>
            </>
          )}

          {/* VIEW 2: INSTITUTIONS & ENTERPRISES TAB (SuperAdmin only) */}
          {adminActiveTab === 'tenants' && (
            <>
              <div className="admin-controls-bar">
                <div className="admin-search-wrap">
                  <Search size={15} className="search-icon" />
                  <input
                    type="text"
                    placeholder="Search institutions by name or slug..."
                    value={adminSearch}
                    onChange={e => setAdminSearch(e.target.value)}
                    className="admin-search-input"
                  />
                  {adminSearch && (
                    <button className="clear-search-btn" onClick={() => setAdminSearch('')}>
                      <X size={13} />
                    </button>
                  )}
                </div>

                <div className="admin-actions-group">
                  <button
                    className="admin-add-user-btn"
                    onClick={() => {
                      setIsCreateTenantModalOpen(true);
                      setNewTenantName('');
                      setNewTenantSlug('');
                      setNewTenantMaxUsers(50);
                    }}
                    title="Provision a new enterprise institution workspace"
                  >
                    <Building2 size={14} />
                    <span>Provision Institution</span>
                  </button>

                  <button
                    className="admin-refresh-btn"
                    onClick={() => fetchAdminData()}
                    disabled={isLoadingAdmin}
                    title="Refresh List"
                  >
                    <RotateCw size={14} className={isLoadingAdmin ? 'spin-slow' : ''} />
                    <span>Refresh</span>
                  </button>
                </div>
              </div>

              {/* Institutions Table */}
              <div className="admin-table-container">
                <table className="admin-users-table">
                  <thead>
                    <tr>
                      <th>Institution</th>
                      <th>Slug Code</th>
                      <th>Status</th>
                      <th>Capacity</th>
                      <th>Documents</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {adminTenantsList
                      .filter(t => {
                        const query = adminSearch.toLowerCase();
                        return (
                          t.name.toLowerCase().includes(query) ||
                          t.slug.toLowerCase().includes(query)
                        );
                      })
                      .map(t => (
                        <tr key={t.id} className={t.is_active === false ? 'user-row-inactive' : ''}>
                          <td className="user-profile-cell">
                            <div className="user-table-avatar text-teal">
                              <Building2 size={15} />
                            </div>
                            <div className="user-name-stack">
                              <span className="u-name">{t.name}</span>
                              {t.slug === 'default' && <span className="tenant-default-badge">Primary System Root</span>}
                            </div>
                          </td>

                          <td>
                            <span className="tenant-slug-mono">@{t.slug}</span>
                          </td>

                          <td>
                            {t.slug === 'default' ? (
                              <span className="status-chip-static active">
                                <ShieldCheck size={12} />
                                <span>System Root</span>
                              </span>
                            ) : (
                              <button
                                className={`status-chip-btn ${t.is_active !== false ? 'active' : 'suspended'}`}
                                onClick={() => handleToggleTenantStatus(t.id, t.is_active !== false)}
                                title={`Click to ${t.is_active !== false ? 'suspend' : 'activate'} institution`}
                              >
                                {t.is_active !== false ? <Check size={12} /> : <X size={12} />}
                                <span>{t.is_active !== false ? 'Active' : 'Suspended'}</span>
                              </button>
                            )}
                          </td>

                          <td>
                            <span className="tenant-capacity-badge">
                              {t.user_count || 0} / {t.max_users || 50} climbers
                            </span>
                          </td>

                          <td className="usage-cell">
                            <span className="usage-number">{t.doc_count || 0}</span>
                            <span className="usage-sub">docs</span>
                          </td>

                          <td className="actions-cell">
                            <div className="tenant-actions-row">
                              <button
                                className="btn-ghost-sm"
                                onClick={() => {
                                  setAdminTenantFilter(t.id);
                                  setAdminActiveTab('users');
                                  fetchAdminData(t.id);
                                }}
                                title="View members belonging to this institution"
                              >
                                <Users size={13} />
                                <span>Members</span>
                              </button>
                              {t.slug !== 'default' && (
                                <button
                                  className="user-delete-action-btn"
                                  onClick={() => handleDeleteTenant(t.id, t.name)}
                                  title="Permanently delete institution and purge all data"
                                >
                                  <Trash2 size={14} />
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )}

  {/* Global Custom Confirm Dialog */}
  {confirmDialog.open && (
    <div className="confirm-backdrop" onClick={() => setConfirmDialog(d => ({ ...d, open: false }))}>
      <div className="confirm-card" onClick={e => e.stopPropagation()}>
        <div className={`confirm-icon-ring ${confirmDialog.danger ? 'danger' : 'neutral'}`}>
          <Trash2 size={22} />
        </div>
        <h3 className="confirm-title">{confirmDialog.title}</h3>
        <p className="confirm-message">{confirmDialog.message}</p>
        <div className="confirm-actions">
          <button
            className="confirm-btn-cancel"
            onClick={() => setConfirmDialog(d => ({ ...d, open: false }))}
          >
            Cancel
          </button>
          <button
            className={`confirm-btn-ok ${confirmDialog.danger ? 'danger' : ''}`}
            onClick={confirmDialog.onConfirm}
          >
            {confirmDialog.danger ? (
              <>
                <Trash2 size={14} />
                <span>Delete permanently</span>
              </>
            ) : (
              <span>Confirm</span>
            )}
          </button>
        </div>
      </div>
    </div>
  )}

  {/* Create New Institution Modal Dialog (SuperAdmin) */}
  {isCreateTenantModalOpen && (
    <div className="recall-modal-backdrop add-user-backdrop" onClick={() => setIsCreateTenantModalOpen(false)}>
      <div className="recall-modal-card add-user-card" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="admin-summit-badge">
              <Building2 size={18} />
            </div>
            <div>
              <h3>Provision Institution Enterprise</h3>
              <p className="modal-subtitle-text">Create a dedicated multi-tenant workspace with isolated knowledge bases</p>
            </div>
          </div>
          <button className="modal-close-btn" onClick={() => setIsCreateTenantModalOpen(false)} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleCreateTenant} className="add-user-modal-body">
          <div className="auth-input-group">
            <label>Institution Name</label>
            <div className="auth-input-field-wrap">
              <Building2 size={16} className="input-field-icon" />
              <input
                type="text"
                placeholder="e.g. Stanford AI Institute"
                value={newTenantName}
                onChange={e => {
                  setNewTenantName(e.target.value);
                  if (!newTenantSlug) {
                    setNewTenantSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, ''));
                  }
                }}
                required
                autoFocus
              />
            </div>
          </div>

          <div className="add-user-form-row">
            <div className="auth-input-group">
              <label>Organization Slug Code</label>
              <div className="auth-input-field-wrap">
                <span className="auth-input-prefix">@</span>
                <input
                  type="text"
                  placeholder="stanford-ai"
                  value={newTenantSlug}
                  onChange={e => setNewTenantSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-_]/g, ''))}
                  required
                />
              </div>
            </div>

            <div className="auth-input-group">
              <label>Max Climber Capacity</label>
              <div className="auth-input-field-wrap">
                <Users size={16} className="input-field-icon" />
                <input
                  type="number"
                  min={1}
                  max={10000}
                  value={newTenantMaxUsers}
                  onChange={e => setNewTenantMaxUsers(Math.max(1, parseInt(e.target.value) || 50))}
                  required
                />
              </div>
            </div>
          </div>

          <div className="add-user-footer-actions">
            <button
              type="button"
              className="btn-ghost"
              onClick={() => setIsCreateTenantModalOpen(false)}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="recall-btn-primary"
              disabled={isCreatingTenant}
            >
              {isCreatingTenant ? (
                <>
                  <RotateCw size={15} className="spin-slow" />
                  <span>Provisioning...</span>
                </>
              ) : (
                <>
                  <Building2 size={15} />
                  <span>Create Institution</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )}


      {/* Add New Member Modal Dialog */}
      {isAddUserModalOpen && (
        <div className="recall-modal-backdrop add-user-backdrop" onClick={() => setIsAddUserModalOpen(false)}>
          <div className="recall-modal-card add-user-card" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-wrap">
                <div className="admin-summit-badge">
                  <UserPlus size={18} />
                </div>
                <div>
                  <h3>Provision Enterprise Climber</h3>
                  <p className="modal-subtitle-text">Create a new account in your enterprise workspace</p>
                </div>
              </div>
              <button className="modal-close-btn" onClick={() => setIsAddUserModalOpen(false)} aria-label="Close">
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="add-user-modal-body">
              {user?.role === 'superadmin' && adminTenantsList.length > 0 && (
                <div className="auth-input-group">
                  <label>Assign to Enterprise</label>
                  <div className="auth-select-wrap">
                    <Building2 size={16} className="input-field-icon" />
                    <select
                      className="auth-tenant-select"
                      value={newTenantId || user?.tenant_id}
                      onChange={e => setNewTenantId(e.target.value)}
                    >
                      {adminTenantsList.map(t => (
                        <option key={t.id} value={t.id}>
                          {t.name} (@{t.slug})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )}

              <div className="add-user-form-row">
                <div className="auth-input-group">
                  <label>Username</label>
                  <div className="auth-input-field-wrap">
                    <User size={16} className="input-field-icon" />
                    <input
                      type="text"
                      placeholder="e.g. climber_alex"
                      value={newUsername}
                      onChange={e => setNewUsername(e.target.value)}
                      required
                      minLength={3}
                      autoFocus
                    />
                  </div>
                </div>

                <div className="auth-input-group">
                  <label>Full Name</label>
                  <div className="auth-input-field-wrap">
                    <User size={16} className="input-field-icon" />
                    <input
                      type="text"
                      placeholder="e.g. Alex Mercer"
                      value={newName}
                      onChange={e => setNewName(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              <div className="auth-input-group">
                <label>Email Address</label>
                <div className="auth-input-field-wrap">
                  <Mail size={16} className="input-field-icon" />
                  <input
                    type="email"
                    placeholder="alex@enterprise.com"
                    value={newEmail}
                    onChange={e => setNewEmail(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="auth-input-group">
                <label>Initial Password (Min. 6 chars)</label>
                <div className="auth-input-field-wrap">
                  <Key size={16} className="input-field-icon" />
                  <input
                    type={showNewPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={newPassword}
                    onChange={e => setNewPassword(e.target.value)}
                    required
                    minLength={6}
                  />
                  <button
                    type="button"
                    className="auth-eye-toggle-btn"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                    tabIndex={-1}
                  >
                    {showNewPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              <div className="add-user-form-row">
                <div className="auth-input-group">
                  <label>Permission Role</label>
                  <div className="auth-select-wrap">
                    <select
                      className="auth-tenant-select"
                      value={newRole}
                      onChange={e => setNewRole(e.target.value as 'user' | 'admin')}
                    >
                      <option value="user">Member (Climber)</option>
                      <option value="admin">Enterprise Admin</option>
                    </select>
                  </div>
                </div>

                <div className="auth-input-group">
                  <label>Daily Request Limit</label>
                  <div className="auth-input-field-wrap">
                    <Sliders size={16} className="input-field-icon" />
                    <input
                      type="number"
                      min={1}
                      max={1000000}
                      value={newRole === 'admin' ? 999999 : newLimit}
                      onChange={e => setNewLimit(Math.max(1, parseInt(e.target.value) || 50))}
                      disabled={newRole === 'admin'}
                    />
                  </div>
                </div>
              </div>

              <div className="add-user-footer-actions">
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => setIsAddUserModalOpen(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="recall-btn-primary"
                  disabled={isCreatingUser}
                >
                  {isCreatingUser ? (
                    <>
                      <RotateCw size={15} className="spin-slow" />
                      <span>Creating Member...</span>
                    </>
                  ) : (
                    <>
                      <UserPlus size={15} />
                      <span>Provision Member Account</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}


      {/* Climber Feedback & Accuracy Inquiry Modal */}
      <FeedbackModal
        isOpen={isFeedbackOpen}
        onClose={() => {
          setIsFeedbackOpen(false);
          setFeedbackTargetContext(null);
        }}
        conversationId={activeSessionId}
        targetContext={feedbackTargetContext}
      />


      {/* Authentication Modal (ID + Password Login & Registration) */}
      <AuthModal

        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onSuccess={(newUser, token) => {
          localStorage.setItem('ridge_token', token);
          localStorage.setItem('ridge_user', JSON.stringify(newUser));
          setUser(newUser);
          setIsAuthModalOpen(false);
          showToast(`Welcome, ${newUser.name}`, 'success');
        }}
        onGuestContinue={
          !authConfig?.enabled
            ? () => {
                setIsAuthModalOpen(false);
                setUser({
                  id: 'guest_climber',
                  username: 'guest',
                  name: 'Climber Guest',
                  email: 'guest@ridge.local',
                  is_guest: true,
                  provider: 'guest'
                });
              }
            : undefined
        }
      />

      {/* Toast Notification */}
      {toast && (
        <div className={`recall-toast ${toast.type}`}>
          {toast.type === 'success' && <CheckCircle size={16} />}
          {toast.type === 'error' && <X size={16} />}
          {toast.type === 'info' && <Sparkles size={16} />}
          <span>{toast.msg}</span>
        </div>
      )}
    </div>
  );
}
