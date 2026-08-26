import React, { useState, useEffect } from 'react';
import { 
  Users, UserPlus, ShieldAlert, ShieldCheck, KeyRound, 
  Database, RefreshCw, CheckCircle2, AlertCircle, Loader2, Sparkles, X
} from 'lucide-react';
import api from '../api';

export default function UserManagementView({ databases = [], activeDbId = '', currentUser = null }) {
  const isMasterAdmin = currentUser?.username === 'admin';
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState('');

  // Create User Form State
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('VIEWER');

  // Assign Role Form State
  const [selectedUserId, setSelectedUserId] = useState('');
  const [assignDbId, setAssignDbId] = useState(activeDbId || '');
  const [assignRole, setAssignRole] = useState('EDITOR');

  useEffect(() => {
    fetchUsers();
  }, []);

  useEffect(() => {
    if (activeDbId) {
      setAssignDbId(activeDbId);
    }
  }, [activeDbId]);

  const fetchUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/users');
      setUsers(res.data || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to fetch users');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    if (!newUsername.trim() || !newPassword.trim()) return;

    setActionLoading(true);
    setError(null);
    setSuccess('');
    try {
      const res = await api.post('/users', {
        username: newUsername,
        password: newPassword,
        role: newRole
      });
      if (res.data.success) {
        setSuccess(`User '${newUsername}' created successfully with '${newRole}' role for active database.`);
        setNewUsername('');
        setNewPassword('');
        fetchUsers();
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to create user.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleAssignRole = async (e) => {
    e.preventDefault();
    if (!selectedUserId || !assignRole) return;

    setActionLoading(true);
    setError(null);
    setSuccess('');
    try {
      const res = await api.post(`/users/${selectedUserId}/roles`, {
        user_id: parseInt(selectedUserId, 10),
        role: assignRole
      });
      if (res.data.success) {
        const u = users.find(x => x.id === parseInt(selectedUserId, 10));
        setSuccess(`Successfully updated role to '${assignRole}' for user '${u?.username || selectedUserId}' on '${res.data.database_id}'.`);
        fetchUsers();
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to assign role.');
    } finally {
      setActionLoading(false);
    }
  };

  const getBadgeColor = (roleStr) => {
    switch (roleStr) {
      case 'ADMIN':
        return 'bg-purple-950/80 text-purple-300 border-purple-800/80';
      case 'EDITOR':
        return 'bg-blue-950/80 text-blue-300 border-blue-800/80';
      case 'VIEWER':
        return 'bg-slate-900 text-slate-300 border-slate-700';
      default:
        return 'bg-slate-900 text-slate-400 border-slate-800';
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-[#1F2A44]">
        <div>
          <div className="flex items-center gap-2">
            <Users className="w-6 h-6 text-purple-400" />
            <h2 className="text-2xl font-black text-white tracking-tight">
              Enterprise User & RBAC Management
            </h2>
            <span className="text-[10px] bg-purple-950 border border-purple-800 text-purple-300 font-extrabold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
              ADMIN ONLY
            </span>
          </div>
          <p className="text-xs text-slate-400 font-medium mt-1">
            Manage user credentials and database-scoped roles (ADMIN, EDITOR, VIEWER).
          </p>
        </div>

        <button
          onClick={fetchUsers}
          className="px-4 py-2 rounded-xl bg-[#131A2B] hover:bg-[#1A2340] text-slate-200 hover:text-white text-xs font-bold border border-[#1F2A44] flex items-center gap-2 transition-all cursor-pointer shadow-md"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-blue-400 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Users</span>
        </button>
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

      {/* Main Grid: Management Forms & User Table */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column: Actions (Create User & Assign Role) */}
        <div className="space-y-6">
          
          {/* Card 1: Create New User */}
          <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-6 space-y-4 shadow-xl">
            <div className="flex items-center gap-2 pb-2 border-b border-[#1F2A44]">
              <UserPlus className="w-4 h-4 text-blue-400" />
              <h3 className="text-sm font-black text-white uppercase tracking-wider">
                Create New User
              </h3>
            </div>

            <form onSubmit={handleCreateUser} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider block">
                  Username
                </label>
                <input
                  type="text"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  placeholder="e.g. janesmith"
                  required
                  className="w-full bg-[#0F1626] border border-[#1F2A44] rounded-xl px-3.5 py-2 text-xs text-slate-100 font-medium placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider block">
                  Password
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Minimum 6 characters"
                  required
                  className="w-full bg-[#0F1626] border border-[#1F2A44] rounded-xl px-3.5 py-2 text-xs text-slate-100 font-medium placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider block">
                  Role for Active DB ({activeDbId || 'Connected DB'})
                </label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  className="w-full bg-[#0F1626] border border-[#1F2A44] rounded-xl px-3.5 py-2 text-xs text-slate-100 font-bold outline-none cursor-pointer"
                >
                  <option value="VIEWER">VIEWER (Read Only)</option>
                  <option value="EDITOR">EDITOR (Read & Write)</option>
                  {isMasterAdmin && <option value="ADMIN">ADMIN (Full Control / DB Admin)</option>}
                </select>
                {!isMasterAdmin && (
                  <p className="text-[10px] text-amber-400 font-medium">
                    * Only Master Admin ('admin') can assign ADMIN role to new users.
                  </p>
                )}
              </div>

              <button
                type="submit"
                disabled={actionLoading}
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer shadow-md shadow-blue-900/30 disabled:opacity-50"
              >
                {actionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <UserPlus className="w-3.5 h-3.5" />}
                <span>Create User</span>
              </button>
            </form>
          </div>

          {/* Card 2: Assign Database-Scoped Role */}
          <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-6 space-y-4 shadow-xl">
            <div className="flex items-center gap-2 pb-2 border-b border-[#1F2A44]">
              <KeyRound className="w-4 h-4 text-purple-400" />
              <h3 className="text-sm font-black text-white uppercase tracking-wider">
                Assign Database Role
              </h3>
            </div>

            <form onSubmit={handleAssignRole} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider block">
                  Select User
                </label>
                <select
                  value={selectedUserId}
                  onChange={(e) => setSelectedUserId(e.target.value)}
                  required
                  className="w-full bg-[#0F1626] border border-[#1F2A44] rounded-xl px-3.5 py-2 text-xs text-slate-100 font-bold outline-none cursor-pointer"
                >
                  <option value="">-- Choose User --</option>
                  {users.map(u => (
                    <option key={u.id} value={u.id}>
                      {u.username} (ID: {u.id})
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider block">
                  Target Role ({activeDbId})
                </label>
                <select
                  value={assignRole}
                  onChange={(e) => setAssignRole(e.target.value)}
                  className="w-full bg-[#0F1626] border border-[#1F2A44] rounded-xl px-3.5 py-2 text-xs text-slate-100 font-bold outline-none cursor-pointer"
                >
                  <option value="VIEWER">VIEWER (Read Only)</option>
                  <option value="EDITOR">EDITOR (Read & Write)</option>
                  {isMasterAdmin && <option value="ADMIN">ADMIN (Full Control)</option>}
                </select>
                {!isMasterAdmin && (
                  <p className="text-[10px] text-amber-400 font-medium">
                    * DB Admins can grant EDITOR and VIEWER permissions.
                  </p>
                )}
              </div>

              <button
                type="submit"
                disabled={actionLoading || !selectedUserId}
                className="w-full py-2.5 bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer shadow-md shadow-purple-900/30 disabled:opacity-50"
              >
                {actionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}
                <span>Assign Database Role</span>
              </button>
            </form>
          </div>

        </div>

        {/* Right Column: Registered Users Table */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-[#1F2A44]">
              <div>
                <h3 className="text-sm font-black text-white uppercase tracking-wider">
                  Registered System Users ({users.length})
                </h3>
                <p className="text-[11px] text-slate-400 font-medium mt-0.5">
                  Permissions are strictly database-scoped per user.
                </p>
              </div>
            </div>

            {loading ? (
              <div className="py-12 text-center text-slate-400 flex flex-col items-center justify-center space-y-2">
                <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
                <span className="text-xs">Loading user repository...</span>
              </div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-[#1F2A44] bg-[#0F1626]">
                <table className="w-full text-xs text-left">
                  <thead className="bg-[#131A2B] text-slate-400 border-b border-[#1F2A44] font-extrabold uppercase text-[10px] tracking-wider">
                    <tr>
                      <th className="px-5 py-3">ID</th>
                      <th className="px-5 py-3">User</th>
                      <th className="px-5 py-3">Assigned Database Roles</th>
                      <th className="px-5 py-3 text-right">Quick Role Assign</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1F2A44]">
                    {users.map((u) => (
                      <tr key={u.id} className="hover:bg-[#131A2B]/60 transition-colors">
                        <td className="px-5 py-3.5 font-mono text-slate-400 font-bold">#{u.id}</td>
                        <td className="px-5 py-3.5">
                          <span className="font-bold text-white text-xs">{u.username}</span>
                        </td>
                        <td className="px-5 py-3.5">
                          {u.roles && u.roles.length > 0 ? (
                            <div className="flex flex-wrap gap-1.5">
                              {u.roles.map((r, idx) => (
                                <span
                                  key={idx}
                                  className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${getBadgeColor(r.role)}`}
                                >
                                  {r.database_id}: {r.role}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-500 italic text-[11px]">No roles assigned</span>
                          )}
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <button
                            onClick={() => {
                              setSelectedUserId(u.id.toString());
                              window.scrollTo({ top: 0, behavior: 'smooth' });
                            }}
                            className="px-3 py-1 bg-[#131A2B] hover:bg-[#1A2340] text-blue-400 hover:text-white border border-[#1F2A44] rounded-lg text-[11px] font-bold transition-all cursor-pointer"
                          >
                            Manage Role
                          </button>
                        </td>
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
