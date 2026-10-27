import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useStore } from './App.jsx'
import { MOCK, api, downloadServerCsv, can, canSeeArm, armOf, trialStatus, prereqs, stratumKey, verifyChain, ELIGIBILITY, TRIAL_WEEKS, VISIT_WEEKS } from './lib.js'

/* ════════════════════════════════════════════
   SHARED PRIMITIVES
   ════════════════════════════════════════════ */

function Page({ title, sub, breadcrumb, badge, bar, children }) {
  return (
    <>
      {/* Page header */}
      <div className="shrink-0 bg-white border-b border-trace-sage/60 px-6 py-4 shadow-sm">
        {breadcrumb && (
          <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wide mb-1">{breadcrumb}</div>
        )}
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-trace-dark">{title}</h1>
          {badge && <span className="chip">{badge}</span>}
        </div>
        {sub && <p className="text-xs text-slate-500 mt-0.5 italic">{sub}</p>}
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-auto p-6 fade-up">{children}</div>

      {/* Footer action bar */}
      <footer className="shrink-0 bg-white border-t border-trace-sage/60 flex items-center justify-end gap-2 px-6 py-3 shadow-sm">
        {bar}
      </footer>
    </>
  )
}

const Stat = ({ label, value, warn, sub }) => (
  <div className="card hover:shadow-md transition-shadow duration-200">
    <div className="text-[11px] font-bold text-trace-dark/60 uppercase tracking-wide">{label}</div>
    <div className={`text-3xl font-bold mt-1 ${warn ? 'text-red-600' : 'text-trace-dark'}`}>{value}</div>
    {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
  </div>
)

const Field = ({ label, children }) => (
  <label className="block">
    <span className="lbl">{label}</span>
    {children}
  </label>
)

/* ════════════════════════════════════════════
   LANDING PAGE
   ════════════════════════════════════════════ */

export function Landing() {
  const { user } = useStore()
  const navigate = useNavigate()

  const goToApp = () => navigate(user ? '/app/' : '/app/')

  return (
    <div className="min-h-screen flex flex-col bg-[#f4f8f5] font-sans">
      {/* ── Navbar ── */}
      <nav className="bg-white/80 backdrop-blur-md border-b border-trace-sage/40 sticky top-0 z-50">
        <div className="w-full max-w-7xl mx-auto px-8 h-16 flex items-center justify-between">
          <span className="text-2xl font-bold tracking-widest text-trace-dark">TRACE</span>
          <div className="hidden md:flex items-center gap-10 text-base font-medium text-slate-600">
            {['Platform', 'Enrollment', 'Randomization', 'Analytics', 'Security'].map((item) => (
              <a
                key={item}
                href={`#${item.toLowerCase()}`}
                className="hover:text-trace-dark transition-colors duration-150 cursor-pointer"
              >
                {item}
              </a>
            ))}
          </div>
          <button
            id="landing-secure-access"
            onClick={goToApp}
            className="landing-btn text-base px-6 py-3 shadow-sm"
          >
            Secure Access
          </button>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section id="platform" className="w-full max-w-7xl mx-auto px-8 py-20 flex flex-col md:flex-row items-center gap-14">
        <div className="flex-1 fade-up">
          <h1 className="text-5xl font-bold text-trace-dark leading-tight mb-5">
            Precision in Clinical Trial<br />Administration
          </h1>
          <p className="text-slate-600 text-base leading-relaxed mb-8 max-w-lg">
            TRACE delivers a robust, secure, and intuitive platform for managing complex clinical
            research. Streamline enrollment, ensure rigorous randomization, and maintain real-time
            oversight with our advanced{' '}
            <span className="text-trace-dark font-medium">analytics suite</span>.
          </p>
          <div className="flex gap-4 flex-wrap">
            <button
              id="landing-demo"
              onClick={goToApp}
              className="landing-btn text-base px-6 py-3"
            >
              Request Demonstration
            </button>
            <a href="#platform" className="landing-btn-outline text-base px-6 py-3">
              View Platform Specs
            </a>
          </div>
        </div>
        {/* Dashboard preview card */}
        <div className="flex-1 max-w-lg w-full fade-up">
          <div className="rounded-2xl overflow-hidden shadow-2xl border border-trace-sage/40 bg-white">
            <div className="h-7 bg-slate-100 border-b border-trace-sage/30 flex items-center px-3 gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
            </div>
            <img
              src="/dashboard-preview.jpg"
              alt="TRACE platform dashboard showing trial analytics and enrollment metrics"
              className="w-full object-cover"
              loading="lazy"
            />
          </div>
        </div>
      </section>

      {/* ── Core Capabilities ── */}
      <section id="analytics" className="bg-white/60 border-y border-trace-sage/40 py-20">
        <div className="w-full max-w-7xl mx-auto px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-trace-dark mb-3">Core Capabilities</h2>
            <p className="text-base text-slate-500 max-w-2xl mx-auto leading-relaxed">
              Engineered to reduce cognitive load while maintaining strict{' '}
              <span className="text-trace-dark font-medium">regulatory compliance</span> and data{' '}
              <span className="text-trace-dark font-medium">integrity</span> across all phases of clinical evaluation.
            </p>
          </div>

          <div id="enrollment" className="grid md:grid-cols-3 gap-8">
            {/* Enrollment */}
            <div className="feature-card">
              <div className="w-12 h-12 rounded-xl bg-trace-sage/40 flex items-center justify-center mb-5">
                <svg className="w-6 h-6 text-trace-dark" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
              <h3 className="font-bold text-trace-dark mb-2 text-lg">Enrollment</h3>
              <p className="text-sm text-slate-500 leading-relaxed mb-5">
                Seamless participant registration workflows designed to minimise data entry errors and
                accelerate onboarding timelines. Integrated eligibility screening protocols.
              </p>
              <button
                id="landing-eligible-tracker"
                onClick={goToApp}
                className="feature-tag text-[10px]"
              >
                Eligible Tracker
              </button>
            </div>

            {/* Randomization */}
            <div id="randomization" className="feature-card">
              <div className="w-12 h-12 rounded-xl bg-trace-sage/40 flex items-center justify-center mb-5">
                <svg className="w-6 h-6 text-trace-dark" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </div>
              <h3 className="font-bold text-trace-dark mb-2 text-lg">Randomization</h3>
              <p className="text-sm text-slate-500 leading-relaxed mb-5">
                Rigorous, stratified allocation algorithms ensuring statistical validity and eliminating
                selection bias. Support for complex, multi-arm adaptive trial designs.
              </p>
              <button
                id="landing-algorithm-active"
                onClick={goToApp}
                className="feature-tag text-[10px]"
              >
                Algorithm Active
              </button>
            </div>

            {/* Analytics */}
            <div className="feature-card">
              <div className="w-12 h-12 rounded-xl bg-trace-sage/40 flex items-center justify-center mb-5">
                <svg className="w-6 h-6 text-trace-dark" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <h3 className="font-bold text-trace-dark mb-2 text-lg">Analytics</h3>
              <p className="text-sm text-slate-500 leading-relaxed mb-5">
                Real-time trial integrity monitoring through advanced data visualisation. Proactive
                identification of anomalies and protocol deviations before they impact study outcomes.
              </p>
              <button
                id="landing-live-metrics"
                onClick={goToApp}
                className="feature-tag text-[10px]"
              >
                Live Metrics
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ── Security strip ── */}
      <section id="security" className="w-full max-w-7xl mx-auto px-8 py-16 text-center">
        <div className="inline-flex items-center gap-2 bg-trace-sage/30 text-trace-dark text-sm font-semibold px-5 py-2.5 rounded-full mb-5">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          Hash-chained audit trail · SHA-256 · GCP ICH E6(R3) aligned
        </div>
        <p className="text-base text-slate-500 max-w-lg mx-auto">
          Every action is cryptographically signed and chained. Tamper-evident by design.
        </p>
      </section>

      {/* ── Footer ── */}
      <footer className="bg-[#1b4f5e] text-white mt-auto">
        <div className="w-full max-w-7xl mx-auto px-8 py-10 flex flex-col md:flex-row items-center justify-between gap-4">
          <div>
            <span className="font-bold tracking-widest text-2xl">TRACE</span>
            <p className="text-sm text-white/50 mt-1">
              © {new Date().getFullYear()} TRACE – Trial Research Administration &amp; Clinical Evaluation. Clinical Precision.
            </p>
          </div>
          <div className="flex flex-wrap gap-6 text-sm text-white/60">
            {['Privacy Policy', 'Terms of Service', 'Security Whitepaper', 'Contact Support'].map((l) => (
              <a key={l} href="#" className="hover:text-white transition-colors">{l}</a>
            ))}
          </div>
        </div>
      </footer>
    </div>
  )
}

