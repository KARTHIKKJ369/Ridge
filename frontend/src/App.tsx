import React, { useState, useRef, useEffect } from 'react';
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
  Command, 
  Zap, 
  ShieldCheck, 
  Edit3,
  Paperclip,
  ArrowUp,
  LogOut,
  LogIn,
  Square,
  Video,
  Image,
  Code
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { AuthModal } from './components/AuthModal';
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

type TraceEvent = {
  node: string;
  message: string;
  timestamp?: string;
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
  timestamp?: string;
  liked?: boolean | null;
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
};

type AuthConfig = {
  enabled: boolean;
  providers: {
    github: boolean;
    google: boolean;
  };
};

const DEFAULT_SUGGESTIONS = [
  "Summarize the key findings and core concepts across the indexed documents.",
  "What are the main methodologies and step-by-step implementations described?",
  "Audit the knowledge base for contradictory claims or edge cases."
];

export default function App() {
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

  // Theme Management: Defaults to 'stone' (Stone & Summit)
  const [theme, setTheme] = useState<ThemeMode>(() => {
    return (localStorage.getItem('recall_theme') as ThemeMode) || 'stone';
  });

  // Sidebar & Layout: Defaults to collapsed on refresh so the Hero is front and center
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isArtifactsOpen, setIsArtifactsOpen] = useState(false);
  const [activeArtifactTab, setActiveArtifactTab] = useState<'trace' | 'knowledge' | 'grader'>('trace');

  // Multi-Session Chat State
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    const saved = localStorage.getItem('recall_crag_sessions');
    if (saved) {
      try { return JSON.parse(saved); } catch (e) {}
    }
    return [{
      id: 'default-session',
      title: 'Initial Ascent',
      createdAt: Date.now(),
      messages: []
    }];
  });
  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    const savedActive = localStorage.getItem('recall_crag_active_session');
    return savedActive || 'default-session';
  });

  const activeSession = sessions.find(s => s.id === activeSessionId) || sessions[0];
  const messages = activeSession?.messages || [];

  // Input & Streaming States
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [expandedThinking, setExpandedThinking] = useState<{ [msgId: string]: boolean }>({});
  const [showSlashMenu, setShowSlashMenu] = useState(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState(true);

  // Modals & Tools
  const [isIngestOpen, setIsIngestOpen] = useState(false);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [selectedSourceModal, setSelectedSourceModal] = useState<any | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' | 'info' } | null>(null);

  // Ingestion States
  const [ingestMode, setIngestMode] = useState<'file' | 'url'>('file');
  const [ingestInput, setIngestInput] = useState('');
  const [isIngesting, setIsIngesting] = useState(false);
  const [isIngestSuccess, setIsIngestSuccess] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
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
  interface KBSource {
    source: string;
    name: string;
    type: string;
    h1: string;
    chunk_count: number;
    sample: string;
    ids: string[];
  }
  const [kbSources, setKbSources] = useState<KBSource[]>([]);
  const [isLoadingKBSources, setIsLoadingKBSources] = useState(false);
  const [deletingSource, setDeletingSource] = useState<string | null>(null);
  const [isClearingKB, setIsClearingKB] = useState(false);
  const [searchDocFilter, setSearchDocFilter] = useState('');

  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatAttachRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
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

  // Save sessions to localStorage
  useEffect(() => {
    localStorage.setItem('recall_crag_sessions', JSON.stringify(sessions));
  }, [sessions]);

  useEffect(() => {
    localStorage.setItem('recall_crag_active_session', activeSessionId);
  }, [activeSessionId]);

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
        setSelectedSourceModal(null);
        setShowSlashMenu(false);
        if (window.innerWidth < 768) {
          setIsSidebarOpen(false);
          setIsArtifactsOpen(false);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [sessions, isLoading]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

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
    showToast('Signed out of Ridge', 'info');
    if (authConfig?.enabled) {
      setIsAuthModalOpen(true);
    }
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

  const handleDeleteKBSource = async (source: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete '${name}' and all its indexed chunks from the knowledge base?`)) {
      return;
    }
    setDeletingSource(source);
    try {
      const res = await fetchWithAuth('/api/kb/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source })
      });
      if (res.ok) {
        showToast(`Deleted '${name}' from knowledge base`, 'success');
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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Session Management Helpers
  const handleNewChat = () => {
    const newSession: ChatSession = {
      id: Date.now().toString(),
      title: 'New Research Ascent',
      createdAt: Date.now(),
      messages: []
    };
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    setInput('');
    if (window.innerWidth < 768) setIsSidebarOpen(false);
    showToast('Started new research ascent', 'info');
  };

  const handleDeleteSession = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (sessions.length === 1) {
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

  const updateCurrentMessages = (updater: (prevMsgs: Message[]) => Message[]) => {
    setSessions(prev => prev.map(s => {
      if (s.id === activeSessionId) {
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
    const queryToSend = customQuery || input;
    if (!queryToSend.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: queryToSend.trim(),
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

    updateCurrentMessages(prev => [...prev, userMessage, assistantMessage]);
    setInput('');
    setShowSlashMenu(false);
    setIsLoading(true);
    setExpandedThinking(prev => ({ ...prev, [assistantId]: true }));

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const response = await fetchWithAuth('/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: userMessage.content }),
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
              const data = JSON.parse(dataStr) as TraceEvent;

              updateCurrentMessages(prev => prev.map(msg => {
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
      ));
      showToast('Error during pipeline ascent', 'error');
    } finally {
      abortControllerRef.current = null;
      updateCurrentMessages(prev => prev.map(msg =>
        msg.id === assistantId ? { ...msg, isStreaming: false } : msg
      ));
      setIsLoading(false);
    }
  };

  // Ingestion Handler
  const handleIngest = async () => {
    if (!ingestInput.trim() && !selectedFile) return;
    setIsIngesting(true);
    try {
      let response;

      if (selectedFile) {
        const formData = new FormData();
        formData.append('file', selectedFile);

        response = await fetchWithAuth('/upload', {
          method: 'POST',
          body: formData
        });
      } else {
        response = await fetchWithAuth('/ingest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text_or_url: ingestInput.trim() })
        });
      }

      if (!response.ok) throw new Error('Server returned an error');
      const data = await response.json();
      showToast(`Anchored ${data.chunks_added} chunks into knowledge crag`);
      setIsIngestSuccess(true);
      setTimeout(() => {
        setIsIngestSuccess(false);
        setIsIngestOpen(false);
        setIngestInput('');
        setSelectedFile(null);
      }, 1200);
    } catch (e: any) {
      console.error(e);
      showToast('Ingestion failed: ' + (e.message || 'Unknown error'), 'error');
    } finally {
      setIsIngesting(false);
      fetchSuggestionsAndStats(true);
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setSelectedFile(e.dataTransfer.files[0]);
      setIngestInput('');
    }
  };

  const handleChatFileAttach = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
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

  const clearCurrentChat = () => {
    updateCurrentMessages(() => []);
    showToast('Conversation cleared');
  };

  const exportConversation = (format: 'md' | 'json') => {
    let content = '';
    let mimeType = 'text/plain';
    let ext = format;

    if (format === 'json') {
      content = JSON.stringify(messages, null, 2);
      mimeType = 'application/json';
    } else {
      content = `# Ridge: ${activeSession.title}\nExported on ${new Date().toLocaleString()}\n\n---\n\n` +
        messages.map(m => `### ${m.role === 'user' ? 'User' : 'Ridge'}\n${m.content}\n\n`).join('\n---\n\n');
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ridge-${activeSession.id}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
    setIsExportOpen(false);
    showToast(`Exported as .${ext}`);
  };

  // Node details mapped with rock climbing difficulty color hierarchy
  const getNodeDetails = (nodeName: string): { title: string; desc: string; icon: React.ReactNode; color: string } => {
    switch (nodeName) {
      case 'retrieve_node':
        return { 
          title: 'MMR Vector Retrieval', 
          desc: 'Chroma vector search with MMR diversity', 
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
      default:
        return { 
          title: nodeName, 
          desc: 'Pipeline state executed', 
          icon: <Zap size={13} />, 
          color: 'muted' 
        };
    }
  };

  // Last assistant traces for Stepper & Artifacts
  const lastAssistantMessage = messages.filter(m => m.role === 'assistant').pop();
  const activeTraces = lastAssistantMessage?.traces || [];
  const isCurrentlyStreaming = lastAssistantMessage?.isStreaming;

  const allDocGrades: any[] = activeTraces.reduce<any[]>((acc, trace) => {
    if (trace.doc_grades) acc.push(...trace.doc_grades);
    return acc;
  }, []);

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
          <div className="recall-brand">
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
                onClick={() => {
                  setActiveSessionId(s.id);
                  if (window.innerWidth < 768) setIsSidebarOpen(false);
                }}
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
            <span>ChromaDB · FlashRank · LangGraph · Groq</span>
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

            <div className="navbar-brand-anchor">
              <span className="navbar-title">Ridge</span>
              <div className="engine-status-tag">
                <span className="engine-live-dot" />
                <span className="engine-name">Groq LLM</span>
              </div>
            </div>
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
              <button 
                className="nav-action-pill ingest-pill"
                onClick={() => setIsIngestOpen(true)}
                title="Ingest documents and articles into Knowledge Crag"
                aria-label="Ingest documents"
              >
                <Upload size={15} />
                <span>Ingest</span>
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
                          <span className={`provider-badge ${user.provider || 'local'}`}>
                            {user.provider === 'local' ? 'Local Account' : user.provider}
                          </span>
                        </div>
                      </div>
                      <div className="dropdown-divider" />
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
                        onClick={() => {
                          setInput(sug);
                          handleSend(sug);
                        }}
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
                        onClick={() => {
                          const q = "Summarize the primary topo knowledge anchored in the crag.";
                          setInput(q);
                          handleSend(q);
                        }}
                      >
                        <div className="prompt-content-wrap">
                          <span className="prompt-title">Summarize Topo Sources</span>
                          <span className="prompt-desc">Synthesize key concepts across all indexed vectors</span>
                        </div>
                        <ChevronRight size={16} className="prompt-arrow" />
                      </button>

                      <button 
                        className="recall-prompt-card"
                        onClick={() => {
                          const q = "Explain the architectural components and state machine graph.";
                          setInput(q);
                          handleSend(q);
                        }}
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
              {messages.map((msg) => {
                const isAssistant = msg.role === 'assistant';
                const msgTraces = msg.traces || [];
                const msgGrades: any[] = msgTraces.reduce<any[]>((acc, t) => {
                  if (t.doc_grades) acc.push(...t.doc_grades);
                  return acc;
                }, []);
                const isExpanded = expandedThinking[msg.id] ?? false;

                return (
                  <div key={msg.id} className={`message-container ${msg.role}`}>
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
                          <span className="author-name">
                            {isAssistant ? 'Ridge' : 'You'}
                          </span>
                          {msg.timestamp && (
                            <span className="message-time">{msg.timestamp}</span>
                          )}
                        </div>

                        {/* State Machine Thinking Accordion */}
                        {isAssistant && msgTraces.length > 0 && (
                          <div className="recall-thinking-block">
                            <button 
                              className="thinking-toggle-bar"
                              onClick={() => setExpandedThinking(prev => ({ ...prev, [msg.id]: !isExpanded }))}
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
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Markdown Text */}
                        {msg.content ? (
                          <div className="recall-markdown-body">
                            <ReactMarkdown>{msg.content}</ReactMarkdown>
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

                        {/* Embedded Citations & Veracity Cards */}
                        {isAssistant && msgGrades.length > 0 && (
                          <div className="recall-citations-section">
                            <div className="citations-header">
                              <BookOpen size={13} className="text-teal" />
                              <span>Anchored Topo and Grader Verdicts ({msgGrades.length} chunks evaluated)</span>
                            </div>
                            <div className="citations-flex">
                              {msgGrades.map((g: any, idx: number) => {
                                const fname = g.source ? g.source.split('/').pop() || g.source : `Chunk #${idx + 1}`;
                                const isRelevant = g.score === 'yes';
                                return (
                                  <button 
                                    key={idx} 
                                    className={`citation-pill ${isRelevant ? 'relevant' : 'filtered'}`}
                                    onClick={() => setSelectedSourceModal(g)}
                                    title="Inspect grader rationale and chunk excerpt"
                                  >
                                    <span className="cit-icon">
                                      {isRelevant ? <Check size={12} className="text-moss" /> : <X size={12} className="text-rust" />}
                                    </span>
                                    <span className="cit-name">{fname}</span>
                                    <span className={`cit-verdict ${isRelevant ? 'pass' : 'fail'}`}>
                                      {isRelevant ? 'Verified' : 'Filtered Crux'}
                                    </span>
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* Assistant Message Action Bar in Grouped Pill Container */}
                        {isAssistant && msg.content && (
                          <div className="message-action-footer">
                            <div className="action-pill-container">
                              <button 
                                className="msg-action-btn"
                                onClick={() => copyToClipboard(msg.content, msg.id)}
                                title="Copy response"
                                aria-label="Copy response"
                              >
                                {copiedId === msg.id ? <Check size={14} className="text-moss" /> : <Copy size={14} />}
                                <span>{copiedId === msg.id ? 'Copied' : 'Copy'}</span>
                              </button>

                              <button 
                                className={`msg-action-btn ${msg.liked === true ? 'active-like' : ''}`}
                                onClick={() => handleReaction(msg.id, true)}
                                title="Helpful ascent"
                                aria-label="Helpful response"
                              >
                                <ThumbsUp size={14} />
                              </button>

                              <button 
                                className={`msg-action-btn ${msg.liked === false ? 'active-dislike' : ''}`}
                                onClick={() => handleReaction(msg.id, false)}
                                title="Crux encountered"
                                aria-label="Crux encountered"
                              >
                                <ThumbsDown size={14} />
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Bottom Input Deck Anchored with Top Border */}
        <div className="recall-input-deck">
          {/* Slash Commands Dropup */}
          {showSlashMenu && (
            <div className="slash-menu-popover">
              <div className="slash-menu-header">
                <Command size={13} />
                <span>Quick Inquiries and Actions</span>
              </div>
              <button 
                className="slash-menu-item"
                onClick={() => {
                  setInput("Summarize the key findings across all indexed documents.");
                  setShowSlashMenu(false);
                }}
              >
                <Sparkles size={14} className="text-teal" />
                <div className="slash-item-meta">
                  <span className="slash-label">/summarize</span>
                  <span className="slash-desc">Generate comprehensive summary across indexed chunks</span>
                </div>
              </button>

              <button 
                className="slash-menu-item"
                onClick={() => {
                  setInput("Audit all sources for contradictory claims or hallucinations.");
                  setShowSlashMenu(false);
                }}
              >
                <ShieldCheck size={14} className="text-moss" />
                <div className="slash-item-meta">
                  <span className="slash-label">/verify</span>
                  <span className="slash-desc">Check veracity and contrast retrieved documents</span>
                </div>
              </button>

              <button 
                className="slash-menu-item"
                onClick={() => {
                  setInput("Extract all step-by-step methodologies mentioned in the knowledge base.");
                  setShowSlashMenu(false);
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
              value={input}
              onChange={(e) => {
                const val = e.target.value;
                setInput(val);
                if (val.startsWith('/')) {
                  setShowSlashMenu(true);
                } else if (showSlashMenu) {
                  setShowSlashMenu(false);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              rows={1}
              disabled={isLoading}
            />

            <div className="input-toolbar-row">
              <div className="toolbar-left">
                {/* File Attachment Button */}
                <input 
                  type="file" 
                  ref={chatAttachRef} 
                  onChange={handleChatFileAttach}
                  accept=".pdf,.md,.txt"
                  style={{ display: 'none' }}
                />
                <button 
                  className="toolbar-btn attach-btn"
                  onClick={() => chatAttachRef.current?.click()}
                  title="Attach file (PDF, TXT, MD) to index into Crag"
                  aria-label="Attach file"
                >
                  <Paperclip size={14} />
                  <span>Attach</span>
                </button>

                {/* Web Search Fallback Mode Toggle */}
                <button 
                  className={`toolbar-btn fallback-toggle-chip ${webSearchEnabled ? 'active' : ''}`}
                  onClick={() => setWebSearchEnabled(!webSearchEnabled)}
                  title={webSearchEnabled ? "Web fallback enabled when knowledge base recall is low" : "Web fallback disabled"}
                  aria-label="Toggle web fallback"
                >
                  <Globe size={13} className="fallback-globe-icon" />
                  <span>Web fallback</span>
                  <span className={`fallback-indicator-dot ${webSearchEnabled ? 'active' : ''}`} />
                </button>

                {/* Quick Prompts Helper */}
                <button
                  className="toolbar-btn prompts-trigger-btn"
                  onClick={() => setShowSlashMenu(!showSlashMenu)}
                  title="Browse structured prompts"
                  aria-label="Browse prompts"
                >
                  <Sparkles size={13} />
                  <span>Prompts</span>
                  <kbd className="prompt-slash-kbd">/</kbd>
                </button>
              </div>

              <div className="toolbar-right">
                {isLoading ? (
                  <button 
                    type="button"
                    className="recall-stop-btn"
                    onClick={handleStopGeneration}
                    title="Stop ascent generation (Esc)"
                    aria-label="Stop generation"
                  >
                    <Square size={11} fill="currentColor" />
                  </button>
                ) : (
                  <>
                    <span className="keyboard-enter-hint">Enter ↵</span>
                    <button 
                      type="button"
                      className={`recall-send-btn ${input.trim() ? 'ready' : ''}`}
                      onClick={() => handleSend()}
                      disabled={!input.trim()}
                      title="Send message (Enter)"
                      aria-label="Send message"
                    >
                      <ArrowUp size={17} strokeWidth={2.4} />
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="input-deck-disclaimer">
            Ridge can make mistakes. Verify important information against indexed sources.
          </div>
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
                    <p>No documents or chunks are currently stored in ChromaDB. Anchor a file, URL, or YouTube video to get started.</p>
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
                              onClick={() => handleDeleteKBSource(src.source, src.name)}
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
            {activeArtifactTab === 'grader' && (
              <div className="tab-pane grader-pane">
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
            )}
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
                <div 
                  className={`recall-dropzone ${isDragging ? 'dragging' : ''} ${selectedFile ? 'has-file' : ''}`}
                  onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={handleFileDrop}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input 
                    type="file" 
                    ref={fileInputRef} 
                    onChange={(e) => {
                      if (e.target.files && e.target.files.length > 0) {
                        setSelectedFile(e.target.files[0]);
                        setIngestInput('');
                      }
                    }}
                    accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tiff,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.csv,.tsv,.md,.markdown,.txt,.py,.js,.ts,.tsx,.jsx,.json,.yaml,.yml,.toml,.sql,.html,.css,.cpp,.c,.h,.java,.go,.rs,.sh,.srt,.vtt"
                    style={{ display: 'none' }}
                  />
                  {selectedFile ? (
                    <div className="dropzone-file-preview">
                      <FileText size={36} className="text-teal" />
                      <span className="file-preview-name">{selectedFile.name}</span>
                      <span className="file-preview-size">{(selectedFile.size / 1024).toFixed(1)} KB</span>
                    </div>
                  ) : (
                    <div className="dropzone-empty-prompt">
                      <Upload size={32} className="text-teal" />
                      <p>Drag and drop <strong>Documents, Images (OCR), Code, or Spreadsheets</strong></p>
                      <span className="dropzone-sub-formats">PDF, Images (PNG, JPG), Word (.docx), PPTX, Excel, CSV, Code, Markdown</span>
                      <span className="dropzone-tap-prompt">or tap to browse files</span>
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
                disabled={(!ingestInput.trim() && !selectedFile) || isIngesting || isIngestSuccess}
              >
                {isIngesting ? (
                  <>
                    <RotateCw size={15} className="spin-slow" />
                    <span>Anchoring Chunks...</span>
                  </>
                ) : isIngestSuccess ? (
                  <>
                    <Check size={15} />
                    <span>Successfully Anchored</span>
                  </>
                ) : (
                  <>
                    <Plus size={15} />
                    <span>Anchor to Crag</span>
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

      {/* Citation Detail Modal */}
      {selectedSourceModal && (
        <div className="recall-modal-backdrop" onClick={() => setSelectedSourceModal(null)}>
          <div className="recall-modal-card citation-detail-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-wrap">
                <BookOpen size={18} className="text-teal" />
                <h3>Source Grader Analysis</h3>
              </div>
              <button className="modal-close-btn" onClick={() => setSelectedSourceModal(null)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body-area">
              <div className="citation-badge-line">
                <span className={`grader-badge ${selectedSourceModal.score === 'yes' ? 'pass' : 'fail'}`}>
                  <span className="badge-icon-inline">
                    {selectedSourceModal.score === 'yes' ? <Check size={11} /> : <X size={11} />}
                  </span>
                  {selectedSourceModal.score === 'yes' ? 'USED IN ANSWER' : 'FILTERED OUT AS CRUX'}
                </span>
                {selectedSourceModal.source && (
                  <span className="source-uri-tag">{selectedSourceModal.source}</span>
                )}
              </div>

              <div className="detail-box">
                <h4>LLM Grader Rationale:</h4>
                <p className="rationale-text">{selectedSourceModal.rationale || 'No rationale provided by grader.'}</p>
              </div>
            </div>
          </div>
        </div>
      )}

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
