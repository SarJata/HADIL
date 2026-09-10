import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Upload, 
  Trash2, 
  ShieldAlert, 
  CheckCircle, 
  Clock, 
  Database, 
  Globe, 
  Sliders, 
  AlertCircle,
  RefreshCw
} from 'lucide-react';
import { 
  fetchPolicies, 
  uploadPolicy, 
  deletePolicy, 
  fetchPolicyConfig, 
  updatePolicyConfig 
} from '../api';

export default function PolicyManagementView({ activeDatabase, userRole }) {
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Upload Form State
  const [file, setFile] = useState(null);
  const [scopeType, setScopeType] = useState('GLOBAL'); // 'GLOBAL' or 'DATABASE'
  
  // Config State
  const [threshold, setThreshold] = useState(0.65);
  const [configLoading, setConfigLoading] = useState(false);

  const isAdmin = userRole === 'ADMIN';

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPolicies();
      setPolicies(data);

      if (isAdmin) {
        const cfg = await fetchPolicyConfig();
        if (cfg && cfg.threshold !== undefined) {
          setThreshold(cfg.threshold);
        }
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load policy documents.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a file to upload.');
      return;
    }

    setUploading(true);
    setError(null);
    setSuccessMsg(null);

    const formData = new FormData();
    formData.append('file', file);
    
    const targetScope = scopeType === 'GLOBAL' 
      ? 'GLOBAL' 
      : `DATABASE:${activeDatabase?.id || 'default'}`;
    
    formData.append('scope', targetScope);

    try {
      const res = await uploadPolicy(formData);
      setSuccessMsg(res.message || 'Policy uploaded and indexed successfully.');
      setFile(null);
      // Reset file input
      e.target.reset();
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to upload policy document.');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docId, filename) => {
    if (!window.confirm(`Are you sure you want to delete policy '${filename}'? This will remove all associated vector embeddings.`)) {
      return;
    }

    try {
      await deletePolicy(docId);
      setSuccessMsg(`Deleted policy document '${filename}'.`);
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete policy document.');
    }
  };

  const handleSaveThreshold = async () => {
    setConfigLoading(true);
    setError(null);
    try {
      await updatePolicyConfig(parseFloat(threshold));
      setSuccessMsg(`Similarity threshold updated to ${threshold}.`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update threshold config.');
    } finally {
      setConfigLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header Banner */}

      <div className="bg-[#131A2B] border border-[#1F2A44] rounded-lg p-5 flex items-start justify-between">
        <div>
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-[#0F1626] border border-[#1F2A44] rounded text-emerald-400">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-serif-brand text-white tracking-wide">Policy Documents RAG</h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Upload organizational policies to guide LLM query generation and verification with contextual business constraints.
              </p>
            </div>
          </div>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="px-3 py-1.5 bg-[#0F1626] hover:bg-[#1A2340] border border-[#1F2A44] rounded text-slate-300 text-xs flex items-center space-x-1.5 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Alert Banners */}
      {error && (
        <div className="p-3 bg-rose-950/40 border border-rose-800 text-rose-300 text-xs rounded flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="p-3 bg-emerald-950/40 border border-emerald-800 text-emerald-300 text-xs rounded flex items-center space-x-2">
          <CheckCircle className="w-4 h-4 flex-shrink-0 text-emerald-400" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Main Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Upload Form Section (Admin Only) */}
        <div className="lg:col-span-1 space-y-4">
          {isAdmin ? (
            <div className="bg-[#131A2B] border border-[#1F2A44] rounded-lg p-4 space-y-4">
              <h2 className="text-sm font-semibold text-white flex items-center space-x-2">
                <Upload className="w-4 h-4 text-emerald-400" />
                <span>Upload Policy Document</span>
              </h2>

              <form onSubmit={handleUploadSubmit} className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Document File (.pdf, .txt, .docx)
                  </label>
                  <input
                    type="file"
                    accept=".pdf,.txt,.docx"
                    onChange={handleFileChange}
                    className="w-full text-xs text-slate-300 file:mr-2 file:py-1 file:px-2.5 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-emerald-900/60 file:text-emerald-300 hover:file:bg-emerald-800 cursor-pointer bg-[#0F1626] rounded border border-[#1F2A44] p-1"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Policy Scope
                  </label>
                  <select
                    value={scopeType}
                    onChange={(e) => setScopeType(e.target.value)}
                    className="w-full bg-[#0F1626] border border-[#1F2A44] text-slate-200 rounded px-3 py-1.5 text-xs focus:outline-none focus:border-emerald-500"
                  >
                    <option value="GLOBAL">GLOBAL (Applies to all connected databases)</option>
                    <option value="DATABASE">
                      DATABASE: {activeDatabase?.name || activeDatabase?.id || 'Active Selected DB'}
                    </option>
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={uploading || !file}
                  className="w-full py-2 bg-emerald-700 hover:bg-emerald-600 border border-emerald-600 text-white rounded font-medium text-xs transition-colors flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {uploading ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Extracting & Indexing...</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-3.5 h-3.5" />
                      <span>Upload & Index Document</span>
                    </>
                  )}
                </button>
              </form>
            </div>
          ) : (
            <div className="bg-[#131A2B] border border-[#1F2A44] rounded-lg p-4 text-center">
              <ShieldAlert className="w-6 h-6 text-slate-500 mx-auto mb-2" />
              <h3 className="text-xs font-semibold text-slate-300">Admin Privileges Required</h3>
              <p className="text-[11px] text-slate-500 mt-1">
                Only ADMIN users can upload or delete policy documents.
              </p>
            </div>
          )}

          {/* Config Section (Admin Only) */}
          {isAdmin && (
            <div className="bg-[#131A2B] border border-[#1F2A44] rounded-lg p-4 space-y-3">
              <h2 className="text-sm font-semibold text-white flex items-center space-x-2">
                <Sliders className="w-4 h-4 text-emerald-400" />
                <span>RAG Retrieval Config</span>
              </h2>

              <div className="space-y-3">
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-xs font-medium text-slate-300">
                      Similarity Threshold ({threshold})
                    </label>
                    <span className="text-[11px] font-mono text-slate-500">Cosine</span>
                  </div>
                  <input
                    type="range"
                    min="0.10"
                    max="0.95"
                    step="0.05"
                    value={threshold}
                    onChange={(e) => setThreshold(e.target.value)}
                    className="w-full accent-emerald-500 cursor-pointer"
                  />
                  <p className="text-[11px] text-slate-400 mt-1">
                    Chunks with cosine score below {threshold} are filtered out.
                  </p>
                </div>

                <button
                  onClick={handleSaveThreshold}
                  disabled={configLoading}
                  className="w-full py-1.5 bg-[#0F1626] hover:bg-[#1A2340] text-slate-200 border border-[#1F2A44] rounded font-medium text-xs transition-colors flex items-center justify-center space-x-2"
                >
                  {configLoading ? 'Saving...' : 'Save Configuration'}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Policy Documents List Table */}
        <div className="lg:col-span-2">
          <div className="bg-[#131A2B] border border-[#1F2A44] rounded-lg overflow-hidden">
            <div className="p-3.5 border-b border-[#1F2A44] flex justify-between items-center">
              <h2 className="text-sm font-semibold text-white flex items-center space-x-2">
                <FileText className="w-4 h-4 text-emerald-400" />
                <span>Uploaded Policy Documents</span>
              </h2>
              <span className="text-[10px] text-slate-400 font-mono bg-[#0F1626] px-2 py-0.5 rounded border border-[#1F2A44]">
                {policies.length} Document(s)
              </span>
            </div>

            {loading ? (
              <div className="p-8 text-center text-slate-400 space-y-2">
                <RefreshCw className="w-5 h-5 animate-spin mx-auto text-emerald-400" />
                <p className="text-xs font-mono">Loading policy documents...</p>
              </div>
            ) : policies.length === 0 ? (
              <div className="p-10 text-center text-slate-500 space-y-2">
                <FileText className="w-8 h-8 mx-auto text-slate-600" />
                <p className="text-xs font-medium text-slate-400">No Policy Documents Uploaded</p>
                <p className="text-[11px] max-w-sm mx-auto text-slate-500">
                  Upload company policies to allow HADIL to retrieve rules during natural-language queries.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-[#0F1626] text-[10px] uppercase font-mono text-slate-400 border-b border-[#1F2A44]">
                    <tr>
                      <th className="px-3.5 py-2.5">Document</th>
                      <th className="px-3.5 py-2.5">Scope</th>
                      <th className="px-3.5 py-2.5">Status</th>
                      <th className="px-3.5 py-2.5">Chunks</th>
                      <th className="px-3.5 py-2.5">Uploaded</th>
                      {isAdmin && <th className="px-3.5 py-2.5 text-right">Actions</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1F2A44]/60 font-mono">
                    {policies.map((doc) => (
                      <tr key={doc.id} className="hover:bg-[#1A2340]/50 transition-colors">
                        <td className="px-3.5 py-2.5 font-medium text-white flex items-center space-x-2">
                          <FileText className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                          <span className="truncate max-w-xs font-sans text-xs" title={doc.filename}>{doc.filename}</span>
                        </td>
                        <td className="px-3.5 py-2.5 text-[10px]">
                          {doc.scope === 'GLOBAL' ? (
                            <span className="px-1.5 py-0.5 rounded bg-slate-900 text-blue-300 border border-slate-700">
                              GLOBAL
                            </span>
                          ) : (
                            <span className="px-1.5 py-0.5 rounded bg-slate-900 text-purple-300 border border-slate-700">
                              {doc.scope}
                            </span>
                          )}
                        </td>
                        <td className="px-3.5 py-2.5 text-[10px]">
                          {doc.indexing_status === 'INDEXED' ? (
                            <span className="text-emerald-400 font-bold">
                              [INDEXED]
                            </span>
                          ) : (
                            <span className="text-rose-400 font-bold">
                              [FAILED]
                            </span>
                          )}
                        </td>
                        <td className="px-3.5 py-2.5 text-xs text-slate-400">
                          {doc.chunk_count}
                        </td>
                        <td className="px-3.5 py-2.5 text-[11px] text-slate-400 font-sans">
                          {doc.upload_timestamp ? new Date(doc.upload_timestamp).toLocaleDateString() : 'N/A'}
                        </td>
                        {isAdmin && (
                          <td className="px-3.5 py-2.5 text-right">
                            <button
                              onClick={() => handleDelete(doc.id, doc.filename)}
                              className="p-1 hover:bg-rose-950/60 text-slate-400 hover:text-rose-300 rounded border border-transparent hover:border-rose-800 transition-colors"
                              title="Delete policy"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>


      </div>
    </div>
  );
}
