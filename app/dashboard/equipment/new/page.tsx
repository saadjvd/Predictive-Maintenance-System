'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  Cpu,
  ArrowLeft,
  ArrowRight,
  Check,
  Building2,
  Layers,
  AlertTriangle,
  ShieldCheck,
  Plus,
  Lock,
  Loader2,
  Info,
} from 'lucide-react'
import apiClient, {
  SiteDetails,
  EquipmentCategoryItem,
  ProductionAreaItem,
  ProductionLineItem,
} from '@/lib/api-client'

export default function NewEquipmentPage() {
  const router = useRouter()
  const [currentStep, setCurrentStep] = useState(1)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Options loaded from backend
  const [sites, setSites] = useState<SiteDetails[]>([])
  const [categories, setCategories] = useState<EquipmentCategoryItem[]>([])
  const [areas, setAreas] = useState<ProductionAreaItem[]>([])
  const [lines, setLines] = useState<ProductionLineItem[]>([])
  const [loadingInitial, setLoadingInitial] = useState(true)

  // Quick modals for adding area or line inline
  const [showAddAreaModal, setShowAddAreaModal] = useState(false)
  const [newAreaName, setNewAreaName] = useState('')
  const [creatingArea, setCreatingArea] = useState(false)

  const [showAddLineModal, setShowAddLineModal] = useState(false)
  const [newLineName, setNewLineName] = useState('')
  const [newLineCode, setNewLineCode] = useState('')
  const [creatingLine, setCreatingLine] = useState(false)

  // Form State
  const [formData, setFormData] = useState({
    // Step 1: Identification
    asset_code: '',
    equipment_name: '',
    category_id: '',
    manufacturer: '',
    model: '',
    serial_number: '',

    // Step 2: Location
    site_id: '',
    production_area_id: '',
    production_line_id: '',

    // Step 3: Technical & Criticality
    installation_date: '',
    criticality: 'Medium' as 'Low' | 'Medium' | 'High' | 'Critical',
    description: '',
  })

  // Load initial sites and categories
  useEffect(() => {
    let mounted = true
    Promise.all([apiClient.getSites(), apiClient.getCategories()])
      .then(([sitesRes, catRes]) => {
        if (!mounted) return
        const loadedSites = sitesRes.data?.sites || []
        const loadedCats = catRes.data?.categories || []
        if (loadedSites.length > 0) {
          setSites(loadedSites)
          setFormData((prev) => ({ ...prev, site_id: loadedSites[0].id }))
        }
        if (loadedCats.length > 0) {
          setCategories(loadedCats)
          setFormData((prev) => ({ ...prev, category_id: loadedCats[0].id }))
        }
        setLoadingInitial(false)
      })
      .catch((err) => {
        if (!mounted) return
        setError(err.message || 'Failed to initialize equipment form')
        setLoadingInitial(false)
      })

    return () => {
      mounted = false
    }
  }, [])

  // Load production areas & lines when selected site changes
  useEffect(() => {
    if (!formData.site_id) {
      setAreas([])
      setLines([])
      return
    }

    apiClient.getProductionAreas(formData.site_id).then((res) => {
      if (res.data?.production_areas) {
        setAreas(res.data.production_areas)
      }
    })

    apiClient.getProductionLines({ site_id: formData.site_id }).then((res) => {
      if (res.data?.production_lines) {
        setLines(res.data.production_lines)
      }
    })
  }, [formData.site_id])

  // Handle Quick Area Creation
  const handleCreateArea = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newAreaName.trim() || !formData.site_id) return
    setCreatingArea(true)
    try {
      const res = await apiClient.createProductionArea({
        site_id: formData.site_id,
        name: newAreaName.trim(),
      })
      if (res.data?.production_area) {
        setAreas((prev) => [...prev, res.data!.production_area])
        setFormData((prev) => ({ ...prev, production_area_id: res.data!.production_area.id }))
        setShowAddAreaModal(false)
        setNewAreaName('')
      } else {
        alert(res.error || 'Failed to create production area')
      }
    } finally {
      setCreatingArea(false)
    }
  }

  // Handle Quick Line Creation
  const handleCreateLine = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newLineName.trim() || !formData.site_id) return
    setCreatingLine(true)
    try {
      const res = await apiClient.createProductionLine({
        site_id: formData.site_id,
        name: newLineName.trim(),
        line_code: newLineCode.trim() || undefined,
        production_area_id: formData.production_area_id || undefined,
      })
      if (res.data?.production_line) {
        setLines((prev) => [...prev, res.data!.production_line])
        setFormData((prev) => ({ ...prev, production_line_id: res.data!.production_line.id }))
        setShowAddLineModal(false)
        setNewLineName('')
        setNewLineCode('')
      } else {
        alert(res.error || 'Failed to create production line')
      }
    } finally {
      setCreatingLine(false)
    }
  }

  // Validation checks per step
  const validateStep = (step: number): boolean => {
    setError(null)
    if (step === 1) {
      if (!formData.asset_code.trim()) {
        setError('Asset Code is required (e.g., PKG-BLIST-001).')
        return false
      }
      if (!formData.equipment_name.trim()) {
        setError('Equipment Name is required (e.g., Blister Packaging Machine 01).')
        return false
      }
      if (!formData.category_id) {
        setError('Please select an equipment category.')
        return false
      }
    } else if (step === 2) {
      if (!formData.site_id) {
        setError('Please select the manufacturing site location.')
        return false
      }
    }
    return true
  }

  const handleNext = () => {
    if (validateStep(currentStep)) {
      setCurrentStep((prev) => Math.min(4, prev + 1))
    }
  }

  const handleBack = () => {
    setError(null)
    setCurrentStep((prev) => Math.max(1, prev - 1))
  }

  const handleSubmit = async () => {
    setError(null)
    setSubmitting(true)

    try {
      const res = await apiClient.createEquipment({
        asset_code: formData.asset_code.trim(),
        equipment_name: formData.equipment_name.trim(),
        category_id: formData.category_id,
        site_id: formData.site_id,
        production_area_id: formData.production_area_id || undefined,
        production_line_id: formData.production_line_id || undefined,
        manufacturer: formData.manufacturer.trim() || undefined,
        model: formData.model.trim() || undefined,
        serial_number: formData.serial_number.trim() || undefined,
        installation_date: formData.installation_date.trim() || undefined,
        criticality: formData.criticality,
        description: formData.description.trim() || undefined,
      })

      if (res.data?.equipment) {
        // Successfully created! Navigate to the equipment detail view
        router.push(`/dashboard/equipment/${res.data.equipment.id}`)
      } else {
        setError(res.error || 'Failed to register equipment')
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration request failed')
    } finally {
      setSubmitting(false)
    }
  }

  const selectedSiteObj = sites.find((s) => s.id === formData.site_id)
  const selectedCategoryObj = categories.find((c) => c.id === formData.category_id)
  const selectedAreaObj = areas.find((a) => a.id === formData.production_area_id)
  const selectedLineObj = lines.find((l) => l.id === formData.production_line_id)

  const steps = [
    { number: 1, title: 'Identification', desc: 'Asset code & model' },
    { number: 2, title: 'Plant Location', desc: 'Site, area & line' },
    { number: 3, title: 'Specifications', desc: 'Criticality & notes' },
    { number: 4, title: 'Review & Register', desc: 'Verification' },
  ]

  if (loadingInitial) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center text-slate-400">
        <Loader2 className="size-8 animate-spin text-[#1685ff]" />
        <p className="mt-3 text-xs font-semibold">Loading registration wizard...</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      {/* Back Link & Header */}
      <div className="flex flex-col gap-2">
        <Link
          href="/dashboard/equipment"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 transition hover:text-[#1685ff]"
        >
          <ArrowLeft className="size-3.5" />
          <span>Back to Equipment Registry</span>
        </Link>
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#1685ff]">
          <Cpu className="size-4" /> Universal Onboarding
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-[#102c50] sm:text-3xl">
          Register Pharmaceutical Machine
        </h1>
        <p className="text-xs text-slate-500">
          Step-by-step universal equipment onboarding for pharmaceutical manufacturing assets.
        </p>
      </div>

      {/* Wizard Progress Bar */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {steps.map((s) => {
          const isDone = currentStep > s.number
          const isCurrent = currentStep === s.number
          return (
            <div
              key={s.number}
              className={`flex items-center gap-3 rounded-xl border p-3 text-left transition ${
                isCurrent
                  ? 'border-[#1685ff] bg-blue-50/50 shadow-sm'
                  : isDone
                  ? 'border-emerald-200 bg-emerald-50/40'
                  : 'border-slate-200 bg-white opacity-60'
              }`}
            >
              <span
                className={`grid size-7 shrink-0 place-items-center rounded-lg text-xs font-bold ${
                  isCurrent
                    ? 'bg-[#1685ff] text-white'
                    : isDone
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-100 text-slate-600'
                }`}
              >
                {isDone ? <Check className="size-3.5" /> : s.number}
              </span>
              <div className="min-w-0">
                <div
                  className={`text-xs font-bold leading-tight ${
                    isCurrent ? 'text-[#102c50]' : isDone ? 'text-emerald-800' : 'text-slate-700'
                  }`}
                >
                  {s.title}
                </div>
                <div className="truncate text-[10px] text-slate-400">{s.desc}</div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Error Alert */}
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-700">
          <p className="font-semibold">Validation Issue</p>
          <p className="mt-0.5">{error}</p>
        </div>
      )}

      {/* Wizard Step Content Card */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        {/* STEP 1: IDENTIFICATION */}
        {currentStep === 1 && (
          <div className="space-y-6">
            <div className="border-b border-slate-100 pb-4">
              <h2 className="text-base font-bold text-[#102c50]">Step 1: Machine Identification</h2>
              <p className="text-xs text-slate-500">
                Provide core equipment identifiers, machine category, and manufacturer details.
              </p>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              {/* Asset Code */}
              <div>
                <label className="block text-xs font-semibold text-slate-700">
                  Asset Code <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. PKG-BLIST-001 or TAB-PRESS-04"
                  value={formData.asset_code}
                  onChange={(e) =>
                    setFormData({ ...formData, asset_code: e.target.value.toUpperCase() })
                  }
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 font-mono text-xs text-slate-800 placeholder-slate-400 outline-none transition focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
                />
                <p className="mt-1 text-[11px] text-slate-400">
                  Unique internal code used across plant maintenance logs.
                </p>
              </div>

              {/* Equipment Name */}
              <div>
                <label className="block text-xs font-semibold text-slate-700">
                  Equipment Name <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. High-Speed Blister Machine 01"
                  value={formData.equipment_name}
                  onChange={(e) => setFormData({ ...formData, equipment_name: e.target.value })}
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-xs text-slate-800 placeholder-slate-400 outline-none transition focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
                />
                <p className="mt-1 text-[11px] text-slate-400">Descriptive operational title.</p>
              </div>

              {/* Equipment Category */}
              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-slate-700">
                  Equipment Category <span className="text-rose-500">*</span>
                </label>
                <select
                  value={formData.category_id}
                  onChange={(e) => setFormData({ ...formData, category_id: e.target.value })}
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-xs text-slate-800 outline-none transition focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
                >
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.name} {cat.description ? `— ${cat.description}` : ''}
                    </option>
                  ))}
                </select>
              </div>

              {/* Manufacturer */}
              <div>
                <label className="block text-xs font-semibold text-slate-700">Manufacturer</label>
                <input
                  type="text"
                  placeholder="e.g. Uhlmann, Fette, Bosch, Glatt"
                  value={formData.manufacturer}
                  onChange={(e) => setFormData({ ...formData, manufacturer: e.target.value })}
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-xs text-slate-800 placeholder-slate-400 outline-none transition focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
                />
              </div>

              {/* Model */}
              <div>
                <label className="block text-xs font-semibold text-slate-700">Model / Type</label>
                <input
                  type="text"
                  placeholder="e.g. B 1240, FE55, Romaco Noack"
                  value={formData.model}
                  onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-xs text-slate-800 placeholder-slate-400 outline-none transition focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
                />
              </div>

              {/* Serial Number */}
              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-slate-700">Serial Number</label>
                <input
                  type="text"
                  placeholder="e.g. SN-99824-2023"
                  value={formData.serial_number}
                  onChange={(e) => setFormData({ ...formData, serial_number: e.target.value })}
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 font-mono text-xs text-slate-800 placeholder-slate-400 outline-none transition focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
                />
              </div>
            </div>
          </div>
        )}

        {/* STEP 2: PLANT LOCATION */}
        {currentStep === 2 && (
          <div className="space-y-6">
            <div className="border-b border-slate-100 pb-4">
              <h2 className="text-base font-bold text-[#102c50]">Step 2: Plant Location & Line</h2>
              <p className="text-xs text-slate-500">
                Assign this asset within your factory hierarchy (Site → Production Area → Production Line).
              </p>
            </div>

            <div className="space-y-5">
              {/* Site Selection */}
              <div>
                <label className="block text-xs font-semibold text-slate-700">
                  Manufacturing Site <span className="text-rose-500">*</span>
                </label>
                <select
                  value={formData.site_id}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      site_id: e.target.value,
                      production_area_id: '',
                      production_line_id: '',
                    })
                  }
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-xs text-slate-800 outline-none transition focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
                >
                  {sites.map((site) => (
                    <option key={site.id} value={site.id}>
                      {site.name} {site.location ? `(${site.location})` : ''}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-[11px] text-slate-400">
                  Every machine belongs to an authorized manufacturing site in your organization.
                </p>
              </div>

              {/* Production Area */}
              <div>
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-700">
                    Production Area (Optional)
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowAddAreaModal(true)}
                    className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#1685ff] hover:underline"
                  >
                    <Plus className="size-3" />
                    <span>Create Area</span>
                  </button>
                </div>
                <select
                  value={formData.production_area_id}
                  onChange={(e) =>
                    setFormData({ ...formData, production_area_id: e.target.value })
                  }
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-xs text-slate-800 outline-none transition focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
                >
                  <option value="">None / Standalone in Factory</option>
                  {areas.map((area) => (
                    <option key={area.id} value={area.id}>
                      {area.name}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-[11px] text-slate-400">
                  E.g., OSD Production, Packaging Hall A, Sterile Core, Clean Utilities.
                </p>
              </div>

              {/* Production Line */}
              <div>
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-700">
                    Production Line (Optional)
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowAddLineModal(true)}
                    className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#1685ff] hover:underline"
                  >
                    <Plus className="size-3" />
                    <span>Create Line</span>
                  </button>
                </div>
                <select
                  value={formData.production_line_id}
                  onChange={(e) =>
                    setFormData({ ...formData, production_line_id: e.target.value })
                  }
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-xs text-slate-800 outline-none transition focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
                >
                  <option value="">None / Standalone Machine</option>
                  {lines.map((line) => (
                    <option key={line.id} value={line.id}>
                      {line.name} {line.line_code ? `[${line.line_code}]` : ''}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-[11px] text-slate-400">
                  Production lines are optional for standalone equipment (e.g., HVAC, central chillers).
                </p>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: TECHNICAL & CRITICALITY */}
        {currentStep === 3 && (
          <div className="space-y-6">
            <div className="border-b border-slate-100 pb-4">
              <h2 className="text-base font-bold text-[#102c50]">
                Step 3: Criticality & Maintenance Notes
              </h2>
              <p className="text-xs text-slate-500">
                Define the asset criticality level and record commissioning information.
              </p>
            </div>

            <div className="space-y-5">
              {/* Criticality Radio Cards */}
              <div>
                <label className="block text-xs font-semibold text-slate-700">
                  Equipment Criticality Tier <span className="text-rose-500">*</span>
                </label>
                <div className="mt-2 grid gap-3 sm:grid-cols-2">
                  {[
                    {
                      tier: 'Critical',
                      badge: 'bg-rose-50 text-rose-700 border-rose-200',
                      desc: 'Direct impact on GMP batch release, sterile boundary, or entire plant stoppage.',
                    },
                    {
                      tier: 'High',
                      badge: 'bg-amber-50 text-amber-700 border-amber-200',
                      desc: 'Major production bottleneck with significant downtime financial risk.',
                    },
                    {
                      tier: 'Medium',
                      badge: 'bg-blue-50 text-blue-700 border-blue-200',
                      desc: 'Important asset with secondary buffer capacity or batch rerouting available.',
                    },
                    {
                      tier: 'Low',
                      badge: 'bg-slate-50 text-slate-700 border-slate-200',
                      desc: 'Auxiliary machine with negligible immediate impact on plant production.',
                    },
                  ].map((crit) => {
                    const isSelected = formData.criticality === crit.tier
                    return (
                      <label
                        key={crit.tier}
                        className={`flex cursor-pointer flex-col rounded-xl border p-3.5 transition ${
                          isSelected
                            ? 'border-[#1685ff] bg-blue-50/40 ring-2 ring-[#1685ff]/20'
                            : 'border-slate-200 bg-white hover:bg-slate-50'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span
                            className={`rounded-full border px-2.5 py-0.5 text-xs font-bold ${crit.badge}`}
                          >
                            {crit.tier}
                          </span>
                          <input
                            type="radio"
                            name="criticality"
                            checked={isSelected}
                            onChange={() =>
                              setFormData({
                                ...formData,
                                criticality: crit.tier as 'Low' | 'Medium' | 'High' | 'Critical',
                              })
                            }
                            className="size-4 text-[#1685ff]"
                          />
                        </div>
                        <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
                          {crit.desc}
                        </p>
                      </label>
                    )
                  })}
                </div>
              </div>

              {/* Commissioning / Installation Date */}
              <div>
                <label className="block text-xs font-semibold text-slate-700">
                  Commissioning / Installation Date
                </label>
                <input
                  type="date"
                  value={formData.installation_date}
                  onChange={(e) =>
                    setFormData({ ...formData, installation_date: e.target.value })
                  }
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-xs text-slate-800 outline-none transition focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
                />
              </div>

              {/* Description & Maintenance Notes */}
              <div>
                <label className="block text-xs font-semibold text-slate-700">
                  Description & Maintenance Notes
                </label>
                <textarea
                  rows={4}
                  placeholder="Record initial machine state, operating parameters, lubrication schedules, or baseline vibration thresholds..."
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-xs text-slate-800 placeholder-slate-400 outline-none transition focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
                />
              </div>
            </div>
          </div>
        )}

        {/* STEP 4: REVIEW & REGISTER */}
        {currentStep === 4 && (
          <div className="space-y-6">
            <div className="border-b border-slate-100 pb-4">
              <h2 className="text-base font-bold text-[#102c50]">Step 4: Review & Confirm Registration</h2>
              <p className="text-xs text-slate-500">
                Please verify equipment specifications before recording into the universal asset registry.
              </p>
            </div>

            {/* Structured Review Card */}
            <div className="grid gap-4 rounded-xl border border-slate-200 bg-slate-50/50 p-5 sm:grid-cols-2">
              <div>
                <span className="text-[11px] font-semibold text-slate-400">Asset Code</span>
                <p className="font-mono text-sm font-bold text-[#102c50]">{formData.asset_code}</p>
              </div>

              <div>
                <span className="text-[11px] font-semibold text-slate-400">Equipment Name</span>
                <p className="text-sm font-bold text-slate-800">{formData.equipment_name}</p>
              </div>

              <div>
                <span className="text-[11px] font-semibold text-slate-400">Category</span>
                <p className="text-xs font-semibold text-slate-700">
                  {selectedCategoryObj?.name || 'Unassigned'}
                </p>
              </div>

              <div>
                <span className="text-[11px] font-semibold text-slate-400">Manufacturer & Model</span>
                <p className="text-xs text-slate-700">
                  {formData.manufacturer || 'Unspecified'}
                  {formData.model ? ` · ${formData.model}` : ''}
                </p>
              </div>

              <div>
                <span className="text-[11px] font-semibold text-slate-400">Serial Number</span>
                <p className="font-mono text-xs text-slate-700">
                  {formData.serial_number || 'None'}
                </p>
              </div>

              <div>
                <span className="text-[11px] font-semibold text-slate-400">Installation Date</span>
                <p className="text-xs text-slate-700">
                  {formData.installation_date || 'Not specified'}
                </p>
              </div>

              <div>
                <span className="text-[11px] font-semibold text-slate-400">Plant Location</span>
                <p className="text-xs font-medium text-slate-700">
                  {selectedSiteObj?.name || 'Selected Site'}
                  {selectedAreaObj ? ` → ${selectedAreaObj.name}` : ''}
                  {selectedLineObj ? ` → ${selectedLineObj.name}` : ''}
                </p>
              </div>

              <div>
                <span className="text-[11px] font-semibold text-slate-400">Criticality</span>
                <p className="text-xs font-bold text-slate-800">{formData.criticality} Tier</p>
              </div>

              {formData.description && (
                <div className="sm:col-span-2 border-t border-slate-200/60 pt-3">
                  <span className="text-[11px] font-semibold text-slate-400">Description / Notes</span>
                  <p className="mt-1 text-xs text-slate-600">{formData.description}</p>
                </div>
              )}
            </div>

            {/* Industrial Connectivity Security Notice */}
            <div className="flex items-start gap-3 rounded-xl border border-blue-200 bg-blue-50/60 p-4 text-xs text-blue-900">
              <Lock className="mt-0.5 size-4 shrink-0 text-[#1685ff]" />
              <div>
                <p className="font-semibold">Protected Industrial Connectivity Baseline</p>
                <p className="mt-0.5 leading-relaxed text-blue-700">
                  This equipment asset will default safely to <strong>Not Configured</strong> for connection and{' '}
                  <strong>Not Started</strong> for monitoring. Industrial telemetry protocols (OPC UA, MQTT) and
                  predictive models will be activated in Phase 4 & Phase 5 without exposing unauthenticated endpoints.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="mt-8 flex items-center justify-between border-t border-slate-100 pt-5">
          {currentStep > 1 ? (
            <button
              type="button"
              onClick={handleBack}
              disabled={submitting}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50"
            >
              <ArrowLeft className="size-3.5" />
              <span>Back</span>
            </button>
          ) : (
            <div />
          )}

          {currentStep < 4 ? (
            <button
              type="button"
              onClick={handleNext}
              className="inline-flex items-center gap-2 rounded-lg bg-[#1685ff] px-5 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-[#126bd0]"
            >
              <span>Continue</span>
              <ArrowRight className="size-3.5" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitting}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-6 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-emerald-700 disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  <span>Registering Equipment...</span>
                </>
              ) : (
                <>
                  <Check className="size-4" />
                  <span>Register Equipment Asset</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Modal: Quick Add Area */}
      {showAddAreaModal && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-base font-bold text-[#102c50]">Create Production Area</h3>
            <p className="mt-1 text-xs text-slate-500">
              Add a production zone or hall for site: {selectedSiteObj?.name}.
            </p>
            <form onSubmit={handleCreateArea} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700">Area Name</label>
                <input
                  type="text"
                  placeholder="e.g. OSD Production or Packaging Hall 1"
                  value={newAreaName}
                  onChange={(e) => setNewAreaName(e.target.value)}
                  required
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-800 outline-none focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddAreaModal(false)}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingArea}
                  className="inline-flex items-center gap-1 rounded-lg bg-[#1685ff] px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-[#126bd0] disabled:opacity-50"
                >
                  {creatingArea && <Loader2 className="size-3 animate-spin" />}
                  <span>Save Area</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Quick Add Line */}
      {showAddLineModal && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-base font-bold text-[#102c50]">Create Production Line</h3>
            <p className="mt-1 text-xs text-slate-500">
              Add a manufacturing line for site: {selectedSiteObj?.name}.
            </p>
            <form onSubmit={handleCreateLine} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700">Line Name</label>
                <input
                  type="text"
                  placeholder="e.g. Blister Packaging Line 01"
                  value={newLineName}
                  onChange={(e) => setNewLineName(e.target.value)}
                  required
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-800 outline-none focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700">Line Code (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. LINE-PKG-01"
                  value={newLineCode}
                  onChange={(e) => setNewLineCode(e.target.value.toUpperCase())}
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-800 outline-none focus:border-[#1685ff] focus:ring-2 focus:ring-[#1685ff]/20"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddLineModal(false)}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingLine}
                  className="inline-flex items-center gap-1 rounded-lg bg-[#1685ff] px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-[#126bd0] disabled:opacity-50"
                >
                  {creatingLine && <Loader2 className="size-3 animate-spin" />}
                  <span>Save Line</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

