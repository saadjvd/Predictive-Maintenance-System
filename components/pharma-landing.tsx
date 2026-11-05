'use client'

import { useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Canvas, useFrame } from '@react-three/fiber'
import { Float, MeshTransmissionMaterial, OrbitControls } from '@react-three/drei'
import type { Group, Mesh } from 'three'
import {
  Activity,
  ArrowRight,
  Bot,
  Check,
  ChevronDown,
  CircleCheck,
  Clock3,
  Cpu,
  Gauge,
  Menu,
  Network,
  Pill,
  ScanLine,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
  Wrench,
  X,
  Zap,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const sensorData = [
  { time: '08:00', value: 24 },
  { time: '09:00', value: 29 },
  { time: '10:00', value: 27 },
  { time: '11:00', value: 34 },
  { time: '12:00', value: 31 },
  { time: '13:00', value: 39 },
  { time: '14:00', value: 36 },
]

const challenges = [
  ['Reduce Unplanned Downtime', 'Detect abnormal equipment behavior before it develops into an unexpected breakdown.', Clock3],
  ['Optimize Maintenance Costs', 'Support smarter maintenance planning using actual equipment condition.', Wrench],
  ['Protect Production Quality', 'Identify equipment deterioration that may affect manufacturing reliability.', ShieldCheck],
  ['Improve Maintenance Visibility', 'Centralize equipment health, diagnostic alerts, and maintenance information.', TrendingUp],
] as const

const capabilities = [
  ['Real-Time Equipment Monitoring', 'Monitor temperature, vibration, motor current, speed, pressure, and alarm events.', Activity],
  ['AI-Powered Anomaly Detection', 'Identify unusual operating patterns against established machine baselines.', ScanLine],
  ['Predictive Maintenance Intelligence', 'Estimate defined failure risks when sufficient data and validated models are available.', Gauge],
  ['Intelligent Root Cause Analysis', 'Investigate possible faults using equipment history and technical knowledge.', Bot],
  ['Maintenance Recommendations', 'Generate evidence-supported inspection recommendations for engineer review.', Check],
  ['Universal Machine Integration', 'Connect different pharmaceutical machines with configurable adapters.', Network],
] as const

const primaryButton = 'group relative isolate inline-flex items-center justify-center overflow-hidden rounded-lg bg-[#1685ff] px-5 py-3.5 text-sm font-semibold text-white shadow-xl shadow-blue-500/20 transition duration-250 ease-out hover:-translate-y-0.5 hover:bg-[#3a98ff] hover:shadow-[0_10px_28px_rgba(22,133,255,.28)] active:scale-[.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#61b4ff] focus-visible:ring-offset-2 before:absolute before:inset-y-0 before:-left-1/2 before:w-1/3 before:-skew-x-12 before:bg-gradient-to-r before:from-transparent before:via-white/30 before:to-transparent before:opacity-0 before:transition-transform before:duration-600 before:ease-out hover:before:translate-x-[440%] hover:before:opacity-100 motion-reduce:transition-none motion-reduce:hover:translate-y-0 motion-reduce:hover:before:translate-x-0'
const secondaryButton = 'group inline-flex items-center justify-center rounded-lg border border-white/25 px-5 py-3.5 text-center text-sm font-semibold text-white transition duration-250 ease-out hover:-translate-y-0.5 hover:border-[#61b4ff]/70 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#61b4ff] focus-visible:ring-offset-2 motion-reduce:transition-none motion-reduce:hover:translate-y-0'
const arrowMotion = 'ml-2 inline size-4 transition-transform duration-200 ease-out group-hover:translate-x-1 motion-reduce:transition-none motion-reduce:transform-none'

const equipment = [
  ['Blister Packaging Machines', 'Track sealing, forming, and drive systems.', 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=900&q=85'],
  ['Tablet Compression Machines', 'Monitor compression force and cycle health.', 'https://images.unsplash.com/photo-1587854692152-cbe660dbde88?auto=format&fit=crop&w=900&q=85'],
  ['Capsule Filling Machines', 'Surface fill-rate and dosing anomalies earlier.', 'https://images.unsplash.com/photo-1471864190281-a93a3070b6de?auto=format&fit=crop&w=900&q=85'],
  ['Mixers & Granulators', 'Understand motor load, torque, and process patterns.', 'https://images.unsplash.com/photo-1576671081837-49000212a370?auto=format&fit=crop&w=900&q=85'],
  ['Liquid Filling Systems', 'Protect precision dosing and line availability.', 'https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?auto=format&fit=crop&w=900&q=85'],
  ['HVAC & Pharmaceutical Utilities', 'Keep critical environmental systems visible.', 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=900&q=85'],
]

function Logo() {
  return <a href="#top" className="flex items-center gap-3" aria-label="PharmaPredict AI home"><span className="grid size-10 place-items-center rounded-xl bg-[#0d9488] text-white shadow-lg shadow-teal-900/20"><Pill className="size-5" /></span><span className="text-[15px] font-semibold tracking-[-0.02em] text-[#102c50]">PharmaPredict <span className="text-[#1685ff]">AI</span></span></a>
}

function Molecule({ position, scale = 1, color = '#61b4ff' }: { position: [number, number, number]; scale?: number; color?: string }) {
  const group = useRef<Group>(null)
  useFrame((state) => {
    if (group.current) group.current.rotation.y = state.clock.elapsedTime * 0.18
  })
  return <group ref={group} position={position} scale={scale}>
    <mesh><sphereGeometry args={[0.22, 24, 24]} /><meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.7} /></mesh>
    {[[-0.9, 0.5, 0], [0.8, 0.55, 0], [0, -0.85, 0]].map((bond, index) => <group key={index} rotation={[0, 0, index * 1.8 - 0.5]}>
      <mesh position={[0, 0.55, 0]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[0.035, 0.035, 1.1, 10]} /><meshStandardMaterial color="#b8e8ff" transparent opacity={0.7} /></mesh>
      <mesh position={bond as [number, number, number]}><sphereGeometry args={[0.13, 16, 16]} /><meshStandardMaterial color="#d8f4ff" emissive="#1685ff" emissiveIntensity={0.4} /></mesh>
    </group>)}
  </group>
}

function HeroSceneContents() {
  const molecule = useRef<Group>(null)
  const ring = useRef<Mesh>(null)
  useFrame((state) => {
    if (molecule.current) molecule.current.rotation.y = state.clock.elapsedTime * 0.12
    if (ring.current) ring.current.rotation.z = state.clock.elapsedTime * 0.08
  })
  return <>
    <ambientLight intensity={1.2} />
    <pointLight position={[2, 2, 4]} intensity={18} color="#b8e8ff" />
    <pointLight position={[-3, -1, 2]} intensity={10} color="#1685ff" />
    <Float speed={1.4} rotationIntensity={0.35} floatIntensity={0.7}>
      <group ref={molecule}>
        <mesh><icosahedronGeometry args={[1.35, 2]} /><MeshTransmissionMaterial backside thickness={0.35} roughness={0.12} transmission={0.72} chromaticAberration={0.08} color="#1685ff" /></mesh>
        <mesh ref={ring} rotation={[Math.PI / 2.4, 0.2, 0]}><torusGeometry args={[1.9, 0.025, 16, 96]} /><meshBasicMaterial color="#61b4ff" transparent opacity={0.65} /></mesh>
        <Molecule position={[0, 0, 1.5]} scale={0.72} />
        <Molecule position={[-1.7, 0.8, -0.2]} scale={0.5} color="#2dd4bf" />
        <Molecule position={[1.6, -0.9, -0.3]} scale={0.42} color="#8bd3ff" />
      </group>
    </Float>
    <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={0.35} />
  </>
}

function HeroScene() {
  return <Canvas camera={{ position: [0, 0, 6], fov: 42 }} dpr={[1, 1.5]}><HeroSceneContents /></Canvas>
}

function DashboardPreview() {
  return <motion.div initial={{ opacity: 0, y: 24, rotate: 1 }} animate={{ opacity: 1, y: 0, rotate: 0 }} transition={{ duration: .8, delay: .2 }} className="relative mx-auto w-full max-w-[590px] rounded-2xl border border-white/70 bg-white/95 p-3 shadow-[0_30px_90px_rgba(4,22,48,.3)] backdrop-blur sm:p-4">
    <div className="rounded-xl border border-slate-200 bg-[#f8fafc] p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3 border-b border-slate-200 pb-4"><div><div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[.16em] text-[#1685ff]"><span className="size-1.5 rounded-full bg-emerald-500" /> Illustrative demo data</div><h3 className="mt-2 text-sm font-bold text-[#102c50] sm:text-base">Equipment Overview</h3><p className="mt-1 text-xs text-slate-500">Blister Machine — Line 1</p></div><span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">Running</span></div>
      <div className="grid gap-3 py-4 sm:grid-cols-[.85fr_1.15fr]"><div className="rounded-xl bg-[#102c50] p-4 text-white"><div className="flex items-center justify-between text-xs text-slate-300"><span>Equipment health</span><CircleCheck className="size-4 text-emerald-400" /></div><div className="mt-5 flex items-end gap-2"><span className="text-5xl font-semibold tracking-[-.06em]">92</span><span className="mb-2 text-sm text-slate-300">/ 100</span></div><div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/15"><div className="h-full w-[92%] rounded-full bg-[#34d399]" /></div><p className="mt-3 text-[11px] text-slate-300">Stable operating condition</p></div><div className="grid grid-cols-2 gap-2">{[['Temperature','36.4 °C'],['Vibration','0.28 mm/s'],['Current','12.6 A'],['Speed','145 RPM']].map(([label,value]) => <div key={label} className="rounded-xl border border-slate-200 bg-white p-3"><span className="text-[10px] font-medium text-slate-500">{label}</span><p className="mt-1 text-sm font-bold text-[#102c50]">{value}</p><div className="mt-3 h-1 rounded-full bg-slate-100"><div className="h-full w-2/3 rounded-full bg-[#1685ff]" /></div></div>)}</div></div>
      <div className="grid gap-3 sm:grid-cols-[1.25fr_.75fr]"><div className="rounded-xl border border-slate-200 bg-white p-3"><div className="mb-2 flex items-center justify-between"><span className="text-xs font-semibold text-[#102c50]">Vibration trend</span><span className="text-[10px] text-slate-400">Last 6 hours</span></div><div className="h-28"><ResponsiveContainer width="100%" height="100%"><AreaChart data={sensorData}><defs><linearGradient id="vibration" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#1685ff" stopOpacity={.3}/><stop offset="100%" stopColor="#1685ff" stopOpacity={0}/></linearGradient></defs><XAxis dataKey="time" hide/><YAxis hide domain={[0,50]}/><Tooltip contentStyle={{fontSize: 11, borderRadius: 8, border: '1px solid #e2e8f0'}}/><Area type="monotone" dataKey="value" stroke="#1685ff" strokeWidth={2} fill="url(#vibration)" /></AreaChart></ResponsiveContainer></div></div><div className="rounded-xl border border-blue-100 bg-blue-50/70 p-3"><div className="flex items-center gap-2 text-xs font-semibold text-[#102c50]"><Sparkles className="size-3.5 text-[#1685ff]" /> AI diagnostic</div><p className="mt-3 text-[11px] leading-relaxed text-slate-600">Elevated vibration trend detected. Inspection recommended.</p><button className="group mt-3 text-[11px] font-bold text-[#1685ff] transition-colors duration-200 hover:text-[#126bd0] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#61b4ff] focus-visible:ring-offset-2 motion-reduce:transition-none">Review insight <ArrowRight className="ml-1 inline size-3 transition-transform duration-200 group-hover:translate-x-1 motion-reduce:transition-none" /></button></div></div>
      <p className="mt-3 text-center text-[10px] text-slate-400">Preview only · No equipment is connected</p>
    </div>
  </motion.div>
}

function SectionHeading({ eyebrow, title, copy, light = false }: { eyebrow: string; title: string; copy?: string; light?: boolean }) { return <div className="max-w-2xl"><p className={`text-xs font-bold uppercase tracking-[.18em] ${light ? 'text-cyan-300' : 'text-[#1685ff]'}`}>{eyebrow}</p><h2 className={`mt-4 text-3xl font-semibold tracking-[-.045em] sm:text-4xl lg:text-[46px] ${light ? 'text-white' : 'text-[#102c50]'}`}>{title}</h2>{copy && <p className={`mt-5 max-w-xl text-base leading-7 ${light ? 'text-slate-300' : 'text-slate-600'}`}>{copy}</p>}</div> }

function DemoModal({ onClose }: { onClose: () => void }) { const [submitted, setSubmitted] = useState(false); return <div className="fixed inset-0 z-50 grid place-items-center bg-[#071b31]/70 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="demo-title"><div className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl sm:p-8"><button onClick={onClose} className="absolute right-4 top-4 rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Close demo request"><X className="size-5" /></button>{submitted ? <div className="py-8 text-center"><span className="mx-auto grid size-14 place-items-center rounded-full bg-emerald-50 text-emerald-600"><Check /></span><h2 className="mt-5 text-2xl font-bold text-[#102c50]">Thanks for your interest</h2><p className="mt-3 text-sm leading-6 text-slate-600">This demo form is currently in demo mode. Your message has not been sent, but the form is ready to connect to a real endpoint.</p><button onClick={onClose} className="mt-6 rounded-lg bg-[#1685ff] px-5 py-3 text-sm font-semibold text-white">Close</button></div> : <><p className="text-xs font-bold uppercase tracking-[.18em] text-[#1685ff]">See the platform</p><h2 id="demo-title" className="mt-3 text-3xl font-semibold tracking-tight text-[#102c50]">Book a demo</h2><p className="mt-3 text-sm leading-6 text-slate-600">Tell us a little about your manufacturing environment and we&apos;ll tailor the conversation.</p><form onSubmit={(e) => { e.preventDefault(); setSubmitted(true) }} className="mt-6 grid gap-4"><div className="grid gap-4 sm:grid-cols-2"><label className="grid gap-2 text-sm font-medium text-slate-700">Full name<input required className="rounded-lg border border-slate-200 px-3 py-2.5 outline-none focus:border-[#1685ff] focus:ring-2 focus:ring-blue-100" /></label><label className="grid gap-2 text-sm font-medium text-slate-700">Company name<input required className="rounded-lg border border-slate-200 px-3 py-2.5 outline-none focus:border-[#1685ff] focus:ring-2 focus:ring-blue-100" /></label></div><div className="grid gap-4 sm:grid-cols-2"><label className="grid gap-2 text-sm font-medium text-slate-700">Work email<input required type="email" className="rounded-lg border border-slate-200 px-3 py-2.5 outline-none focus:border-[#1685ff] focus:ring-2 focus:ring-blue-100" /></label><label className="grid gap-2 text-sm font-medium text-slate-700">Job role<input required className="rounded-lg border border-slate-200 px-3 py-2.5 outline-none focus:border-[#1685ff] focus:ring-2 focus:ring-blue-100" /></label></div><label className="grid gap-2 text-sm font-medium text-slate-700">Message<textarea rows={4} className="resize-none rounded-lg border border-slate-200 px-3 py-2.5 outline-none focus:border-[#1685ff] focus:ring-2 focus:ring-blue-100" placeholder="What would you like to explore?" /></label><button className="rounded-lg bg-[#1685ff] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#126bd0]">Request demo <ArrowRight className="ml-2 inline size-4" /></button><p className="text-center text-xs text-slate-400">Demo mode · No message will be sent</p></form></>}</div></div> }

export default function PharmaLanding() { const [menuOpen, setMenuOpen] = useState(false); const [modalOpen, setModalOpen] = useState(false); const nav = [['Platform','#platform'],['How It Works','#how-it-works'],['Features','#features'],['Equipment','#equipment'],['Compliance','#compliance'],['Contact','#contact']]; return <main id="top" className="overflow-hidden bg-[#f8fafc] text-slate-900"><header className="fixed inset-x-0 top-0 z-40 border-b border-slate-200/70 bg-white/85 backdrop-blur-xl"><div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 lg:px-8"><Logo/><nav className="hidden items-center gap-7 lg:flex">{nav.map(([label,href]) => <a key={label} href={href} className="group relative text-[13px] font-medium text-slate-600 transition duration-200 hover:text-[#1685ff] after:absolute after:-bottom-2 after:left-0 after:h-px after:w-0 after:bg-[#1685ff] after:transition-all after:duration-200 after:content-[''] hover:after:w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#61b4ff] motion-reduce:transition-none motion-reduce:after:transition-none">{label}</a>)}</nav><div className="hidden items-center gap-3 lg:flex"><a href="/login" className="rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-semibold text-[#102c50] transition duration-200 hover:border-[#1685ff] hover:bg-blue-50/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#61b4ff] focus-visible:ring-offset-2 motion-reduce:transition-none">Sign in</a><button onClick={() => setModalOpen(true)} className={`${primaryButton} px-4 py-2.5 shadow-lg`}>Book a demo <ArrowRight className={arrowMotion} /></button></div><button onClick={() => setMenuOpen(!menuOpen)} className="rounded-lg p-2 text-[#102c50] lg:hidden" aria-label="Toggle navigation menu" aria-expanded={menuOpen}>{menuOpen ? <X /> : <Menu />}</button></div>{menuOpen && <nav className="grid gap-1 border-t border-slate-100 bg-white px-5 py-4 lg:hidden">{nav.map(([label,href]) => <a onClick={() => setMenuOpen(false)} key={label} href={href} className="rounded-lg px-3 py-3 text-sm font-medium text-slate-600 hover:bg-slate-50">{label}</a>)}<a href="/login" onClick={() => setMenuOpen(false)} className="rounded-lg border border-slate-200 px-3 py-2.5 text-center text-sm font-semibold text-[#102c50] hover:bg-slate-50">Sign in</a><button onClick={() => { setMenuOpen(false); setModalOpen(true) }} className={`${primaryButton} mt-2 w-full py-3`}>Book a demo <ArrowRight className={arrowMotion} /></button></nav>}</header>

<section className="relative isolate flex min-h-[790px] items-center pt-28"><div className="absolute inset-0 -z-20 bg-[#092342]" /><div className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,rgba(4,22,48,.96)_0%,rgba(4,22,48,.78)_35%,rgba(4,22,48,.3)_75%,rgba(4,22,48,.55)_100%)]" /><div className="absolute inset-0 -z-10 bg-cover bg-center opacity-60 mix-blend-screen" style={{ backgroundImage: "url('/pharma-hero.png')" }} /><div className="pointer-events-none absolute inset-y-0 right-0 top-16 hidden w-[58%] opacity-90 lg:block" aria-hidden="true"><HeroScene /></div><div className="mx-auto grid w-full max-w-7xl items-center gap-14 px-5 py-16 lg:grid-cols-[.9fr_1.1fr] lg:px-8"><motion.div initial={{opacity:0,x:-24}} animate={{opacity:1,x:0}} transition={{duration:.7}}><p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[.2em] text-cyan-300"><span className="size-2 rounded-full bg-cyan-300" /> AI-powered pharmaceutical maintenance</p><h1 className="mt-6 max-w-2xl text-5xl font-semibold leading-[1.02] tracking-[-.06em] text-white sm:text-6xl lg:text-[68px]">Smarter machines.<br/>Safer production.<br/><span className="text-[#61b4ff]">Predictable maintenance.</span></h1><p className="mt-7 max-w-xl text-base leading-7 text-slate-300 sm:text-lg">Connect pharmaceutical equipment, monitor machine performance in real time, and make smarter maintenance decisions with AI-powered diagnostics and predictive intelligence.</p><div className="mt-8 flex flex-col gap-3 sm:flex-row"><button onClick={() => setModalOpen(true)} className={primaryButton}>Book a demo <ArrowRight className={arrowMotion} /></button><a href="#platform" className={secondaryButton}>Explore platform <ArrowRight className={arrowMotion} /></a></div><div className="mt-10 grid gap-3 text-sm text-slate-300 sm:grid-cols-3"><span className="flex items-center gap-2"><CircleCheck className="size-4 text-cyan-300" /> Reduce downtime</span><span className="flex items-center gap-2"><CircleCheck className="size-4 text-cyan-300" /> Optimize costs</span><span className="flex items-center gap-2"><CircleCheck className="size-4 text-cyan-300" /> Improve reliability</span></div></motion.div><DashboardPreview/></div></section>

<section className="bg-white px-5 py-24 lg:px-8" id="platform"><div className="mx-auto max-w-7xl"><SectionHeading eyebrow="Built for pharmaceutical manufacturing" title="Solve critical production challenges" copy="Unplanned equipment failures can interrupt production, increase operating expenses, and complicate maintenance planning. PharmaPredict AI helps teams identify developing equipment problems earlier."/><div className="mt-14 grid gap-4 md:grid-cols-2 lg:grid-cols-4">{challenges.map(([title,copy,Icon],i) => <motion.article whileHover={{y:-5}} transition={{duration:.2}} key={title} className="rounded-2xl border border-slate-200 bg-[#f8fafc] p-6"><span className="grid size-11 place-items-center rounded-xl bg-blue-50 text-[#1685ff]"><Icon className="size-5" /></span><h3 className="mt-6 font-semibold text-[#102c50]">{title}</h3><p className="mt-3 text-sm leading-6 text-slate-600">{copy}</p><span className="mt-6 block h-px w-8 bg-[#1685ff]" /></motion.article>)}</div></div></section>

<section className="relative overflow-hidden bg-[#102c50] px-5 py-24 lg:px-8" id="features"><div className="absolute -right-24 top-10 size-80 rounded-full bg-[#1685ff]/20 blur-3xl"/><div className="relative mx-auto max-w-7xl"><SectionHeading light eyebrow="Powered by real machine data" title="Turn equipment data into actionable insights" copy="PharmaPredict AI combines continuous equipment monitoring, predictive analytics, and AI-assisted diagnostics within one intelligent maintenance platform."/><div className="mt-14 grid gap-x-8 gap-y-10 md:grid-cols-2 lg:grid-cols-3">{capabilities.map(([title,copy,Icon]) => <div key={title} className="border-t border-white/15 pt-5"><Icon className="size-5 text-cyan-300"/><h3 className="mt-5 font-semibold text-white">{title}</h3><p className="mt-3 text-sm leading-6 text-slate-300">{copy}</p></div>)}</div></div></section>

<section className="bg-[#f8fafc] px-5 py-24 lg:px-8" id="how-it-works"><div className="mx-auto max-w-7xl"><SectionHeading eyebrow="A clearer path to reliability" title="From machine signals to smarter maintenance"/><div className="relative mt-14 grid gap-8 md:grid-cols-4">{([['01','Connect','Register equipment and connect available machine signals through OPC UA or supported integrations.',Network],['02','Monitor','Collect and validate operating data while tracking machine conditions.',Activity],['03','Analyze','Detect abnormal patterns and investigate possible equipment problems.',Sparkles],['04','Act','Review recommendations, investigate faults, and plan approved maintenance.',Zap]] as [string, string, string, React.ComponentType<{ className?: string }>][]).map(([num,title,copy,Icon],i) => <div key={title} className="relative"><div className="flex items-center gap-4"><span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-white text-[#1685ff] shadow-sm ring-1 ring-slate-200"><Icon className="size-5" /></span><span className="text-xs font-bold tracking-[.18em] text-[#1685ff]">STEP {num}</span></div><h3 className="mt-5 font-semibold text-[#102c50]">{title}</h3><p className="mt-3 text-sm leading-6 text-slate-600">{copy}</p>{i < 3 && <span className="absolute left-12 top-6 hidden h-px w-[calc(100%-3rem)] bg-blue-200 md:block" />}</div>)}</div></div></section>

<section className="bg-white px-5 py-24 lg:px-8" id="equipment"><div className="mx-auto max-w-7xl"><SectionHeading eyebrow="Universal equipment intelligence" title="From production to packaging" copy="One configurable platform designed to monitor different pharmaceutical machines, manufacturers, and production environments."/><div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{equipment.map(([title,copy,image]) => <motion.article whileHover={{y:-5}} key={title} className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="relative h-48 overflow-hidden bg-slate-100"><img src={image} alt="" className="size-full object-cover grayscale-[20%] transition duration-500 group-hover:scale-105 group-hover:grayscale-0"/><div className="absolute inset-0 bg-gradient-to-t from-[#102c50]/65 to-transparent"/></div><div className="p-5"><h3 className="font-semibold text-[#102c50]">{title}</h3><p className="mt-2 text-sm text-slate-600">{copy}</p></div></motion.article>)}</div><p className="mt-8 text-sm text-slate-500">Compatibility and predictive capabilities depend on equipment connectivity, available signals, and model validation. <a href="#contact" className="font-semibold text-[#1685ff]">Explore supported equipment <ArrowRight className="ml-1 inline size-3" /></a></p></div></section>

<section className="bg-[#edf5fb] px-5 py-24 lg:px-8"><div className="mx-auto max-w-7xl"><SectionHeading eyebrow="Intelligence with evidence" title="More than monitoring. Intelligent diagnostics." copy="Make advanced AI understandable for factory managers and maintenance engineers."/><div className="mt-14 grid gap-3 md:grid-cols-6">{[['Machine data','Signals from connected equipment'],['Machine learning','Validated patterns and predictions'],['LangGraph agents','Coordinated diagnostic workflows'],['RAG retrieval','Manuals, SOPs, and records'],['Recommendations','Evidence-supported next steps'],['Engineer review','Human approval stays central']].map(([title,copy],i) => <div key={title} className="relative rounded-2xl border border-blue-100 bg-white p-5 md:col-span-2 lg:col-span-1"><span className="text-xs font-bold text-[#1685ff]">0{i+1}</span><h3 className="mt-5 text-sm font-semibold text-[#102c50]">{title}</h3><p className="mt-2 text-xs leading-5 text-slate-600">{copy}</p>{i < 5 && <ArrowRight className="absolute -right-3 top-1/2 z-10 hidden size-5 rounded-full bg-[#1685ff] p-1 text-white lg:block" />}</div>)}</div><div className="mt-10 grid gap-4 sm:grid-cols-3"><div className="rounded-xl bg-white/70 p-5"><p className="text-sm font-semibold text-[#102c50]">LangChain + RAG</p><p className="mt-2 text-xs leading-5 text-slate-600">Retrieve relevant equipment manuals, SOPs, and maintenance records.</p></div><div className="rounded-xl bg-white/70 p-5"><p className="text-sm font-semibold text-[#102c50]">LangSmith</p><p className="mt-2 text-xs leading-5 text-slate-600">Support AI-agent tracing, testing, and evaluation.</p></div><div className="rounded-xl bg-white/70 p-5"><p className="text-sm font-semibold text-[#102c50]">Human-in-the-loop</p><p className="mt-2 text-xs leading-5 text-slate-600">Keep maintenance engineers responsible for approving decisions.</p></div></div></div></section>

<section className="bg-white px-5 py-24 lg:px-8" id="compliance"><div className="mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-[.9fr_1.1fr]"><div className="relative min-h-[420px] overflow-hidden rounded-3xl bg-[#102c50]"><img src="https://images.unsplash.com/photo-1581093458791-9d42e3c9b8e7?auto=format&fit=crop&w=1200&q=85" alt="Engineer reviewing industrial equipment" className="absolute inset-0 size-full object-cover opacity-75"/><div className="absolute inset-0 bg-gradient-to-t from-[#102c50]/80 to-transparent"/><div className="absolute bottom-6 left-6 right-6 rounded-xl border border-white/20 bg-white/10 p-4 backdrop-blur-md"><p className="text-xs font-semibold text-white">Traceable by design</p><p className="mt-1 text-xs text-slate-200">Secure connectivity · Audit-ready diagnostics · Human approval</p></div></div><div><SectionHeading eyebrow="Designed for regulated environments" title="Built with reliability, safety and traceability in mind" copy="PharmaPredict AI is designed to support pharmaceutical equipment monitoring with secure data handling, traceable diagnostics, and human-controlled maintenance decisions."/><div className="mt-8 grid gap-4 sm:grid-cols-2">{['Role-based access control','Audit trails & traceability','Secure industrial connectivity','Human approval workflows','Controlled model versions','Risk-based validation support'].map(item => <div key={item} className="flex items-center gap-3 text-sm font-medium text-[#102c50]"><Check className="size-4 text-[#0d9488]"/>{item}</div>)}</div><p className="mt-8 text-xs leading-5 text-slate-500">Designed to support GMP-aligned workflows. PharmaPredict AI does not claim GMP certification, FDA approval, or formal validation.</p></div></div></section>

<section className="bg-[#f8fafc] px-5 py-24 lg:px-8"><div className="mx-auto max-w-7xl"><SectionHeading eyebrow="Why PharmaPredict AI" title="A smarter approach to equipment reliability"/><div className="mt-14 grid gap-5 lg:grid-cols-3">{([['Universal by design','Configure different machine categories, sensor types, and equipment integrations.',Cpu],['Intelligence with evidence','Combine sensor analytics, validated ML outputs, technical documentation, and explainable diagnostics.',Sparkles],['Engineers stay in control','Provide AI-assisted guidance while maintaining human review, authorization, and safety controls.',Users]] as [string, string, React.ComponentType<{ className?: string }>][]).map(([title,copy,Icon]) => <div key={title} className="rounded-2xl bg-white p-8 shadow-sm ring-1 ring-slate-200"><Icon className="size-6 text-[#1685ff]"/><p className="mt-10 text-xs font-bold uppercase tracking-[.18em] text-[#1685ff]">{title}</p><p className="mt-4 text-lg leading-7 text-[#102c50]">{copy}</p></div>)}</div></div></section>

<section className="relative overflow-hidden bg-[#102c50] px-5 py-24 lg:px-8" id="contact"><div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,rgba(22,133,255,.35),transparent_35%)]"/><div className="relative mx-auto flex max-w-7xl flex-col items-start justify-between gap-8 md:flex-row md:items-end"><div><p className="text-xs font-bold uppercase tracking-[.18em] text-cyan-300">Start a better conversation</p><h2 className="mt-4 max-w-2xl text-4xl font-semibold tracking-[-.05em] text-white sm:text-5xl">Ready to make your production more predictable?</h2><p className="mt-5 max-w-xl text-base leading-7 text-slate-300">Discover how PharmaPredict AI can help your maintenance team gain better equipment visibility and make more informed decisions.</p></div><div className="flex shrink-0 flex-col gap-3 sm:flex-row"><button onClick={() => setModalOpen(true)} className={primaryButton}>Book a demo <ArrowRight className={arrowMotion} /></button><a href="mailto:hello@pharmapredict.ai" className={secondaryButton}>Contact us <ArrowRight className={arrowMotion} /></a></div></div></section>

<footer className="bg-[#0f172a] px-5 py-14 text-slate-400 lg:px-8"><div className="mx-auto max-w-7xl"><div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.8fr_1fr_1fr_1fr]"><div><Logo/><p className="mt-5 max-w-xs text-sm leading-6">Smarter maintenance for a healthier world.</p></div>{[['Platform','Overview','Features','Equipment','AI diagnostics'],['Company','About','Contact','Request demo'],['Resources','Privacy policy','Terms of service','Documentation']].map(([heading,...links]) => <div key={heading}><p className="text-sm font-semibold text-white">{heading}</p><div className="mt-5 grid gap-3">{links.map(link => <a key={link} href={link === 'Request demo' ? '#contact' : '#top'} className="text-sm hover:text-white">{link}</a>)}</div></div>)}</div><div className="mt-14 flex flex-col gap-3 border-t border-white/10 pt-6 text-xs sm:flex-row sm:items-center sm:justify-between"><span>© 2026 PharmaPredict AI. All rights reserved.</span><span>Designed to support GMP-aligned workflows.</span></div></div></footer>{modalOpen && <DemoModal onClose={() => setModalOpen(false)} />}</main> }
