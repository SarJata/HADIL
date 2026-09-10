import React, { useState, useEffect } from 'react';
import { 
  ShieldCheck, FolderPlus, Folder, Trash2, Cpu, CheckCircle2, AlertCircle, 
  Loader2, RefreshCw, Activity, Database, FileText, X
} from 'lucide-react';
import api from '../api';

export default function SuAdminView({ databases = [], activeDbId = '' }) {
  const [activeTab, setActiveTab] = useState('directories');
  
  // Database Directories State
  const [directories, setDirectories] = useState([]);
  const [newDirPath, setNewDirPath] = useState('');
  const [dirLoading, setDirLoading] = useState(false);

  // System Diagnostics State
  const [systemDiagnostics, setSystemDiagnostics] = useState(null);
  const [diagLoading, setDiagLoading] = useState(false);

  // Notifications State
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (activeTab === 'directories') {
      fetchDirectories();
    } else if (activeTab === 'diagnostics') {
      fetchSystemDiagnostics();
    }
  }, [activeTab]);

  const fetchDirectories = async () => {
    setDirLoading(true);
    setError(null);
    try {
      const res = await api.get('/admin/db-directories');
      setDirectories(res.data?.directories || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to fetch DB directories.');
    } fontFinally: {
      setDirLoading(false);
    }
  };

  const handleAddDirectory = async (e) => {
    e.preventDefault();
    if (!newDirPath.trim()) return;

    setDirLoading(true);
    setError(null);
    setSuccess('');
    try {
      const res = await api.post('/admin/db-directories', { path: newDirPath.trim() });
      if (res.data?.success) {
        setSuccess(res.data.message || 'Directory added successfully.');
        setNewDirPath('');
        fetchDirectories();
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to add directory.');
    } finally {
      setDirLoading(false);
    }
  };

  const handleRemoveDirectory = async (pathToRemove) => {
    if (!window.confirm(`Are you sure you want to remove directory '${pathToRemove}' from configuration?`)) return;

    setDirLoading(true);
    setError(null);
    setSuccess('');
    try {
      const res = await api.delete(`/admin/db-directories?path=${encodeURIComponent(pathToRemove)}`);
      if (res.data?.success) {
        setSuccess(res.data.message || 'Directory removed successfully.');
        fetchDirectories();
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to remove directory.');
    } finally {
      setDirLoading(false);
    }
  };

  const fetchSystemDiagnostics = async () => {
    setDiagLoading(true);
    setError(null);
    try {
      const res = await api.get('/admin/system-status');
      setSystemDiagnostics(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to fetch system status diagnostics.');
    } finally {
      setDiagLoading(false);
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-[#1F2A44]">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-6 h-6 text-emerald-400" />
            <h2 className="text-2xl font-black text-white tracking-tight">
              SuAdmin Administrative Control Panel
            </h2>
            <span className="text-[10px] bg-emerald-950 border border-emerald-800 text-emerald-300 font-extrabold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
              SuAdmin
            </span>
          </div>
          <p className="text-xs text-slate-400 font-medium mt-1">
            System administration, database directory discovery, and runtime diagnostics.
          </p>
        </div>

        {/* Section Tabs */}
        <div className="flex items-center gap-2 bg-[#131A2B] border border-[#1F2A44] p-1 rounded-xl">
          <button
            onClick={() => setActiveTab('directories')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-2 ${
              activeTab === 'directories'
                ? 'bg-emerald-600 text-white shadow-md'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Folder className="w-3.5 h-3.5" />
            <span>DB Directories</span>
          </button>

          <button
            onClick={() => setActiveTab('diagnostics')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-2 ${
              activeTab === 'diagnostics'
                ? 'bg-emerald-600 text-white shadow-md'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>System Diagnostics</span>
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-4 rounded-2xl bg-rose-950/60 border border-rose-800/80 text-rose-200 text-xs font-medium flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {success && (
        <div className="p-4 rounded-2xl bg-emerald-950/60 border border-emerald-800/80 text-emerald-200 text-xs font-medium flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{success}</span>
          </div>
          <button onClick={() => setSuccess('')} className="text-emerald-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* TAB 1: DATABASE DIRECTORY DISCOVERY MANAGEMENT */}
      {activeTab === 'directories' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Add Directory Form Card */}
          <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-6 space-y-4 shadow-xl">
            <div className="flex items-center gap-2 pb-2 border-b border-[#1F2A44]">
              <FolderPlus className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-black text-white uppercase tracking-wider">
                Add Database Directory
              </h3>
            </div>
            <form onSubmit={handleAddDirectory} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider block">
                  Absolute Directory Path
                </label>
                <input
                  type="text"
                  value={newDirPath}
                  onChange={(e) => setNewDirPath(e.target.value)}
                  placeholder="e.g. C:\Databases or ./data"
                  required
                  className="w-full bg-[#0F1626] border border-[#1F2A44] rounded-xl px-3.5 py-2.5 text-xs text-slate-100 font-mono placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                />
                <p className="text-[10px] text-slate-400">
                  HADIL automatically scans configured directories for SQLite `.db` / `.sqlite` files.
                </p>
              </div>

              <button
                type="submit"
                disabled={dirLoading || !newDirPath.trim()}
                className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer shadow-md shadow-emerald-900/30 disabled:opacity-50"
              >
                {dirLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FolderPlus className="w-3.5 h-3.5" />}
                <span>Add & Scan Directory</span>
              </button>
            </form>
          </div>

          {/* Configured Directories Table */}
          <div className="lg:col-span-2 space-y-4">
            <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-6 space-y-4 shadow-xl">
              <div className="flex items-center justify-between pb-3 border-b border-[#1F2A44]">
                <div>
                  <h3 className="text-sm font-black text-white uppercase tracking-wider">
                    Configured Auto-Discovery Directories ({directories.length})
                  </h3>
                  <p className="text-[11px] text-slate-400 font-medium mt-0.5">
                    HADIL inspects these filesystem locations to populate available databases.
                  </p>
                </div>
                <button
                  onClick={fetchDirectories}
                  className="p-2 bg-[#0F1626] hover:bg-[#1A2340] border border-[#1F2A44] rounded-xl text-slate-300 hover:text-white transition-colors cursor-pointer"
                  title="Refresh Directories"
                >
                  <RefreshCw className={`w-3.5 h-3.5 text-emerald-400 ${dirLoading ? 'animate-spin' : ''}`} />
                </button>
              </div>

              {dirLoading && directories.length === 0 ? (
                <div className="py-12 text-center text-slate-400 flex flex-col items-center justify-center space-y-2">
                  <Loader2 className="w-6 h-6 animate-spin text-emerald-400" />
                  <span className="text-xs">Loading database directories...</span>
                </div>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-[#1F2A44] bg-[#0F1626]">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-[#131A2B] text-slate-400 border-b border-[#1F2A44] font-extrabold uppercase text-[10px] tracking-wider">
                      <tr>
                        <th className="px-5 py-3">Path</th>
                        <th className="px-5 py-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1F2A44]">
                      {directories.length === 0 ? (
                        <tr>
                          <td colSpan={2} className="px-5 py-6 text-center text-slate-500 italic text-xs">
                            No directory paths configured for auto-discovery.
                          </td>
                        </tr>
                      ) : (
                        directories.map((dir, idx) => (
                          <tr key={idx} className="hover:bg-[#131A2B]/60 transition-colors">
                            <td className="px-5 py-3.5 font-mono text-slate-200 font-semibold flex items-center gap-2">
                              <Folder className="w-4 h-4 text-emerald-400 shrink-0" />
                              <span>{dir}</span>
                            </td>
                            <td className="px-5 py-3.5 text-right">
                              <button
                                onClick={() => handleRemoveDirectory(dir)}
                                className="px-3 py-1 bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800 rounded-lg text-[11px] font-bold transition-all flex items-center gap-1.5 ml-auto cursor-pointer"
                              >
                                <Trash2 className="w-3 h-3" />
                                <span>Remove</span>
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: SYSTEM DIAGNOSTICS & SUBSYSTEM HEALTH */}
      {activeTab === 'diagnostics' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-black text-white uppercase tracking-wider">
              HADIL Subsystem Health & Operational Diagnostics
            </h3>
            <button
              onClick={fetchSystemDiagnostics}
              className="px-4 py-2 bg-[#131A2B] hover:bg-[#1A2340] text-slate-200 border border-[#1F2A44] rounded-xl text-xs font-bold flex items-center gap-2 transition-all cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-emerald-400 ${diagLoading ? 'animate-spin' : ''}`} />
              <span>Refresh Status</span>
            </button>
          </div>

          {diagLoading && !systemDiagnostics ? (
            <div className="py-16 text-center text-slate-400 flex flex-col items-center justify-center space-y-2 bg-[#131A2B] border border-[#1F2A44] rounded-2xl">
              <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
              <span className="text-xs font-bold uppercase tracking-wider">Running System Diagnostics...</span>
            </div>
          ) : systemDiagnostics ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* Card 1: HADIL Core Subsystem */}
              <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-5 space-y-3 shadow-lg">
                <div className="flex items-center justify-between border-b border-[#1F2A44] pb-2">
                  <span className="text-xs font-bold text-slate-300 uppercase">HADIL Core Subsystem</span>
                  <span className="text-[10px] font-mono font-bold bg-emerald-950 text-emerald-400 border border-emerald-800 px-2 py-0.5 rounded">
                    {systemDiagnostics.fastapi_status}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">Background application daemon & REST router.</p>
              </div>

              {/* Card 2: Metadata Database */}
              <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-5 space-y-3 shadow-lg">
                <div className="flex items-center justify-between border-b border-[#1F2A44] pb-2">
                  <span className="text-xs font-bold text-slate-300 uppercase">Metadata Database</span>
                  <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                    systemDiagnostics.metadata_db_status === 'OK' ? 'bg-emerald-950 text-emerald-400 border-emerald-800' : 'bg-rose-950 text-rose-400 border-rose-800'
                  }`}>
                    {systemDiagnostics.metadata_db_status}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">Persistent SQLite store for users, RBAC, & settings.</p>
              </div>

              {/* Card 3: Database Manager */}
              <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-5 space-y-3 shadow-lg">
                <div className="flex items-center justify-between border-b border-[#1F2A44] pb-2">
                  <span className="text-xs font-bold text-slate-300 uppercase">Database Manager</span>
                  <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                    systemDiagnostics.database_manager_status === 'OK' ? 'bg-emerald-950 text-emerald-400 border-emerald-800' : 'bg-rose-950 text-rose-400 border-rose-800'
                  }`}>
                    {systemDiagnostics.database_manager_status}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">Multi-database pooling & SQL query execution manager.</p>
              </div>

              {/* Card 4: Policy RAG Service */}
              <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-5 space-y-3 shadow-lg">
                <div className="flex items-center justify-between border-b border-[#1F2A44] pb-2">
                  <span className="text-xs font-bold text-slate-300 uppercase">Policy RAG Service</span>
                  <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                    systemDiagnostics.policy_rag_status === 'OK' ? 'bg-emerald-950 text-emerald-400 border-emerald-800' : 'bg-rose-950 text-rose-400 border-rose-800'
                  }`}>
                    {systemDiagnostics.policy_rag_status}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">
                  Indexed documents: <strong className="text-slate-200">{systemDiagnostics.indexed_policy_count}</strong>
                </p>
              </div>

              {/* Card 5: FAISS Vector Index */}
              <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-5 space-y-3 shadow-lg">
                <div className="flex items-center justify-between border-b border-[#1F2A44] pb-2">
                  <span className="text-xs font-bold text-slate-300 uppercase">FAISS Vector Index</span>
                  <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                    systemDiagnostics.faiss_index_status === 'OK' ? 'bg-emerald-950 text-emerald-400 border-emerald-800' : 'bg-amber-950 text-amber-400 border-amber-800'
                  }`}>
                    {systemDiagnostics.faiss_index_status}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">Vector store for semantic policy search.</p>
              </div>

              {/* Card 6: Active LLM Configuration */}
              <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-5 space-y-3 shadow-lg">
                <div className="flex items-center justify-between border-b border-[#1F2A44] pb-2">
                  <span className="text-xs font-bold text-slate-300 uppercase">Active LLM Provider</span>
                  <span className="text-[10px] font-mono font-bold bg-purple-950 text-purple-300 border border-purple-800 px-2 py-0.5 rounded">
                    {systemDiagnostics.llm_provider}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">
                  Model: <strong className="text-slate-200">{systemDiagnostics.llm_model}</strong>
                </p>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
