'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import {
  Cpu,
  Activity,
  AlertTriangle,
  Clock,
  Building2,
  MapPin,
  CheckCircle2,
  PlusCircle,
  ExternalLink,
  ShieldCheck,
  ChevronRight,
  Plus,
} from 'lucide-react'
import apiClient, {
  AuthMeResponse,
  SiteDetails,
  EquipmentSummary,
  EquipmentItem,
} from '@/lib/api-client'

export default function DashboardPage() {
  const [authData, setAuthData] = useState<AuthMeResponse | null>(null)
  const [sites, setSites] = useState<SiteDetails[]>([])
  const [summary, setSummary] = useState<EquipmentSummary | null>(null)
  const [recentEquipment, setRecentEquipment] = useState<EquipmentItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    Promise.all([
      apiClient.getMe(),
      apiClient.getSites(),
      apiClient.getEquipmentSummary(),
      apiClient.getEquipment({ per_page: 5 }),
    ]).then(([authRes, sitesRes, sumRes, equipRes]) => {
      if (!mounted) return
      if (authRes.data) setAuthData(authRes.data)
      if (sitesRes.data?.sites) setSites(sitesRes.data.sites)
      if (sumRes.data) setSummary(sumRes.data)
      if (equipRes.data?.equipment) setRecentEquipment(equipRes.data.equipment)
      setLoading(false)
    })

    return () => {
      mounted = false
    }
  }, [])

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-72 animate-pulse rounded-lg bg-slate-200" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 animate-pulse rounded-2xl bg-slate-200" />
          ))}
        </div>
      </div>
    )
  }

  const primaryRole = authData?.roles?.[0] || 'Team Member'
  const orgName = authData?.organization?.name || 'Your Facility'

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#1685ff]">
            <ShieldCheck className="size-4" /> Operational Workspace
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-[#102c50] sm:text-3xl">
            Welcome back, {authData?.user?.full_name}
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            Assigned Role: <span className="font-semibold text-slate-700">{primaryRole}</span> · Tenant Organization:{' '}
            <span className="font-semibold text-slate-700">{orgName}</span>
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/dashboard/equipment/new"
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#1685ff] px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-[#126bd0]"
          >
            <Plus className="size-3.5" />
            <span>Add Equipment</span>
          </Link>
          <Link
            href="/dashboard/sites"
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            <Building2 className="size-3.5 text-[#1685ff]" />
            <span>Sites ({sites.length})</span>
          </Link>
          <a
            href="/api/v1/health"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            <span>API Health</span>
            <ExternalLink className="size-3 text-slate-400" />
          </a>
        </div>
      </div>

      {/* 4 Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Card 1: Total Machines */}
        <Link
          href="/dashboard/equipment"
          className="group block rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-[#1685ff]/50"
        >
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="font-semibold text-slate-600">Total Registered</span>
            <span className="grid size-8 place-items-center rounded-lg bg-blue-50 text-[#1685ff] transition group-hover:bg-[#1685ff] group-hover:text-white">
              <Cpu className="size-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold tracking-tight text-[#102c50]">
              {summary ? summary.total_machines : 0}
            </span>
            <span className="text-xs text-slate-400">assets</span>
          </div>
          <p className="mt-2 text-[11px] text-slate-500">Universal equipment registry</p>
        </Link>

        {/* Card 2: Running Machines */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="font-semibold text-slate-600">Active Operational</span>
            <span className="grid size-8 place-items-center rounded-lg bg-emerald-50 text-emerald-600">
              <Activity className="size-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold tracking-tight text-emerald-600">
              {summary ? summary.active_machines : 0}
            </span>
            <span className="text-xs text-slate-400">in production</span>
          </div>
          <p className="mt-2 text-[11px] text-slate-500">Operating under nominal status</p>
        </div>

        {/* Card 3: High Criticality */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="font-semibold text-slate-600">High & Critical Tier</span>
            <span className="grid size-8 place-items-center rounded-lg bg-amber-50 text-amber-600">
              <AlertTriangle className="size-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold tracking-tight text-amber-600">
              {summary ? summary.high_criticality : 0}
            </span>
            <span className="text-xs text-slate-400">priority assets</span>
          </div>
          <p className="mt-2 text-[11px] text-slate-500">Targeted for predictive maintenance</p>
        </div>

        {/* Card 4: Industrial Gateway */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="font-semibold text-slate-600">Industrial Gateway</span>
            <span className="grid size-8 place-items-center rounded-lg bg-indigo-50 text-indigo-600">
              <Clock className="size-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold tracking-tight text-[#102c50]">
              {summary ? summary.connected_machines : 0}
            </span>
            <span className="text-xs text-slate-400">connected</span>
          </div>
          <p className="mt-2 text-[11px] text-slate-500">OPC UA gateway (Phase 4)</p>
        </div>
      </div>

      {/* Main Grid: Sites & Equipment */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column: Registered Manufacturing Sites */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-1">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <h2 className="text-sm font-bold text-[#102c50]">Authorized Sites</h2>
              <p className="text-[11px] text-slate-500">Production plants for {orgName}</p>
            </div>
            <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-[#1685ff]">
              {sites.length} Active
            </span>
          </div>

          <div className="mt-4 space-y-3">
            {sites.map((site) => (
              <div
                key={site.id}
                className="rounded-xl border border-slate-200/80 bg-[#f8fafc] p-3.5 transition hover:border-slate-300"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[#102c50]">{site.name}</span>
                  {site.code && (
                    <span className="rounded bg-white px-1.5 py-0.5 text-[10px] font-mono font-medium text-slate-600 shadow-xs">
                      {site.code}
                    </span>
                  )}
                </div>
                {site.location && (
                  <p className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-500">
                    <MapPin className="size-3 text-slate-400" />
                    <span>{site.location}</span>
                  </p>
                )}
                <div className="mt-2.5 flex items-center gap-1.5 text-[10px] text-emerald-700">
                  <CheckCircle2 className="size-3 text-emerald-500" />
                  <span>Isolated tenant partition active</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Equipment Section */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <h2 className="text-sm font-bold text-[#102c50]">Registered Machinery</h2>
              <p className="text-[11px] text-slate-500">Pharmaceutical production assets</p>
            </div>
            <div className="flex items-center gap-2">
              <Link
                href="/dashboard/equipment"
                className="text-xs font-semibold text-[#1685ff] hover:underline"
              >
                View All ({summary ? summary.total_machines : 0})
              </Link>
            </div>
          </div>

          {recentEquipment.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <span className="grid size-12 place-items-center rounded-2xl bg-blue-50 text-[#1685ff]">
                <Cpu className="size-6" />
              </span>
              <h3 className="mt-3 text-base font-bold text-[#102c50]">
                No Equipment Registered Yet
              </h3>
              <p className="mt-1.5 max-w-md text-xs leading-relaxed text-slate-500">
                Register pharmaceutical machinery (blister packaging, tablet compression, liquid filling, HVAC) to
                track subassemblies and prepare for live industrial telemetry.
              </p>
              <Link
                href="/dashboard/equipment/new"
                className="mt-5 inline-flex items-center gap-2 rounded-lg bg-[#1685ff] px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-[#126bd0]"
              >
                <PlusCircle className="size-4" />
                <span>Register Machine</span>
              </Link>
            </div>
          ) : (
            <div className="mt-4 divide-y divide-slate-100">
              {recentEquipment.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between py-3 transition hover:bg-slate-50/50"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-[#102c50]">
                        {item.asset_code}
                      </span>
                      <span className="text-xs font-semibold text-slate-800">
                        {item.equipment_name}
                      </span>
                    </div>
                    <div className="mt-0.5 text-[11px] text-slate-400">
                      {item.category_name} · {item.site_name}
                      {item.production_line_name ? ` · Line: ${item.production_line_name}` : ''}
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${
                        item.criticality === 'Critical'
                          ? 'bg-rose-50 text-rose-700 border-rose-200'
                          : item.criticality === 'High'
                          ? 'bg-amber-50 text-amber-700 border-amber-200'
                          : 'bg-blue-50 text-blue-700 border-blue-200'
                      }`}
                    >
                      {item.criticality}
                    </span>
                    <Link
                      href={`/dashboard/equipment/${item.id}`}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-600 transition hover:border-[#1685ff] hover:text-[#1685ff]"
                    >
                      <span>Manage</span>
                      <ChevronRight className="size-3" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
