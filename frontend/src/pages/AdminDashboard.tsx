import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users,
  Database,
  Building2,

  UserPlus,
  ShieldCheck,
  Crown,
  Search,
  RotateCw,
  Trash2,
  X,
  Sliders,
  Check,
  ArrowLeft,
  User,
  Mail,
  Key,
  Eye,
  EyeOff,
  BarChart3,
  Server,
  Layers,
  Cpu,
  TrendingUp,
  HardDrive,
  UserX,
  UserCheck,
  MessageSquare,
  FileText,
  Globe,
  Lock,
  CheckCircle2,
  Clock,
  GitBranch,
  ArrowRight,
  Sparkles,
  Workflow,
} from 'lucide-react';




import './AdminDashboard.css';

// Symmetrical Mountain Summit & Neural Ridge Emblem
const RidgeLogo = ({ size = 26, className = '' }: { size?: number; className?: string }) => (
  <svg 
    width={size} 
    height={size} 
    viewBox="0 0 32 32" 
    fill="none" 
    xmlns="http://www.w3.org/2000/svg"
    className={`recall-emblem ${className}`}
  >
    <defs>
      <linearGradient id="admin-crag-logo-bg" x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#1E293B" />
        <stop offset="100%" stopColor="#0F172A" />
      </linearGradient>
      <linearGradient id="admin-summit-left-slope" x1="6" y1="24" x2="16" y2="8" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0284C7" />
        <stop offset="100%" stopColor="#38BDF8" />
      </linearGradient>
      <linearGradient id="admin-summit-right-slope" x1="16" y1="8" x2="26" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#F97316" />
        <stop offset="100%" stopColor="#EA580C" />
      </linearGradient>
    </defs>
    {/* Outer Rounded Squircle Frame */}
    <rect x="2" y="2" width="28" height="28" rx="8" fill="url(#admin-crag-logo-bg)" stroke="#334155" strokeWidth="1" />
    
    {/* Symmetrical Mountain Peak: Left (Summit Blue) & Right (Terracotta Rust) */}
    <polygon points="16,8 6,24 16,24" fill="url(#admin-summit-left-slope)" />
    <polygon points="16,8 16,24 26,24" fill="url(#admin-summit-right-slope)" />
    
    {/* Center Summit Ridge Line */}
    <line x1="16" y1="8" x2="16" y2="24" stroke="#FFFFFF" strokeWidth="1" strokeLinecap="round" />
    
    {/* Snowcap Top Triangle */}
    <polygon points="16,8 12.5,14 16,12.5 19.5,14" fill="#FFFFFF" />
    
    {/* High Altitude Beacon */}
    <circle cx="16" cy="6" r="1.5" fill="#38BDF8" stroke="#FFFFFF" strokeWidth="0.75" />
  </svg>
);

type ThemeMode = 'void' | 'stone' | 'rust';


interface UserProfile {
  id: string;
  username: string;
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
}

interface AdminUser {
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
}

interface AdminDocument {
  id: string;
  filename: string;
  file_size: number;
  mime_type: string;
  source_type: string;
  source_url: string;
  is_shared: boolean;
  status: string;
  chunk_count: number;
  uploaded_by: string;
  uploader_username: string;
  uploader_name: string;
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  created_at: string;
}

interface FeedbackItem {
  id: string;
  user_id?: string;
  username: string;
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  category: string;
  message: string;
  conversation_id?: string;
  status: 'open' | 'in_review' | 'resolved';
  admin_notes?: string;
  resolved_by?: string;
  created_at: string;
  updated_at: string;
}

interface ActivityDay {
  date: string;
  day: string;
  requests: number;
  active_users: number;
}

interface TopUser {
  id: string;
  username: string;
  name: string;
  role: string;
  requests_today: number;
  tenant_name: string;
}

interface AdminStats {
  total_users: number;
  active_users: number;
  total_requests_today: number;
  total_documents: number;
  total_chunks: number;
  storage_bytes?: number;
  storage_mb?: number;
  tenant_id?: string;
  tenant_name?: string;
  tenant_slug?: string;
  is_superadmin?: boolean;
  activity_history?: ActivityDay[];
  top_users?: TopUser[];
  system_status?: {
    vector_store: string;
    reranker: string;
    crag_evaluator: string;
    uptime: string;
  };
}

interface TenantItem {
  id: string;
  name: string;
  slug: string;
  is_active?: boolean;
  max_users?: number;
  user_count?: number;
  doc_count?: number;
  created_at?: string;
}

