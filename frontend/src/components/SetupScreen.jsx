import React, { useState, useEffect } from 'react';
import { ShieldCheck, User, Lock, ArrowRight, Loader2, AlertCircle, Sparkles } from 'lucide-react';
import api from '../api';

export default function SetupScreen({ onSetupComplete }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [checkingStatus, setCheckingStatus] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    const verifySetupStatus = async () => {
      try {
        const res = await api.get('/setup/status');
        if (isMounted) {
          if (res.data && res.data.setup_required === false) {
            onSetupComplete();
            return;
          }
          setCheckingStatus(false);
        }
      } catch (err) {
        console.error("Failed to verify setup status:", err);
        if (isMounted) {
          setCheckingStatus(false);
        }
      }
    };
    verifySetupStatus();
    return () => { isMounted = false; };
  }, [onSetupComplete]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    const trimmedUser = username.trim();
    if (!trimmedUser) {
      setError('Please enter an administrator username.');
      return;
    }
    if (!password) {
      setError('Please enter an administrator password.');
      return;
    }
    if (password.length < 4) {
      setError('Password should be at least 4 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/setup/admin', {
        username: trimmedUser,
        password: password
      });

      if (response.data && response.data.success) {
        onSetupComplete(trimmedUser);
      } else {
        setError(response.data?.message || 'Failed to complete initial setup.');
      }
    } catch (err) {
      const status = err.response?.status;
      const msg = err.response?.data?.detail || err.message || 'An error occurred during first-time setup.';
      
      if (status === 403 || (typeof msg === 'string' && msg.includes('already been completed'))) {
        onSetupComplete();
        return;
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (checkingStatus) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-white font-sans">
        <div className="flex flex-col items-center space-y-4">
          <Loader2 className="w-10 h-10 text-emerald-500 animate-spin" />
          <p className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Checking HADIL System Provisioning State...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6 relative overflow-hidden font-sans antialiased">
      {/* Dynamic Background Glow Elements */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[650px] h-[650px] bg-emerald-600/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-96 h-96 bg-teal-600/10 rounded-full blur-[120px] pointer-events-none" />

      <div className="w-full max-w-md space-y-8 relative z-10">
        {/* Brand Header */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-gradient-to-tr from-emerald-600 to-teal-600 rounded-2xl shadow-xl shadow-emerald-600/30 border border-emerald-400/30 mb-2">
            <ShieldCheck className="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-black tracking-tight text-white">HADIL Setup</h1>
            <p className="text-xs font-bold uppercase tracking-widest text-emerald-400 mt-1">
              Initial Administrator Configuration
            </p>
          </div>
          <p className="text-xs text-slate-400 font-medium max-w-sm mx-auto">
            Welcome to HADIL. Create the primary Administrator account to complete installation and secure your workspace.
          </p>
        </div>

        {/* Setup Card */}
        <div className="bg-[#131A2B] border border-[#1F2A44] rounded-3xl p-8 shadow-2xl space-y-6">
          <div className="flex items-center justify-center gap-2 py-1.5 px-3 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-[11px] font-semibold w-fit mx-auto">
            <Sparkles className="w-3.5 h-3.5" />
            <span>One-Time System Provisioning</span>
          </div>

          {error && (
            <div className="p-4 rounded-2xl bg-rose-950/60 border border-rose-800/80 text-rose-200 text-xs font-medium flex items-start gap-3 animate-in fade-in duration-200">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <label className="text-xs font-extrabold uppercase tracking-wider text-slate-300 block">
                Admin Username
              </label>
              <div className="relative flex items-center">
                <div className="absolute left-3.5 text-slate-400">
                  <User className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. admin"
                  required
                  className="w-full bg-[#0F1626] border border-[#1F2A44] rounded-xl pl-10 pr-4 py-3 text-xs text-slate-100 font-medium placeholder-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-extrabold uppercase tracking-wider text-slate-300 block">
                Admin Password
              </label>
              <div className="relative flex items-center">
                <div className="absolute left-3.5 text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter a secure password"
                  required
                  className="w-full bg-[#0F1626] border border-[#1F2A44] rounded-xl pl-10 pr-4 py-3 text-xs text-slate-100 font-medium placeholder-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-extrabold uppercase tracking-wider text-slate-300 block">
                Confirm Password
              </label>
              <div className="relative flex items-center">
                <div className="absolute left-3.5 text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter password"
                  required
                  className="w-full bg-[#0F1626] border border-[#1F2A44] rounded-xl pl-10 pr-4 py-3 text-xs text-slate-100 font-medium placeholder-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                />
              </div>
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-extrabold text-xs rounded-xl shadow-lg shadow-emerald-900/40 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 active:scale-[0.99]"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Provisioning Admin Account...</span>
                  </>
                ) : (
                  <>
                    <span>Complete Initial Setup</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Footer info */}
        <div className="text-center text-[11px] text-slate-500 flex items-center justify-center gap-2">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Server-Enforced Role-Based Access Control</span>
        </div>
      </div>
    </div>
  );
}

