import React, { useState } from 'react';
import { X, Lock, ShieldCheck, User, ArrowRight, UserPlus, LogIn, Mail, Key, AlertCircle } from 'lucide-react';

interface UserProfile {
  id: string;
  username: string;
  name: string;
  email: string;
  avatar_url?: string;
  provider?: string;
  is_guest?: boolean;
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
  const [tab, setTab] = useState<'login' | 'register'>('login');
  
  // Form fields
  const [loginIdentifier, setLoginIdentifier] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  
  const [regUsername, setRegUsername] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPassword, setRegConfirmPassword] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

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

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!regUsername.trim() || !regEmail.trim() || !regPassword.trim()) {
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
          email: regEmail.trim(),
          password: regPassword,
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

  return (
    <div className="recall-modal-backdrop" onClick={onClose}>
      <div className="recall-modal-card auth-modal-card" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="auth-summit-badge">
              <Lock size={18} />
            </div>
            <h3>Ridge Access Gate</h3>
          </div>
          {onGuestContinue && (
            <button className="modal-close-btn" onClick={onClose} aria-label="Close">
              <X size={18} />
            </button>
          )}
        </div>

        <div className="auth-modal-body">
          {/* Header Branding */}
          <div className="auth-hero-pitch">
            <div className="auth-logo-mountain">
              <svg width="40" height="40" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M16 4L3 26H29L16 4Z" fill="var(--color-5, #0284C7)" opacity="0.95" />
                <path d="M16 4L20 12L14 15L16 4Z" fill="#F8FAFC" opacity="0.95" />
                <path d="M16 4L11.5 13L16.5 16L21 26H29L16 4Z" fill="var(--color-5, #0284C7)" opacity="0.6" />
                <circle cx="16" cy="18" r="2.2" fill="#F8FAFC" />
              </svg>
            </div>
            <h4>{tab === 'login' ? 'Sign In to Ridge' : 'Create Ridge Account'}</h4>
            <p>
              {tab === 'login'
                ? 'Enter your credentials to unlock your verified knowledge ascents.'
                : 'Register a local account to secure your ChromaDB knowledge crag.'}
            </p>
          </div>

          {/* Mode Switcher Tabs */}
          <div className="auth-mode-tabs">
            <button
              type="button"
              className={`auth-tab-btn ${tab === 'login' ? 'active' : ''}`}
              onClick={() => {
                setTab('login');
                setErrorMsg(null);
              }}
            >
              <LogIn size={15} />
              <span>Sign In</span>
            </button>
            <button
              type="button"
              className={`auth-tab-btn ${tab === 'register' ? 'active' : ''}`}
              onClick={() => {
                setTab('register');
                setErrorMsg(null);
              }}
            >
              <UserPlus size={15} />
              <span>Register</span>
            </button>
          </div>

          {/* Error Banner */}
          {errorMsg && (
            <div className="auth-error-banner">
              <AlertCircle size={15} className="error-icon" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Sign In Form */}
          {tab === 'login' && (
            <form onSubmit={handleLoginSubmit} className="auth-form-stack">
              <div className="auth-input-group">
                <label htmlFor="login-id">Username or Email</label>
                <div className="auth-input-field-wrap">
                  <User size={16} className="input-field-icon" />
                  <input
                    id="login-id"
                    type="text"
                    placeholder="e.g. climber or karthik@example.com"
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
                    type="password"
                    placeholder="••••••••"
                    value={loginPassword}
                    onChange={e => setLoginPassword(e.target.value)}
                    required
                  />
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
          )}

          {/* Register Form */}
          {tab === 'register' && (
            <form onSubmit={handleRegisterSubmit} className="auth-form-stack">
              <div className="auth-input-group">
                <label htmlFor="reg-user">Username</label>
                <div className="auth-input-field-wrap">
                  <User size={16} className="input-field-icon" />
                  <input
                    id="reg-user"
                    type="text"
                    placeholder="e.g. summit_climber"
                    value={regUsername}
                    onChange={e => setRegUsername(e.target.value)}
                    required
                    minLength={3}
                    autoFocus
                  />
                </div>
              </div>

              <div className="auth-input-group">
                <label htmlFor="reg-email">Email Address</label>
                <div className="auth-input-field-wrap">
                  <Mail size={16} className="input-field-icon" />
                  <input
                    id="reg-email"
                    type="email"
                    placeholder="name@example.com"
                    value={regEmail}
                    onChange={e => setRegEmail(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="auth-input-group">
                <label htmlFor="reg-pass">Password (Min. 6 chars)</label>
                <div className="auth-input-field-wrap">
                  <Key size={16} className="input-field-icon" />
                  <input
                    id="reg-pass"
                    type="password"
                    placeholder="••••••••"
                    value={regPassword}
                    onChange={e => setRegPassword(e.target.value)}
                    required
                    minLength={6}
                  />
                </div>
              </div>

              <div className="auth-input-group">
                <label htmlFor="reg-confirm">Confirm Password</label>
                <div className="auth-input-field-wrap">
                  <Key size={16} className="input-field-icon" />
                  <input
                    id="reg-confirm"
                    type="password"
                    placeholder="••••••••"
                    value={regConfirmPassword}
                    onChange={e => setRegConfirmPassword(e.target.value)}
                    required
                  />
                </div>
              </div>

              <button type="submit" className="auth-submit-btn" disabled={isLoading}>
                {isLoading ? (
                  <span>Creating Account...</span>
                ) : (
                  <>
                    <span>Create Account & Enter</span>
                    <ArrowRight size={16} />
                  </>
                )}
              </button>
            </form>
          )}

          {/* Optional Guest / Demo Access */}
          {onGuestContinue && (
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
            <span>Salted PBKDF2 hashing & signed JWT encryption.</span>
          </div>
        </div>
      </div>
    </div>
  );
};
