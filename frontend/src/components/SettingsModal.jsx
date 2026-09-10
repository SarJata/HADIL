import React, { useState, useEffect } from 'react';
import { X, Database, Cpu, CheckCircle2, AlertCircle, Loader2, Globe, Key } from 'lucide-react';
import api, { getStoredServerAddress, updateServerAddress, testServerConnection } from '../api';

export default function SettingsModal({ isOpen, onClose, selectedDbId, currentDbName, userRole }) {
  const isAdmin = userRole === 'ADMIN' || userRole === 'MASTER_ADMIN';

  const [genProvider, setGenProvider] = useState('openai');
  const [verProvider, setVerProvider] = useState('openai');

  // API Key States (Stores only new input values when replacing existing key)
  const [genApiKey, setGenApiKey] = useState('');
  const [verApiKey, setVerApiKey] = useState('');
  const [genKeyConfigured, setGenKeyConfigured] = useState(false);
  const [verKeyConfigured, setVerKeyConfigured] = useState(false);

  const [serverAddress, setServerAddress] = useState(getStoredServerAddress());
  const [serverStatus, setServerStatus] = useState('CONNECTED');
  const [testingServer, setTestingServer] = useState(false);
  const [serverTestResult, setServerTestResult] = useState(null);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);


  useEffect(() => {
    if (isOpen) {
      setServerAddress(getStoredServerAddress());
      fetchLLMConfig();
    }
  }, [isOpen]);

  const handleTestServerConnection = async () => {
    setTestingServer(true);
    setServerTestResult(null);
    const res = await testServerConnection(serverAddress);
    setServerTestResult(res);
    setServerStatus(res.success ? 'CONNECTED' : 'UNAVAILABLE');
    setTestingServer(false);
  };

  const handleSaveServerAddress = () => {
    try {
      const normalized = updateServerAddress(serverAddress);
      setServerAddress(normalized);
      setStatusMsg({ type: 'success', text: `HADIL connection updated to ${normalized}` });
      handleTestServerConnection();
    } catch (err) {
      setServerTestResult({ success: false, message: err.message || 'Please enter a valid HADIL address beginning with http:// or https://.' });
      setServerStatus('UNAVAILABLE');
    }
  };

  const fetchLLMConfig = async () => {
    try {
      setLoading(true);
      const res = await api.get('/admin/llm-config');
      const gen = res.data.generator || {};
      const ver = res.data.verifier || {};

      setGenProvider(gen.provider_type || 'openai');
      setVerProvider(ver.provider_type || 'openai');
      setGenKeyConfigured(Boolean(gen.api_key_configured));
      setVerKeyConfigured(Boolean(ver.api_key_configured));
      setGenApiKey('');
      setVerApiKey('');
    } catch (e) {
      if (e.response?.status === 403) {
        setGenProvider('openai');
        setVerProvider('openai');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setStatusMsg(null);
      const payload = {
        generator: {
          provider_type: genProvider,
          api_key: genApiKey.trim() || undefined
        },
        verifier: {
          provider_type: verProvider,
          api_key: verApiKey.trim() || undefined
        }
      };
      await api.post('/admin/llm-config', payload);
      setStatusMsg({ type: 'success', text: 'AI Provider configuration updated successfully.' });
      fetchLLMConfig();
    } catch (e) {
      setStatusMsg({ type: 'error', text: e.response?.data?.detail || 'Failed to save provider configuration.' });
    } finally {
      setSaving(false);
    }
  };


  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#0F1626] border border-[#1F2A44] rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200 text-slate-100">
        {/* Header */}
        <div className="px-6 py-4 bg-[#131A2B] border-b border-[#1F2A44] flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center">
              <Cpu className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-sm font-extrabold text-white">System & AI Settings</h3>
              <p className="text-[11px] text-slate-400 font-medium">Manage HADIL connection & LLM providers</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-white hover:bg-[#1A2340] rounded-lg transition-colors cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body - Owned Scroll Container */}
        <div className="p-6 overflow-y-auto flex-1 space-y-5 text-xs text-slate-300 custom-scrollbar">
          {/* Status Message */}
          {statusMsg && (
            <div className={`p-3 rounded-xl border flex items-center gap-2 ${
              statusMsg.type === 'success' ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300' : 'bg-rose-950/60 border-rose-800 text-rose-300'
            }`}>
              {statusMsg.type === 'success' ? <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" /> : <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />}
              <span className="font-semibold text-xs">{statusMsg.text}</span>
            </div>
          )}

          {/* Active Data Connection Context */}
          <div className="p-4 bg-[#131A2B] border border-[#1F2A44] rounded-xl space-y-2">
            <h4 className="font-extrabold text-slate-200 uppercase tracking-wider text-[10px] flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-emerald-400" /> Active Data Connection
            </h4>
            <div className="grid grid-cols-2 gap-2 text-slate-300 font-medium pt-1">
              <div>
                <span className="text-[11px] text-slate-400">Database Name:</span>
                <p className="font-bold text-white text-xs">{currentDbName || 'Default Sales DB'}</p>
              </div>
              <div>
                <span className="text-[11px] text-slate-400">Active Role Scope:</span>
                <p className="font-bold text-white flex items-center gap-1 mt-0.5">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                    isAdmin ? 'bg-emerald-950 border border-emerald-800 text-emerald-400' : 'bg-slate-800 text-slate-300'
                  }`}>
                    {userRole || 'VIEWER'}
                  </span>
                </p>
              </div>
            </div>
          </div>

          {/* HADIL Connection Configuration Section */}
          <div className="p-4 bg-[#131A2B] border border-[#1F2A44] rounded-xl space-y-3">
            <div className="flex items-center justify-between border-b border-[#1F2A44] pb-2.5">
              <h4 className="font-extrabold text-slate-200 uppercase tracking-wider text-[10px] flex items-center gap-1.5">
                <Globe className="w-3.5 h-3.5 text-emerald-400" /> HADIL Connection
              </h4>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                serverStatus === 'CONNECTED' ? 'bg-emerald-950 border border-emerald-800 text-emerald-400' :
                serverStatus === 'UNAVAILABLE' ? 'bg-rose-950 border border-rose-800 text-rose-400' : 'bg-slate-800 text-slate-300'
              }`}>
                {serverStatus}
              </span>
            </div>

            <div className="space-y-2">
              <label className="block text-[11px] font-bold text-slate-300">
                Connection Address
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={serverAddress}
                  onChange={(e) => setServerAddress(e.target.value)}
                  placeholder="https://hadil.example.com"
                  className="flex-1 px-3 py-2 bg-[#0F1626] border border-[#1F2A44] rounded-lg text-xs font-mono text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                />
                <button
                  type="button"
                  onClick={handleTestServerConnection}
                  disabled={testingServer}
                  className="px-3 py-2 bg-[#1A2340] hover:bg-[#253259] text-slate-200 text-xs font-bold rounded-lg transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1 shrink-0"
                >
                  {testingServer ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                  <span>Test</span>
                </button>
              </div>
              <p className="text-[10px] text-slate-400 font-medium">
                Address must begin with http:// or https://
              </p>

              {serverTestResult && (
                <div className={`p-2.5 rounded-lg border text-[11px] font-medium flex items-center gap-2 ${
                  serverTestResult.success ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300' : 'bg-rose-950/60 border-rose-800 text-rose-300'
                }`}>
                  {serverTestResult.success ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" /> : <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />}
                  <span>{serverTestResult.message}</span>
                </div>
              )}

              <div className="pt-1 flex justify-end">
                <button
                  type="button"
                  onClick={handleSaveServerAddress}
                  className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg transition-colors cursor-pointer"
                >
                  Save Address
                </button>
              </div>
            </div>
          </div>

          {/* AI Provider Selection Card - Strictly SuAdmin (MASTER_ADMIN) Only */}
          {userRole === 'MASTER_ADMIN' && (
            <div className="p-4 bg-[#131A2B] border border-[#1F2A44] rounded-xl space-y-4">
              <div className="flex items-center justify-between border-b border-[#1F2A44] pb-2.5">
                <h4 className="font-extrabold text-slate-200 uppercase tracking-wider text-[10px] flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-purple-400" /> LLM Provider Selection
                </h4>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-purple-950 border border-purple-800 text-purple-300">
                  SuAdmin Configurable
                </span>
              </div>

              {loading ? (
                <div className="py-6 flex items-center justify-center gap-2 text-slate-400 font-medium text-xs">
                  <Loader2 className="w-4 h-4 animate-spin text-emerald-400" /> Loading provider settings...
                </div>
              ) : (
                <div className="space-y-3">
                  {/* GENERATOR PROVIDER */}
                  <div className="p-3 bg-[#0F1626] border border-[#1F2A44] rounded-xl space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="block text-[11px] font-bold text-slate-300">
                        Generator LLM Provider
                      </label>
                      <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                        genKeyConfigured ? 'bg-emerald-950 border-emerald-800 text-emerald-300' : 'bg-amber-950 border-amber-800 text-amber-300'
                      }`}>
                        {genKeyConfigured ? '✓ Key Configured' : 'Key Optional / Missing'}
                      </span>
                    </div>
                    <select
                      value={genProvider}
                      onChange={(e) => setGenProvider(e.target.value)}
                      className="w-full px-3 py-2 bg-[#131A2B] border border-[#1F2A44] rounded-lg text-xs font-semibold text-slate-200 focus:outline-none focus:border-emerald-500"
                    >
                      <option value="sarvam">Sarvam AI (India LLM)</option>
                      <option value="gemini">Google Gemini</option>
                      <option value="openai">OpenAI Cloud</option>
                      <option value="claude">Anthropic Claude</option>
                      <option value="ollama">Ollama / Local (Qwen)</option>
                      <option value="custom">Custom / Self-hosted</option>
                    </select>

                    <div className="pt-1">
                      <div className="relative flex items-center">
                        <Key className="w-3.5 h-3.5 text-slate-500 absolute left-3 pointer-events-none" />
                        <input
                          type="password"
                          placeholder={genKeyConfigured ? "•••••••• (Leave blank to keep existing key)" : "Enter API Key for Generator Provider"}
                          value={genApiKey}
                          onChange={(e) => setGenApiKey(e.target.value)}
                          className="w-full pl-9 pr-3 py-1.5 bg-[#131A2B] border border-[#1F2A44] rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                        />
                      </div>
                    </div>
                  </div>

                  {/* VERIFIER PROVIDER */}
                  <div className="p-3 bg-[#0F1626] border border-[#1F2A44] rounded-xl space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="block text-[11px] font-bold text-slate-300">
                        Verifier LLM Provider
                      </label>
                      <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                        verKeyConfigured ? 'bg-emerald-950 border-emerald-800 text-emerald-300' : 'bg-amber-950 border-amber-800 text-amber-300'
                      }`}>
                        {verKeyConfigured ? '✓ Key Configured' : 'Key Optional / Missing'}
                      </span>
                    </div>
                    <select
                      value={verProvider}
                      onChange={(e) => setVerProvider(e.target.value)}
                      className="w-full px-3 py-2 bg-[#131A2B] border border-[#1F2A44] rounded-lg text-xs font-semibold text-slate-200 focus:outline-none focus:border-emerald-500"
                    >
                      <option value="sarvam">Sarvam AI (India LLM)</option>
                      <option value="gemini">Google Gemini</option>
                      <option value="openai">OpenAI Cloud</option>
                      <option value="claude">Anthropic Claude</option>
                      <option value="ollama">Ollama / Local (Qwen)</option>
                      <option value="custom">Custom / Self-hosted</option>
                    </select>

                    <div className="pt-1">
                      <div className="relative flex items-center">
                        <Key className="w-3.5 h-3.5 text-slate-500 absolute left-3 pointer-events-none" />
                        <input
                          type="password"
                          placeholder={verKeyConfigured ? "•••••••• (Leave blank to keep existing key)" : "Enter API Key for Verifier Provider"}
                          value={verApiKey}
                          onChange={(e) => setVerApiKey(e.target.value)}
                          className="w-full pl-9 pr-3 py-1.5 bg-[#131A2B] border border-[#1F2A44] rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>



        {/* Footer */}
        <div className="px-6 py-3 bg-[#131A2B] border-t border-[#1F2A44] flex items-center justify-between shrink-0">
          <div className="text-[10px] text-slate-400 font-medium">
            Active Role: <span className="font-bold text-emerald-400 uppercase font-mono">{userRole || 'VIEWER'}</span>
          </div>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-4 py-2 bg-[#1A2340] hover:bg-[#253259] text-slate-300 font-bold text-xs rounded-lg transition-colors cursor-pointer">
              Close
            </button>
            {isAdmin && (
              <button
                onClick={handleSave}
                disabled={saving || loading}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Save AI Settings
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
