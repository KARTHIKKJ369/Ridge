import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Activity, CheckCircle, RotateCw, X, Plus, Upload, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import './App.css';

type TraceEvent = {
  node: string;
  message: string;
  timestamp: string;
  documents?: string[];
  doc_grades?: any[];
  answer?: string;
  latency_ms?: number;
};

type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  traces?: TraceEvent[];
  isStreaming?: boolean;
};

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isIngestOpen, setIsIngestOpen] = useState(false);
  const [isTraceOpen, setIsTraceOpen] = useState(false);
  const [toast, setToast] = useState<{msg: string; type: 'success'|'error'} | null>(null);

  const showToast = (msg: string, type: 'success'|'error' = 'success') => {
    setToast({msg, type});
    setTimeout(() => setToast(null), 3500);
  };
  const [ingestInput, setIngestInput] = useState('');
  const [isIngesting, setIsIngesting] = useState(false);
  const [isIngestSuccess, setIsIngestSuccess] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [stats, setStats] = useState({ doc_count: 0, chunk_count: 0 });
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const fetchSuggestionsAndStats = async () => {
    try {
      const [sugRes, statRes] = await Promise.all([
        fetch('/api/suggestions'),
        fetch('/api/stats')
      ]);
      const sugData = await sugRes.json();
      const statData = await statRes.json();
      if (!sugData.empty) setSuggestions(sugData.suggestions || []);
      setStats(statData);
    } catch (e) {
      console.error('Failed to fetch stats/suggestions:', e);
    }
  };

  useEffect(() => {
    fetchSuggestionsAndStats();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim()
    };
    
    const assistantId = (Date.now() + 1).toString();
    const assistantMessage: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      traces: [],
      isStreaming: true
    };
    
    setMessages(prev => [...prev, userMessage, assistantMessage]);
    setInput('');
    setIsLoading(true);
    
    try {
      const response = await fetch('/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: userMessage.content })
      });
      
      if (!response.ok) throw new Error('API Error');
      
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No reader');
      
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
              const data = JSON.parse(dataStr) as TraceEvent;
              
              setMessages(prev => prev.map(msg => {
                if (msg.id === assistantId) {
                  const newMsg = { ...msg };
                  newMsg.traces = [...(newMsg.traces || []), data];
                  if (data.answer) {
                    newMsg.content = data.answer;
                  }
                  return newMsg;
                }
                return msg;
              }));
            } catch (e) {
              console.error('Failed to parse:', dataStr);
            }
          }
        }
      }
    } catch (error) {
      console.error(error);
      setMessages(prev => prev.map(msg => 
        msg.id === assistantId ? { ...msg, content: 'Sorry, there was an error processing your request.' } : msg
      ));
    } finally {
      setMessages(prev => prev.map(msg => 
        msg.id === assistantId ? { ...msg, isStreaming: false } : msg
      ));
      setIsLoading(false);
    }
  };

  const handleIngest = async () => {
    if (!ingestInput.trim() && !selectedFile) return;
    setIsIngesting(true);
    try {
      let response;
      
      if (selectedFile) {
        const formData = new FormData();
        formData.append('file', selectedFile);
        
        response = await fetch('/upload', {
          method: 'POST',
          body: formData
        });
      } else {
        response = await fetch('/ingest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text_or_url: ingestInput })
        });
      }
      
      if (!response.ok) throw new Error('Failed to ingest');
      const data = await response.json();
      showToast(`Embedded ${data.chunks_added} chunks successfully`);
      setIsIngestSuccess(true);
      setTimeout(() => {
        setIsIngestSuccess(false);
        setIsIngestOpen(false);
        setIngestInput('');
        setSelectedFile(null);
      }, 1500);
    } catch (e: any) {
      console.error(e);
      showToast('Ingestion failed: ' + e.message, 'error');
    } finally {
      setIsIngesting(false);
      fetchSuggestionsAndStats();
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setSelectedFile(e.dataTransfer.files[0]);
      setIngestInput(''); // Clear text input if file is dropped
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
      setIngestInput(''); // Clear text input if file is selected
    }
  };



  const getNodeTitle = (nodeName: string) => {
    switch(nodeName) {
      case 'retrieve_node': return 'Retrieval';
      case 'grade_node': return 'Grading';
      case 'web_search_node': return 'Web Search';
      case 'rewrite_node': return 'Rewriting Query';
      case 'generate_node': return 'Generation';
      default: return nodeName;
    }
  };

  // Active Traces for Stepper
  const lastAssistantMessage = messages.filter(m => m.role === 'assistant').pop();
  const activeTraces = lastAssistantMessage?.traces || [];
  const isCurrentlyStreaming = lastAssistantMessage?.isStreaming;

  // Flatten all doc_grades from all trace events
  const allDocGrades: any[] = activeTraces.reduce<any[]>((acc, trace) => {
    if (trace.doc_grades) acc.push(...trace.doc_grades);
    return acc;
  }, []);

  return (
    <div className="app-container">
      {/* Main Chat Section */}
      <main className="chat-section">
        <header className="chat-header">
          <div className="logo-text" style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
            <RotateCw size={24} color="var(--accent)" strokeWidth={2.5} />
            <span>recall<span className="logo-dot">.</span></span>
          </div>
          <div className="header-actions">
            {stats.chunk_count > 0 && (
              <span style={{fontSize: '0.8rem', color: 'var(--text-muted)', marginRight: '16px', fontWeight: 500}}>
                {stats.doc_count} documents · {stats.chunk_count} chunks
              </span>
            )}
            <span style={{fontSize: '0.8rem', color: 'var(--text-muted)', marginRight: '16px'}}>built by karthik.</span>
            <button onClick={() => setIsTraceOpen(true)} className={isCurrentlyStreaming ? 'pulse-button' : ''}>
              <Activity size={16} />
              Pipeline
            </button>
            <button onClick={() => setIsIngestOpen(true)} className="btn-primary">
              <Plus size={16} />
              <span>Ingest</span>
            </button>
          </div>
        </header>
        
        <div className="messages-container">
          {messages.length === 0 && (
            <div style={{textAlign: 'center', color: 'var(--text-muted)', margin: '48px 0 auto', position: 'relative', padding: '32px 0'}}>
              <div className="mesh-bg"></div>
              <div className="hero-glow"></div>
              <div style={{position: 'relative', zIndex: 1}}>
                <div className="logo-text" style={{fontSize: '3.5rem', marginBottom: '16px', letterSpacing: '-0.05em', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px'}}>
                  <RotateCw size={48} color="var(--accent)" strokeWidth={2.5} />
                  <span>recall<span style={{color: 'var(--accent)'}}>.</span></span>
                </div>
                <h2 style={{fontSize: '1.5rem', color: 'var(--text-main)', marginBottom: '8px'}}>Your knowledge, instantly.</h2>
                <p style={{maxWidth: '500px', margin: '0 auto', lineHeight: '1.6', fontSize: '1.1rem', color: 'var(--text-muted)'}}>
                  Ask anything across your ingested documents.
                </p>
                <div className="hero-chips">
                  {suggestions.length > 0 ? (
                    suggestions.map((sug, i) => (
                      <button key={i} onClick={() => setInput(sug)}>{sug}</button>
                    ))
                  ) : (
                    <button className="dimmed-chip" onClick={() => setIsIngestOpen(true)}>
                      Ingest a document to get started →
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
          
          {messages.map((msg) => (
            <div key={msg.id} className={`message ${msg.role}`}>
              <div className="message-avatar">
                {msg.role === 'user' ? <User size={22} color="var(--bg-dark)" /> : <Bot size={22} color="var(--text-main)" />}
              </div>
              <div className="message-content">
                {msg.content ? (
                  <div className="markdown-content">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                ) : (
                  msg.isStreaming && (
                    <div className="loading-dots" style={{display: 'flex', gap: '4px', alignItems: 'center', height: '24px'}}>
                      <span style={{width: '6px', height: '6px', background: 'var(--text-muted)', borderRadius: '50%'}}></span>
                      <span style={{width: '6px', height: '6px', background: 'var(--text-muted)', borderRadius: '50%'}}></span>
                      <span style={{width: '6px', height: '6px', background: 'var(--text-muted)', borderRadius: '50%'}}></span>
                    </div>
                  )
                )}
                
                {msg.role === 'assistant' && allDocGrades.length > 0 && (
                  <div className="source-cards">
                    {allDocGrades.map((g: any, idx: number) => {
                      const fname = g.source ? g.source.split('/').pop() || g.source : `Source ${idx + 1}`;
                      return (
                        <div key={idx} className={`source-card ${g.score === 'no' ? 'irrelevant' : ''}`}>
                          <strong style={{color: 'var(--text-main)', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px'}}>
                            <span style={{fontFamily: 'var(--font-mono)', fontSize: '0.78rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '160px'}} title={fname}>
                              📄 {fname}
                            </span>
                            <span className={`grade-badge ${g.score}`}>
                              {g.score === 'yes' ? '✓ USED' : '✕ FILTERED'}
                            </span>
                          </strong>
                          {g.rationale && (
                            <div className="source-rationale">{g.rationale}</div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        
        <div className={`chat-input-wrapper ${messages.length === 0 ? 'centered' : 'active'}`}>
          <div className={`input-container ${isCurrentlyStreaming ? 'loading' : ''}`}>
            <input
              type="text"
              className="input-field"
              placeholder="Ask anything..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              disabled={isLoading}
              autoFocus
            />
            <button 
              className="send-button"
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </main>
      
      {/* Overlay when trace is open */}
      <div className={`trace-overlay ${isTraceOpen ? 'active' : ''}`} onClick={() => setIsTraceOpen(false)} />

      {/* Right Trace Pipeline Drawer */}
      <aside className={`trace-panel ${isTraceOpen ? 'open' : ''}`}>
        <div className="trace-header">
          <div style={{display: 'flex', alignItems: 'center', gap: '12px'}}>
            <Activity size={22} color="var(--accent)" className={isCurrentlyStreaming ? "pulse-icon" : ""} />
            <h2>Data Flow</h2>
          </div>
          <button className="close-button" onClick={() => setIsTraceOpen(false)}>
            <X size={20} />
          </button>
        </div>
        <div className="trace-content">
          {activeTraces.length === 0 ? (
            <div style={{color: 'var(--text-muted)', textAlign: 'center', margin: 'auto 0', opacity: 0.5}}>
              <Activity size={48} style={{margin: '0 auto 16px', display: 'block'}} />
              Waiting for execution...
            </div>
          ) : (
            <div className="trace-timeline">
              {activeTraces.map((trace, i) => {
                const isLast = i === activeTraces.length - 1;
                const isActive = isCurrentlyStreaming && isLast;

                return (
                  <div
                    key={i}
                    className={`trace-node ${isActive ? 'active' : 'completed'}`}
                    style={{ animationDelay: `${i * 150}ms` }}
                  >
                    <div className="tl-connector">
                      <div className="tl-dot">
                        {isActive
                          ? <Activity size={11} />
                          : <CheckCircle size={11} />}
                      </div>
                      {!isLast && <div className="tl-line" />}
                    </div>
                    <div className="node-content">
                      <div className="node-title" style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                        <span>{getNodeTitle(trace.node)}</span>
                        {trace.latency_ms != null && (
                          <span className="latency-badge">{trace.latency_ms}ms</span>
                        )}
                      </div>
                      <div className="node-desc">{trace.message}</div>
                    </div>
                  </div>
                );
              })}
              {isCurrentlyStreaming && (
                <div className="trace-node active">
                  <div className="tl-connector">
                    <div className="tl-dot spinning">
                      <RotateCw size={11} />
                    </div>
                  </div>
                  <div className="node-content">
                    <div className="node-title">Processing...</div>
                    <div className="node-desc" style={{opacity: 0.5}}>Waiting for next step</div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </aside>

      {/* Toast notification */}
      {toast && (
        <div className={`toast toast-${toast.type}`}>
          {toast.type === 'success' ? '✓' : '✕'} {toast.msg}
        </div>
      )}

      {/* Ingest Modal */}
      {isIngestOpen && (
        <div className="modal-overlay" onClick={() => setIsIngestOpen(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Upload size={22} color="var(--accent)" />
                Ingest Document
              </h2>
              <button className="close-button" onClick={() => setIsIngestOpen(false)}>
                <X size={24} />
              </button>
            </div>
            <div className="modal-body">
              <div 
                className={`file-dropzone ${isDragging ? 'drag-active' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleFileDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  onChange={handleFileSelect}
                  accept=".pdf,.md,.txt"
                  style={{ display: 'none' }}
                />
                {selectedFile ? (
                  <>
                    <FileText size={36} color="var(--accent)" style={{ margin: '0 auto 12px', display: 'block' }} />
                    <div className="file-drop-text">
                      Selected: <strong>{selectedFile.name}</strong>
                    </div>
                  </>
                ) : (
                  <>
                    <Upload size={36} color="var(--text-muted)" style={{ margin: '0 auto 12px', display: 'block' }} />
                    <div className="file-drop-text">
                      Drag & drop a file here, or <strong>browse</strong> (PDF, MD, TXT)
                    </div>
                  </>
                )}
              </div>
              
              <div className="divider">OR</div>

              <p>Provide a URL to scrape or paste raw text. The system will chunk and embed it into your Chroma vector store.</p>
              <textarea 
                className="modal-textarea"
                placeholder="https://example.com/article OR Paste raw text here..."
                value={ingestInput}
                onChange={e => { setIngestInput(e.target.value); setSelectedFile(null); }}
                disabled={!!selectedFile}
              />
            </div>
            <div className="modal-footer">
              <button className="btn" onClick={() => setIsIngestOpen(false)}>Cancel</button>
              <button 
                className={`btn btn-primary ${isIngestSuccess ? 'btn-success' : ''}`} 
                onClick={handleIngest} 
                disabled={(!ingestInput.trim() && !selectedFile) || isIngesting || isIngestSuccess}
              >
                {isIngesting ? 'Ingesting...' : isIngestSuccess ? '✓ Embedded successfully' : 'Add to Knowledge Base'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
