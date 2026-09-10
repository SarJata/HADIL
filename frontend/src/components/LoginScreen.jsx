import React, { useState } from 'react';
import { ShieldCheck, User, Lock, ArrowRight, Loader2, AlertCircle, KeyRound, Globe, CheckCircle2 } from 'lucide-react';
import { getStoredServerAddress, updateServerAddress, testServerConnection } from '../api';

export default function LoginScreen({ onLogin, loading, authError }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const [serverAddress, setServerAddress] = useState(getStoredServerAddress());
  const [showServerConfig, setShowServerConfig] = useState(false);
  const [testingServer, setTestingServer] = useState(false);
  const [serverTestResult, setServerTestResult] = useState(null);

  const handleTestServer = async () => {
    setTestingServer(true);
    setServerTestResult(null);
    const res = await testServerConnection(serverAddress);
    setServerTestResult(res);
    setTestingServer(false);
  };

  const handleSaveServer = () => {
    try {
      const normalized = updateServerAddress(serverAddress);
      setServerAddress(normalized);
      handleTestServer();
    } catch (err) {
      setServerTestResult({ success: false, message: err.message || 'Please enter a valid HADIL server address beginning with http:// or https://.' });
    }
  };

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
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-emerald-600/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-96 h-96 bg-teal-600/10 rounded-full blur-[120px] pointer-events-none" />

      <div className="w-full max-w-md space-y-8 relative z-10">
        {/* Brand Header */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-transparent mb-2 drop-shadow-[0_4px_12px_rgba(16,185,129,0.4)]">
            <img src="/hadil-logo.png" alt="HADIL Logo" className="w-full h-full object-contain filter brightness-110" />
          </div>
          <div>
            <h1 className="text-3xl font-black tracking-tight text-white">HADIL</h1>
            <p className="text-xs font-bold uppercase tracking-widest text-emerald-400 mt-1">
              Database Intelligence Workspace
            </p>
          </div>
          <p className="text-xs text-slate-400 font-medium">
            Sign in to access your database-scoped analytics & AI grounding.
          </p>
        </div>

        {/* Connect to HADIL Connection Status & Selector */}
        <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-4 text-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-300 font-bold">
              <Globe className="w-4 h-4 text-emerald-400" />
              <span>Connect to HADIL</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950/80 border border-emerald-800 text-emerald-400">
                Ready
              </span>
              <button
                type="button"
                onClick={() => setShowServerConfig(!showServerConfig)}
                className="text-[11px] font-bold text-emerald-400 hover:text-emerald-300 underline cursor-pointer"
              >
                {showServerConfig ? 'Hide' : 'Settings'}
              </button>
            </div>
          </div>

          {showServerConfig && (
            <div className="pt-2 border-t border-[#1F2A44] space-y-3 animate-in fade-in duration-200">
              <label className="text-[11px] font-bold uppercase tracking-wider text-slate-300 block">
                Connection Address
              </label>
              <input
                type="text"
                value={serverAddress}
                onChange={(e) => setServerAddress(e.target.value)}
                placeholder="https://hadil.example.com"
                className="w-full bg-[#0F1626] border border-[#1F2A44] rounded-xl px-3 py-2 text-xs font-mono text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
              />
              <p className="text-[10px] text-slate-400">
                Specify optional remote connection address for HADIL workspace.
              </p>

              {serverTestResult && (
                <div className={`p-2.5 rounded-xl border text-[11px] font-medium flex items-center gap-2 ${
                  serverTestResult.success ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300' : 'bg-rose-950/40 border-rose-800 text-rose-300'
                }`}>
                  {serverTestResult.success ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" /> : <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />}
                  <span>{serverTestResult.message}</span>
                </div>
              )}

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleTestServer}
                  disabled={testingServer}
                  className="flex-1 py-2 bg-[#1A2340] hover:bg-[#253259] text-slate-200 font-bold rounded-xl text-xs transition-colors flex items-center justify-center gap-1 cursor-pointer disabled:opacity-50"
                >
                  {testingServer ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                  <span>Test Connection</span>
                </button>
                <button
                  type="button"
                  onClick={handleSaveServer}
                  className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl text-xs transition-colors cursor-pointer"
                >
                  Connect to HADIL
                </button>
              </div>
            </div>
          )}
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
                  className="w-full bg-[#0F1626] border border-[#1F2A44] rounded-xl pl-10 pr-4 py-3 text-xs text-slate-100 font-medium placeholder-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
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
                  className="w-full bg-[#0F1626] border border-[#1F2A44] rounded-xl pl-10 pr-4 py-3 text-xs text-slate-100 font-medium placeholder-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-extrabold text-xs rounded-xl shadow-lg shadow-emerald-900/40 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 active:scale-[0.99]"
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

        {/* Security Footer */}
        <div className="flex items-center justify-center gap-2 text-[11px] text-slate-500 font-medium">
          <ShieldCheck className="w-4 h-4 text-emerald-500" />
          <span>Server-Enforced JWT Bearer & Scoped RBAC Security</span>
        </div>
      </div>
    </div>
  );
}
