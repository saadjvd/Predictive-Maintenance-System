'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import {
  Cpu,
  Plus,
  Search,
  Filter,
  RefreshCw,
  Building2,
  ChevronRight,
  AlertTriangle,
  Activity,
  Layers,
  ArrowUpDown,
  Lock,
  ChevronLeft,
  X,
  Radio,
} from 'lucide-react'
import apiClient, {
  EquipmentItem,
  EquipmentSummary,
  EquipmentCategoryItem,
  SiteDetails,
} from '@/lib/api-client'

export default function EquipmentListPage() {
  const [equipment, setEquipment] = useState<EquipmentItem[]>([])
  const [summary, setSummary] = useState<EquipmentSummary | null>(null)
  const [categories, setCategories] = useState<EquipmentCategoryItem[]>([])
  const [sites, setSites] = useState<SiteDetails[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Filters & Search
  const [search, setSearch] = useState('')
  const [selectedSite, setSelectedSite] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('')
  const [selectedCriticality, setSelectedCriticality] = useState('')
  const [selectedStatus, setSelectedStatus] = useState('')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalItems, setTotalItems] = useState(0)

  const fetchData = useCallback(
    async (isRefresh = false) => {
      if (isRefresh) setRefreshing(true)
      else setLoading(true)
      setError(null)

      try {
        const [equipRes, sumRes, catRes, siteRes] = await Promise.all([
          apiClient.getEquipment({
            search: search.trim() || undefined,
            site_id: selectedSite || undefined,
            category_id: selectedCategory || undefined,
            criticality: selectedCriticality || undefined,
            lifecycle_status: selectedStatus || undefined,
            page,
            per_page: 15,
          }),
          apiClient.getEquipmentSummary(),
          apiClient.getCategories(),
          apiClient.getSites(),
        ])

        if (equipRes.data) {
          setEquipment(equipRes.data.equipment)
          setTotalPages(equipRes.data.pagination.pages || 1)
          setTotalItems(equipRes.data.pagination.total || 0)
        } else if (equipRes.error) {
          setError(equipRes.error)
        }

        if (sumRes.data) {
          setSummary(sumRes.data)
        }

        if (catRes.data?.categories) {
          setCategories(catRes.data.categories)
        }

        if (siteRes.data?.sites) {
          setSites(siteRes.data.sites)
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to load equipment registry')
      } finally {
        setLoading(false)
        setRefreshing(false)
      }
    },
    [search, selectedSite, selectedCategory, selectedCriticality, selectedStatus, page]
  )

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleClearFilters = () => {
    setSearch('')
    setSelectedSite('')
    setSelectedCategory('')
    setSelectedCriticality('')
    setSelectedStatus('')
    setPage(1)
  }

  const hasActiveFilters =
    Boolean(search) ||
    Boolean(selectedSite) ||
    Boolean(selectedCategory) ||
    Boolean(selectedCriticality) ||
    Boolean(selectedStatus)

  const getCriticalityBadge = (crit: string) => {
    switch (crit) {
      case 'Critical':
        return 'bg-rose-50 text-rose-700 border-rose-200'
      case 'High':
        return 'bg-amber-50 text-amber-700 border-amber-200'
      case 'Medium':
        return 'bg-blue-50 text-blue-700 border-blue-200'
      default:
        return 'bg-slate-50 text-slate-700 border-slate-200'
    }
  }

  const getLifecycleBadge = (status: string) => {
    switch (status) {
      case 'Active':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200'
      case 'Under Maintenance':
        return 'bg-amber-50 text-amber-700 border-amber-200'
      case 'Decommissioned':
        return 'bg-rose-50 text-rose-700 border-rose-200'
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200'
    }
  }

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#1685ff]">
            <Cpu className="size-4" /> Asset Management
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-[#102c50] sm:text-3xl">
            Universal Equipment Registry
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            Pharmaceutical manufacturing assets, line assignments, and baseline connectivity profiles.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => fetchData(true)}
            disabled={refreshing}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50"
            title="Refresh Registry"
          >
            <RefreshCw className={`size-3.5 text-slate-400 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <Link
            href="/dashboard/equipment/new"
            className="inline-flex items-center gap-2 rounded-lg bg-[#1685ff] px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-[#126bd0]"
          >
            <Plus className="size-4" />
            <span>Register Equipment</span>
          </Link>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Total Assets */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="font-semibold text-slate-600">Total Registered</span>
            <span className="grid size-8 place-items-center rounded-lg bg-blue-50 text-[#1685ff]">
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
        </div>

        {/* Active Machines */}
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
          <p className="mt-2 text-[11px] text-slate-500">Ready for telemetry ingestion</p>
        </div>

        {/* High / Critical Assets */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="font-semibold text-slate-600">High & Critical</span>
            <span className="grid size-8 place-items-center rounded-lg bg-amber-50 text-amber-600">
              <AlertTriangle className="size-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold tracking-tight text-amber-600">
              {summary ? summary.high_criticality : 0}
            </span>
            <span className="text-xs text-slate-400">critical tier</span>
          </div>
          <p className="mt-2 text-[11px] text-slate-500">Priority for AI predictive models</p>
        </div>

        {/* Industrial Connectivity */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="font-semibold text-slate-600">Industrial Gateway</span>
            <span className="grid size-8 place-items-center rounded-lg bg-indigo-50 text-indigo-600">
              <Radio className="size-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold tracking-tight text-[#102c50]">
              {summary ? summary.connected_machines : 0}
            </span>
            <span className="text-xs text-slate-400">streams active</span>
          </div>
          <p className="mt-2 text-[11px] text-slate-500">
            {summary && summary.total_machines > 0
              ? `${summary.by_connection['Not Configured'] || 0} awaiting OPC UA setup`
              : 'Configured during Phase 4'}
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          {/* Search Input */}
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by asset code, equipment name, manufacturer, or model..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
              className="w-full rounded-lg border border-slate-200 bg-slate-50/50 py-2 pl-10 pr-4 text-xs text-slate-800 placeholder-slate-400 outline-none transition focus:border-[#1685ff] focus:bg-white focus:ring-2 focus:ring-[#1685ff]/20"
            />
          </div>

          {/* Dropdown Filters */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Site Filter */}
            <select
              value={selectedSite}
              onChange={(e) => {
                setSelectedSite(e.target.value)
                setPage(1)
              }}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 outline-none focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
            >
              <option value="">All Sites</option>
              {sites.map((site) => (
                <option key={site.id} value={site.id}>
                  {site.name}
                </option>
              ))}
            </select>

            {/* Category Filter */}
            <select
              value={selectedCategory}
              onChange={(e) => {
                setSelectedCategory(e.target.value)
                setPage(1)
              }}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 outline-none focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
            >
              <option value="">All Categories</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name}
                </option>
              ))}
            </select>

            {/* Criticality Filter */}
            <select
              value={selectedCriticality}
              onChange={(e) => {
                setSelectedCriticality(e.target.value)
                setPage(1)
              }}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 outline-none focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
            >
              <option value="">All Criticalities</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>

            {/* Lifecycle Status Filter */}
            <select
              value={selectedStatus}
              onChange={(e) => {
                setSelectedStatus(e.target.value)
                setPage(1)
              }}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 outline-none focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
            >
              <option value="">All Statuses</option>
              <option value="Active">Active</option>
              <option value="Under Maintenance">Under Maintenance</option>
              <option value="Inactive">Inactive</option>
              <option value="Decommissioned">Decommissioned</option>
            </select>

            {hasActiveFilters && (
              <button
                onClick={handleClearFilters}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-100 px-2.5 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-200"
              >
                <X className="size-3.5" />
                <span>Reset</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-700">
          <p className="font-semibold">Unable to load equipment records</p>
          <p className="mt-0.5">{error}</p>
        </div>
      )}

      {/* Equipment Table / Empty State */}
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400">
            <RefreshCw className="size-8 animate-spin text-[#1685ff]" />
            <p className="mt-3 text-xs font-semibold">Loading equipment records...</p>
          </div>
        ) : equipment.length === 0 ? (
          <div className="flex min-h-[380px] flex-col items-center justify-center p-8 text-center">
            <div className="grid size-14 place-items-center rounded-2xl bg-blue-50 text-[#1685ff]">
              <Cpu className="size-7" />
            </div>
            <h3 className="mt-4 text-base font-bold text-[#102c50]">
              {hasActiveFilters ? 'No equipment matching your criteria' : 'No pharmaceutical machines registered'}
            </h3>
            <p className="mt-1.5 max-w-md text-xs leading-relaxed text-slate-500">
              {hasActiveFilters
                ? 'Try broadening your search term or resetting your active filters.'
                : 'Register your first production asset (blister machine, tablet press, fluid bed dryer, or HVAC) to assign manufacturing lines and define components.'}
            </p>
            {hasActiveFilters ? (
              <button
                onClick={handleClearFilters}
                className="mt-5 inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
              >
                <X className="size-3.5" />
                <span>Clear All Filters</span>
              </button>
            ) : (
              <Link
                href="/dashboard/equipment/new"
                className="mt-5 inline-flex items-center gap-2 rounded-lg bg-[#1685ff] px-4 py-2.5 text-xs font-semibold text-white shadow-sm transition hover:bg-[#126bd0]"
              >
                <Plus className="size-4" />
                <span>Register First Machine</span>
              </Link>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/75 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="px-5 py-3.5">Asset Code</th>
                  <th className="px-5 py-3.5">Equipment & Model</th>
                  <th className="px-5 py-3.5">Category</th>
                  <th className="px-5 py-3.5">Plant Location</th>
                  <th className="px-5 py-3.5">Criticality</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5">Connectivity</th>
                  <th className="px-5 py-3.5 text-center">Components</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {equipment.map((item) => (
                  <tr key={item.id} className="transition hover:bg-slate-50/50">
                    {/* Asset Code */}
                    <td className="px-5 py-4 font-mono font-bold text-[#102c50]">
                      <Link
                        href={`/dashboard/equipment/${item.id}`}
                        className="hover:text-[#1685ff] hover:underline"
                      >
                        {item.asset_code}
                      </Link>
                    </td>

                    {/* Equipment Name & Model */}
                    <td className="px-5 py-4">
                      <div className="font-semibold text-slate-900">{item.equipment_name}</div>
                      <div className="mt-0.5 text-[11px] text-slate-500">
                        {item.manufacturer || 'Manufacturer unspecified'}
                        {item.model ? ` · ${item.model}` : ''}
                      </div>
                    </td>

                    {/* Category */}
                    <td className="px-5 py-4">
                      <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-700">
                        {item.category_name || 'General Equipment'}
                      </span>
                    </td>

                    {/* Location */}
                    <td className="px-5 py-4">
                      <div className="font-medium text-slate-800">{item.site_name || 'Assigned Site'}</div>
                      <div className="mt-0.5 text-[11px] text-slate-400">
                        {item.production_area_name ? item.production_area_name : 'No Area'}
                        {item.production_line_name ? ` → ${item.production_line_name}` : ''}
                      </div>
                    </td>

                    {/* Criticality */}
                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${getCriticalityBadge(
                          item.criticality
                        )}`}
                      >
                        {item.criticality}
                      </span>
                    </td>

                    {/* Lifecycle Status */}
                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${getLifecycleBadge(
                          item.lifecycle_status
                        )}`}
                      >
                        <span
                          className={`size-1.5 rounded-full ${
                            item.lifecycle_status === 'Active'
                              ? 'bg-emerald-500 animate-pulse'
                              : 'bg-slate-400'
                          }`}
                        />
                        {item.lifecycle_status}
                      </span>
                    </td>

                    {/* Connectivity */}
                    <td className="px-5 py-4">
                      <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-500">
                        <Lock className="size-3 text-slate-400" />
                        <span>{item.connection_status}</span>
                      </span>
                    </td>

                    {/* Components Count */}
                    <td className="px-5 py-4 text-center">
                      <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-700">
                        {item.components_count} {item.components_count === 1 ? 'part' : 'parts'}
                      </span>
                    </td>

                    {/* Actions */}
                    <td className="px-5 py-4 text-right">
                      <Link
                        href={`/dashboard/equipment/${item.id}`}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-[#1685ff] shadow-sm transition hover:border-[#1685ff] hover:bg-blue-50/50"
                      >
                        <span>Manage</span>
                        <ChevronRight className="size-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        {equipment.length > 0 && (
          <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50/50 px-5 py-3 text-xs text-slate-500">
            <span>
              Showing <span className="font-semibold text-slate-700">{equipment.length}</span> of{' '}
              <span className="font-semibold text-slate-700">{totalItems}</span> registered machines
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-40"
              >
                <ChevronLeft className="size-3" />
                <span>Prev</span>
              </button>
              <span className="text-xs font-medium text-slate-600">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-40"
              >
                <span>Next</span>
                <ChevronRight className="size-3" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
