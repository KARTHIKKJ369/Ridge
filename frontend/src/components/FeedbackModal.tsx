import React, { useState, useEffect } from 'react';
import {
  X,
  MessageSquare,
  Send,
  AlertCircle,
  CheckCircle2,
  Clock,
  Sparkles,
  HelpCircle,
  Bug,
  Target,
  Lightbulb,
  RotateCw,
  CornerDownRight,
  FileQuestion,
} from 'lucide-react';

interface FeedbackItem {
  id: string;
  category: string;
  message: string;
  conversation_id?: string;
  status: 'open' | 'in_review' | 'resolved';
  admin_notes?: string;
  resolved_by?: string;
  created_at: string;
  updated_at: string;
}

export interface FeedbackTargetContext {
  query?: string;
  answerSnippet?: string;
  messageId?: string;
}

interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  conversationId?: string;
  targetContext?: FeedbackTargetContext | null;
}

export const FeedbackModal: React.FC<FeedbackModalProps> = ({
  isOpen,
  onClose,
  conversationId = '',
  targetContext = null,
}) => {
  const [activeTab, setActiveTab] = useState<'submit' | 'history'>('submit');
  const [category, setCategory] = useState<'accuracy' | 'bug' | 'feature' | 'general'>(
    targetContext ? 'accuracy' : 'accuracy'
  );
  const [message, setMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // History state
  const [historyItems, setHistoryItems] = useState<FeedbackItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setErrorMsg(null);
      setSuccessMsg(null);
      if (targetContext) {
        setCategory('accuracy');
        setMessage('');
        setActiveTab('submit');
      }
    }
  }, [isOpen, targetContext]);

  const fetchWithAuth = async (url: string, options: RequestInit = {}) => {
    const token = localStorage.getItem('ridge_token');
    const headers = {
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    };
    return fetch(url, { ...options, headers });
  };

  const fetchHistory = async () => {
    setIsLoadingHistory(true);
    try {
      const res = await fetchWithAuth('/api/feedback/mine');
      if (res.ok) {
        const data = await res.json();
        setHistoryItems(data.feedback || []);
      }
    } catch (e) {
      console.error('Failed to load feedback history:', e);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  useEffect(() => {
    if (isOpen && activeTab === 'history') {
      fetchHistory();
    }
  }, [isOpen, activeTab]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) {
      setErrorMsg('Please describe what was inaccurate or what you would like improved.');
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    let fullMessage = message.trim();
    if (targetContext?.query || targetContext?.answerSnippet) {
      fullMessage = `[Context]\nQuery: ${targetContext.query || 'N/A'}\nResponse Snippet: ${targetContext.answerSnippet?.slice(0, 300) || 'N/A'}\n\n[Feedback Details]\n${message.trim()}`;
    }

    try {
      const res = await fetchWithAuth('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category,
          message: fullMessage,
          conversation_id: conversationId,
        }),
      });

      if (res.ok) {
        setSuccessMsg('Your feedback has been delivered to the administration team.');
        setMessage('');
        setTimeout(() => {
          setSuccessMsg(null);
          setActiveTab('history');
          fetchHistory();
        }, 1200);
      } else {
        const err = await res.json();
        setErrorMsg(err.detail || 'Failed to submit feedback.');
      }
    } catch (e: any) {
      setErrorMsg(e.message || 'Network error submitting feedback.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const categoryOptions = [
    { id: 'accuracy', label: 'Retrieval Accuracy', icon: <Target size={14} />, desc: 'Report incorrect facts or poor citations' },
    { id: 'bug', label: 'Bug Report', icon: <Bug size={14} />, desc: 'System glitch, streaming or UI issue' },
    { id: 'feature', label: 'Feature Request', icon: <Lightbulb size={14} />, desc: 'Suggest improvements to Ridge' },
    { id: 'general', label: 'General Inquiry', icon: <HelpCircle size={14} />, desc: 'Questions or assistance' },
  ];

  return (
    <div className="recall-modal-backdrop" onClick={onClose}>
      <div
        className="recall-modal-card"
        style={{ maxWidth: 560 }}
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="admin-summit-badge">
              <MessageSquare size={18} />
            </div>
            <div>
              <h3>Feedback & Inquiries</h3>
              <p className="modal-subtitle-text">
                {targetContext
                  ? 'Submit specific feedback on this generated answer'
                  : 'Direct line to enterprise administrators and AI researchers'}
              </p>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        {/* Modal Navigation Tabs */}
        <div style={{ display: 'flex', gap: 6, padding: '10px 20px 0', borderBottom: '1px solid var(--recall-border)' }}>
          <button
            type="button"
            className={`admin-subnav-btn ${activeTab === 'submit' ? 'active' : ''}`}
            onClick={() => setActiveTab('submit')}
          >
            <span>Submit Feedback</span>
          </button>
          <button
            type="button"
            className={`admin-subnav-btn ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('history');
              fetchHistory();
            }}
          >
            <span>My Inquiries ({historyItems.length})</span>
          </button>
        </div>

        <div className="add-user-modal-body">
          {errorMsg && (
            <div className="auth-error-banner">
              <AlertCircle size={15} />
              <span>{errorMsg}</span>
            </div>
          )}

          {successMsg && (
            <div className="auth-error-banner" style={{ background: 'var(--recall-success-subtle)', borderColor: 'rgba(22, 163, 74, 0.3)', color: 'var(--recall-success)' }}>
              <CheckCircle2 size={15} />
              <span>{successMsg}</span>
            </div>
          )}

          {activeTab === 'submit' ? (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Context Banner if triggered from a specific message */}
              {targetContext && (
                <div
                  style={{
                    background: 'var(--recall-surface-elevated)',
                    border: '1px solid var(--recall-border)',
                    borderRadius: 'var(--radius-sm, 8px)',
                    padding: '12px 14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.74rem', fontWeight: 700, color: 'var(--recall-accent)', textTransform: 'uppercase' }}>
                    <FileQuestion size={14} />
                    <span>Feedback Target Context</span>
                  </div>

                  {targetContext.query && (
                    <div style={{ fontSize: '0.82rem', color: 'var(--recall-text-primary)' }}>
                      <strong style={{ color: 'var(--recall-text-muted)', fontSize: '0.76rem' }}>Prompt Query: </strong>
                      <span>"{targetContext.query}"</span>
                    </div>
                  )}

                  {targetContext.answerSnippet && (
                    <div style={{ display: 'flex', gap: 6, fontSize: '0.78rem', color: 'var(--recall-text-muted)', background: 'var(--recall-surface)', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--recall-border)' }}>
                      <CornerDownRight size={13} style={{ flexShrink: 0, marginTop: 2, color: 'var(--recall-accent)' }} />
                      <span style={{ fontStyle: 'italic', lineHeight: 1.4 }}>
                        "{targetContext.answerSnippet.slice(0, 180)}..."
                      </span>
                    </div>
                  )}
                </div>
              )}

              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--recall-text-muted)', display: 'block', marginBottom: 8 }}>
                  Inquiry Category
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  {categoryOptions.map(opt => (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => setCategory(opt.id as any)}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'flex-start',
                        gap: 4,
                        padding: '10px 12px',
                        borderRadius: 'var(--radius-sm, 8px)',
                        background: category === opt.id ? 'var(--recall-accent-subtle)' : 'var(--recall-surface-elevated)',
                        border: `1.5px solid ${category === opt.id ? 'var(--recall-accent)' : 'var(--recall-border)'}`,
                        color: category === opt.id ? 'var(--recall-accent)' : 'var(--recall-text-primary)',
                        cursor: 'pointer',
                        textAlign: 'left',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, fontSize: '0.82rem' }}>
                        {opt.icon}
                        <span>{opt.label}</span>
                      </div>
                      <span style={{ fontSize: '0.7rem', color: 'var(--recall-text-muted)', lineHeight: 1.3 }}>
                        {opt.desc}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--recall-text-muted)', display: 'block', marginBottom: 6 }}>
                  {targetContext ? 'What was incorrect or unhelpful?' : 'Your Message & Details'}
                </label>
                <textarea
                  value={message}
                  onChange={e => setMessage(e.target.value)}
                  placeholder={
                    targetContext
                      ? "Explain what information was inaccurate, missing, or improperly cited..."
                      : "Describe the issue, missing source document, or suggestion in detail..."
                  }
                  rows={4}
                  required
                  autoFocus={Boolean(targetContext)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: 'var(--radius-sm, 8px)',
                    background: 'var(--recall-surface-elevated)',
                    border: '1px solid var(--recall-border)',
                    color: 'var(--recall-text-primary)',
                    fontSize: '0.86rem',
                    fontFamily: 'inherit',
                    resize: 'vertical',
                    minHeight: 90,
                  }}
                />
              </div>

              <div className="add-user-footer-actions">
                <button type="button" className="btn-ghost" onClick={onClose}>
                  Cancel
                </button>
                <button type="submit" className="recall-btn-primary" disabled={isSubmitting}>
                  {isSubmitting ? (
                    <>
                      <RotateCw size={15} className="spin-slow" />
                      <span>Submitting...</span>
                    </>
                  ) : (
                    <>
                      <Send size={14} />
                      <span>Send to Admin</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minHeight: 200 }}>
              {isLoadingHistory ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 40, gap: 10, color: 'var(--recall-text-muted)' }}>
                  <RotateCw size={18} className="spin-slow" />
                  <span>Loading inquiries...</span>
                </div>
              ) : historyItems.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--recall-text-muted)' }}>
                  <Sparkles size={28} style={{ opacity: 0.4, margin: '0 auto 10px' }} />
                  <p style={{ margin: 0, fontWeight: 600 }}>No feedback inquiries submitted yet</p>
                  <p style={{ margin: '4px 0 0', fontSize: '0.78rem' }}>When you submit questions or accuracy reports, you can track resolutions here.</p>
                </div>
              ) : (
                historyItems.map(item => (
                  <div
                    key={item.id}
                    style={{
                      background: 'var(--recall-surface-elevated)',
                      border: '1px solid var(--recall-border)',
                      borderRadius: 'var(--radius-sm, 8px)',
                      padding: 14,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: '0.74rem', textTransform: 'uppercase', fontWeight: 700, color: 'var(--recall-accent)' }}>
                        {item.category}
                      </span>
                      <span
                        className={`status-chip-static ${item.status === 'resolved' ? 'active' : item.status === 'in_review' ? 'amber' : 'neutral'}`}
                        style={{
                          padding: '2px 8px',
                          borderRadius: 'var(--radius-full, 9999px)',
                          fontSize: '0.7rem',
                          fontWeight: 700,
                          textTransform: 'uppercase',
                        }}
                      >
                        {item.status === 'resolved' ? '✓ Resolved' : item.status === 'in_review' ? 'In Review' : 'Open'}
                      </span>
                    </div>

                    <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--recall-text-primary)', lineHeight: 1.4, whiteSpace: 'pre-wrap' }}>
                      {item.message}
                    </p>

                    {item.admin_notes && (
                      <div
                        style={{
                          background: 'var(--recall-accent-subtle)',
                          borderLeft: '3px solid var(--recall-accent)',
                          padding: '8px 10px',
                          borderRadius: 4,
                          fontSize: '0.78rem',
                          color: 'var(--recall-text-primary)',
                        }}
                      >
                        <strong style={{ display: 'block', color: 'var(--recall-accent)', fontSize: '0.72rem', textTransform: 'uppercase' }}>
                          Admin Response {item.resolved_by ? `(@${item.resolved_by})` : ''}:
                        </strong>
                        <span>{item.admin_notes}</span>
                      </div>
                    )}

                    <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.68rem', color: 'var(--recall-text-muted)' }}>
                      <Clock size={11} />
                      <span>{new Date(item.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default FeedbackModal;
