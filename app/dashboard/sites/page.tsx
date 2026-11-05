'use client'

import { useEffect, useState } from 'react'
import { Building2, MapPin, CheckCircle2, ShieldCheck, Loader2 } from 'lucide-react'
import apiClient, { SiteDetails } from '@/lib/api-client'

export default function SitesPage() {
  const [sites, setSites] = useState<SiteDetails[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    apiClient.getSites().then((res) => {
      if (!mounted) return
      if (res.data?.sites) setSites(res.data.sites)
      setLoading(false)
    })
    return () => {
      mounted = false
    }
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#1685ff]">
          <Building2 className="size-4" /> Multi-Site Infrastructure
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-[#102c50]">
          Manufacturing Sites & Facilities
        </h1>
        <p className="mt-1 text-xs text-slate-500">
          Authorized plant locations configured under your organization&apos;s isolated tenant space.
        </p>
      </div>

      {loading ? (
        <div className="py-12 text-center text-xs text-slate-400">
          <Loader2 className="mx-auto size-6 animate-spin text-[#1685ff]" />
          <p className="mt-2">Loading facility sites...</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sites.map((site) => (
            <div
              key={site.id}
              className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:shadow-md"
            >
              <div className="flex items-center justify-between">
                <span className="grid size-10 place-items-center rounded-xl bg-blue-50 text-[#1685ff]">
                  <Building2 className="size-5" />
                </span>
                {site.code && (
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 font-mono text-xs font-bold text-slate-700">
                    {site.code}
                  </span>
                )}
              </div>

              <h2 className="mt-4 text-base font-bold text-[#102c50]">{site.name}</h2>
              {site.location && (
                <p className="mt-1.5 flex items-start gap-1.5 text-xs text-slate-500">
                  <MapPin className="mt-0.5 size-3.5 shrink-0 text-slate-400" />
                  <span>{site.location}</span>
                </p>
              )}

              <div className="mt-6 flex items-center justify-between border-t border-slate-100 pt-4 text-xs">
                <span className="flex items-center gap-1.5 text-emerald-700 font-medium">
                  <CheckCircle2 className="size-3.5 text-emerald-500" />
                  <span>Active Partition</span>
                </span>
                <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
                  <ShieldCheck className="size-3" />
                  Tenant Verified
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