export const AdminDashboard: React.FC = () => {
  const navigate = useNavigate();

  // Theme Management (Synchronized with main application)
  const [theme, setTheme] = useState<ThemeMode>(() => {
    return (localStorage.getItem('recall_theme') as ThemeMode) || 'stone';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('recall_theme', theme);
  }, [theme]);

  // Current Auth User
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(() => {
    try {
      const saved = localStorage.getItem('ridge_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  // Navigation tabs: 'analytics' | 'users' | 'documents' | 'feedback' | 'tenants' | 'pipeline'
  const [activeTab, setActiveTab] = useState<'analytics' | 'users' | 'documents' | 'feedback' | 'tenants' | 'pipeline'>('analytics');

  // Admin Data State
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
  const [adminDocuments, setAdminDocuments] = useState<AdminDocument[]>([]);
  const [adminFeedbacks, setAdminFeedbacks] = useState<FeedbackItem[]>([]);
  const [adminStats, setAdminStats] = useState<AdminStats | null>(null);
  const [adminTenantsList, setAdminTenantsList] = useState<TenantItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [tenantFilter, setTenantFilter] = useState('');

  // Feedback filter states
  const [feedbackStatusFilter, setFeedbackStatusFilter] = useState<string>('all');
  const [feedbackCategoryFilter, setFeedbackCategoryFilter] = useState<string>('all');
  const [selectedFeedbackForResolution, setSelectedFeedbackForResolution] = useState<FeedbackItem | null>(null);
  const [resolutionStatus, setResolutionStatus] = useState<'open' | 'in_review' | 'resolved'>('resolved');
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [isUpdatingFeedback, setIsUpdatingFeedback] = useState(false);

  // Multi-select Users State
  const [selectedUserIds, setSelectedUserIds] = useState<Set<string>>(new Set());
  const [isBulkDeletingUsers, setIsBulkDeletingUsers] = useState(false);

  // Multi-select Documents State
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [isBulkDeletingDocs, setIsBulkDeletingDocs] = useState(false);

  // Multi-select Institutions State
  const [selectedTenantIds, setSelectedTenantIds] = useState<string[]>([]);
  const [selectedInstitutionsFilter, setSelectedInstitutionsFilter] = useState<string[]>([]);

  // Quota Edit State
  const [editingLimitUserId, setEditingLimitUserId] = useState<string | null>(null);
  const [tempLimitValue, setTempLimitValue] = useState<number>(50);

  // Modals State
  const [isAddUserModalOpen, setIsAddUserModalOpen] = useState(false);
  const [isCreateTenantModalOpen, setIsCreateTenantModalOpen] = useState(false);

  // New User Form State
  const [newUsername, setNewUsername] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newName, setNewName] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState<'user' | 'admin'>('user');
  const [newLimit, setNewLimit] = useState<number>(50);
  const [newTenantId, setNewTenantId] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [isCreatingUser, setIsCreatingUser] = useState(false);

  // New Tenant Form State
  const [newTenantName, setNewTenantName] = useState('');
  const [newTenantSlug, setNewTenantSlug] = useState('');
  const [newTenantMaxUsers, setNewTenantMaxUsers] = useState<number>(50);
  const [isCreatingTenant, setIsCreatingTenant] = useState(false);

  // Chart Interactive Hover State
  const [hoveredDayIdx, setHoveredDayIdx] = useState<number | null>(null);

  // Pipeline Visualizer Selected Node State
  const [selectedPipelineNode, setSelectedPipelineNode] = useState<string>('reranker');

  // Custom Toast State
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);



  // Custom Confirmation Dialog State
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    title: string;
    message: string;
    danger?: boolean;
    onConfirm: () => void;
  }>({ open: false, title: '', message: '', onConfirm: () => {} });

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  // Authenticated fetch wrapper
  const fetchWithAuth = async (url: string, options: RequestInit = {}) => {
    const token = localStorage.getItem('ridge_token');
    const headers = {
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    };
    return fetch(url, { ...options, headers });
  };

  // Fetch all admin resources
  const fetchAdminData = async (targetTenantFilter?: string) => {
    setIsLoading(true);
    try {
      const activeFilter = targetTenantFilter !== undefined ? targetTenantFilter : tenantFilter;
      const filterParam = activeFilter ? `?tenant_id=${encodeURIComponent(activeFilter)}` : '';

      const [usersRes, statsRes, tenantsRes, docsRes, feedbackRes] = await Promise.all([
        fetchWithAuth(`/api/admin/users${filterParam}`),
        fetchWithAuth('/api/admin/stats'),
        fetchWithAuth('/api/admin/tenants'),
        fetchWithAuth(`/api/admin/documents${filterParam}`),
        fetchWithAuth('/api/admin/feedback')
      ]);

      if (usersRes.ok) {
        const uData = await usersRes.json();
        setAdminUsers(uData.users || []);
      }
      if (statsRes.ok) {
        const sData = await statsRes.json();
        setAdminStats(sData);
        if (sData.is_superadmin && currentUser && currentUser.role !== 'superadmin') {
          const updatedUser = { ...currentUser, role: 'superadmin' };
          setCurrentUser(updatedUser);
          localStorage.setItem('ridge_user', JSON.stringify(updatedUser));
        }
      }
      if (tenantsRes && tenantsRes.ok) {
        const tData = await tenantsRes.json();
        setAdminTenantsList(tData.tenants || []);
      }
      if (docsRes && docsRes.ok) {
        const dData = await docsRes.json();
        setAdminDocuments(dData.documents || []);
      }
      if (feedbackRes && feedbackRes.ok) {
        const fData = await feedbackRes.json();
        setAdminFeedbacks(fData.feedback || []);
      }
    } catch (e) {
      console.error('Failed to load admin data:', e);
      showToast('Failed to load dashboard metrics', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  // Multi-select Users handlers
  const handleToggleSelectAllUsers = (checked: boolean, visibleUsers: AdminUser[]) => {
    if (checked) {
      const deletableIds = visibleUsers
        .filter(u => u.role !== 'superadmin' && u.id !== currentUser?.id)
        .map(u => u.id);
      setSelectedUserIds(new Set(deletableIds));
    } else {
      setSelectedUserIds(new Set());
    }
  };

  const handleToggleSelectUser = (userId: string) => {
    setSelectedUserIds(prev => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  // Bulk Delete Users
  const handleBulkDeleteUsers = () => {
    const ids = Array.from(selectedUserIds);
    const deletable = adminUsers.filter(u => ids.includes(u.id) && u.role !== 'superadmin' && u.id !== currentUser?.id);
    if (deletable.length === 0) {
      showToast('No eligible climbers selected for deletion', 'error');
      return;
    }

    setConfirmDialog({
      open: true,
      title: `Delete ${deletable.length} Climber Account${deletable.length > 1 ? 's' : ''}`,
      message: `Permanently delete ${deletable.length} selected accounts and all their uploaded documents? This action is irreversible.`,
      danger: true,
      onConfirm: async () => {
        setConfirmDialog(d => ({ ...d, open: false }));
        setIsBulkDeletingUsers(true);
        try {
          const res = await fetchWithAuth('/api/admin/users/bulk-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_ids: deletable.map(u => u.id) })
          });
          if (res.ok) {
            showToast(`Deleted ${deletable.length} climber account${deletable.length > 1 ? 's' : ''}`, 'success');
            setSelectedUserIds(new Set());
            fetchAdminData();
          } else {
            const err = await res.json();
            showToast(err.detail || 'Bulk deletion failed', 'error');
          }
        } catch (e) {
          showToast('Error during bulk deletion', 'error');
        } finally {
          setIsBulkDeletingUsers(false);
        }
      }
    });
  };

  // Single User Delete
  const handleDeleteSingleUser = (userId: string, username: string) => {
    setConfirmDialog({
      open: true,
      title: 'Delete Climber Account',
      message: `Permanently delete @${username} and all their indexed knowledge? This action cannot be undone.`,
      danger: true,
      onConfirm: async () => {
        setConfirmDialog(d => ({ ...d, open: false }));
        try {
          const res = await fetchWithAuth(`/api/admin/users/${userId}`, { method: 'DELETE' });
          if (res.ok) {
            showToast(`Climber @${username} deleted`, 'success');
            setAdminUsers(prev => prev.filter(u => u.id !== userId));
            setSelectedUserIds(prev => {
              const next = new Set(prev);
              next.delete(userId);
              return next;
            });
          } else {
            const err = await res.json();
            showToast(err.detail || 'Failed to delete user', 'error');
          }
        } catch (e) {
          showToast('Error deleting user', 'error');
        }
      }
    });
  };

  // Multi-select Documents handlers
  const handleToggleSelectAllDocs = (checked: boolean, visibleDocs: AdminDocument[]) => {
    if (checked) {
      setSelectedDocIds(new Set(visibleDocs.map(d => d.id)));
    } else {
      setSelectedDocIds(new Set());
    }
  };

  const handleToggleSelectDoc = (docId: string) => {
    setSelectedDocIds(prev => {
      const next = new Set(prev);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });
  };

  // Bulk Delete Documents
  const handleBulkDeleteDocs = () => {
    const ids = Array.from(selectedDocIds);
    if (ids.length === 0) return;

    setConfirmDialog({
      open: true,
      title: `Delete ${ids.length} Document${ids.length > 1 ? 's' : ''}`,
      message: `Permanently delete ${ids.length} selected knowledge document${ids.length > 1 ? 's' : ''} and all their vector embeddings?`,
      danger: true,
      onConfirm: async () => {
        setConfirmDialog(d => ({ ...d, open: false }));
        setIsBulkDeletingDocs(true);
        try {
          const res = await fetchWithAuth('/api/admin/documents/bulk-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ document_ids: ids })
          });
          if (res.ok) {
            showToast(`Deleted ${ids.length} document${ids.length > 1 ? 's' : ''}`, 'success');
            setSelectedDocIds(new Set());
            fetchAdminData();
          } else {
            const err = await res.json();
            showToast(err.detail || 'Bulk deletion failed', 'error');
          }
        } catch (e) {
          showToast('Error during document deletion', 'error');
        } finally {
          setIsBulkDeletingDocs(false);
        }
      }
    });
  };

  // Single Document Delete
  const handleDeleteSingleDoc = (docId: string, filename: string) => {
    setConfirmDialog({
      open: true,
      title: 'Delete Knowledge Document',
      message: `Permanently delete "${filename}" and all its indexed chunks?`,
      danger: true,
      onConfirm: async () => {
        setConfirmDialog(d => ({ ...d, open: false }));
        try {
          const res = await fetchWithAuth(`/api/admin/documents/${docId}`, { method: 'DELETE' });
          if (res.ok) {
            showToast(`Document "${filename}" deleted`, 'success');
            setAdminDocuments(prev => prev.filter(d => d.id !== docId));
            setSelectedDocIds(prev => {
              const next = new Set(prev);
              next.delete(docId);
              return next;
            });
            fetchAdminData();
          } else {
            const err = await res.json();
            showToast(err.detail || 'Failed to delete document', 'error');
          }
        } catch (e) {
          showToast('Error deleting document', 'error');
        }
      }
    });
  };

  // Document Sharing Toggle
  const handleToggleDocumentSharing = async (docId: string, currentShared: boolean) => {
    const newShared = !currentShared;
    try {
      const res = await fetchWithAuth(`/api/kb/documents/${docId}/share`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_shared: newShared })
      });
      if (res.ok) {
        showToast(`Document set to ${newShared ? 'Shared across Enterprise' : 'Private to Climber'}`, 'success');
        setAdminDocuments(prev => prev.map(d => d.id === docId ? { ...d, is_shared: newShared } : d));
      } else {
        const err = await res.json();
        showToast(err.detail || 'Failed to update sharing setting', 'error');
      }
    } catch (e) {
      showToast('Error updating document sharing', 'error');
    }
  };

  // Feedback Resolution
  const handleSaveFeedbackResolution = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFeedbackForResolution) return;

    setIsUpdatingFeedback(true);
    try {
      const res = await fetchWithAuth(`/api/admin/feedback/${selectedFeedbackForResolution.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: resolutionStatus,
          admin_notes: resolutionNotes.trim(),
        })
      });

      if (res.ok) {
        showToast('Feedback status updated and resolution notes saved', 'success');
        setSelectedFeedbackForResolution(null);
        setResolutionNotes('');
        fetchAdminData();
      } else {
        const err = await res.json();
        showToast(err.detail || 'Failed to update feedback', 'error');
      }
    } catch (e) {
      showToast('Error updating feedback status', 'error');
    } finally {
      setIsUpdatingFeedback(false);
    }
  };

  // Delete Feedback
  const handleDeleteFeedback = (feedbackId: string) => {
    setConfirmDialog({
      open: true,
      title: 'Delete Feedback Inquiry',
      message: 'Permanently remove this inquiry from the administration records?',
      danger: true,
      onConfirm: async () => {
        setConfirmDialog(d => ({ ...d, open: false }));
        try {
          const res = await fetchWithAuth(`/api/admin/feedback/${feedbackId}`, { method: 'DELETE' });
          if (res.ok) {
            showToast('Feedback inquiry deleted', 'success');
            setAdminFeedbacks(prev => prev.filter(f => f.id !== feedbackId));
          } else {
            const err = await res.json();
            showToast(err.detail || 'Failed to delete feedback', 'error');
          }
        } catch (e) {
          showToast('Error deleting feedback', 'error');
        }
      }
    });
  };

  // Role promotion / demotion
  const handleUpdateRole = async (targetId: string, currentRole: string) => {
    const newRoleVal = currentRole === 'admin' ? 'user' : 'admin';
    try {
      const res = await fetchWithAuth(`/api/admin/users/${targetId}/role`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: newRoleVal })
      });
      if (res.ok) {
        showToast(`Role updated to ${newRoleVal === 'admin' ? 'Enterprise Admin' : 'Climber'}`, 'success');
        setAdminUsers(prev => prev.map(u => u.id === targetId ? { ...u, role: newRoleVal } : u));
      } else {
        const err = await res.json();
        showToast(err.detail || 'Failed to update role', 'error');
      }
    } catch (e) {
      showToast('Error updating role', 'error');
    }
  };

  // Status toggle
  const handleUpdateStatus = async (targetId: string, currentStatus: boolean) => {
    const newStatus = !currentStatus;
    try {
      const res = await fetchWithAuth(`/api/admin/users/${targetId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: newStatus })
      });
      if (res.ok) {
        showToast(`Account ${newStatus ? 'activated' : 'suspended'}`, 'success');
        setAdminUsers(prev => prev.map(u => u.id === targetId ? { ...u, is_active: newStatus } : u));
      } else {
        const err = await res.json();
        showToast(err.detail || 'Failed to update status', 'error');
      }
    } catch (e) {
      showToast('Error updating status', 'error');
    }
  };

  // Quota save
  const handleSaveLimit = async (targetId: string, limitVal: number) => {
    try {
      const res = await fetchWithAuth(`/api/admin/users/${targetId}/limit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: limitVal })
      });
      if (res.ok) {
        showToast(`Daily quota set to ${limitVal} queries/day`, 'success');
        setAdminUsers(prev => prev.map(u => u.id === targetId ? { ...u, daily_request_limit: limitVal } : u));
        setEditingLimitUserId(null);
      } else {
        const err = await res.json();
        showToast(err.detail || 'Failed to update quota limit', 'error');
      }
    } catch (e) {
      showToast('Error updating quota limit', 'error');
    }
  };

  // Tenant toggle
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

  // Bulk Toggle Tenant Status
  const handleBulkToggleTenantStatus = async (tenantIds: string[], newStatus: boolean) => {
    if (tenantIds.length === 0) return;
    try {
      const promises = tenantIds.map(tId =>
        fetchWithAuth(`/api/admin/tenants/${tId}/status`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_active: newStatus })
        })
      );
      await Promise.all(promises);
      showToast(`${tenantIds.length} institutions ${newStatus ? 'activated' : 'suspended'}`, 'success');
      setAdminTenantsList(prev =>
        prev.map(t => tenantIds.includes(t.id) ? { ...t, is_active: newStatus } : t)
      );
      setSelectedTenantIds([]);
    } catch (e) {
      showToast('Error updating institutions in bulk', 'error');
    }
  };

  // Bulk Delete Tenants & Cascaded Users
  const handleBulkDeleteTenants = (tenantIds: string[]) => {
    if (tenantIds.length === 0) return;
    const nonDefaultIds = tenantIds.filter(id => {
      const t = adminTenantsList.find(item => item.id === id);
      return t && t.slug !== 'default';
    });
    if (nonDefaultIds.length === 0) {
      showToast('Cannot delete the primary system root institution.', 'error');
      return;
    }
    setConfirmDialog({
      open: true,
      title: `Delete ${nonDefaultIds.length} Institutions & All Members`,
      message: `Permanently delete ${nonDefaultIds.length} selected institutions and ALL of their associated members/climbers, knowledge bases, documents, and chunks? This operation cannot be undone.`,
      danger: true,
      onConfirm: async () => {
        setConfirmDialog(d => ({ ...d, open: false }));
        try {
          const res = await fetchWithAuth('/api/admin/tenants/bulk-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tenant_ids: nonDefaultIds })
          });
          if (res.ok) {
            const data = await res.json();
            showToast(`${data.deleted_count || nonDefaultIds.length} institutions and all associated users deleted`, 'success');
            setAdminTenantsList(prev => prev.filter(t => !nonDefaultIds.includes(t.id)));
            setSelectedTenantIds([]);
            fetchAdminData();
          } else {
            const err = await res.json();
            showToast(err.detail || 'Failed to delete selected institutions', 'error');
          }
        } catch (e) {
          showToast('Error deleting selected institutions', 'error');
        }
      }
    });
  };

  // Delete Tenant
  const handleDeleteTenant = (tenantId: string, tenantName: string) => {
    setConfirmDialog({
      open: true,
      title: 'Delete Institution Enterprise',
      message: `Permanently delete "${tenantName}" and all associated climbers, documents, and vector embeddings? This cannot be recovered.`,
      danger: true,
      onConfirm: async () => {
        setConfirmDialog(d => ({ ...d, open: false }));
        try {
          const res = await fetchWithAuth(`/api/admin/tenants/${tenantId}`, { method: 'DELETE' });
          if (res.ok) {
            showToast(`Institution "${tenantName}" deleted`, 'success');
            setAdminTenantsList(prev => prev.filter(t => t.id !== tenantId));
            if (tenantFilter === tenantId) setTenantFilter('');
            fetchAdminData();
          } else {
            const err = await res.json();
            showToast(err.detail || 'Failed to delete institution', 'error');
          }
        } catch (e) {
          showToast('Error deleting institution', 'error');
        }
      }
    });
  };

  // Create User
  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUsername.trim() || !newEmail.trim() || !newPassword.trim()) {
      showToast('Please fill all required user fields', 'error');
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
      if ((currentUser?.role === 'superadmin' || adminStats?.is_superadmin) && newTenantId) {
        payload.tenant_id = newTenantId;
      }

      const res = await fetchWithAuth('/api/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        showToast(`Climber @${newUsername.trim()} created successfully!`, 'success');
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
        showToast(err.detail || 'Failed to create user account', 'error');
      }
    } catch (e) {
      showToast('Error creating user account', 'error');
    } finally {
      setIsCreatingUser(false);
    }
  };

  // Create Tenant
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
        showToast(`Institution "${newTenantName}" provisioned!`, 'success');
        setIsCreateTenantModalOpen(false);
        setNewTenantName('');
        setNewTenantSlug('');
        setNewTenantMaxUsers(50);
        fetchAdminData();
      } else {
        const err = await res.json();
        showToast(err.detail || 'Failed to provision institution', 'error');
      }
    } catch (e) {
      showToast('Error provisioning institution', 'error');
    } finally {
      setIsCreatingTenant(false);
    }
  };

  // Filtered Users list
  const filteredUsers = adminUsers.filter(u => {
    if (selectedInstitutionsFilter.length > 0) {
      if (!u.tenant_id || !selectedInstitutionsFilter.includes(u.tenant_id)) {
        return false;
      }
    }
    const q = searchQuery.toLowerCase();
    return (
      u.username.toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q) ||
      (u.name && u.name.toLowerCase().includes(q)) ||
      u.role.toLowerCase().includes(q) ||
      (u.tenant_name && u.tenant_name.toLowerCase().includes(q)) ||
      (u.tenant_slug && u.tenant_slug.toLowerCase().includes(q))
    );
  });

  // Filtered Documents list
  const filteredDocs = adminDocuments.filter(d => {
    const q = searchQuery.toLowerCase();
    return (
      d.filename.toLowerCase().includes(q) ||
      d.uploader_username.toLowerCase().includes(q) ||
      d.uploader_name.toLowerCase().includes(q) ||
      (d.tenant_name && d.tenant_name.toLowerCase().includes(q))
    );
  });

  // Filtered Feedbacks list
  const filteredFeedbacks = adminFeedbacks.filter(f => {
    const q = searchQuery.toLowerCase();
    const matchesSearch =
      f.username.toLowerCase().includes(q) ||
      f.message.toLowerCase().includes(q) ||
      f.category.toLowerCase().includes(q) ||
      (f.tenant_name && f.tenant_name.toLowerCase().includes(q));

    const matchesStatus = feedbackStatusFilter === 'all' || f.status === feedbackStatusFilter;
    const matchesCategory = feedbackCategoryFilter === 'all' || f.category === feedbackCategoryFilter;

    return matchesSearch && matchesStatus && matchesCategory;
  });

  const isSuperAdmin = currentUser?.role === 'superadmin' || adminStats?.is_superadmin;
  const activityHistory = adminStats?.activity_history || [];
  const maxHistoryReqs = Math.max(...activityHistory.map(d => d.requests), 6);
  const totalWeeklyReqs = activityHistory.reduce((acc, curr) => acc + curr.requests, 0);
  const avgDailyReqs = activityHistory.length > 0 ? Math.round(totalWeeklyReqs / activityHistory.length) : 0;
  const peakDayReqs = activityHistory.length > 0 ? Math.max(...activityHistory.map(d => d.requests)) : 0;
  const unresolvedFeedbackCount = adminFeedbacks.filter(f => f.status !== 'resolved').length;


  return (

    <div className="admin-page-container" data-theme={theme}>
      {/* Toast Notification */}
      {toast && (
        <div className={`toast-notification ${toast.type}`}>
          {toast.message}
        </div>
      )}

      {/* 1. Top Navbar */}
      <header className="admin-top-navbar">
        <div className="admin-nav-left">
          <button
            onClick={() => navigate('/')}
            className="admin-brand-link"
            title="Return to Ridge Ascent"
          >
            <div className="brand-logo-frame">
              <RidgeLogo size={26} />
            </div>
            <div className="brand-texts">
              <div className="brand-row">
                <span className="brand-name">Ridge<span className="brand-dot">.</span></span>
              </div>
              <span className="brand-subtitle">Console</span>
            </div>
          </button>


          {adminStats?.tenant_name && (
            <span className="admin-enterprise-badge">
              <Building2 size={13} />
              <span>{adminStats.tenant_name}</span>
              {adminStats.tenant_slug && <span className="tenant-slug-tag">@{adminStats.tenant_slug}</span>}
            </span>
          )}

          {isSuperAdmin && (
            <span className="superadmin-status-pill">
              <Crown size={12} />
              <span>SuperAdmin Global Root</span>
            </span>
          )}
        </div>

        <div className="admin-nav-right">
          <div className="admin-system-health-pill">
            <span className="health-dot" />
            <span>CRAG Pipeline Live</span>
          </div>

          <button
            onClick={() => navigate('/')}
            className="admin-back-chat-btn"
            title="Return to Knowledge Ascent"
          >
            <ArrowLeft size={15} />
            <span>Back to Ascent</span>
          </button>

          <div className="admin-user-profile-badge">
            <div className="admin-user-avatar">
              {(currentUser?.name || currentUser?.username || 'A').charAt(0).toUpperCase()}
            </div>
            <span>@{currentUser?.username || 'admin'}</span>
          </div>
        </div>
      </header>

      {/* 2. Main Body (Sidebar + Content Canvas) */}
      <div className="admin-main-body">
        {/* Left Navigation Sidebar */}
        <aside className="admin-sidebar">
          <div className="admin-sidebar-nav">
            <span className="admin-nav-category-label">Command Center</span>
            
            <button
              className={`admin-tab-item ${activeTab === 'analytics' ? 'active' : ''}`}
              onClick={() => setActiveTab('analytics')}
            >
              <BarChart3 size={17} />
              <span>Analytics & Metrics</span>
            </button>

            <button
              className={`admin-tab-item ${activeTab === 'users' ? 'active' : ''}`}
              onClick={() => setActiveTab('users')}
            >
              <Users size={17} />
              <span>Climbers & Users</span>
              <span className="tab-badge">{adminUsers.length}</span>
            </button>

            <button
              className={`admin-tab-item ${activeTab === 'documents' ? 'active' : ''}`}
              onClick={() => setActiveTab('documents')}
            >
              <FileText size={17} />
              <span>Knowledge & Docs</span>
              <span className="tab-badge">{adminDocuments.length}</span>
            </button>

            <button
              className={`admin-tab-item ${activeTab === 'feedback' ? 'active' : ''}`}
              onClick={() => setActiveTab('feedback')}
            >
              <MessageSquare size={17} />
              <span>Feedback & Inquiries</span>
              {unresolvedFeedbackCount > 0 && (
                <span className="tab-badge feedback-badge" title={`${unresolvedFeedbackCount} unresolved inquiries`}>
                  {unresolvedFeedbackCount}
                </span>
              )}
            </button>




            {isSuperAdmin && (
              <button
                className={`admin-tab-item ${activeTab === 'tenants' ? 'active' : ''}`}
                onClick={() => setActiveTab('tenants')}
              >
                <Building2 size={17} />
                <span>Institutions</span>
                <span className="tab-badge">{adminTenantsList.length}</span>
              </button>
            )}

            <span className="admin-nav-category-label" style={{ marginTop: 16 }}>Engine & System</span>

            <button
              className={`admin-tab-item ${activeTab === 'pipeline' ? 'active' : ''}`}
              onClick={() => setActiveTab('pipeline')}
            >
              <Server size={17} />
              <span>CRAG Architecture</span>
            </button>
          </div>

          <div className="admin-sidebar-footer">
            {/* Theme Toggle */}
            <div className="admin-theme-switch-row">
              <span className="admin-theme-label">Theme Palette</span>
              <div className="theme-toggle-group" style={{ width: '100%' }}>
                <button 
                  className={`theme-btn ${theme === 'void' ? 'active' : ''}`}
                  onClick={() => setTheme('void')}
                  title="Chalk & Void: Dark Basalt & Alpine Teal"
                  type="button"
                >
                  <span className="theme-color-dot void-dot" />
                  <span>Void</span>
                </button>
                <button 
                  className={`theme-btn ${theme === 'stone' ? 'active' : ''}`}
                  onClick={() => setTheme('stone')}
                  title="Stone & Summit: Warm Sandstone & Summit Blue"
                  type="button"
                >
                  <span className="theme-color-dot stone-dot" />
                  <span>Summit</span>
                </button>
                <button 
                  className={`theme-btn ${theme === 'rust' ? 'active' : ''}`}
                  onClick={() => setTheme('rust')}
                  title="Rust & Ridge: Desert Crag & Terracotta Rust"
                  type="button"
                >
                  <span className="theme-color-dot rust-dot" />
                  <span>Ridge</span>
                </button>
              </div>
            </div>

            <div className="admin-tenant-context-card">
              <span className="context-label">Current Scope</span>
              <span className="context-name">
                <Building2 size={13} />
                {tenantFilter
                  ? adminTenantsList.find(t => t.id === tenantFilter)?.name || 'Filtered'
                  : isSuperAdmin
                  ? 'All Enterprises (Global)'
                  : adminStats?.tenant_name || 'Enterprise Workspace'}
              </span>
            </div>
          </div>
        </aside>

        {/* Content Canvas */}
        <main className="admin-content-canvas">
          {/* ================================================================ */}
          {/* TAB 1: ANALYTICS & OVERVIEW                                     */}
          {/* ================================================================ */}
          {activeTab === 'analytics' && (
            <div>
              <div className="admin-view-header">
                <div className="view-title-wrap">
                  <h1>Executive Analytics & System Usage</h1>
                  <p className="view-subtitle">
                    Real-time ingestion volumes, CRAG retrieval queries, and enterprise capacity utilization
                  </p>
                </div>
                <div className="view-actions-wrap">
                  <button
                    className="btn-secondary-admin"
                    onClick={() => fetchAdminData()}
                    disabled={isLoading}
                  >
                    <RotateCw size={14} className={isLoading ? 'spin-slow' : ''} />
                    <span>Refresh Metrics</span>
                  </button>
                </div>
              </div>

              {/* KPI Cards */}
              <div className="admin-kpi-grid">
                <div className="admin-kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-title">Total Climbers</span>
                    <div className="kpi-icon-wrap blue">
                      <Users size={18} />
                    </div>
                  </div>
                  <div className="kpi-value">{adminStats?.total_users || 0}</div>
                  <span className="kpi-sub">
                    {adminStats?.active_users || 0} active members authenticated
                  </span>
                </div>

                <div className="admin-kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-title">Inference Queries Today</span>
                    <div className="kpi-icon-wrap green">
                      <TrendingUp size={18} />
                    </div>
                  </div>
                  <div className="kpi-value">{adminStats?.total_requests_today || 0}</div>
                  <span className="kpi-sub">Across all verified RAG ascents</span>
                </div>

                <div className="admin-kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-title">Indexed Knowledge Chunks</span>
                    <div className="kpi-icon-wrap purple">
                      <Layers size={18} />
                    </div>
                  </div>
                  <div className="kpi-value">{adminStats?.total_chunks || 0}</div>
                  <span className="kpi-sub">
                    From {adminStats?.total_documents || 0} source documents
                  </span>
                </div>

                <div className="admin-kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-title">Storage Footprint</span>
                    <div className="kpi-icon-wrap amber">
                      <HardDrive size={18} />
                    </div>
                  </div>
                  <div className="kpi-value">
                    {adminStats?.storage_mb && adminStats.storage_mb >= 0.1
                      ? `${adminStats.storage_mb} MB`
                      : adminStats?.storage_bytes && adminStats.storage_bytes > 0
                      ? `${Math.round(adminStats.storage_bytes / 1024)} KB`
                      : `${adminStats?.total_chunks ? Math.round((adminStats.total_chunks * 4096) / 1024) + ' KB' : '0 MB'}`}
                  </div>
                  <span className="kpi-sub">
                    {adminStats?.storage_bytes ? adminStats.storage_bytes.toLocaleString() : (adminStats?.total_chunks ? (adminStats.total_chunks * 4096).toLocaleString() : '0')} embedded bytes
                  </span>
                </div>
              </div>

              {/* Analytics Panels: 7-Day Chart & Top Climbers */}
              <div className="analytics-cards-row">
                {/* 7-Day Query Trend Chart - Clean Minimalist Spline */}
                <div className="analytics-panel ridge-chart-panel">
                  <div className="panel-header">
                    <div>
                      <div className="panel-title">
                        <TrendingUp size={18} style={{ color: 'var(--recall-accent)' }} />
                        <span>7-Day Inference &amp; Query Activity</span>
                      </div>
                      <span className="chart-panel-sub">
                        {totalWeeklyReqs} total verified inferences this week • {avgDailyReqs}/day average
                      </span>
                    </div>

                    <div className="chart-peak-meta">
                      <span className="peak-meta-label">Peak:</span>
                      <strong className="peak-meta-val">{peakDayReqs} reqs</strong>
                      <span className="peak-meta-tag">Today</span>
                    </div>
                  </div>

                  <div className="ridge-chart-viewport">
                    {/* Y-Axis Reference Ticks */}
                    <div className="ridge-y-axis">
                      <span>{maxHistoryReqs}</span>
                      <span>{Math.round(maxHistoryReqs * 0.5)}</span>
                      <span>0</span>
                    </div>

                    {/* Main Chart Canvas */}
                    <div className="ridge-canvas-wrapper">
                      {/* Dashed Horizontal Guide Lines */}
                      <div className="ridge-gridlines">
                        <div className="gridline top" />
                        <div className="gridline mid" />
                        <div className="gridline btm" />
                      </div>

                      {/* SVG Mountain Ridge Spline Area */}
                      {activityHistory.length > 1 && (
                        <svg className="ridge-svg-canvas" viewBox="0 0 700 170" preserveAspectRatio="none">
                          <defs>
                            <linearGradient id="ridgeTerrainGradient" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="var(--recall-accent)" stopOpacity="0.22" />
                              <stop offset="70%" stopColor="var(--recall-accent)" stopOpacity="0.04" />
                              <stop offset="100%" stopColor="var(--recall-accent)" stopOpacity="0.0" />
                            </linearGradient>
                          </defs>

                          {(() => {
                            const numPoints = activityHistory.length;
                            const points = activityHistory.map((d, i) => {
                              const x = (i / (numPoints - 1)) * 620 + 40;
                              const y = 145 - (d.requests / maxHistoryReqs) * 115;
                              return { x, y, data: d };
                            });

                            // Smooth Bézier Spline Line
                            const linePath = points.reduce((acc, pt, i, arr) => {
                              if (i === 0) return `M ${pt.x},${pt.y}`;
                              const prev = arr[i - 1];
                              const cx = (prev.x + pt.x) / 2;
                              return `${acc} C ${cx},${prev.y} ${cx},${pt.y} ${pt.x},${pt.y}`;
                            }, '');

                            const areaPath = `${linePath} L ${points[points.length - 1].x},160 L ${points[0].x},160 Z`;

                            return (
                              <>
                                {/* Mountain Terrain Glow Fill */}
                                <path d={areaPath} fill="url(#ridgeTerrainGradient)" />

                                {/* Topographic Ridge Line */}
                                <path
                                  d={linePath}
                                  fill="none"
                                  stroke="var(--recall-accent)"
                                  strokeWidth="2.5"
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                />

                                {/* Vertical Hover Drop-Line */}
                                {hoveredDayIdx !== null && points[hoveredDayIdx] && (
                                  <line
                                    x1={points[hoveredDayIdx].x}
                                    y1={points[hoveredDayIdx].y}
                                    x2={points[hoveredDayIdx].x}
                                    y2={160}
                                    stroke="var(--recall-accent)"
                                    strokeWidth="1.5"
                                    strokeDasharray="4 4"
                                    opacity="0.8"
                                  />
                                )}

                                {/* Data Vertex Markers */}
                                {points.map((pt, idx) => {
                                  const isFocused = hoveredDayIdx === idx;
                                  const isToday = idx === points.length - 1;

                                  return (
                                    <circle
                                      key={idx}
                                      cx={pt.x}
                                      cy={pt.y}
                                      r={isFocused ? 5.5 : isToday ? 4.5 : 3.5}
                                      fill={isToday ? "var(--recall-warning)" : isFocused ? "var(--recall-accent)" : "var(--recall-surface)"}
                                      stroke={isToday ? "var(--recall-warning)" : "var(--recall-accent)"}
                                      strokeWidth={isFocused ? 2.5 : 2}
                                      style={{ cursor: 'pointer', transition: 'all 0.15s ease' }}
                                    />
                                  );
                                })}
                              </>
                            );
                          })()}
                        </svg>
                      )}

                      {/* Interactive Column Hover Hitboxes */}
                      <div className="ridge-hitbox-overlay">
                        {activityHistory.map((_, idx) => (
                          <div
                            key={idx}
                            className={`ridge-hitbox-col ${hoveredDayIdx === idx ? 'active' : ''}`}
                            onMouseEnter={() => setHoveredDayIdx(idx)}
                            onMouseLeave={() => setHoveredDayIdx(null)}
                          />
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Day Buttons / X-Axis Rail */}
                  <div className="ridge-day-rail">
                    {activityHistory.map((day, idx) => {
                      const isToday = idx === activityHistory.length - 1;
                      const isFocused = hoveredDayIdx === idx;
                      const isPeak = day.requests === peakDayReqs && peakDayReqs > 0;

                      return (
                        <button
                          key={idx}
                          type="button"
                          className={`ridge-day-tab ${isFocused ? 'focused' : ''} ${isToday ? 'is-today' : ''}`}
                          onMouseEnter={() => setHoveredDayIdx(idx)}
                          onMouseLeave={() => setHoveredDayIdx(null)}
                        >
                          <span className="day-name">{isToday ? 'Today' : day.day}</span>
                          <span className={`day-pill ${isPeak ? 'peak' : ''}`}>
                            {day.requests}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Top Active Climbers Leaderboard */}

                <div className="analytics-panel">
                  <div className="panel-header">
                    <div className="panel-title">
                      <Crown size={17} style={{ color: 'var(--recall-warning)' }} />
                      <span>Top Active Climbers</span>
                    </div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--recall-text-muted)', fontWeight: 600 }}>Today</span>
                  </div>

                  <div className="top-users-list">
                    {adminStats?.top_users && adminStats.top_users.length > 0 ? (
                      adminStats.top_users.map((u, i) => (
                        <div key={u.id} className="top-user-row">
                          <div className="top-user-info">
                            <div className="top-user-avatar">#{i + 1}</div>
                            <div className="top-user-names">
                              <span className="top-u-name">{u.name || u.username}</span>
                              <span className="top-u-tenant">@{u.username} • {u.tenant_name}</span>
                            </div>
                          </div>
                          <div className="top-user-count">
                            {u.requests_today} reqs
                          </div>
                        </div>
                      ))
                    ) : (
                      <div style={{ color: 'var(--recall-text-muted)', fontSize: '0.82rem', padding: '24px 0', textAlign: 'center' }}>
                        No activity recorded yet today
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ================================================================ */}
          {/* TAB 2: CLIMBERS & MEMBERS MANAGEMENT                            */}
          {/* ================================================================ */}
          {activeTab === 'users' && (
            <div>
              <div className="admin-view-header">
                <div className="view-title-wrap">
                  <h1>Climbers & Member Roster</h1>
                  <p className="view-subtitle">
                    Manage accounts, configure inference quotas, adjust admin permissions, and batch delete members
                  </p>
                </div>
                <div className="view-actions-wrap">
                  <button
                    className="btn-primary-admin"
                    onClick={() => {
                      setIsAddUserModalOpen(true);
                      setNewUsername('');
                      setNewEmail('');
                      setNewName('');
                      setNewPassword('');
                      setNewRole('user');
                      setNewLimit(50);
                      setNewTenantId(tenantFilter || currentUser?.tenant_id || '');
                    }}
                  >
                    <UserPlus size={15} />
                    <span>Add Member</span>
                  </button>

                  <button
                    className="btn-secondary-admin"
                    onClick={() => fetchAdminData()}
                    disabled={isLoading}
                  >
                    <RotateCw size={14} className={isLoading ? 'spin-slow' : ''} />
                    <span>Refresh</span>
                  </button>
                </div>
              </div>

              <div className="admin-table-card">
                {/* Search Toolbar */}
                <div className="admin-toolbar-row">
                  <div className="admin-search-box">
                    <Search size={15} style={{ color: 'var(--recall-text-muted)' }} />
                    <input
                      type="text"
                      placeholder="Filter by name, username, email, or role..."
                      value={searchQuery}
                      onChange={e => setSearchQuery(e.target.value)}
                    />
                    {searchQuery && (
                      <button onClick={() => setSearchQuery('')} style={{ background: 'transparent', border: 'none', color: 'var(--recall-text-muted)', cursor: 'pointer' }}>
                        <X size={13} />
                      </button>
                    )}
                  </div>
                </div>

                {/* Multi-Institution Filter Bar for Superadmins */}
                {isSuperAdmin && adminTenantsList.length > 0 && (
                  <div className="admin-multi-tenant-bar" style={{ margin: '0 16px 16px 16px' }}>
                    <div className="multi-tenant-label">
                      <Building2 size={13} className="text-teal" />
                      <span>Filter Institutions:</span>
                    </div>
                    <div className="multi-tenant-chips-list">
                      <button
                        type="button"
                        className={`multi-tenant-chip ${selectedInstitutionsFilter.length === 0 ? 'active' : ''}`}
                        onClick={() => setSelectedInstitutionsFilter([])}
                      >
                        All Institutions ({adminTenantsList.length})
                      </button>
                      {adminTenantsList.map(t => {
                        const isSelected = selectedInstitutionsFilter.includes(t.id);
                        return (
                          <button
                            key={t.id}
                            type="button"
                            className={`multi-tenant-chip ${isSelected ? 'active' : ''}`}
                            onClick={() => {
                              setSelectedInstitutionsFilter(prev =>
                                isSelected ? prev.filter(id => id !== t.id) : [...prev, t.id]
                              );
                            }}
                            title={`Click to ${isSelected ? 'remove' : 'include'} ${t.name}`}
                          >
                            <span>{t.name}</span>
                            {isSelected && <Check size={11} className="chip-check-icon" />}
                          </button>
                        );
                      })}
                      {selectedInstitutionsFilter.length > 0 && (
                        <button
                          type="button"
                          className="multi-tenant-clear-btn"
                          onClick={() => setSelectedInstitutionsFilter([])}
                        >
                          Reset
                        </button>
                      )}
                    </div>
                  </div>
                )}

                {/* Bulk Selection Action Banner */}
                {selectedUserIds.size > 0 && (
                  <div className="admin-bulk-banner">
                    <span className="bulk-count-badge">
                      <Check size={16} />
                      <span>{selectedUserIds.size} climber{selectedUserIds.size > 1 ? 's' : ''} selected</span>
                    </span>

                    <div className="bulk-actions-group">
                      <button
                        className="btn-bulk-delete"
                        onClick={handleBulkDeleteUsers}
                        disabled={isBulkDeletingUsers}
                      >
                        <Trash2 size={14} />
                        <span>{isBulkDeletingUsers ? 'Deleting...' : `Delete Selected (${selectedUserIds.size})`}</span>
                      </button>

                      <button
                        className="btn-bulk-clear"
                        onClick={() => setSelectedUserIds(new Set())}
                      >
                        Clear Selection
                      </button>
                    </div>
                  </div>
                )}

                {/* Main Users Table with Horizontal Scroll Support */}
                <div className="admin-table-scroll-wrap">
                  <table className="admin-full-table">
                    <thead>
                      <tr>
                        <th style={{ width: 44, textAlign: 'center' }}>
                          <div
                            className={`admin-custom-checkbox ${
                              filteredUsers.length > 0 &&
                              filteredUsers.filter(u => u.role !== 'superadmin' && u.id !== currentUser?.id).length > 0 &&
                              filteredUsers
                                .filter(u => u.role !== 'superadmin' && u.id !== currentUser?.id)
                                .every(u => selectedUserIds.has(u.id))
                                ? 'checked'
                                : ''
                            }`}
                            onClick={() => {
                              const deletables = filteredUsers.filter(u => u.role !== 'superadmin' && u.id !== currentUser?.id);
                              const allSelected = deletables.length > 0 && deletables.every(u => selectedUserIds.has(u.id));
                              handleToggleSelectAllUsers(!allSelected, filteredUsers);
                            }}
                            title="Select all visible climbers"
                          >
                            {filteredUsers.length > 0 &&
                              filteredUsers.filter(u => u.role !== 'superadmin' && u.id !== currentUser?.id).length > 0 &&
                              filteredUsers
                                .filter(u => u.role !== 'superadmin' && u.id !== currentUser?.id)
                                .every(u => selectedUserIds.has(u.id)) && <Check size={12} />}
                          </div>
                        </th>
                        <th>Climber</th>
                        {isSuperAdmin && !tenantFilter && <th>Enterprise</th>}
                        <th>Email</th>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Daily Limit</th>
                        <th>Usage Today</th>
                        <th style={{ textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredUsers.length === 0 ? (
                        <tr>
                          <td colSpan={9} style={{ textAlign: 'center', padding: '40px 0', color: 'var(--recall-text-muted)' }}>
                            No climbers found matching query.
                          </td>
                        </tr>
                      ) : (
                        filteredUsers.map(u => {
                          const isSelected = selectedUserIds.has(u.id);
                          const isProtected = u.role === 'superadmin' || u.id === currentUser?.id;

                          return (
                            <tr key={u.id} className={`${!u.is_active ? 'user-row-inactive' : ''} ${isSelected ? 'selected' : ''}`}>
                              <td style={{ textAlign: 'center' }}>
                                {!isProtected ? (
                                  <div
                                    className={`admin-custom-checkbox ${isSelected ? 'checked' : ''}`}
                                    onClick={() => handleToggleSelectUser(u.id)}
                                  >
                                    {isSelected && <Check size={12} />}
                                  </div>
                                ) : (
                                  <span style={{ opacity: 0.2 }}>—</span>
                                )}
                              </td>

                              <td>
                                <div className="climber-cell">
                                  <div className="climber-avatar-circle">
                                    {(u.name || u.username).charAt(0).toUpperCase()}
                                  </div>
                                  <div className="climber-names">
                                    <span className="climber-name-text" title={u.name || u.username}>{u.name || u.username}</span>
                                    <span className="climber-username-text">@{u.username}</span>
                                  </div>
                                </div>
                              </td>

                              {isSuperAdmin && !tenantFilter && (
                                <td>
                                  <span className="tenant-table-badge">
                                    <Building2 size={12} />
                                    <span>{u.tenant_name || 'Default'}</span>
                                  </span>
                                </td>
                              )}

                              <td>
                                <span className="user-email-text" title={u.email}>
                                  {u.email}
                                </span>
                              </td>


                            <td>
                              {u.role === 'superadmin' ? (
                                <span className="role-chip-static superadmin">
                                  <Crown size={12} />
                                  <span>SuperAdmin</span>
                                </span>
                              ) : (
                                <button
                                  className={`role-chip-btn ${u.role === 'admin' ? 'admin' : 'user'}`}
                                  onClick={() => handleUpdateRole(u.id, u.role)}
                                  title="Click to toggle role between Admin and Member"
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
                                  >
                                    <Check size={13} />
                                  </button>
                                  <button
                                    className="quota-cancel-btn"
                                    onClick={() => setEditingLimitUserId(null)}
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
                                  title={u.role === 'superadmin' ? 'Unlimited SuperAdmin quota' : 'Click to edit quota'}
                                >
                                  <span>{u.role === 'superadmin' || u.role === 'admin' ? 'Unlimited' : `${u.daily_request_limit} / day`}</span>
                                  {u.role !== 'superadmin' && <Sliders size={11} className="quota-edit-icon" />}
                                </div>
                              )}
                            </td>

                            <td>
                              <span style={{ fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{u.requests_today}</span>
                              <span style={{ fontSize: '0.72rem', color: 'var(--recall-text-muted)', marginLeft: 4 }}>reqs</span>
                            </td>

                            <td style={{ textAlign: 'right' }}>
                              <button
                                className="user-delete-action-btn"
                                onClick={() => handleDeleteSingleUser(u.id, u.username)}
                                disabled={isProtected}
                                title={isProtected ? 'Protected account' : 'Delete user'}
                              >
                                <Trash2 size={14} />
                              </button>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}


          {/* ================================================================ */}
          {/* TAB 3: KNOWLEDGE & DOCUMENT MANAGEMENT                          */}
          {/* ================================================================ */}
          {activeTab === 'documents' && (
            <div>
              <div className="admin-view-header">
                <div className="view-title-wrap">
                  <h1>Knowledge & Document Repository</h1>
                  <p className="view-subtitle">
                    Inspect indexed source files, manage multi-tenant chunk embeddings, toggle enterprise visibility, and batch purge documents
                  </p>
                </div>
                <div className="view-actions-wrap">
                  <button
                    className="btn-secondary-admin"
                    onClick={() => fetchAdminData()}
                    disabled={isLoading}
                  >
                    <RotateCw size={14} className={isLoading ? 'spin-slow' : ''} />
                    <span>Refresh Documents</span>
                  </button>
                </div>
              </div>

              <div className="admin-table-card">
                {/* Search & Toolbar */}
                <div className="admin-toolbar-row">
                  <div className="admin-search-box">
                    <Search size={15} style={{ color: 'var(--recall-text-muted)' }} />
                    <input
                      type="text"
                      placeholder="Search documents by filename, uploader, or enterprise..."
                      value={searchQuery}
                      onChange={e => setSearchQuery(e.target.value)}
                    />
                    {searchQuery && (
                      <button onClick={() => setSearchQuery('')} style={{ background: 'transparent', border: 'none', color: 'var(--recall-text-muted)', cursor: 'pointer' }}>
                        <X size={13} />
                      </button>
                    )}
                  </div>

                  {isSuperAdmin && adminTenantsList.length > 0 && (
                    <select
                      className="admin-tenant-filter-select"
                      value={tenantFilter}
                      onChange={e => {
                        setTenantFilter(e.target.value);
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
                  )}
                </div>

                {/* Bulk Document Deletion Banner */}
                {selectedDocIds.size > 0 && (
                  <div className="admin-bulk-banner">
                    <span className="bulk-count-badge">
                      <Check size={16} />
                      <span>{selectedDocIds.size} document{selectedDocIds.size > 1 ? 's' : ''} selected</span>
                    </span>

                    <div className="bulk-actions-group">
                      <button
                        className="btn-bulk-delete"
                        onClick={handleBulkDeleteDocs}
                        disabled={isBulkDeletingDocs}
                      >
                        <Trash2 size={14} />
                        <span>{isBulkDeletingDocs ? 'Purging...' : `Delete Selected (${selectedDocIds.size})`}</span>
                      </button>

                      <button
                        className="btn-bulk-clear"
                        onClick={() => setSelectedDocIds(new Set())}
                      >
                        Clear Selection
                      </button>
                    </div>
                  </div>
                )}

                {/* Documents Table with Horizontal Scroll Support */}
                <div className="admin-table-scroll-wrap">
                  <table className="admin-full-table">
                    <thead>
                      <tr>
                        <th style={{ width: 44, textAlign: 'center' }}>
                          <div
                            className={`admin-custom-checkbox ${
                              filteredDocs.length > 0 &&
                              filteredDocs.every(d => selectedDocIds.has(d.id))
                                ? 'checked'
                                : ''
                            }`}
                            onClick={() => {
                              const allSelected = filteredDocs.length > 0 && filteredDocs.every(d => selectedDocIds.has(d.id));
                              handleToggleSelectAllDocs(!allSelected, filteredDocs);
                            }}
                            title="Select all visible documents"
                          >
                            {filteredDocs.length > 0 && filteredDocs.every(d => selectedDocIds.has(d.id)) && <Check size={12} />}
                          </div>
                        </th>
                        <th>Document</th>
                        {isSuperAdmin && !tenantFilter && <th>Enterprise</th>}
                        <th>Uploader</th>
                        <th>Chunks</th>
                        <th>Size</th>
                        <th>Visibility</th>
                        <th>Ingested</th>
                        <th style={{ textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredDocs.length === 0 ? (
                        <tr>
                          <td colSpan={9} style={{ textAlign: 'center', padding: '40px 0', color: 'var(--recall-text-muted)' }}>
                            No documents found matching query.
                          </td>
                        </tr>
                      ) : (
                        filteredDocs.map(doc => {
                          const isSelected = selectedDocIds.has(doc.id);
                          const fileSizeFormatted = doc.file_size > 1024 * 1024
                            ? `${(doc.file_size / (1024 * 1024)).toFixed(2)} MB`
                            : `${Math.round(doc.file_size / 1024)} KB`;

                          return (
                            <tr key={doc.id} className={isSelected ? 'selected' : ''}>
                              <td style={{ textAlign: 'center' }}>
                                <div
                                  className={`admin-custom-checkbox ${isSelected ? 'checked' : ''}`}
                                  onClick={() => handleToggleSelectDoc(doc.id)}
                                >
                                  {isSelected && <Check size={12} />}
                                </div>
                              </td>

                              <td>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10, maxWidth: 300 }}>
                                  <div style={{ width: 28, height: 28, borderRadius: 6, background: 'var(--recall-accent-subtle)', color: 'var(--recall-accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                    <FileText size={15} />
                                  </div>
                                  <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
                                    <span className="doc-filename-text" title={doc.filename}>{doc.filename}</span>
                                    <span style={{ fontSize: '0.7rem', color: 'var(--recall-text-muted)' }}>{doc.mime_type}</span>
                                  </div>
                                </div>
                              </td>

                              {isSuperAdmin && !tenantFilter && (
                                <td>
                                  <span className="tenant-table-badge">
                                    <Building2 size={12} />
                                    <span>{doc.tenant_name || 'Default'}</span>
                                  </span>
                                </td>
                              )}

                              <td>
                                <div style={{ display: 'flex', flexDirection: 'column' }}>
                                  <span style={{ fontSize: '0.82rem', color: 'var(--recall-text-primary)' }} title={doc.uploader_name}>{doc.uploader_name}</span>
                                  <span style={{ fontSize: '0.7rem', color: 'var(--recall-text-muted)' }}>@{doc.uploader_username}</span>
                                </div>
                              </td>

                              <td>
                                <span style={{ fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{doc.chunk_count}</span>
                                <span style={{ fontSize: '0.72rem', color: 'var(--recall-text-muted)', marginLeft: 4 }}>chunks</span>
                              </td>

                              <td>
                                <span style={{ fontSize: '0.82rem', fontFamily: 'var(--font-mono)' }}>{fileSizeFormatted}</span>
                              </td>

                              <td>
                                <button
                                  className={`status-chip-btn ${doc.is_shared ? 'active' : 'neutral'}`}
                                  onClick={() => handleToggleDocumentSharing(doc.id, doc.is_shared)}
                                  title="Click to toggle between Enterprise Shared and Climber Private"
                                >
                                  {doc.is_shared ? <Globe size={12} /> : <Lock size={12} />}
                                  <span>{doc.is_shared ? 'Shared' : 'Private'}</span>
                                </button>
                              </td>

                              <td>
                                <span style={{ fontSize: '0.74rem', color: 'var(--recall-text-muted)' }}>
                                  {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : '—'}
                                </span>
                              </td>

                              <td style={{ textAlign: 'right' }}>
                                <button
                                  className="user-delete-action-btn"
                                  onClick={() => handleDeleteSingleDoc(doc.id, doc.filename)}
                                  title="Permanently delete document"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}


          {/* ================================================================ */}
          {/* TAB 4: FEEDBACK & INQUIRIES                                     */}
          {/* ================================================================ */}
          {activeTab === 'feedback' && (
            <div>
              <div className="admin-view-header">
                <div className="view-title-wrap">
                  <h1>Climber Feedback & Inquiry Lifecycle</h1>
                  <p className="view-subtitle">
                    Review accuracy reports, bugs, and feature requests submitted by climbers with resolution tracking
                  </p>
                </div>
                <div className="view-actions-wrap">
                  <button
                    className="btn-secondary-admin"
                    onClick={() => fetchAdminData()}
                    disabled={isLoading}
                  >
                    <RotateCw size={14} className={isLoading ? 'spin-slow' : ''} />
                    <span>Refresh Feed</span>
                  </button>
                </div>
              </div>

              {/* Filter Row */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  {['all', 'open', 'in_review', 'resolved'].map(st => (
                    <button
                      key={st}
                      type="button"
                      className={`admin-subnav-btn ${feedbackStatusFilter === st ? 'active' : ''}`}
                      onClick={() => setFeedbackStatusFilter(st)}
                    >
                      <span>{st.replace('_', ' ').toUpperCase()}</span>
                    </button>
                  ))}

                  <select
                    className="admin-tenant-filter-select"
                    style={{ height: 32, fontSize: '0.78rem' }}
                    value={feedbackCategoryFilter}
                    onChange={e => setFeedbackCategoryFilter(e.target.value)}
                  >
                    <option value="all">All Categories</option>
                    <option value="accuracy">Accuracy / Citation</option>
                    <option value="bug">Bug Report</option>
                    <option value="feature">Feature Request</option>
                    <option value="general">General Inquiry</option>
                  </select>
                </div>

                <div className="admin-search-box" style={{ minWidth: 260 }}>
                  <Search size={15} style={{ color: 'var(--recall-text-muted)' }} />
                  <input
                    type="text"
                    placeholder="Filter feedback content or climber..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                  />
                </div>
              </div>


              {/* Feedback Inquiries Grid */}
              {filteredFeedbacks.length === 0 ? (
                <div className="admin-table-card" style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--recall-text-muted)' }}>
                  <MessageSquare size={32} style={{ opacity: 0.4, margin: '0 auto 12px' }} />
                  <h3 style={{ margin: 0, color: 'var(--recall-text-primary)', fontSize: '1rem' }}>No feedback inquiries found</h3>
                  <p style={{ margin: '6px 0 0', fontSize: '0.82rem' }}>All climber queries and accuracy issues are currently resolved.</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {filteredFeedbacks.map(fb => (
                    <div
                      key={fb.id}
                      style={{
                        background: 'var(--recall-surface)',
                        border: '1px solid var(--recall-border)',
                        borderRadius: 'var(--radius-md, 12px)',
                        padding: 18,
                        boxShadow: 'var(--shadow-sm)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 12,
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div className="climber-avatar-circle" style={{ width: 28, height: 28, fontSize: '0.75rem' }}>
                            {fb.username.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <span style={{ fontWeight: 700, color: 'var(--recall-text-primary)', fontSize: '0.88rem' }}>@{fb.username}</span>
                            <span style={{ fontSize: '0.74rem', color: 'var(--recall-text-muted)', marginLeft: 8 }}>• {fb.tenant_name}</span>
                          </div>
                          <span
                            style={{
                              padding: '2px 8px',
                              borderRadius: 'var(--radius-xs, 6px)',
                              background: 'var(--recall-accent-subtle)',
                              color: 'var(--recall-accent)',
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              textTransform: 'uppercase',
                            }}
                          >
                            {fb.category}
                          </span>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span
                            className={`status-chip-static ${fb.status === 'resolved' ? 'active' : fb.status === 'in_review' ? 'amber' : 'neutral'}`}
                            style={{
                              padding: '3px 10px',
                              borderRadius: 'var(--radius-full, 9999px)',
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              textTransform: 'uppercase',
                            }}
                          >
                            {fb.status === 'resolved' ? '✓ Resolved' : fb.status === 'in_review' ? 'In Review' : 'Open'}
                          </span>

                          <button
                            className="btn-primary-admin"
                            style={{ padding: '4px 12px', fontSize: '0.78rem' }}
                            onClick={() => {
                              setSelectedFeedbackForResolution(fb);
                              setResolutionStatus(fb.status);
                              setResolutionNotes(fb.admin_notes || '');
                            }}
                          >
                            <span>Resolve / Notes</span>
                          </button>

                          <button
                            className="user-delete-action-btn"
                            onClick={() => handleDeleteFeedback(fb.id)}
                            title="Delete feedback item"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>

                      <p style={{ margin: 0, fontSize: '0.88rem', color: 'var(--recall-text-primary)', lineHeight: 1.5, background: 'var(--recall-surface-elevated)', padding: 12, borderRadius: 8, border: '1px solid var(--recall-border)' }}>
                        {fb.message}
                      </p>

                      {fb.admin_notes && (
                        <div
                          style={{
                            background: 'var(--recall-accent-subtle)',
                            borderLeft: '3px solid var(--recall-accent)',
                            padding: '10px 14px',
                            borderRadius: 4,
                            fontSize: '0.82rem',
                            color: 'var(--recall-text-primary)',
                          }}
                        >
                          <strong style={{ display: 'block', color: 'var(--recall-accent)', fontSize: '0.72rem', textTransform: 'uppercase' }}>
                            Admin Resolution Notes {fb.resolved_by ? `(by @${fb.resolved_by})` : ''}:
                          </strong>
                          <span>{fb.admin_notes}</span>
                        </div>
                      )}

                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.72rem', color: 'var(--recall-text-muted)' }}>
                        <Clock size={12} />
                        <span>Submitted {new Date(fb.created_at).toLocaleString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ================================================================ */}
          {/* TAB 5: INSTITUTIONS & MULTI-TENANCY                             */}
          {/* ================================================================ */}
          {activeTab === 'tenants' && isSuperAdmin && (
            <div>
              <div className="admin-view-header">
                <div className="view-title-wrap">
                  <h1>Enterprise Institutions & Tenants</h1>
                  <p className="view-subtitle">
                    Multi-tenant workspace provisioning, pgvector schema boundaries, and member quotas
                  </p>
                </div>
                <div className="view-actions-wrap">
                  {adminTenantsList.filter(t => t.slug !== 'default').length > 0 && (
                    <button
                      className="btn-secondary-admin"
                      onClick={() => {
                        const nonDefault = adminTenantsList.filter(t => t.slug !== 'default').map(t => t.id);
                        setSelectedTenantIds(selectedTenantIds.length === nonDefault.length ? [] : nonDefault);
                      }}
                      title="Select or deselect all institutions"
                    >
                      <Check size={14} />
                      <span>{selectedTenantIds.length > 0 && selectedTenantIds.length === adminTenantsList.filter(t => t.slug !== 'default').length ? 'Deselect All' : 'Select All'}</span>
                    </button>
                  )}

                  <button
                    className="btn-primary-admin"
                    onClick={() => {
                      setIsCreateTenantModalOpen(true);
                      setNewTenantName('');
                      setNewTenantSlug('');
                      setNewTenantMaxUsers(50);
                    }}
                  >
                    <Building2 size={15} />
                    <span>Provision Institution</span>
                  </button>

                  <button
                    className="btn-secondary-admin"
                    onClick={() => fetchAdminData()}
                    disabled={isLoading}
                  >
                    <RotateCw size={14} className={isLoading ? 'spin-slow' : ''} />
                    <span>Refresh</span>
                  </button>
                </div>
              </div>

              {/* Bulk Institutions Action Banner */}
              {selectedTenantIds.length > 0 && (
                <div className="admin-bulk-banner" style={{ marginBottom: 18 }}>
                  <span className="bulk-count-badge">
                    <Check size={16} />
                    <span>{selectedTenantIds.length} institution{selectedTenantIds.length > 1 ? 's' : ''} selected</span>
                  </span>

                  <div className="bulk-actions-group">
                    <button
                      className="btn-bulk-activate"
                      style={{ background: 'var(--recall-accent)', color: '#ffffff', padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', fontWeight: 600 }}
                      onClick={() => handleBulkToggleTenantStatus(selectedTenantIds, true)}
                    >
                      <Check size={13} />
                      <span>Activate ({selectedTenantIds.length})</span>
                    </button>

                    <button
                      className="btn-bulk-suspend"
                      style={{ background: 'var(--recall-surface-elevated)', color: 'var(--recall-text-primary)', border: '1px solid var(--recall-border)', padding: '6px 12px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', fontWeight: 600 }}
                      onClick={() => handleBulkToggleTenantStatus(selectedTenantIds, false)}
                    >
                      <X size={13} />
                      <span>Suspend ({selectedTenantIds.length})</span>
                    </button>

                    <button
                      className="btn-bulk-delete"
                      style={{ background: '#ef4444', color: '#ffffff', padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', fontWeight: 600 }}
                      onClick={() => handleBulkDeleteTenants(selectedTenantIds)}
                      title="Permanently delete selected institutions and all their members"
                    >
                      <Trash2 size={14} />
                      <span>Delete ({selectedTenantIds.length}) & Users</span>
                    </button>

                    <button
                      className="btn-bulk-filter"
                      style={{ background: 'var(--recall-surface-subtle)', color: 'var(--recall-accent)', border: '1px solid var(--recall-border)', padding: '6px 12px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', fontWeight: 600 }}
                      onClick={() => {
                        setSelectedInstitutionsFilter(selectedTenantIds);
                        setActiveTab('users');
                      }}
                    >
                      <Users size={13} />
                      <span>Filter Climbers ({selectedTenantIds.length})</span>
                    </button>

                    <button
                      className="btn-bulk-clear"
                      onClick={() => setSelectedTenantIds([])}
                    >
                      Clear Selection
                    </button>
                  </div>
                </div>
              )}

              {/* Institution Cards Grid */}
              <div className="institutions-grid">
                {adminTenantsList.map(t => {
                  const capacityPercent = Math.min(100, Math.round(((t.user_count || 0) / (t.max_users || 50)) * 100));
                  const isSelected = selectedTenantIds.includes(t.id);
                  const isRoot = t.slug === 'default';

                  const toggleSelection = () => {
                    if (isRoot) return;
                    setSelectedTenantIds(prev =>
                      prev.includes(t.id) ? prev.filter(id => id !== t.id) : [...prev, t.id]
                    );
                  };

                  return (
                    <div 
                      key={t.id} 
                      className={`institution-card ${isSelected ? 'institution-card-selected' : ''}`}
                      onClick={toggleSelection}
                      style={{ cursor: isRoot ? 'default' : 'pointer' }}
                    >
                      <div>
                        <div className="inst-card-top">
                          <div>
                            <div className="inst-card-title">{t.name}</div>
                            <span className="inst-slug-pill">@{t.slug}</span>
                          </div>
                          {isRoot ? (
                            <span className="tenant-default-badge" style={{ padding: '2px 6px', background: 'var(--recall-warning-subtle)', borderRadius: 4 }}>
                              System Root
                            </span>
                          ) : (
                            <div 
                              className={`inst-select-box ${isSelected ? 'selected' : ''}`}
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleSelection();
                              }}
                              title={isSelected ? `Deselect ${t.name}` : `Select ${t.name}`}
                              style={{
                                width: 22,
                                height: 22,
                                borderRadius: 6,
                                border: isSelected ? '2px solid var(--recall-accent)' : '2px solid var(--recall-border-strong)',
                                background: isSelected ? 'var(--recall-accent)' : 'var(--recall-surface-elevated)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                cursor: 'pointer',
                                color: '#ffffff',
                                transition: 'all 0.15s ease',
                                flexShrink: 0
                              }}
                            >
                              {isSelected && <Check size={14} strokeWidth={3} />}
                            </div>
                          )}
                        </div>

                        <div className="inst-card-metrics">
                          <div className="inst-metric-stat">
                            <span>Climbers</span>
                            <strong>{t.user_count || 0} / {t.max_users || 50}</strong>
                          </div>
                          <div className="inst-metric-stat">
                            <span>Documents</span>
                            <strong>{t.doc_count || 0} docs</strong>
                          </div>
                        </div>

                        {/* Capacity Progress Bar */}
                        <div style={{ marginTop: 10 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--recall-text-muted)', marginBottom: 4 }}>
                            <span>Capacity</span>
                            <span>{capacityPercent}%</span>
                          </div>
                          <div style={{ height: 6, background: 'var(--recall-surface-elevated)', borderRadius: 3, overflow: 'hidden', border: '1px solid var(--recall-border)' }}>
                            <div style={{ width: `${capacityPercent}%`, height: '100%', background: 'var(--recall-accent)' }} />
                          </div>
                        </div>
                      </div>

                      <div className="inst-card-footer" onClick={(e) => e.stopPropagation()}>
                        {isRoot ? (
                          <span style={{ fontSize: '0.75rem', color: 'var(--recall-success)', fontWeight: 600 }}>Active</span>
                        ) : (
                          <button
                            className={`status-chip-btn ${t.is_active !== false ? 'active' : 'suspended'}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleToggleTenantStatus(t.id, t.is_active !== false);
                            }}
                          >
                            {t.is_active !== false ? <Check size={12} /> : <X size={12} />}
                            <span>{t.is_active !== false ? 'Active' : 'Suspended'}</span>
                          </button>
                        )}

                        <div style={{ display: 'flex', gap: 6 }}>
                          <button
                            className="btn-ghost-sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedInstitutionsFilter([t.id]);
                              setActiveTab('users');
                              fetchAdminData(t.id);
                            }}
                          >
                            <Users size={13} />
                            <span>View Climbers</span>
                          </button>

                          {!isRoot && (
                            <button
                              className="user-delete-action-btn"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteTenant(t.id, t.name);
                              }}
                              title="Delete institution"
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ================================================================ */}
          {/* TAB 6: CRAG ENGINE & ARCHITECTURE                               */}
          {/* ================================================================ */}
          {activeTab === 'pipeline' && (
            <div className="crag-pipeline-container">
              <div className="admin-view-header">
                <div className="view-title-wrap">
                  <h1>Corrective RAG Pipeline Architecture</h1>
                  <p className="view-subtitle">
                    Stateful multi-node LangGraph execution graph with dynamic web fallback and neural hallucination suppression
                  </p>
                </div>
                <div className="pipeline-status-badge">
                  <div className="status-indicator-dot online" />
                  <span>LangGraph Engine Active</span>
                </div>
              </div>

              {/* Pipeline Telemetry KPI Bar */}
              <div className="admin-kpi-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', marginBottom: '24px' }}>
                <div className="admin-kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-title">Vector Precision</span>
                    <div className="kpi-icon-wrap blue"><Database size={16} /></div>
                  </div>
                  <div className="kpi-value" style={{ color: 'var(--recall-accent)' }}>99.85%</div>
                  <span className="kpi-sub">HNSW Partitioned by Tenant</span>
                </div>

                <div className="admin-kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-title">Reranking Latency</span>
                    <div className="kpi-icon-wrap green"><Cpu size={16} /></div>
                  </div>
                  <div className="kpi-value">~64 ms</div>
                  <span className="kpi-sub">MS-MARCO Cross-Encoder</span>
                </div>

                <div className="admin-kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-title">Web Search Fallback</span>
                    <div className="kpi-icon-wrap yellow"><Globe size={16} /></div>
                  </div>
                  <div className="kpi-value" style={{ color: 'var(--recall-warning)' }}>4.2%</div>
                  <span className="kpi-sub">Autonomous confidence trigger</span>
                </div>

                <div className="admin-kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-title">Hallucination Guard</span>
                    <div className="kpi-icon-wrap purple"><ShieldCheck size={16} /></div>
                  </div>
                  <div className="kpi-value">99.6%</div>
                  <span className="kpi-sub">NLI Claim-Level Verification</span>
                </div>
              </div>

              {/* Interactive Pipeline Graph Flow */}
              <div className="pipeline-flow-card">
                <div className="pipeline-card-header">
                  <div className="pipeline-card-title">
                    <Workflow size={18} style={{ color: 'var(--recall-accent)' }} />
                    <span>Multi-Node LangGraph Execution Flow</span>
                  </div>
                  <span className="pipeline-hint">Click any node to inspect execution details</span>
                </div>

                <div className="pipeline-graph-steps">
                  {/* Node 1: Vector Retrieval */}
                  <div
                    className={`pipeline-node-box ${selectedPipelineNode === 'retriever' ? 'active-node' : ''}`}
                    onClick={() => setSelectedPipelineNode('retriever')}
                  >
                    <div className="node-step-tag">Step 01</div>
                    <div className="node-icon-bubble blue">
                      <Database size={20} />
                    </div>
                    <div className="node-title">Vector Retrieval</div>
                    <div className="node-tech">pgvector (HNSW)</div>
                    <div className="node-badge-sub">Tenant Isolated</div>
                  </div>

                  <div className="pipeline-flow-arrow">
                    <ArrowRight size={18} />
                  </div>

                  {/* Node 2: Cross-Encoder Reranker */}
                  <div
                    className={`pipeline-node-box ${selectedPipelineNode === 'reranker' ? 'active-node' : ''}`}
                    onClick={() => setSelectedPipelineNode('reranker')}
                  >
                    <div className="node-step-tag">Step 02</div>
                    <div className="node-icon-bubble green">
                      <Cpu size={20} />
                    </div>
                    <div className="node-title">Neural Reranker</div>
                    <div className="node-tech">MS-MARCO MiniLM</div>
                    <div className="node-badge-sub">Threshold &gt; 0.40</div>
                  </div>

                  <div className="pipeline-flow-arrow">
                    <ArrowRight size={18} />
                  </div>

                  {/* Node 3: Self-Correction Router */}
                  <div
                    className={`pipeline-node-box ${selectedPipelineNode === 'router' ? 'active-node' : ''}`}
                    onClick={() => setSelectedPipelineNode('router')}
                  >
                    <div className="node-step-tag">Step 03</div>
                    <div className="node-icon-bubble yellow">
                      <GitBranch size={20} />
                    </div>
                    <div className="node-title">Correction Router</div>
                    <div className="node-tech">Dynamic Decision</div>
                    <div className="node-badge-sub">Web Search &lt; 0.15</div>
                  </div>

                  <div className="pipeline-flow-arrow">
                    <ArrowRight size={18} />
                  </div>

                  {/* Node 4: Synthesis */}
                  <div
                    className={`pipeline-node-box ${selectedPipelineNode === 'generator' ? 'active-node' : ''}`}
                    onClick={() => setSelectedPipelineNode('generator')}
                  >
                    <div className="node-step-tag">Step 04</div>
                    <div className="node-icon-bubble orange">
                      <Sparkles size={20} />
                    </div>
                    <div className="node-title">Synthesis Engine</div>
                    <div className="node-tech">Contextual Assembly</div>
                    <div className="node-badge-sub">Multi-Chunk Fused</div>
                  </div>

                  <div className="pipeline-flow-arrow">
                    <ArrowRight size={18} />
                  </div>

                  {/* Node 5: Citation Guard */}
                  <div
                    className={`pipeline-node-box ${selectedPipelineNode === 'guard' ? 'active-node' : ''}`}
                    onClick={() => setSelectedPipelineNode('guard')}
                  >
                    <div className="node-step-tag">Step 05</div>
                    <div className="node-icon-bubble purple">
                      <ShieldCheck size={20} />
                    </div>
                    <div className="node-title">Citation Guard</div>
                    <div className="node-tech">SentenceTransformers</div>
                    <div className="node-badge-sub">NLI Verified</div>
                  </div>
                </div>

                {/* Node Technical Detail Inspector */}
                <div className="pipeline-node-inspector">
                  {selectedPipelineNode === 'retriever' && (
                    <div className="inspector-content">
                      <div className="inspector-header">
                        <div className="inspector-title">
                          <Database size={18} style={{ color: 'var(--recall-accent)' }} />
                          <span>Node 01: PostgreSQL + pgvector Hybrid Retrieval Layer</span>
                        </div>
                        <span className="inspector-pill blue">HNSW Indexing Active</span>
                      </div>
                      <p className="inspector-desc">
                        Queries undergo hybrid dense vector retrieval against embedded document chunks. Multi-tenant isolation is strictly enforced at the database query partition level: <code>WHERE tenant_id = :tenant_id</code>.
                      </p>
                      <div className="inspector-specs-grid">
                        <div className="spec-card">
                          <span className="spec-label">Distance Metric</span>
                          <strong className="spec-val">Cosine Distance (&lt; 0.28 cutoff)</strong>
                        </div>
                        <div className="spec-card">
                          <span className="spec-label">Embedding Dimensions</span>
                          <strong className="spec-val">768-d (all-mpnet-base-v2)</strong>
                        </div>
                        <div className="spec-card">
                          <span className="spec-label">Chunk Overlap</span>
                          <strong className="spec-val">512 tokens / 64 token stride</strong>
                        </div>
                        <div className="spec-card">
                          <span className="spec-label">Average Latency</span>
                          <strong className="spec-val">~28 ms</strong>
                        </div>
                      </div>
                    </div>
                  )}

                  {selectedPipelineNode === 'reranker' && (
                    <div className="inspector-content">
                      <div className="inspector-header">
                        <div className="inspector-title">
                          <Cpu size={18} style={{ color: '#10B981' }} />
                          <span>Node 02: Neural Cross-Encoder Contextual Reranking</span>
                        </div>
                        <span className="inspector-pill green">BGE / MS-MARCO Reranker</span>
                      </div>
                      <p className="inspector-desc">
                        Re-ranks initial candidate chunks using full joint cross-attention over <code>[Query, Chunk]</code> pairs, filtering out semantic noise and calculating hard confidence scores for self-correction.
                      </p>
                      <div className="inspector-specs-grid">
                        <div className="spec-card">
                          <span className="spec-label">Relevance Threshold</span>
                          <strong className="spec-val">&gt; 0.40 (Verified Relevant)</strong>
                        </div>
                        <div className="spec-card">
                          <span className="spec-label">Ambiguity Zone</span>
                          <strong className="spec-val">0.15 - 0.40 (Re-evaluate)</strong>
                        </div>
                        <div className="spec-card">
                          <span className="spec-label">Top-K Selection</span>
                          <strong className="spec-val">Top 4 highest ranked chunks</strong>
                        </div>
                        <div className="spec-card">
                          <span className="spec-label">Inference Model</span>
                          <strong className="spec-val">cross-encoder/ms-marco-MiniLM-L-6-v2</strong>
                        </div>
                      </div>
                    </div>
                  )}

                  {selectedPipelineNode === 'router' && (
                    <div className="inspector-content">
                      <div className="inspector-header">
                        <div className="inspector-title">
                          <GitBranch size={18} style={{ color: '#F59E0B' }} />
                          <span>Node 03: Autonomous Self-Correction & Dynamic Web Fallback</span>
                        </div>
                        <span className="inspector-pill yellow">Adaptive Decision Node</span>
                      </div>
                      <p className="inspector-desc">
                        Evaluates knowledge sufficiency. When internal corpus confidence falls below <code>0.15</code>, the graph automatically triggers a dynamic Tavily Web Search, reformulates the inquiry, scrapes live sources, and incorporates fresh context.
                      </p>
                      <div className="inspector-specs-grid">
                        <div className="spec-card">
                          <span className="spec-label">Fallback Trigger</span>
                          <strong className="spec-val">Max Chunk Score &lt; 0.15</strong>
                        </div>
                        <div className="spec-card">
                          <span className="spec-label">Search Provider</span>
                          <strong className="spec-val">Tavily Search API</strong>
                        </div>
                        <div className="spec-card">
                          <span className="spec-label">Query Rewriting</span>
                          <strong className="spec-val">Hypothetical Document Embeddings (HyDE)</strong>
                        </div>
                        <div className="spec-card">
                          <span className="spec-label">Web Citation Strategy</span>
                          <strong className="spec-val">Inline Domain Anchor Tags</strong>
                        </div>
                      </div>
                    </div>
                  )}

                  {selectedPipelineNode === 'generator' && (
                    <div className="inspector-content">
                      <div className="inspector-header">
                        <div className="inspector-title">
                          <Sparkles size={18} style={{ color: '#F97316' }} />
                          <span>Node 04: Structured Multi-Chunk Context Synthesis</span>
                        </div>
                        <span className="inspector-pill orange">Grounding Prompt Engine</span>
                      </div>
                      <p className="inspector-desc">
                        Assembles the verified context envelope with strict citation provenance metadata. Passes structured reasoning instructions to the model to guarantee answers remain strictly tethered to retrieved knowledge.
                      </p>
                      <div className="inspector-specs-grid">
                        <div className="spec-card">
                          <span className="spec-label">Prompt Structure</span>
                          <strong className="spec-val">Strict Grounded Context Envelope</strong>
                        </div>
                        <div className="spec-card">
                          <span className="spec-label">Provenance Tracking</span>
                          <strong className="spec-val">Source filename + Chunk Index</strong>
                        </div>
                        <div className="spec-card">
                          <span className="spec-label">Streaming Mode</span>
                          <strong className="spec-val">Server-Sent Events (SSE) Enabled</strong>
                        </div>
                        <div className="spec-card">
                          <span className="spec-label">Context Budget</span>
                          <strong className="spec-val">Max 4,096 tokens</strong>
                        </div>
                      </div>
                    </div>
                  )}

                  {selectedPipelineNode === 'guard' && (
                    <div className="inspector-content">
                      <div className="inspector-header">
                        <div className="inspector-title">
                          <ShieldCheck size={18} style={{ color: '#A855F7' }} />
                          <span>Node 05: Sentence-Transformers NLI Hallucination Verification</span>
                        </div>
                        <span className="inspector-pill purple">Zero-Hallucination Guard</span>
                      </div>
                      <p className="inspector-desc">
                        Runs claim-level Natural Language Inference (NLI) cross-entropy validation between generated claims and the source chunks. Any ungrounded or contradictory assertions are suppressed before delivering the final response.
                      </p>
                      <div className="inspector-specs-grid">
                        <div className="spec-card">
                          <span className="spec-label">Entailment Confidence</span>
                          <strong className="spec-val">&gt; 0.85 Entailment Score</strong>
                        </div>
                        <div className="spec-card">
                          <span className="spec-label">Verification Engine</span>
                          <strong className="spec-val">Sentence-Transformers NLI</strong>
                        </div>
                        <div className="spec-card">
                          <span className="spec-label">Contradiction Action</span>
                          <strong className="spec-val">Automatic Suppress &amp; Refine</strong>
                        </div>
                        <div className="spec-card">
                          <span className="spec-label">Citation Enforcement</span>
                          <strong className="spec-val">100% Inline Verified Citations</strong>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

        </main>
      </div>

      {/* ==================================================================== */}
      {/* 3. MODALS (Resolve Feedback, Add User, Provision Tenant, Confirm)    */}
      {/* ==================================================================== */}

      {/* Feedback Resolution Modal Dialog */}
      {selectedFeedbackForResolution && (
        <div className="recall-modal-backdrop add-user-backdrop" onClick={() => setSelectedFeedbackForResolution(null)}>
          <div className="recall-modal-card add-user-card" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-wrap">
                <div className="admin-summit-badge">
                  <CheckCircle2 size={18} />
                </div>
                <div>
                  <h3>Update Inquiry Resolution</h3>
                  <p className="modal-subtitle-text">Inquiry by @{selectedFeedbackForResolution.username}</p>
                </div>
              </div>
              <button className="modal-close-btn" onClick={() => setSelectedFeedbackForResolution(null)} aria-label="Close">
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveFeedbackResolution} className="add-user-modal-body">
              <div style={{ background: 'var(--recall-surface-elevated)', padding: 12, borderRadius: 8, border: '1px solid var(--recall-border)', fontSize: '0.84rem' }}>
                <strong style={{ display: 'block', fontSize: '0.72rem', color: 'var(--recall-text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>
                  Climber Message:
                </strong>
                <span>{selectedFeedbackForResolution.message}</span>
              </div>

              <div className="auth-input-group">
                <label>Resolution Status</label>
                <div className="auth-select-wrap">
                  <select
                    className="auth-tenant-select"
                    value={resolutionStatus}
                    onChange={e => setResolutionStatus(e.target.value as any)}
                  >
                    <option value="open">Open</option>
                    <option value="in_review">In Review (Investigating)</option>
                    <option value="resolved">Resolved (Complete)</option>
                  </select>
                </div>
              </div>

              <div className="auth-input-group">
                <label>Admin Explanation / Resolution Notes (Visible to Climber)</label>
                <textarea
                  value={resolutionNotes}
                  onChange={e => setResolutionNotes(e.target.value)}
                  placeholder="Explain the resolution, document update, or action taken..."
                  rows={4}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: 'var(--radius-sm, 8px)',
                    background: 'var(--recall-surface)',
                    border: '1px solid var(--recall-border)',
                    color: 'var(--recall-text-primary)',
                    fontSize: '0.86rem',
                    fontFamily: 'inherit',
                  }}
                />
              </div>

              <div className="add-user-footer-actions">
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => setSelectedFeedbackForResolution(null)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="recall-btn-primary"
                  disabled={isUpdatingFeedback}
                >
                  {isUpdatingFeedback ? (
                    <>
                      <RotateCw size={15} className="spin-slow" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <Check size={15} />
                      <span>Save Resolution</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Custom Confirm Dialog Modal */}
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
                    <span>Delete Permanently</span>
                  </>
                ) : (
                  <span>Confirm</span>
                )}
              </button>
            </div>
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
                  <p className="modal-subtitle-text">Create a new member account in your organization</p>
                </div>
              </div>
              <button className="modal-close-btn" onClick={() => setIsAddUserModalOpen(false)} aria-label="Close">
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="add-user-modal-body">
              {isSuperAdmin && adminTenantsList.length > 0 && (
                <div className="auth-input-group">
                  <label>Assign to Enterprise</label>
                  <div className="auth-select-wrap">
                    <Building2 size={16} className="input-field-icon" />
                    <select
                      className="auth-tenant-select"
                      value={newTenantId || currentUser?.tenant_id}
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

                <div className="auth-input-group">
                  <label>Username</label>
                  <div className="auth-input-field-wrap">
                    <User size={16} className="input-field-icon" />
                    <input
                      type="text"
                      placeholder="alex_mercer"
                      value={newUsername}
                      onChange={e => setNewUsername(e.target.value)}
                      required
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
                <label>Temporary Password</label>
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
                  <label>Role</label>
                  <div className="auth-select-wrap">
                    <select
                      className="auth-tenant-select"
                      value={newRole}
                      onChange={e => setNewRole(e.target.value as any)}
                    >
                      <option value="user">Climber (Member)</option>
                      <option value="admin">Enterprise Admin</option>
                    </select>
                  </div>
                </div>

                <div className="auth-input-group">
                  <label>Daily Query Quota</label>
                  <div className="auth-input-field-wrap">
                    <input
                      type="number"
                      min={1}
                      max={1000000}
                      value={newLimit}
                      onChange={e => setNewLimit(Math.max(1, parseInt(e.target.value) || 50))}
                      disabled={newRole === 'admin'}
                      required
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
                      <span>Creating...</span>
                    </>
                  ) : (
                    <>
                      <UserPlus size={15} />
                      <span>Create Climber</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create New Institution Modal Dialog */}
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
                  <p className="modal-subtitle-text">Create an isolated workspace with dedicated knowledge boundaries</p>
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
    </div>
  );
};

export default AdminDashboard;
