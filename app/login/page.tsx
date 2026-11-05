'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Pill, Eye, EyeOff, ArrowRight, ShieldCheck, AlertCircle, Loader2 } from 'lucide-react'
import apiClient from '@/lib/api-client'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [seeded, setSeeded] = useState(false)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const res = await apiClient.login(email, password)
      if (res.error) {
        setError(res.error)
        setLoading(false)
        return
      }

      // Successful login
      router.push('/dashboard')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'An unexpected error occurred.'
      setError(msg)
      setLoading(false)
    }
  }

  const handleFillDemo = async (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail)
    setPassword(demoPass)
    setError(null)

    // Trigger seed in background if database is fresh
    if (!seeded) {
      try {
        await apiClient.seedDemoData()
        setSeeded(true)
      } catch {
        // Silently continue
      }
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-[#f8fafc] text-slate-900">
      {/* Top Header */}
      <header className="border-b border-slate-200/70 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8">
          <Link href="/" className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-xl bg-[#0d9488] text-white shadow-md shadow-teal-900/20">
              <Pill className="size-4" />
            </span>
            <span className="text-[15px] font-semibold tracking-[-0.02em] text-[#102c50]">
              PharmaPredict <span className="text-[#1685ff]">AI</span>
            </span>
          </Link>

          <Link
            href="/"
            className="text-xs font-semibold text-slate-500 transition hover:text-[#1685ff]"
          >
            ← Back to Overview
          </Link>
        </div>
      </header>

      {/* Main Login Card */}
      <main className="flex flex-1 items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
        <div className="w-full max-w-md">
          <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-xl shadow-slate-200/50 sm:p-10">
            {/* Header */}
            <div className="text-center">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-[#1685ff]">
                <ShieldCheck className="size-3.5" /> Secure Enterprise Portal
              </span>
              <h1 className="mt-4 text-2xl font-bold tracking-tight text-[#102c50]">
                Sign in to your account
              </h1>
              <p className="mt-2 text-xs leading-relaxed text-slate-500">
                Authorized access for pharmaceutical plant maintenance & condition monitoring
              </p>
            </div>

            {/* Error Banner */}
            {error && (
              <div
                role="alert"
                className="mt-6 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50/80 p-3.5 text-xs text-rose-800"
              >
                <AlertCircle className="mt-0.5 size-4 shrink-0 text-rose-600" />
                <span className="leading-relaxed">{error}</span>
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleLogin} className="mt-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700">
                  Work Email
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="engineer@getzpharma.com"
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-[#1685ff] focus:ring-2 focus:ring-blue-100"
                />
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700">
                    Password
                  </label>
                  <span className="text-[11px] text-slate-400">
                    Case-sensitive
                  </span>
                </div>
                <div className="relative mt-1.5">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 pr-10 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-[#1685ff] focus:ring-2 focus:ring-blue-100"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition hover:text-slate-600"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="group mt-2 flex w-full items-center justify-center rounded-lg bg-[#1685ff] py-3 text-sm font-semibold text-white shadow-lg shadow-blue-500/25 transition duration-200 hover:bg-[#126bd0] focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 size-4 animate-spin" /> Signing in...
                  </>
                ) : (
                  <>
                    Sign in to Platform <ArrowRight className="ml-2 size-4 transition-transform group-hover:translate-x-1" />
                  </>
                )}
              </button>
            </form>

            {/* Demo Accounts Helper */}
            <div className="mt-8 rounded-xl border border-blue-100 bg-blue-50/50 p-4">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#1685ff]">
                  Demo Accounts
                </span>
                <span className="rounded bg-blue-100/70 px-1.5 py-0.5 text-[10px] font-medium text-[#102c50]">
                  Pre-configured
                </span>
              </div>
              <p className="mt-1 text-[11px] text-slate-500">
                Click any profile to populate credentials:
              </p>
              <div className="mt-3 grid gap-2">
                <button
                  type="button"
                  onClick={() => handleFillDemo('saad.javed@pharmapredict.ai', 'PharmaPredict@2026')}
                  className="flex items-center justify-between rounded-lg border border-slate-200/80 bg-white px-3 py-2 text-left text-xs transition hover:border-[#1685ff] hover:bg-blue-50/30"
                >
                  <div>
                    <span className="font-semibold text-[#102c50]">Saad Javed</span>
                    <span className="ml-2 text-[10px] text-slate-400">Getz Pharma · Manager</span>
                  </div>
                  <span className="text-[10px] font-medium text-[#1685ff]">Select →</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleFillDemo('admin@getzpharma.com', 'Admin@Getz2026')}
                  className="flex items-center justify-between rounded-lg border border-slate-200/80 bg-white px-3 py-2 text-left text-xs transition hover:border-[#1685ff] hover:bg-blue-50/30"
                >
                  <div>
                    <span className="font-semibold text-[#102c50]">Org Administrator</span>
                    <span className="ml-2 text-[10px] text-slate-400">Getz Pharma · Admin</span>
                  </div>
                  <span className="text-[10px] font-medium text-[#1685ff]">Select →</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleFillDemo('engineer@benchmarkpharma.com', 'Benchmark@2026')}
                  className="flex items-center justify-between rounded-lg border border-slate-200/80 bg-white px-3 py-2 text-left text-xs transition hover:border-[#1685ff] hover:bg-blue-50/30"
                >
                  <div>
                    <span className="font-semibold text-[#102c50]">Benchmark Engineer</span>
                    <span className="ml-2 text-[10px] text-slate-400">Benchmark Tenant</span>
                  </div>
                  <span className="text-[10px] font-medium text-[#1685ff]">Select →</span>
                </button>
              </div>
            </div>

            {/* Compliance Footer */}
            <p className="mt-6 text-center text-[11px] leading-relaxed text-slate-400">
              Audit-ready session management · Strict multi-tenant isolation
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}

