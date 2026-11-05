'use client'

import { useEffect, useState } from 'react'
import {
  Users,
  UserPlus,
  Shield,
  Mail,
  Calendar,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Copy,
  Check,
} from 'lucide-react'
import apiClient, { UserProfile } from '@/lib/api-client'

export default function UsersPage() {
  const [users, setUsers] = useState<UserProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('Maintenance Engineer')
  const [inviting, setInviting] = useState(false)
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string; inviteUrl?: string } | null>(null)
  const [copied, setCopied] = useState(false)

  const fetchUsers = async () => {
    setLoading(true)
    const res = await apiClient.getUsers()
    if (res.data?.users) {
      setUsers(res.data.users)
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchUsers()
  }, [])

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    setInviting(true)
    setFeedback(null)

    const res = await apiClient.inviteUser(inviteEmail, inviteRole)
    setInviting(false)

    if (res.error) {
      setFeedback({ type: 'error', message: res.error })
      return
    }

    const invitation = (res.data as { invitation?: { invitation_url?: string } })?.invitation
    setFeedback({
      type: 'success',
      message: `Invitation successfully created for ${inviteEmail}.`,
      inviteUrl: invitation?.invitation_url,
    })
    setInviteEmail('')
    fetchUsers()
  }

  const handleCopyUrl = (url: string) => {
    navigator.clipboard.writeText(window.location.origin + url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#1685ff]">
          <Users className="size-4" /> Team Management
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-[#102c50]">
          Organization Team Members
        </h1>
        <p className="mt-1 text-xs text-slate-500">
          Manage roles, view authorized engineers, and invite new members with single-use invitations.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left 2 Cols: User List */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <h2 className="text-sm font-bold text-[#102c50]">Active Members ({users.length})</h2>
            <span className="text-[11px] text-slate-400">Strictly tenant-scoped</span>
          </div>

          {loading ? (
            <div className="py-12 text-center text-xs text-slate-400">
              <Loader2 className="mx-auto size-6 animate-spin text-[#1685ff]" />
              <p className="mt-2">Loading organization members...</p>
            </div>
          ) : (
            <div className="mt-4 divide-y divide-slate-100">
              {users.map((u) => (
                <div key={u.id} className="flex items-center justify-between py-3.5">
                  <div className="flex items-center gap-3">
                    <div className="grid size-9 place-items-center rounded-full bg-blue-50 text-xs font-bold text-[#1685ff]">
                      {u.full_name.charAt(0)}
                    </div>
                    <div>
                      <p className="text-xs font-bold text-[#102c50]">{u.full_name}</p>
                      <p className="flex items-center gap-1.5 text-[11px] text-slate-500">
                        <Mail className="size-3 text-slate-400" />
                        <span>{u.email}</span>
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-0.5 text-[10px] font-semibold text-[#1685ff]">
                      <Shield className="size-3" />
                      {u.roles?.[0] || 'Team Member'}
                    </span>

                    <span className="flex items-center gap-1 text-[10px] text-emerald-600">
                      <CheckCircle2 className="size-3" /> Active
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Col: Invite User */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-4">
            <UserPlus className="size-4 text-[#1685ff]" />
            <h2 className="text-sm font-bold text-[#102c50]">Invite Team Member</h2>
          </div>

          <form onSubmit={handleInvite} className="mt-4 space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700">
                Email Address
              </label>
              <input
                type="email"
                required
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="colleague@yourcompany.com"
                className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-[#1685ff] focus:ring-2 focus:ring-blue-100"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700">
                Assigned Role
              </label>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-[#1685ff] focus:ring-2 focus:ring-blue-100"
              >
                <option value="Maintenance Engineer">Maintenance Engineer</option>
                <option value="Maintenance Manager">Maintenance Manager</option>
                <option value="Viewer">Viewer (Read-Only)</option>
                <option value="Organization Administrator">Organization Administrator</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={inviting}
              className="flex w-full items-center justify-center rounded-lg bg-[#1685ff] py-2.5 text-xs font-semibold text-white shadow-sm transition hover:bg-[#126bd0] disabled:opacity-60"
            >
              {inviting ? (
                <>
                  <Loader2 className="mr-2 size-3.5 animate-spin" /> Generating Invitation...
                </>
              ) : (
                'Generate Single-Use Invite'
              )}
            </button>
          </form>

          {feedback && (
            <div
              className={`mt-4 rounded-xl p-3.5 text-xs ${
                feedback.type === 'success'
                  ? 'border border-emerald-200 bg-emerald-50 text-emerald-800'
                  : 'border border-rose-200 bg-rose-50 text-rose-800'
              }`}
            >
              <div className="flex items-center gap-2">
                {feedback.type === 'success' ? (
                  <CheckCircle2 className="size-4 shrink-0 text-emerald-600" />
                ) : (
                  <AlertCircle className="size-4 shrink-0 text-rose-600" />
                )}
                <span>{feedback.message}</span>
              </div>

              {feedback.inviteUrl && (
                <div className="mt-3 rounded-lg border border-emerald-300 bg-white p-2">
                  <p className="text-[10px] font-semibold text-slate-600">Simulated Invitation URL:</p>
                  <div className="mt-1 flex items-center justify-between gap-2">
                    <code className="truncate text-[10px] text-slate-800">{feedback.inviteUrl}</code>
                    <button
                      onClick={() => handleCopyUrl(feedback.inviteUrl!)}
                      className="inline-flex shrink-0 items-center gap-1 rounded bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-700 hover:bg-slate-200"
                    >
                      {copied ? <Check className="size-3 text-emerald-600" /> : <Copy className="size-3" />}
                      <span>{copied ? 'Copied' : 'Copy'}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="mt-6 rounded-xl border border-slate-100 bg-[#f8fafc] p-3 text-[11px] leading-relaxed text-slate-500">
            <p className="font-semibold text-slate-700">Controlled Onboarding Protocol:</p>
            <p className="mt-1">
              Invitations expire in 72 hours. Public unauthenticated user registration is strictly blocked to maintain tenant security.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

