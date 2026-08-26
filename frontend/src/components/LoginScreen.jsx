import React, { useState } from 'react';
import { Zap, ShieldCheck, User, Lock, ArrowRight, Loader2, AlertCircle, KeyRound, Sparkles } from 'lucide-react';

export default function LoginScreen({ onLogin, loading, authError }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return;
    onLogin(username, password);
  };

  const handleQuickLogin = (user, pass) => {
    setUsername(user);
    setPassword(pass);
    onLogin(user, pass);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6 relative overflow-hidden font-sans antialiased">
      {/* Dynamic Background Glow Elements */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-blue-600/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-96 h-96 bg-purple-600/10 rounded-full blur-[120px] pointer-events-none" />

      <div className="w-full max-w-md space-y-8 relative z-10">
        {/* Brand Header */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-2xl shadow-xl shadow-blue-600/30 border border-blue-400/30 mb-2">
            <Zap className="w-8 h-8 text-white fill-current" />
          </div>
          <div>
            <h1 className="text-3xl font-black tracking-tight text-white">HADIL</h1>
            <p className="text-xs font-bold uppercase tracking-widest text-blue-400 mt-1">
              Database Intelligence Workspace
            </p>
          </div>
          <p className="text-xs text-slate-400 font-medium">
            Sign in to access your database-scoped analytics & AI grounding.
          </p>
        </div>

        {/* Login Form Card */}
        <div className="bg-[#131A2B] border border-[#1F2A44] rounded-3xl p-8 shadow-2xl space-y-6">
          {authError && (
            <div className="p-4 rounded-2xl bg-rose-950/60 border border-rose-800/80 text-rose-200 text-xs font-medium flex items-start gap-3 animate-in fade-in duration-200">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{authError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <label className="text-xs font-extrabold uppercase tracking-wider text-slate-300 block">
                Username
              </label>
              <div className="relative flex items-center">
                <div className="absolute left-3.5 text-slate-400">
                  <User className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter your username"
                  required
                  className="w-full bg-[#0F1626] border border-[#1F2A44] rounded-xl pl-10 pr-4 py-3 text-xs text-slate-100 font-medium placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-extrabold uppercase tracking-wider text-slate-300 block">
                Password
              </label>
              <div className="relative flex items-center">
                <div className="absolute left-3.5 text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  className="w-full bg-[#0F1626] border border-[#1F2A44] rounded-xl pl-10 pr-4 py-3 text-xs text-slate-100 font-medium placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-extrabold text-xs rounded-xl shadow-lg shadow-blue-900/40 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 active:scale-[0.99]"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        </div>

        {/* Demo Accounts Quick Login Selector */}
        <div className="bg-[#0F1626] border border-[#1F2A44] rounded-2xl p-5 space-y-3">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-300">
            <KeyRound className="w-4 h-4 text-blue-400" />
            <span>Quick Database-Scoped Admin Logins:</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => handleQuickLogin('admin', 'password123')}
              className="p-2.5 rounded-xl bg-[#131A2B] hover:bg-[#1A2340] border border-[#1F2A44] text-left transition-all cursor-pointer group"
            >
              <div className="text-[11px] font-bold text-white group-hover:text-purple-400">Master Super Admin</div>
              <div className="text-[10px] text-purple-400 font-mono">admin / password123</div>
            </button>

            <button
              type="button"
              onClick={() => handleQuickLogin('admin_sales', 'password123')}
              className="p-2.5 rounded-xl bg-[#131A2B] hover:bg-[#1A2340] border border-[#1F2A44] text-left transition-all cursor-pointer group"
            >
              <div className="text-[11px] font-bold text-white group-hover:text-blue-400">Sales DB Admin</div>
              <div className="text-[10px] text-blue-400 font-mono">admin_sales / password123</div>
            </button>

            <button
              type="button"
              onClick={() => handleQuickLogin('admin_chinook', 'password123')}
              className="p-2.5 rounded-xl bg-[#131A2B] hover:bg-[#1A2340] border border-[#1F2A44] text-left transition-all cursor-pointer group"
            >
              <div className="text-[11px] font-bold text-white group-hover:text-emerald-400">Chinook DB Admin</div>
              <div className="text-[10px] text-emerald-400 font-mono">admin_chinook / password123</div>
            </button>

            <button
              type="button"
              onClick={() => handleQuickLogin('admin_db_a', 'password123')}
              className="p-2.5 rounded-xl bg-[#131A2B] hover:bg-[#1A2340] border border-[#1F2A44] text-left transition-all cursor-pointer group"
            >
              <div className="text-[11px] font-bold text-white group-hover:text-amber-400">DB A Admin</div>
              <div className="text-[10px] text-amber-400 font-mono">admin_db_a / password123</div>
            </button>
          </div>
        </div>

        {/* Security Footer */}
        <div className="flex items-center justify-center gap-2 text-[11px] text-slate-500 font-medium">
          <ShieldCheck className="w-4 h-4 text-emerald-500" />
          <span>Server-Enforced JWT Bearer & Scoped RBAC Security</span>
        </div>
      </div>
    </div>
  );
}