/* ════════════════════════════════════════════
   LOGIN
   ════════════════════════════════════════════ */

export function Login() {
  const { login } = useStore()
  const navigate = useNavigate()
  const [u, setU] = useState(''), [p, setP] = useState(''), [err, setErr] = useState(''), [loading, setLoading] = useState(false)
  const go = async () => {
    try { setErr(''); setLoading(true); await login(u.trim(), p); navigate('/app/') }
    catch (e) { setErr(e.message) }
    finally { setLoading(false) }
  }
  return (
    <div className="min-h-screen bg-[#f4f8f5] flex items-center justify-center p-4">
      <div className="w-full max-w-sm fade-up">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-block text-3xl font-bold tracking-widest text-trace-dark">TRACE</div>
          <p className="text-xs text-slate-500 mt-1">Trial Research Administration &amp; Clinical Evaluation</p>
        </div>
        <div className="card shadow-xl">
          <h2 className="text-base font-bold text-trace-dark mb-5">Secure Sign In</h2>
          <div className="space-y-4">
            <Field label="Username">
              <input
                id="login-username"
                className="inp"
                value={u}
                onChange={(e) => setU(e.target.value)}
                placeholder="e.g. coordinator"
                autoComplete="username"
              />
            </Field>
            <Field label="Password">
              <input
                id="login-password"
                className="inp"
                type="password"
                value={p}
                onChange={(e) => setP(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && go()}
                autoComplete="current-password"
              />
            </Field>
            {err && <p role="alert" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{err}</p>}
            <button id="login-submit" className="btn w-full justify-center" onClick={go} disabled={loading}>
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </div>
          <div className="mt-4 pt-4 border-t border-trace-sage/40">
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Demo credentials: <span className="font-mono text-trace-dark">patient</span>,{' '}
              <span className="font-mono text-trace-dark">coordinator</span>,{' '}
              <span className="font-mono text-trace-dark">supervisor</span>,{' '}
              <span className="font-mono text-trace-dark">supervisor_unblinded</span>. Any password.
            </p>
          </div>
        </div>
        <p className="text-center mt-4">
          <Link to="/" className="text-xs text-trace-dark/60 hover:text-trace-dark transition-colors">
            ← Back to platform overview
          </Link>
        </p>
      </div>
    </div>
  )
}

export function Denied() {
  return (
    <Page title="Access Denied" sub="Your role does not have permission to view this page." breadcrumb="Error">
      <Link to="/app/" className="btn inline-block">Back to dashboard</Link>
    </Page>
  )
}

/* ════════════════════════════════════════════
   DASHBOARD
   ════════════════════════════════════════════ */

export function Dashboard() {
  const { user, parts, aes, chain, dash } = useStore()
  if (user.role === 'PATIENT') return <PatientDash />
  const n = (f) => parts.filter(f).length
  const awaiting = parts.filter((p) => prereqs(p).every(([, ok]) => ok))
  const ov = !MOCK && dash ? dash.overall : null // server-side numbers from Module 3
  const base = [
    ['Registered', ov ? ov.registered : parts.length, false, 'All participants'],
    ['Awaiting screening', ov ? ov.awaiting_screening : n((p) => p.eligibility === 'PENDING_REVIEW'), false, 'Eligibility review pending'],
    ['Eligible', ov ? ov.eligible : n((p) => p.eligibility === 'ELIGIBLE'), false, 'Passed screening'],
    ['Screen failures', ov ? ov.screen_failures : n((p) => p.eligibility === 'SCREEN_FAILURE'), true, 'Did not pass criteria'],
    ['Enrolled', ov ? ov.enrolled : n((p) => p.trial_status === 'ENROLLED'), false, 'Active in trial'],
    ['Awaiting randomization', ov ? ov.awaiting_randomization : awaiting.length, false, 'Ready to randomize'],
  ]
  const sev = (s) => aes.filter((a) => a.severity === s).length
  return (
    <Page
      title={user.role === 'SUPERVISOR' ? 'Trial Oversight' : 'Operational Dashboard'}
      sub="Simulated double-blind Type 2 Diabetes trial · 16 weeks"
      breadcrumb="TRIAL · CASE #ARIA-6492"
      badge={user.role === 'SUPERVISOR' ? 'SUPERVISOR VIEW' : 'COORDINATOR'}
      bar={can(user, 'enroll') && <Link to="/app/patients" className="btn">Enroll New Patient</Link>}
    >
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {base.map(([l, v, w, s]) => <Stat key={l} label={l} value={v} warn={w && v > 0} sub={s} />)}
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card">
          <h2 className="font-bold text-trace-dark mb-4 text-sm">Enrollment Funnel</h2>
          {[
            ['Registered', parts.length],
            ['Eligible', n((p) => p.eligibility === 'ELIGIBLE')],
            ['Randomized', n((p) => p.rand_no)],
            ['Completed', n((p) => p.trial_status === 'COMPLETED')],
          ].map(([l, v]) => (
            <div key={l} className="flex items-center gap-3 mb-3 text-sm">
              <span className="w-24 text-xs text-slate-500">{l}</span>
              <div className="flex-1 bg-trace-sage/30 rounded-full h-3">
                <div
                  className="bg-trace-dark h-3 rounded-full transition-all duration-500"
                  style={{ width: `${(v / Math.max(parts.length, 1)) * 100}%` }}
                />
              </div>
              <span className="w-6 text-right text-xs font-bold text-trace-dark">{v}</span>
            </div>
          ))}
        </div>
        <div className="card">
          <h2 className="font-bold text-trace-dark mb-4 text-sm">
            {user.role === 'SUPERVISOR' ? 'Safety & Integrity' : 'Priority Action Queue'}
          </h2>
          {user.role === 'SUPERVISOR' ? (
            <div className="space-y-3 text-sm">
              <div className="reg-banner-info">
                <span className="font-semibold">Adverse events:</span>{' '}
                Mild {sev('MILD')} · Moderate {sev('MODERATE')} · Severe{' '}
                <span className={sev('SEVERE') > 0 ? 'text-red-700 font-bold' : ''}>{sev('SEVERE')}</span>
              </div>
              <div className="flex items-center justify-between text-xs text-slate-600 border-t border-trace-sage/40 pt-3">
                <span>Audit chain entries: <strong>{chain.length}</strong></span>
                <Link to="/app/audit" className="text-trace-dark underline font-medium">Verify chain →</Link>
              </div>
              <div className="text-xs text-slate-600">
                Missing baseline data:{' '}
                <strong className={n((p) => p.eligibility === 'ELIGIBLE' && !p.baseline_complete) > 0 ? 'text-amber-700' : ''}>
                  {n((p) => p.eligibility === 'ELIGIBLE' && !p.baseline_complete)}
                </strong>
              </div>
            </div>
          ) : (
            <ul className="space-y-2 text-sm">
              {awaiting.map((p) => (
                <li key={p.id} className="flex items-center gap-2 text-xs">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
                  <span><strong>{p.id}</strong> is ready to randomize</span>
                </li>
              ))}
              {parts.filter((p) => p.eligibility === 'ELIGIBLE' && p.consent !== 'OBTAINED').map((p) => (
                <li key={p.id} className="flex items-center gap-2 text-xs text-red-700">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" />
                  <span><strong>{p.id}</strong> has incomplete consent</span>
                </li>
              ))}
              {parts.filter((p) => p.eligibility === 'PENDING_REVIEW').map((p) => (
                <li key={p.id} className="flex items-center gap-2 text-xs text-amber-700">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
                  <span><strong>{p.id}</strong> awaits eligibility review</span>
                </li>
              ))}
              {aes.filter((a) => a.status === 'SUBMITTED').map((a) => (
                <li key={a.id} className="flex items-center gap-2 text-xs text-slate-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-trace-dark shrink-0" />
                  <span>Adverse event for <strong>{a.participant_id}</strong> awaits review</span>
                </li>
              ))}
              {awaiting.length === 0 && parts.filter((p) => p.eligibility === 'ELIGIBLE' && p.consent !== 'OBTAINED').length === 0 && (
                <li className="text-xs text-slate-400 italic">No pending actions.</li>
              )}
            </ul>
          )}
        </div>
      </div>
    </Page>
  )
}

function PatientDash() {
  const { user, parts, vitals, addAE } = useStore()
  const me = parts.find((p) => p.id === user.participant_id)
  const [open, setOpen] = useState(false), [txt, setTxt] = useState(''), [sent, setSent] = useState(false), [aeErr, setAeErr] = useState('')
  if (!me) return <Page title="Loading…" sub="Fetching your record" breadcrumb="PATIENT PORTAL"><p className="text-xs text-slate-400 italic">Loading your record…</p></Page>
  const week = me.week ?? 0, next = VISIT_WEEKS.find((w) => w > week)
  const last = vitals[vitals.length - 1] || {}, prev = vitals[vitals.length - 2] || {}
  return (
    <Page
      title={me.id}
      sub="Your trial progress"
      breadcrumb="PATIENT PORTAL"
      bar={<button className="btn" onClick={() => setOpen(true)}>Report a Symptom</button>}
    >
      <div className="grid sm:grid-cols-3 gap-4 mb-5">
        <Stat label="Trial status" value={trialStatus(me)} />
        <Stat label="Consent" value={me.consent === 'OBTAINED' ? 'Recorded' : 'Not recorded'} />
        <Stat label="Next visit" value={next ? `Week ${next}` : 'None'} />
      </div>
      <div className="card mb-5">
        <div className="text-xs text-slate-500 mb-2">Week {week} of {TRIAL_WEEKS}</div>
        <div className="bg-trace-sage/30 rounded-full h-3">
          <div className="bg-trace-mid h-3 rounded-full transition-all duration-500" style={{ width: `${(week / TRIAL_WEEKS) * 100}%` }} />
        </div>
      </div>
      <div className="card">
        <h2 className="font-bold text-trace-dark mb-3 text-sm">Latest Readings</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-trace-dark/60 uppercase tracking-wide">
              <th className="pb-2">Measure</th><th className="pb-2">Latest</th><th className="pb-2">Previous</th>
            </tr>
          </thead>
          <tbody>
            {[['HbA1c (%)', 'hba1c'], ['Fasting glucose (mg/dL)', 'glucose'], ['Weight (kg)', 'weight'], ['Blood pressure (mmHg)', 'bp']].map(([l, k]) => (
              <tr key={k} className="border-t border-trace-sage/40">
                <td className="py-2 text-xs text-slate-500">{l}</td>
                <td className="font-medium">{last[k] ?? '—'}</td>
                <td className="text-slate-400">{prev[k] ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open && (
        <div className="card mt-5">
          <Field label="Describe the symptom">
            <textarea className="inp" rows={3} value={txt} onChange={(e) => setTxt(e.target.value)} />
          </Field>
          <div className="mt-3 flex gap-2">
            <button className="btn" disabled={!txt} onClick={async () => { try { setAeErr(''); await addAE({ participant_id: me.id, severity: 'MILD', serious: false, relationship: 'NOT_RELATED', description: txt, onset: new Date().toISOString().slice(0, 10) }); setSent(true); setOpen(false); setTxt('') } catch (e) { setSent(false); setAeErr(e.message) } }}>
              Send Report
            </button>
            <button className="btn2" onClick={() => setOpen(false)}>Cancel</button>
          </div>
        </div>
      )}
      {aeErr && <p role="alert" className="mt-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">Could not send: {aeErr}</p>}
      {sent && <p className="mt-4 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">Report sent. Status: SUBMITTED.</p>}
    </Page>
  )
}

/* ════════════════════════════════════════════
   PATIENTS
   ════════════════════════════════════════════ */

export function Patients() {
  const { user, parts, aes, addParticipant, addAE } = useStore()
  const [q, setQ] = useState(''), [sel, setSel] = useState(null), [mode, setMode] = useState(null)
  const [f, setF] = useState({ site: 'SITE-01', age: '', sex: 'F', hba1c: '', therapy: 'STABLE', t2dm: true, consent: false, baseline: false, glucose: '', weight: '' })
  const [ae, setAe] = useState({ onset: '', severity: 'MILD', serious: false, relationship: 'NOT_RELATED', description: '' })
  const [msg, setMsg] = useState('')
  const p = parts.find((x) => x.id === sel)
  const rows = parts.filter((x) => `${x.id} ${x.site}`.toLowerCase().includes(q.toLowerCase()))
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  const eligChip = (e) => {
    if (e === 'ELIGIBLE') return <span className="chip-green">{e}</span>
    if (e === 'SCREEN_FAILURE') return <span className="chip-red">{e}</span>
    if (e === 'PENDING_REVIEW') return <span className="chip-amber">{e}</span>
    return <span className="chip">{e}</span>
  }

  const bar = (
    <>
      {can(user, 'enroll') && <button className="btn" onClick={() => setMode('enroll')}>Enroll New Patient</button>}
      {can(user, 'report_ae') && <button className="btn2" disabled={!p} onClick={() => setMode('ae')}>Log Adverse Event</button>}
    </>
  )
  return (
    <Page
      title="Patients"
      sub="Participant records are never deleted — they change status."
      breadcrumb="AREA / DIRECTORY"
      bar={bar}
    >
      {msg && (
        <div className="mb-4 reg-banner-info flex items-center gap-2">
          <span className="font-semibold">Result:</span> {msg}
        </div>
      )}

      {/* ── Enroll form ── */}
      {mode === 'enroll' && (
        <div className="card mb-5">
          <h2 className="font-bold text-trace-dark mb-1 text-sm">Enroll &amp; Screen Participant</h2>
          <p className="text-xs text-slate-400 mb-4">Complete all fields. Screening criteria will be evaluated automatically.</p>
          <div className="grid sm:grid-cols-4 gap-3 mb-4">
            <Field label="Site">
              <select className="inp" value={f.site} onChange={set('site')}>
                <option>SITE-01</option><option>SITE-02</option>
              </select>
            </Field>
            <Field label="Age"><input className="inp" type="number" value={f.age} onChange={set('age')} /></Field>
            <Field label="Sex">
              <select className="inp" value={f.sex} onChange={set('sex')}><option>F</option><option>M</option></select>
            </Field>
            <Field label="Baseline HbA1c (%)">
              <input className="inp" type="number" step="0.1" value={f.hba1c} onChange={set('hba1c')} />
            </Field>
            <Field label="Background therapy">
              <select className="inp" value={f.therapy} onChange={set('therapy')}><option>STABLE</option><option>NONE</option></select>
            </Field>
          </div>
          <div className="flex flex-wrap gap-5 text-sm mb-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={f.t2dm} onChange={set('t2dm')} className="rounded" />
              <span className="text-xs">Type 2 diabetes confirmed</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={f.consent} onChange={set('consent')} className="rounded" />
              <span className="text-xs">Informed consent obtained</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={f.baseline} onChange={set('baseline')} className="rounded" />
              <span className="text-xs">Baseline data complete</span>
            </label>
          </div>
          {!MOCK && f.baseline && (
            <div className="grid sm:grid-cols-4 gap-3 mb-4">
              <Field label="Fasting glucose (mg/dL)"><input className="inp" type="number" value={f.glucose} onChange={set('glucose')} /></Field>
              <Field label="Weight (kg)"><input className="inp" type="number" step="0.1" value={f.weight} onChange={set('weight')} /></Field>
            </div>
          )}
          <div className="reg-banner mb-4">
            ⚠ Eligibility rules: age {ELIGIBILITY.minAge}–{ELIGIBILITY.maxAge}, HbA1c {ELIGIBILITY.minHba1c}–{ELIGIBILITY.maxHba1c}%. Final criteria from the protocol.
          </div>
          <div className="flex gap-2">
            <button className="btn" disabled={!f.age || !f.hba1c || (!MOCK && f.baseline && (!f.glucose || !f.weight))} onClick={async () => { try { const r = await addParticipant(f); setMsg(`${r.id}: ${r.eligibility}${r.reason ? ` (${r.reason})` : ''}`); setMode(null) } catch (e) { setMsg(`Could not save: ${e.message}`) } }}>
              Save &amp; Screen
            </button>
            <button className="btn2" onClick={() => setMode(null)}>Cancel</button>
          </div>
        </div>
      )}

      {/* ── AE form ── */}
      {mode === 'ae' && p && (
        <div className="card mb-5">
          <h2 className="font-bold text-trace-dark mb-1 text-sm">Adverse Event · <span className="font-mono">{p.id}</span></h2>
          <p className="text-xs text-slate-400 mb-4">Report grade and causality strictly per CTCAE v5.0 guidelines. Grade 3+ requires coordinator notification within 24h.</p>
          <div className="grid sm:grid-cols-3 gap-3 mb-3">
            <Field label="Date of onset">
              <input className="inp" type="date" value={ae.onset} onChange={(e) => setAe({ ...ae, onset: e.target.value })} />
            </Field>
            <Field label="Severity (CTCAE Grade)">
              <select className="inp" value={ae.severity} onChange={(e) => setAe({ ...ae, severity: e.target.value })}>
                <option>MILD</option><option>MODERATE</option><option>SEVERE</option>
              </select>
            </Field>
            <Field label="Causality assessment">
              <select className="inp" value={ae.relationship} onChange={(e) => setAe({ ...ae, relationship: e.target.value })}>
                <option>NOT_RELATED</option><option>POSSIBLY_RELATED</option><option>RELATED</option>
              </select>
            </Field>
          </div>
          <label className="flex items-center gap-2 text-xs mb-3 cursor-pointer">
            <input type="checkbox" checked={ae.serious} onChange={(e) => setAe({ ...ae, serious: e.target.checked })} className="rounded" />
            Serious adverse event (SAE) — requires immediate CRF amendment notification
          </label>
          <Field label="Clinical narrative &amp; observations">
            <textarea className="inp" rows={3} value={ae.description} onChange={(e) => setAe({ ...ae, description: e.target.value })}
              placeholder="Provide a detailed clinical description of the adverse event, symptomatic progression, vitals and baseline shifts…" />
          </Field>
          <div className="mt-3 flex gap-2">
            <button className="btn" disabled={!ae.onset || !ae.description} onClick={async () => { try { await addAE({ ...ae, participant_id: p.id }); setMsg(`Adverse event saved for ${p.id}. Status: SUBMITTED.`); setMode(null) } catch (e) { setMsg(`Could not save: ${e.message}`) } }}>
              Save Adverse Event
            </button>
            <button className="btn2" onClick={() => setMode(null)}>Cancel</button>
          </div>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-4">
        {/* Table */}
        <div className="card lg:col-span-2">
          <input className="inp mb-3" placeholder="Search by ID or site…" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] text-trace-dark/60 uppercase tracking-wide">
                  <th className="pb-2">ID</th><th className="pb-2">Site</th><th className="pb-2">Eligibility</th><th className="pb-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((x) => (
                  <tr
                    key={x.id}
                    onClick={() => setSel(x.id)}
                    className={`border-t border-trace-sage/40 cursor-pointer transition-colors duration-100 ${sel === x.id ? 'bg-trace-sage/30' : 'hover:bg-trace-mint/50'}`}
                  >
                    <td className="py-2.5 font-mono text-xs text-trace-dark font-bold">{x.id}</td>
                    <td className="text-xs text-slate-500">{x.site}</td>
                    <td>{eligChip(x.eligibility)}</td>
                    <td className="text-xs text-slate-600">{trialStatus(x)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        {/* Detail panel */}
        <div className="card text-sm">
          {!p ? (
            <p className="text-xs text-slate-400 italic">Select a participant to see details.</p>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-lg font-bold text-trace-dark font-mono">{p.id}</span>
                {eligChip(p.eligibility)}
              </div>
              <dl className="space-y-2 text-xs">
                {[
                  ['Age / Sex', `${p.age}, ${p.sex}`],
                  ['Baseline HbA1c', p.hba1c != null ? `${p.hba1c}% (${p.hba1c_cat})` : '—'],
                  ['Therapy', p.therapy ?? '—'],
                  ['Consent', p.consent],
                  ['Baseline complete', p.baseline_complete ? 'Yes' : 'No'],
                  ['Stratum', p.id],
                ].map(([l, v]) => (
                  <div key={l} className="flex justify-between border-b border-trace-sage/30 pb-1.5">
                    <span className="text-slate-400">{l}</span>
                    <span className="font-medium text-trace-dark font-mono">{v}</span>
                  </div>
                ))}
                {p.reason && <div className="text-red-700 bg-red-50 rounded px-2 py-1">Screen failure: {p.reason}</div>}
                <div className="flex justify-between border-b border-trace-sage/30 pb-1.5">
                  <span className="text-slate-400">Rand. No.</span>
                  <span className="font-mono font-medium text-trace-dark">{p.rand_no || '—'}</span>
                </div>
                {p.rand_no && (
                  <div className="flex justify-between border-b border-trace-sage/30 pb-1.5">
                    <span className="text-slate-400">Arm</span>
                    <span>{armOf(user, p.arm) ?? <span className="chip">Hidden</span>}</span>
                  </div>
                )}
                <div className="flex justify-between pb-1.5">
                  <span className="text-slate-400">AEs</span>
                  <span className="font-bold text-trace-dark">{aes.filter((a) => a.participant_id === p.id).length}</span>
                </div>
              </dl>
            </>
          )}
        </div>
      </div>

      {/* Bottom status bar (mimics reference) */}
      <div className="mt-4 flex items-center justify-between text-[11px] text-slate-400 bg-white border border-trace-sage/40 rounded-lg px-4 py-2">
        <span>● Indexed changes — Form awaiting investigator signature</span>
        <span className="text-trace-dark font-medium">{parts.length} participants</span>
      </div>
    </Page>
  )
}

/* ════════════════════════════════════════════
   RANDOMIZE
   ════════════════════════════════════════════ */

export function Randomize() {
  const { user, parts, randomize } = useStore()
  const [sel, setSel] = useState(null), [res, setRes] = useState(null), [err, setErr] = useState('')
  const cand = parts.filter((p) => p.eligibility === 'ELIGIBLE' && !p.rand_no)
  const p = cand.find((x) => x.id === sel)
  const ok = p && prereqs(p).every(([, v]) => v)
  const run = async () => { try { setErr(''); setRes({ id: p.id, ...(await randomize(p.id)) }); setSel(null) } catch (e) { setErr(e.message) } }
  return (
    <Page
      title="Randomization"
      sub="Stratified block randomization · 1:1 · block size 4"
      breadcrumb="PROTOCOL / RANDOMIZE"
      bar={<button className="btn" disabled={!ok} onClick={run}>Randomize Participant</button>}
    >
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card">
          <h2 className="font-bold text-trace-dark mb-3 text-sm">Eligible Participants</h2>
          {cand.length === 0 && <p className="text-xs text-slate-400 italic">Everyone eligible has been randomized.</p>}
          {cand.map((x) => (
            <button
              key={x.id}
              onClick={() => setSel(x.id)}
              className={`block w-full text-left px-3 py-2.5 rounded-lg text-sm mb-1 transition-colors duration-100 ${sel === x.id ? 'bg-trace-sage/50 border border-trace-dark/20' : 'hover:bg-trace-mint/60'}`}
            >
              <span className="font-mono font-bold text-trace-dark text-xs">{x.id}</span>{' '}
              <span className="text-slate-400 text-xs">{stratumKey(x)}</span>
            </button>
          ))}
        </div>
        <div className="card">
          <h2 className="font-bold text-trace-dark mb-3 text-sm">Prerequisites</h2>
          {!p ? (
            <p className="text-xs text-slate-400 italic">Pick a participant to check prerequisites.</p>
          ) : (
            prereqs(p).map(([l, v]) => (
              <div key={l} className={`flex items-center gap-2 text-xs py-1.5 border-b border-trace-sage/30 ${v ? 'text-emerald-700' : 'text-red-600'}`}>
                <span>{v ? '✓' : '✗'}</span>
                <span>{l}</span>
              </div>
            ))
          )}
          <p className="text-[11px] text-slate-400 mt-3">The button unlocks only when every prerequisite is met. The server checks them again.</p>
          {err && <p role="alert" className="text-sm text-red-600 mt-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{err}</p>}
          {res && (
            <div className="mt-4 p-3 rounded-lg bg-trace-sage/30 border border-trace-sage text-sm">
              <div className="font-bold text-trace-dark">{res.message} for {res.id}</div>
              <div className="text-xs text-slate-600 mt-1">Randomization number: <span className="font-mono">{res.randomization_number}</span></div>
              <div className="text-xs text-slate-600">Arm: {res.arm ?? <span className="chip">Concealed for your role</span>}</div>
            </div>
          )}
        </div>
      </div>
    </Page>
  )
}

/* ════════════════════════════════════════════
   REPORTS
   ════════════════════════════════════════════ */

export function Reports() {
  const { user, parts, aes } = useStore()
  const unb = canSeeArm(user)
  const strata = [...new Set(parts.filter((p) => p.rand_no).map(stratumKey))]
  const csv = async () => {
    if (!MOCK) { try { await downloadServerCsv() } catch (e) { window.alert(e.message) } return }
    const head = ['participant_id', 'site_id', 'hba1c_cat', 'therapy', 'eligibility_status', 'trial_status', 'consent_status', 'randomization_number', 'arm']
    const lines = parts.map((p) => [p.id, p.site, p.hba1c_cat, p.therapy, p.eligibility, trialStatus(p), p.consent, p.rand_no || '', armOf(user, p.arm) || ''].join(','))
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([[head.join(','), ...lines].join('\n')], { type: 'text/csv' })); a.download = 'participants.csv'; a.click()
  }
  return (
    <Page
      title="Reports"
      sub={unb ? 'Unblinded oversight: arm counts shown' : 'Blinded view: totals only, no arm data'}
      breadcrumb="REPORTS / OVERSIGHT"
      bar={<button className="btn" onClick={csv}>Export CSV</button>}
    >
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card">
          <h2 className="font-bold text-trace-dark mb-3 text-sm">Balance by Stratum</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] text-trace-dark/60 uppercase tracking-wide">
                <th className="pb-2">Stratum</th><th className="pb-2">Total</th>
                {unb && <><th className="pb-2">Arm A</th><th className="pb-2">Arm B</th></>}
              </tr>
            </thead>
            <tbody>
              {strata.map((k) => {
                const r = parts.filter((p) => p.rand_no && stratumKey(p) === k)
                return (
                  <tr key={k} className="border-t border-trace-sage/40">
                    <td className="py-2 font-mono text-xs">{k}</td>
                    <td className="font-bold text-trace-dark">{r.length}</td>
                    {unb && <><td>{r.filter((p) => p.arm === 'A').length}</td><td>{r.filter((p) => p.arm === 'B').length}</td></>}
                  </tr>
                )
              })}
              {strata.length === 0 && <tr><td colSpan={4} className="text-xs text-slate-400 italic pt-2">No randomized participants yet.</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2 className="font-bold text-trace-dark mb-3 text-sm">Adverse Events by Severity</h2>
          {['MILD', 'MODERATE', 'SEVERE'].map((s) => {
            const cnt = aes.filter((a) => a.severity === s).length
            return (
              <div key={s} className="flex items-center justify-between text-sm py-2 border-b border-trace-sage/40">
                <span className={`text-xs font-semibold ${s === 'SEVERE' && cnt > 0 ? 'text-red-700' : s === 'MODERATE' && cnt > 0 ? 'text-amber-700' : 'text-slate-600'}`}>{s}</span>
                <span className="font-bold text-trace-dark">{cnt}</span>
              </div>
            )
          })}
          <h2 className="font-bold text-trace-dark mt-4 mb-2 text-sm">Data Quality</h2>
          <p className="text-xs text-slate-500">
            Eligible without baseline data:{' '}
            <strong className={parts.filter((p) => p.eligibility === 'ELIGIBLE' && !p.baseline_complete).length > 0 ? 'text-amber-700' : 'text-trace-dark'}>
              {parts.filter((p) => p.eligibility === 'ELIGIBLE' && !p.baseline_complete).length}
            </strong>
          </p>
        </div>
      </div>
    </Page>
  )
}

/* ════════════════════════════════════════════
   AUDIT
   ════════════════════════════════════════════ */

export function Audit() {
  const { chain, setChain } = useStore()
  const [status, setStatus] = useState(null)
  const verify = async () => {
    if (MOCK) return setStatus(await verifyChain(chain))
    try { const r = await api('/audit/verify'); setStatus({ ok: r.ok, broken_seq: r.first_broken_seq }) } catch (e) { setStatus({ ok: false, broken_seq: e.message }) }
  }
  const tamper = () => { if (chain.length) { const c = [...chain]; c[0] = { ...c[0], actor_id: 'U-9999' }; setChain(c); setStatus(null) } }
  return (
    <Page
      title="Audit Log"
      sub="Append-only, hash-chained (SHA-256, genesis is 64 zeros)"
      breadcrumb="AUDIT DOSSIER"
      bar={
        <>
          {MOCK && <button className="btn2" onClick={tamper}>Tamper with entry 1 (demo)</button>}
          <button className="btn" onClick={verify}>Verify Chain</button>
        </>
      }
    >
      {status && (
        <div role="status" className={`mb-4 text-sm px-4 py-3 rounded-lg border font-medium ${status.ok ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-red-50 text-red-700 border-red-200'}`}>
          {status.ok ? '✓ Chain is valid — all hashes match.' : `✗ Chain broken at seq ${status.broken_seq}.`}
        </div>
      )}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[11px] text-trace-dark/60 uppercase tracking-wide">
              <th className="pb-2">Seq</th><th className="pb-2">Event</th><th className="pb-2">Actor</th>
              <th className="pb-2">Participant</th><th className="pb-2">Time (UTC)</th><th className="pb-2">Hash</th>
            </tr>
          </thead>
          <tbody>
            {chain.map((e) => (
              <tr key={e.seq} className="border-t border-trace-sage/40 text-xs">
                <td className="py-2 font-bold text-trace-dark">{e.seq}</td>
                <td><span className="chip">{e.event_type}</span></td>
                <td className="font-mono text-slate-500">{e.actor_id}</td>
                <td className="font-mono text-slate-500">{e.payload.participant_id}</td>
                <td className="font-mono text-slate-400">{e.created_at.slice(0, 19)}</td>
                <td className="font-mono text-slate-400">{e.hash.slice(0, 12)}…</td>
              </tr>
            ))}
            {chain.length === 0 && <tr><td colSpan={6} className="text-xs text-slate-400 italic pt-2">No audit entries yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </Page>
  )
}

/* ════════════════════════════════════════════
   CONFIG
   ════════════════════════════════════════════ */

export function Config() {
  const { user } = useStore()
  return (
    <Page title="Trial Configuration" sub="Read only in this version" breadcrumb="CONFIG">
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card text-sm">
          <h2 className="font-bold text-trace-dark mb-3">Stratification Factors</h2>
          <ul className="space-y-2 text-xs text-slate-600">
            <li className="flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-trace-dark" />Study site: SITE-01, SITE-02</li>
            <li className="flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-trace-dark" />Baseline HbA1c: LOW below 8.5%, HIGH 8.5% and above</li>
            <li className="flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-trace-dark" />Background therapy: STABLE or NONE</li>
          </ul>
        </div>
        <div className="card text-sm">
          <h2 className="font-bold text-trace-dark mb-3">Trial Arms</h2>
          <ul className="space-y-2 text-xs text-slate-600">
            <li className="flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-trace-dark" />Arm A: {canSeeArm(user) ? 'Investigational' : 'Hidden (blinded)'}</li>
            <li className="flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-trace-dark" />Arm B: {canSeeArm(user) ? 'Placebo' : 'Hidden (blinded)'}</li>
            <li className="flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-trace-dark" />Allocation 1:1, block size 4</li>
          </ul>
        </div>
        <div className="card text-sm lg:col-span-2">
          <h2 className="font-bold text-trace-dark mb-3">Roles &amp; Permissions</h2>
          <table className="w-full">
            <thead>
              <tr className="text-left text-[11px] text-trace-dark/60 uppercase tracking-wide">
                <th className="pb-2">Role</th><th className="pb-2">Capabilities</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t border-trace-sage/40 text-xs">
                <td className="py-2 font-medium">Patient</td><td className="text-slate-500">View own record, report symptoms</td>
              </tr>
              <tr className="border-t border-trace-sage/40 text-xs">
                <td className="py-2 font-medium">Coordinator</td><td className="text-slate-500">Enroll, consent, screen, visits, adverse events, randomize</td>
              </tr>
              <tr className="border-t border-trace-sage/40 text-xs">
                <td className="py-2 font-medium">Supervisor</td><td className="text-slate-500">Oversight, export, audit, users; arm only if unblinded</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </Page>
  )
}
