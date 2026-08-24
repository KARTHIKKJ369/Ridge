import React, { useState, useEffect } from 'react';
import {
  X,
  Lock,
  ShieldCheck,
  User,
  ArrowRight,
  ArrowLeft,
  UserPlus,
  Mail,
  Key,
  AlertCircle,
  Building2,
  Eye,
  EyeOff,
} from 'lucide-react';


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

interface PublicTenant {
  id: string;
  name: string;
  slug: string;
}

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: UserProfile, token: string) => void;
  onGuestContinue?: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  onGuestContinue,
}) => {
  const [mode, setMode] = useState<'login' | 'register_user' | 'register_institution'>('login');
  
  // Public Tenants List for Join Dropdown
  const [publicTenants, setPublicTenants] = useState<PublicTenant[]>([]);

  // Sign In State
  const [loginIdentifier, setLoginIdentifier] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [showLoginPassword, setShowLoginPassword] = useState(false);

  // Register User State
  const [regTenantSlug, setRegTenantSlug] = useState('default');
  const [regCustomSlug, setRegCustomSlug] = useState('');
  const [isCustomSlug, setIsCustomSlug] = useState(false);
  const [regName, setRegName] = useState('');
  const [regUsername, setRegUsername] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPassword, setRegConfirmPassword] = useState('');
  const [showRegPassword, setShowRegPassword] = useState(false);
  const [showRegConfirmPassword, setShowRegConfirmPassword] = useState(false);

  // Register Institution State
  const [instName, setInstName] = useState('');
  const [instSlug, setInstSlug] = useState('');
  const [instAdminName, setInstAdminName] = useState('');
  const [instAdminUsername, setInstAdminUsername] = useState('');
  const [instAdminEmail, setInstAdminEmail] = useState('');
  const [instAdminPassword, setInstAdminPassword] = useState('');
  const [instAdminConfirmPassword, setInstAdminConfirmPassword] = useState('');
  const [showInstPassword, setShowInstPassword] = useState(false);
  const [showInstConfirmPassword, setShowInstConfirmPassword] = useState(false);
  const [matchedTenant, setMatchedTenant] = useState<PublicTenant | null>(null);


  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Fetch Public Institutions for registration selector
  useEffect(() => {
    if (isOpen) {
      fetch('/api/tenants/public')
        .then(res => res.json())
        .then(data => {
          if (data.tenants && data.tenants.length > 0) {
            setPublicTenants(data.tenants);
            if (!regTenantSlug || regTenantSlug === 'default') {
              setRegTenantSlug(data.tenants[0].slug);
            }
          }
        })
        .catch(() => {
          // Ignore network errors on tenant fetch
        });
    }
  }, [isOpen]);


  if (!isOpen) return null;

  // Auto-generate a unique slug + detect if institution name already exists
  const handleInstNameChange = (val: string) => {
    setInstName(val);
    const base = val
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 28);
    const suffix = Math.random().toString(36).slice(2, 6);
    setInstSlug(base ? `${base}-${suffix}` : suffix);

    // Check for name match in already-registered public tenants
    const trimmed = val.trim().toLowerCase();
    if (trimmed.length >= 3) {
      const found = publicTenants.find(
        t =>
          t.name.toLowerCase() === trimmed ||
          t.name.toLowerCase().includes(trimmed) ||
          trimmed.includes(t.name.toLowerCase())
      );
      setMatchedTenant(found || null);
    } else {
      setMatchedTenant(null);
    }
  };


  // 1. Sign In Form Handler
  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginIdentifier.trim() || !loginPassword.trim()) {
      setErrorMsg('Please enter your username/email and password.');
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username_or_email: loginIdentifier.trim(),
          password: loginPassword,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Login failed. Please check your credentials.');
      }

      onSuccess(data.user, data.token);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to sign in.');
    } finally {
      setIsLoading(false);
    }
  };

  // 2. Register Individual User Handler
  const handleRegisterUserSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const effectiveSlug = isCustomSlug ? regCustomSlug.trim().toLowerCase() : regTenantSlug;

    if (!regUsername.trim() || !regEmail.trim() || !regPassword.trim() || !effectiveSlug) {
      setErrorMsg('Please complete all registration fields.');
      return;
    }

    if (regPassword.length < 6) {
      setErrorMsg('Password must be at least 6 characters long.');
      return;
    }

    if (regPassword !== regConfirmPassword) {
      setErrorMsg('Passwords do not match.');
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);

    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: regUsername.trim(),
          name: regName.trim() || regUsername.trim(),
          email: regEmail.trim(),
          password: regPassword,
          tenant_slug: effectiveSlug,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Registration failed.');
      }

      onSuccess(data.user, data.token);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to create account.');
    } finally {
      setIsLoading(false);
    }
  };

  // 3. Register Institution Handler
  const handleRegisterInstitutionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (
      !instName.trim() ||
      !instSlug.trim() ||
      !instAdminUsername.trim() ||
      !instAdminEmail.trim() ||
      !instAdminPassword.trim()
    ) {
      setErrorMsg('Please complete all institution and administrator fields.');
      return;
    }

    if (instAdminPassword.length < 6) {
      setErrorMsg('Admin password must be at least 6 characters long.');
      return;
    }

    if (instAdminPassword !== instAdminConfirmPassword) {
      setErrorMsg('Passwords do not match.');
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);

    try {
      const res = await fetch('/api/auth/register-institution', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          institution_name: instName.trim(),
          slug: instSlug.trim().toLowerCase(),
          admin_name: instAdminName.trim() || instAdminUsername.trim(),
          admin_username: instAdminUsername.trim(),
          admin_email: instAdminEmail.trim(),
          admin_password: instAdminPassword,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Institution registration failed.');
      }

      onSuccess(data.user, data.token);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to register institution.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="recall-modal-backdrop" onClick={onClose}>
      <div
        className={`recall-modal-card auth-modal-card ${mode !== 'login' ? 'auth-modal-wide' : ''}`}
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="auth-summit-badge">
              {mode === 'register_institution' ? <Building2 size={18} /> : <Lock size={18} />}
            </div>
            <h3>
              {mode === 'login' && 'Ridge Access Gate'}
              {mode === 'register_user' && 'Join Enterprise Institution'}
              {mode === 'register_institution' && 'Register New Institution'}
            </h3>
          </div>
          {onGuestContinue && (
            <button className="modal-close-btn" onClick={onClose} aria-label="Close">
              <X size={18} />
            </button>
          )}
        </div>

        <div className="auth-modal-body">
          {/* Header Branding */}
          <div className={`auth-hero-pitch ${mode !== 'login' ? 'auth-hero-compact' : ''}`}>
            {mode === 'login' && (
              <div className="auth-logo-mountain">
                <svg width="36" height="36" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M16 4L3 26H29L16 4Z" fill="var(--color-5, #0284C7)" opacity="0.95" />
                  <path d="M16 4L20 12L14 15L16 4Z" fill="#F8FAFC" opacity="0.95" />
                  <path d="M16 4L11.5 13L16.5 16L21 26H29L16 4Z" fill="var(--color-5, #0284C7)" opacity="0.6" />
                  <circle cx="16" cy="18" r="2.2" fill="#F8FAFC" />
                </svg>
              </div>
            )}
            <h4>
              {mode === 'login' && 'Sign In to Ridge'}
              {mode === 'register_user' && 'Create Member Account'}
              {mode === 'register_institution' && 'Enterprise Workspace Setup'}
            </h4>
            <p>
              {mode === 'login' && 'Enter your credentials to unlock your verified knowledge ascents.'}
              {mode === 'register_user' && 'Join your institution’s knowledge workspace and private research crags.'}
              {mode === 'register_institution' && 'Provision an isolated enterprise tenant with full admin controls.'}
            </p>
          </div>

          {/* Mode Breadcrumb when in Registration */}
          {mode !== 'login' && (
            <div className="auth-back-nav">
              <button
                type="button"
                className="auth-back-btn"
                onClick={() => {
                  setMode('login');
                  setErrorMsg(null);
                }}
              >
                <ArrowLeft size={14} />
                <span>Back to Sign In</span>
              </button>
            </div>
          )}

          {/* Error Banner */}
          {errorMsg && (
            <div className="auth-error-banner">
              <AlertCircle size={15} className="error-icon" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* ======================================================== */}
          {/* MODE 1: SIGN IN FORM                                     */}
          {/* ======================================================== */}
          {mode === 'login' && (
            <>
              <form onSubmit={handleLoginSubmit} className="auth-form-stack">
                <div className="auth-input-group">
                  <label htmlFor="login-id">Username or Email</label>
                  <div className="auth-input-field-wrap">
                    <User size={16} className="input-field-icon" />
                    <input
                      id="login-id"
                      type="text"
                      placeholder="e.g. admin or climber@ridge.ai"
                      value={loginIdentifier}
                      onChange={e => setLoginIdentifier(e.target.value)}
                      required
                      autoFocus
                    />
                  </div>
                </div>

                <div className="auth-input-group">
                  <label htmlFor="login-pass">Password</label>
                  <div className="auth-input-field-wrap">
                    <Key size={16} className="input-field-icon" />
                    <input
                      id="login-pass"
                      type={showLoginPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={loginPassword}
                      onChange={e => setLoginPassword(e.target.value)}
                      required
                    />
                    <button
                      type="button"
                      className="auth-eye-toggle-btn"
                      onClick={() => setShowLoginPassword(!showLoginPassword)}
                      title={showLoginPassword ? 'Hide password' : 'Show password'}
                      tabIndex={-1}
                    >
                      {showLoginPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>

                <button type="submit" className="auth-submit-btn" disabled={isLoading}>
                  {isLoading ? (
                    <span>Verifying Credentials...</span>
                  ) : (
                    <>
                      <span>Sign In to Ridge</span>
                      <ArrowRight size={16} />
                    </>
                  )}
                </button>
              </form>

              {/* Registration Choices Section */}
              <div className="auth-register-prompt-card">
                <div className="auth-register-prompt-header">
                  <span>Don't have an account?</span>
                </div>
                <div className="auth-register-action-grid">
                  <button
                    type="button"
                    className="auth-choice-card-btn"
                    onClick={() => {
                      setMode('register_institution');
                      setErrorMsg(null);
                    }}
                  >
                    <div className="choice-icon-badge text-teal">
                      <Building2 size={16} />
                    </div>
                    <div className="choice-text">
                      <strong>Register Institution</strong>
                      <span>Create enterprise workspace & become admin</span>
                    </div>
                    <ArrowRight size={14} className="choice-arrow" />
                  </button>

                  <button
                    type="button"
                    className="auth-choice-card-btn"
                    onClick={() => {
                      setMode('register_user');
                      setErrorMsg(null);
                    }}
                  >
                    <div className="choice-icon-badge text-moss">
                      <UserPlus size={16} />
                    </div>
                    <div className="choice-text">
                      <strong>Join Institution</strong>
                      <span>Register as an enterprise climber</span>
                    </div>
                    <ArrowRight size={14} className="choice-arrow" />
                  </button>
                </div>
              </div>
            </>
          )}

          {/* ======================================================== */}
          {/* MODE 2: REGISTER INDIVIDUAL USER                         */}
          {/* ======================================================== */}
          {mode === 'register_user' && (
            <form onSubmit={handleRegisterUserSubmit} className="auth-form-stack">
              <div className="auth-input-group">
                <label>Select Institution / Enterprise</label>
                {!isCustomSlug ? (
                  <div className="auth-select-wrap">
                    <Building2 size={16} className="input-field-icon" />
                    <select
                      className="auth-tenant-select"
                      value={regTenantSlug}
                      onChange={e => {
                        if (e.target.value === '__custom__') {
                          setIsCustomSlug(true);
                        } else {
                          setRegTenantSlug(e.target.value);
                        }
                      }}
                    >
                      {publicTenants.map(t => (
                        <option key={t.id} value={t.slug}>
                          {t.name} (@{t.slug})
                        </option>
                      ))}
                      <option value="__custom__">+ Enter Enterprise Code...</option>
                    </select>
                  </div>
                ) : (
                  <div className="auth-input-field-wrap">
                    <Building2 size={16} className="input-field-icon" />
                    <input
                      type="text"
                      placeholder="e.g. stanford-ai"
                      value={regCustomSlug}
                      onChange={e => setRegCustomSlug(e.target.value)}
                      required
                    />
                    <button
                      type="button"
                      className="auth-inline-switch-btn"
                      onClick={() => setIsCustomSlug(false)}
                      title="Choose from list"
                    >
                      List
                    </button>
                  </div>
                )}
              </div>

              <div className="auth-form-row">
                <div className="auth-input-group">
                  <label htmlFor="reg-name">Full Name (Optional)</label>
                  <div className="auth-input-field-wrap">
                    <User size={16} className="input-field-icon" />
                    <input
                      id="reg-name"
                      type="text"
                      placeholder="e.g. Dr. Alex Mercer"
                      value={regName}
                      onChange={e => setRegName(e.target.value)}
                    />
                  </div>
                </div>

                <div className="auth-input-group">
                  <label htmlFor="reg-user">Username</label>
                  <div className="auth-input-field-wrap">
                    <User size={16} className="input-field-icon" />
                    <input
                      id="reg-user"
                      type="text"
                      placeholder="e.g. alex_mercer"
                      value={regUsername}
                      onChange={e => setRegUsername(e.target.value)}
                      required
                      minLength={3}
                    />
                  </div>
                </div>
              </div>

              <div className="auth-input-group">
                <label htmlFor="reg-email">Email Address</label>
                <div className="auth-input-field-wrap">
                  <Mail size={16} className="input-field-icon" />
                  <input
                    id="reg-email"
                    type="email"
                    placeholder="alex@stanford.edu"
                    value={regEmail}
                    onChange={e => setRegEmail(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="auth-form-row">
                <div className="auth-input-group">
                  <label htmlFor="reg-pass">Password (Min. 6 chars)</label>
                  <div className="auth-input-field-wrap">
                    <Key size={16} className="input-field-icon" />
                    <input
                      id="reg-pass"
                      type={showRegPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={regPassword}
                      onChange={e => setRegPassword(e.target.value)}
                      required
                      minLength={6}
                    />
                    <button
                      type="button"
                      className="auth-eye-toggle-btn"
                      onClick={() => setShowRegPassword(!showRegPassword)}
                      tabIndex={-1}
                    >
                      {showRegPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>

                <div className="auth-input-group">
                  <label htmlFor="reg-confirm">Confirm Password</label>
                  <div className={`auth-input-field-wrap ${regConfirmPassword && regPassword !== regConfirmPassword ? 'input-field-error' : regConfirmPassword && regPassword === regConfirmPassword ? 'input-field-ok' : ''}`}>
                    <Key size={16} className="input-field-icon" />
                    <input
                      id="reg-confirm"
                      type={showRegConfirmPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={regConfirmPassword}
                      onChange={e => setRegConfirmPassword(e.target.value)}
                      required
                    />
                    <button
                      type="button"
                      className="auth-eye-toggle-btn"
                      onClick={() => setShowRegConfirmPassword(!showRegConfirmPassword)}
                      tabIndex={-1}
                    >
                      {showRegConfirmPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                  {regConfirmPassword && regPassword !== regConfirmPassword && (
                    <span className="auth-field-error-msg">Passwords do not match</span>
                  )}
                  {regConfirmPassword && regPassword === regConfirmPassword && (
                    <span className="auth-field-ok-msg">Passwords match ✓</span>
                  )}
                </div>
              </div>

              <button type="submit" className="auth-submit-btn" disabled={isLoading}>
                {isLoading ? (
                  <span>Joining Institution...</span>
                ) : (
                  <>
                    <span>Join Institution & Register</span>
                    <ArrowRight size={16} />
                  </>
                )}
              </button>
            </form>
          )}

          {/* ======================================================== */}
          {/* MODE 3: REGISTER INSTITUTION / ENTERPRISE                */}
          {/* ======================================================== */}
          {mode === 'register_institution' && (
            <form onSubmit={handleRegisterInstitutionSubmit} className="auth-form-stack">
              <div className="auth-form-section-title">
                <Building2 size={15} className="text-teal" />
                <span>Organization Identity</span>
              </div>

              <div className="auth-form-row">
                <div className="auth-input-group">
                  <label htmlFor="inst-name">Institution Name</label>
                  <div className="auth-input-field-wrap">
                    <Building2 size={16} className="input-field-icon" />
                    <input
                      id="inst-name"
                      type="text"
                      placeholder="e.g. Apex BioTech Lab"
                      value={instName}
                      onChange={e => handleInstNameChange(e.target.value)}
                      required
                      autoFocus
                    />
                  </div>
                  {matchedTenant && (
                    <div className="inst-already-exists-hint">
                      <span className="inst-hint-icon">💡</span>
                      <div className="inst-hint-body">
                        <strong>"{matchedTenant.name}"</strong> is already registered.
                        <span className="inst-hint-sub"> You can join as a member instead.</span>
                      </div>
                      <button
                        type="button"
                        className="inst-hint-join-btn"
                        onClick={() => {
                          setMatchedTenant(null);
                          setRegTenantSlug(matchedTenant.slug);
                          setIsCustomSlug(false);
                          setMode('register_user');
                          setErrorMsg(null);
                        }}
                      >
                        Join instead →
                      </button>
                    </div>
                  )}
                </div>


                <div className="auth-input-group">
                  <label htmlFor="inst-slug">Organization Slug / Code</label>
                  <div className="auth-input-field-wrap">
                    <span className="auth-input-prefix">@</span>
                    <input
                      id="inst-slug"
                      type="text"
                      placeholder="apex-biotech"
                      value={instSlug}
                      onChange={e => setInstSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-_]/g, ''))}
                      required
                    />
                  </div>
                </div>
              </div>

              <div className="auth-form-section-title">
                <ShieldCheck size={15} className="text-teal" />
                <span>Primary Administrator Account</span>
              </div>

              <div className="auth-form-row">
                <div className="auth-input-group">
                  <label htmlFor="inst-admin-name">Admin Full Name</label>
                  <div className="auth-input-field-wrap">
                    <User size={16} className="input-field-icon" />
                    <input
                      id="inst-admin-name"
                      type="text"
                      placeholder="e.g. Dr. Jane Doe"
                      value={instAdminName}
                      onChange={e => setInstAdminName(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="auth-input-group">
                  <label htmlFor="inst-admin-user">Admin Username</label>
                  <div className="auth-input-field-wrap">
                    <User size={16} className="input-field-icon" />
                    <input
                      id="inst-admin-user"
                      type="text"
                      placeholder="e.g. janedoe_admin"
                      value={instAdminUsername}
                      onChange={e => setInstAdminUsername(e.target.value)}
                      required
                      minLength={3}
                    />
                  </div>
                </div>
              </div>

              <div className="auth-input-group">
                <label htmlFor="inst-admin-email">Admin Email Address</label>
                <div className="auth-input-field-wrap">
                  <Mail size={16} className="input-field-icon" />
                  <input
                    id="inst-admin-email"
                    type="email"
                    placeholder="jane@apexbiotech.com"
                    value={instAdminEmail}
                    onChange={e => setInstAdminEmail(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="auth-form-row">
                <div className="auth-input-group">
                  <label htmlFor="inst-admin-pass">Admin Password (Min. 6 chars)</label>
                  <div className="auth-input-field-wrap">
                    <Key size={16} className="input-field-icon" />
                    <input
                      id="inst-admin-pass"
                      type={showInstPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={instAdminPassword}
                      onChange={e => setInstAdminPassword(e.target.value)}
                      required
                      minLength={6}
                    />
                    <button
                      type="button"
                      className="auth-eye-toggle-btn"
                      onClick={() => setShowInstPassword(!showInstPassword)}
                      tabIndex={-1}
                    >
                      {showInstPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>

                <div className="auth-input-group">
                  <label htmlFor="inst-admin-confirm">Confirm Password</label>
                  <div className={`auth-input-field-wrap ${instAdminConfirmPassword && instAdminPassword !== instAdminConfirmPassword ? 'input-field-error' : instAdminConfirmPassword && instAdminPassword === instAdminConfirmPassword ? 'input-field-ok' : ''}`}>
                    <Key size={16} className="input-field-icon" />
                    <input
                      id="inst-admin-confirm"
                      type={showInstConfirmPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={instAdminConfirmPassword}
                      onChange={e => setInstAdminConfirmPassword(e.target.value)}
                      required
                    />
                    <button
                      type="button"
                      className="auth-eye-toggle-btn"
                      onClick={() => setShowInstConfirmPassword(!showInstConfirmPassword)}
                      tabIndex={-1}
                    >
                      {showInstConfirmPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                  {instAdminConfirmPassword && instAdminPassword !== instAdminConfirmPassword && (
                    <span className="auth-field-error-msg">Passwords do not match</span>
                  )}
                  {instAdminConfirmPassword && instAdminPassword === instAdminConfirmPassword && (
                    <span className="auth-field-ok-msg">Passwords match ✓</span>
                  )}
                </div>
              </div>

              <button type="submit" className="auth-submit-btn" disabled={isLoading}>
                {isLoading ? (
                  <span>Provisioning Enterprise Workspace...</span>
                ) : (
                  <>
                    <span>Register Institution & Admin</span>
                    <ArrowRight size={16} />
                  </>
                )}
              </button>
            </form>
          )}


          {/* Optional Guest / Demo Access */}
          {onGuestContinue && mode === 'login' && (
            <div className="auth-guest-section">
              <div className="auth-divider">
                <span>or</span>
              </div>
              <button type="button" className="auth-guest-btn" onClick={onGuestContinue}>
                <User size={15} />
                <span>Continue as Guest Climber</span>
                <ArrowRight size={14} />
              </button>
            </div>
          )}

          <div className="auth-security-footer">
            <ShieldCheck size={14} className="security-icon" />
            <span>Multi-Tenant PBKDF2 encryption & isolated pgvector schemas.</span>
          </div>
        </div>
      </div>
    </div>
  );
};
