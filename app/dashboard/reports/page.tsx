import { FileText, ArrowRight } from 'lucide-react'
import Link from 'next/link'

export default function ReportsPlaceholderPage() {
  return (
    <div className="flex min-h-[460px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center">
      <span className="grid size-14 place-items-center rounded-2xl bg-purple-50 text-purple-600">
        <FileText className="size-7" />
      </span>
      <span className="mt-4 rounded-full bg-purple-100 px-3 py-1 text-xs font-bold text-purple-700">
        Coming Soon
      </span>
      <h1 className="mt-3 text-xl font-bold text-[#102c50]">Regulatory & Reliability Reporting</h1>
      <p className="mt-2 max-w-md text-xs leading-relaxed text-slate-500">
        Audit trail logs, calibration status overviews, and GMP-aligned equipment health reports.
      </p>
      <Link
        href="/dashboard"
        className="mt-6 inline-flex items-center gap-2 rounded-lg bg-[#1685ff] px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-[#126bd0]"
      >
        <span>Back to Overview</span>
        <ArrowRight className="size-3.5" />
      </Link>
    </div>
  )
}

