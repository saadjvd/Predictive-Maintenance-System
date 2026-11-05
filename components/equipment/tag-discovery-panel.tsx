'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Radio,
  Search,
  RefreshCw,
  Check,
  ChevronRight,
  ChevronDown,
  Layers,
  Lock,
  Activity,
  AlertCircle,
  Database,
  ArrowRight,
  ShieldCheck,
  Tag,
  CheckCircle2,
  ExternalLink,
} from 'lucide-react'
import apiClient, { DiscoveredTag } from '@/lib/api-client'

interface TagDiscoveryPanelProps {
  machineId: string
  machineName?: string
  initialEndpointUrl?: string
  onSelectionChange?: (selectedNodeIds: string[]) => void
  onProceedToMapping?: (selectedTags: DiscoveredTag[]) => void
}

export default function TagDiscoveryPanel({
  machineId,
  machineName = 'Equipment Asset',
  initialEndpointUrl = 'opc.tcp://127.0.0.1:48401/pharmapredict/server/',
  onSelectionChange,
  onProceedToMapping,
}: TagDiscoveryPanelProps) {
  const [endpointUrl, setEndpointUrl] = useState(initialEndpointUrl)
  const [tags, setTags] = useState<DiscoveredTag[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedNodeIds, setSelectedNodeIds] = useState<Set<string>>(new Set())
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())
  const [liveReadValues, setLiveReadValues] = useState<Record<string, { value: any; time: string }>>({})
  const [readingNode, setReadingNode] = useState<string | null>(null)

  // Fetch / Discover Tags
  const discoverTags = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiClient.getDiscoveredTags(machineId, {
        endpoint_url: endpointUrl.trim(),
        depth: 3,
        max_nodes: 100,
      })

      if (res.data?.tags) {
        setTags(res.data.tags)
        // Auto-expand top level nodes
        const topIds = new Set<string>()
        res.data.tags.forEach((t) => {
          topIds.add(t.node_id)
        })
        setExpandedNodes(topIds)
      } else {
        setError(res.error || 'Failed to discover OPC UA tags. Ensure the server or simulator is active.')
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Discovery connection failed')
    } finally {
      setLoading(false)
    }
  }, [machineId, endpointUrl])

  // Initial auto-discovery attempt
  useEffect(() => {
    discoverTags()
  }, [discoverTags])

  // Toggle selection
  const toggleSelect = (nodeId: string) => {
    const next = new Set(selectedNodeIds)
    if (next.has(nodeId)) {
      next.delete(nodeId)
    } else {
      next.add(nodeId)
    }
    setSelectedNodeIds(next)
    if (onSelectionChange) {
      onSelectionChange(Array.from(next))
    }
  }

  // Toggle node expand/collapse
  const toggleExpand = (nodeId: string) => {
    const next = new Set(expandedNodes)
    if (next.has(nodeId)) {
      next.delete(nodeId)
    } else {
      next.add(nodeId)
    }
    setExpandedNodes(next)
  }

  // Flatten all tags for search & selection count
  const getAllVariables = (nodes: DiscoveredTag[]): DiscoveredTag[] => {
    const vars: DiscoveredTag[] = []
    const traverse = (list: DiscoveredTag[]) => {
      list.forEach((item) => {
        if (item.node_class === 'Variable') {
          vars.push(item)
        }
        if (item.children && item.children.length > 0) {
          traverse(item.children)
        }
      })
    }
    traverse(nodes)
    return vars
  }

  const allVariables = getAllVariables(tags)
  const selectedCount = selectedNodeIds.size

  // Filter nodes matching search query
  const matchesSearch = (tag: DiscoveredTag, query: string): boolean => {
    if (!query) return true
    const q = query.toLowerCase()
    return (
      tag.browse_name.toLowerCase().includes(q) ||
      tag.display_name.toLowerCase().includes(q) ||
      tag.node_id.toLowerCase().includes(q) ||
      (tag.description || '').toLowerCase().includes(q) ||
      (tag.engineering_unit || '').toLowerCase().includes(q)
    )
  }

  // Handle proceed
  const handleProceed = () => {
    const selectedObjs = allVariables.filter((v) => selectedNodeIds.has(v.node_id))
    if (onProceedToMapping) {
      onProceedToMapping(selectedObjs)
    }
  }

  return (
    <div className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 border-b border-slate-100 pb-5 sm:flex-row sm:items-center">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#1685ff]">
            <Radio className="size-4" /> OPC UA Address Space
          </div>
          <h2 className="mt-1 text-xl font-bold text-[#102c50]">Discover Machine Signals</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Browse available PLC and sensor nodes from {machineName}. Select readable signals for predictive monitoring.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => discoverTags()}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50"
          >
            <RefreshCw className={`size-3.5 text-slate-400 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh Tags</span>
          </button>
        </div>
      </div>

      {/* Endpoint Input & Connection Bar */}
      <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex-1">
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Target OPC UA Server Endpoint
            </label>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="text"
                value={endpointUrl}
                onChange={(e) => setEndpointUrl(e.target.value)}
                placeholder="opc.tcp://127.0.0.1:48401/pharmapredict/server/"
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 font-mono text-xs text-slate-800 outline-none transition focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
              />
              <button
                onClick={() => discoverTags()}
                disabled={loading}
                className="shrink-0 rounded-lg bg-[#1685ff] px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-[#126bd0] disabled:opacity-50"
              >
                {loading ? 'Scanning...' : 'Scan Address Space'}
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2 border-t border-slate-200/60 pt-3 sm:border-0 sm:pt-0">
            <span className="flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
              <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>Read-Only Enforced</span>
            </span>
            <span className="flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600">
              <Lock className="size-3 text-slate-400" />
              <span>No Writes</span>
            </span>
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="mt-0.5 size-4 shrink-0 text-amber-600" />
            <div>
              <p className="font-bold">Tag Discovery Warning</p>
              <p className="mt-0.5 leading-relaxed">{error}</p>
              <p className="mt-1.5 text-[11px] text-amber-700">
                Tip: Run the pharmaceutical simulator or ensure port 48401 is accessible.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Search Bar & Tag Stats */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 size-3.5 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search discovered tags by name, NodeId, or unit..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-slate-50/50 py-1.5 pl-9 pr-4 text-xs text-slate-800 outline-none transition focus:border-[#1685ff] focus:bg-white focus:ring-2 focus:ring-[#1685ff]/20"
          />
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span>
            Discovered: <strong className="font-semibold text-slate-700">{allVariables.length}</strong> signals
          </span>
          <span className="text-slate-300">|</span>
          <span>
            Selected: <strong className="font-semibold text-[#1685ff]">{selectedCount}</strong>
          </span>
        </div>
      </div>

      {/* Hierarchical Tag Tree / Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400">
            <RefreshCw className="size-7 animate-spin text-[#1685ff]" />
            <p className="mt-2 text-xs font-semibold">Browsing OPC UA address space...</p>
            <p className="text-[11px] text-slate-400">Querying objects, variables, and engineering units</p>
          </div>
        ) : tags.length === 0 ? (
          <div className="flex min-h-[220px] flex-col items-center justify-center p-8 text-center">
            <div className="grid size-12 place-items-center rounded-xl bg-blue-50 text-[#1685ff]">
              <Database className="size-6" />
            </div>
            <h3 className="mt-3 text-sm font-bold text-[#102c50]">No tags discovered</h3>
            <p className="mt-1 max-w-sm text-xs text-slate-500">
              Verify your OPC UA endpoint address and click &ldquo;Scan Address Space&rdquo; to browse machinery nodes.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/75 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="w-10 px-4 py-3 text-center">Select</th>
                  <th className="px-4 py-3">Signal Name / Browse Path</th>
                  <th className="px-4 py-3">NodeId</th>
                  <th className="px-4 py-3">Class</th>
                  <th className="px-4 py-3">Data Type</th>
                  <th className="px-4 py-3">Engineering Unit</th>
                  <th className="px-4 py-3">Access</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tags.map((tag) => (
                  <TagRow
                    key={tag.node_id}
                    tag={tag}
                    level={0}
                    searchQuery={searchQuery}
                    selectedNodeIds={selectedNodeIds}
                    expandedNodes={expandedNodes}
                    onToggleSelect={toggleSelect}
                    onToggleExpand={toggleExpand}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Bottom Action Tray */}
      <div className="flex flex-col justify-between gap-3 border-t border-slate-100 pt-4 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Tag className="size-4 text-[#1685ff]" />
          <span>
            {selectedCount === 0 ? (
              'Select signals above to configure predictive maintenance parameters.'
            ) : (
              <>
                <strong className="font-semibold text-slate-800">{selectedCount}</strong>{' '}
                {selectedCount === 1 ? 'signal' : 'signals'} chosen for machine onboarding.
              </>
            )}
          </span>
        </div>

        <button
          onClick={handleProceed}
          disabled={selectedCount === 0}
          className="inline-flex items-center gap-2 rounded-lg bg-[#1685ff] px-5 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-[#126bd0] disabled:cursor-not-allowed disabled:opacity-40"
        >
          <span>Continue to Signal Mapping</span>
          <ArrowRight className="size-3.5" />
        </button>
      </div>
    </div>
  )
}

// =============================================================================
// RECURSIVE TAG ROW COMPONENT
// =============================================================================

function TagRow({
  tag,
  level,
  searchQuery,
  selectedNodeIds,
  expandedNodes,
  onToggleSelect,
  onToggleExpand,
}: {
  tag: DiscoveredTag
  level: number
  searchQuery: string
  selectedNodeIds: Set<string>
  expandedNodes: Set<string>
  onToggleSelect: (nodeId: string) => void
  onToggleExpand: (nodeId: string) => void
}) {
  const isExpanded = expandedNodes.has(tag.node_id)
  const isSelected = selectedNodeIds.has(tag.node_id)
  const isVariable = tag.node_class === 'Variable'
  const hasChildren = tag.children && tag.children.length > 0

  return (
    <>
      <tr className={`transition hover:bg-slate-50/60 ${isSelected ? 'bg-blue-50/40' : ''}`}>
        {/* Selection Checkbox */}
        <td className="px-4 py-3 text-center">
          {isVariable && (
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => onToggleSelect(tag.node_id)}
              className="size-4 rounded text-[#1685ff] focus:ring-[#1685ff]/30 cursor-pointer"
            />
          )}
        </td>

        {/* Signal Name / Browse Name */}
        <td className="px-4 py-3" style={{ paddingLeft: `${Math.max(16, level * 24 + 16)}px` }}>
          <div className="flex items-center gap-2">
            {hasChildren ? (
              <button
                type="button"
                onClick={() => onToggleExpand(tag.node_id)}
                className="text-slate-400 hover:text-slate-600"
              >
                {isExpanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
              </button>
            ) : (
              <span className="size-3.5" />
            )}

            <div>
              <span className="font-semibold text-slate-800">{tag.display_name}</span>
              {tag.browse_name !== tag.display_name && (
                <span className="ml-1 text-[11px] text-slate-400">({tag.browse_name})</span>
              )}
              {tag.description && (
                <div className="text-[10px] text-slate-400">{tag.description}</div>
              )}
            </div>
          </div>
        </td>

        {/* NodeId */}
        <td className="px-4 py-3">
          <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[10px] text-slate-600">
            {tag.node_id}
          </span>
        </td>

        {/* Node Class */}
        <td className="px-4 py-3">
          <span
            className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
              tag.node_class === 'Variable'
                ? 'bg-blue-50 text-blue-700'
                : 'bg-slate-100 text-slate-600'
            }`}
          >
            {tag.node_class}
          </span>
        </td>

        {/* Data Type */}
        <td className="px-4 py-3">
          {tag.data_type ? (
            <span className="font-mono text-[11px] text-slate-700">{tag.data_type}</span>
          ) : (
            <span className="text-slate-300">—</span>
          )}
        </td>

        {/* Engineering Unit */}
        <td className="px-4 py-3">
          {tag.engineering_unit ? (
            <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 border border-emerald-100">
              {tag.engineering_unit}
            </span>
          ) : (
            <span className="text-slate-300">—</span>
          )}
        </td>

        {/* Access Level */}
        <td className="px-4 py-3">
          {isVariable ? (
            <span className="inline-flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
              <Check className="size-3 text-emerald-600" />
              <span>Read-Only</span>
            </span>
          ) : (
            <span className="text-slate-300">—</span>
          )}
        </td>
      </tr>

      {/* Render Expanded Children */}
      {isExpanded &&
        hasChildren &&
        tag.children!.map((child) => (
          <TagRow
            key={child.node_id}
            tag={child}
            level={level + 1}
            searchQuery={searchQuery}
            selectedNodeIds={selectedNodeIds}
            expandedNodes={expandedNodes}
            onToggleSelect={onToggleSelect}
            onToggleExpand={onToggleExpand}
          />
        ))}
    </>
  )
}

