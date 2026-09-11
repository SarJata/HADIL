import React, { useEffect, useState } from 'react';
import { Building2, CheckCircle2, AlertCircle, Loader2, ShieldBan, RefreshCw } from 'lucide-react';
import api from '../api';

export default function PlatformOrganizationsView() {
  const [orgs, setOrgs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState('');

  const fetchOrgs = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/platform/organizations');
      setOrgs(res.data?.organizations || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load organizations.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrgs();
  }, []);

  const act = async (id, action) => {
    setError(null);
    setSuccess('');
    try {
      await api.post(`/platform/organizations/${id}/${action}`);
      setSuccess(`Organization ${action}d.`);
      fetchOrgs();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || `Failed to ${action} organization.`);
    }
  };

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h2 className="text-2xl font-serif-brand text-white">Pending Organizations</h2>
        <p className="text-xs text-slate-400 mt-1">
          Approve or reject organization registrations. Platform Master Admins do not receive customer database access.
        </p>
      </div>
      {error && (
        <div className="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-200 text-xs flex gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="p-3 rounded-xl bg-emerald-950/50 border border-emerald-800 text-emerald-200 text-xs flex gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{success}</span>
        </div>
      )}
      <button
        type="button"
        onClick={fetchOrgs}
        className="text-xs font-bold text-emerald-400 flex items-center gap-1"
      >
        <RefreshCw className="w-3.5 h-3.5" /> Refresh
      </button>
      {loading ? (
        <Loader2 className="w-5 h-5 animate-spin text-emerald-400" />
      ) : (
        <div className="space-y-3">
          {orgs.length === 0 && (
            <p className="text-sm text-slate-500">No organization registrations.</p>
          )}
          {orgs.map((org) => (
            <div key={org.id} className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-start gap-3">
                <Building2 className="w-5 h-5 text-emerald-400 mt-0.5" />
                <div>
                  <div className="text-sm font-bold text-white">{org.name} <span className="text-slate-500 font-mono">({org.slug})</span></div>
                  <div className="text-xs text-slate-400 mt-1">{org.suadmin_username || 'No SUADMIN'} · {org.status}</div>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {org.status === 'PENDING' && (
                  <>
                    <button type="button" onClick={() => act(org.id, 'approve')} className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-bold">Approve</button>
                    <button type="button" onClick={() => act(org.id, 'reject')} className="px-3 py-1.5 rounded-lg bg-rose-800 text-white text-xs font-bold">Reject</button>
                  </>
                )}
                {org.status === 'ACTIVE' && (
                  <button type="button" onClick={() => act(org.id, 'suspend')} className="px-3 py-1.5 rounded-lg bg-amber-700 text-white text-xs font-bold flex items-center gap-1">
                    <ShieldBan className="w-3.5 h-3.5" /> Suspend
                  </button>
                )}
                {org.status === 'SUSPENDED' && (
                  <button type="button" onClick={() => act(org.id, 'reactivate')} className="px-3 py-1.5 rounded-lg bg-emerald-700 text-white text-xs font-bold">Reactivate</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
