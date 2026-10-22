import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { HashRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { MOCK, MOCK_USERS, SEED, SEED_VITALS, ELIGIBILITY, CHAINED_EVENT_TYPES, BLOCK_SIZE, api, setToken, can, armOf, hba1cCat, stratumKey, prereqs, makeEntry } from './lib.js'
import { fromApiParticipant, fromApiAE, toApiAE, toVitals, prettyReason } from './adapters.js'
import { Landing, Login, Denied, Dashboard, Patients, Randomize, Reports, Audit, Config } from './pages.jsx'

const Ctx = createContext(null)
export const useStore = () => useContext(Ctx)

function Provider({ children }) {
  const [user, setUser] = useState(null)
  const [parts, setParts] = useState(MOCK ? SEED : [])
  const [aes, setAes] = useState([])
  const [chain, setChain] = useState([])
  const [vitals, setVitals] = useState(MOCK ? SEED_VITALS : [])
  const [dash, setDash] = useState(null) // Module 3 numbers (API mode only)
  const [loadErr, setLoadErr] = useState('')
  const blocks = useRef({})

  useEffect(() => { // mock mode only: seed the chain with the two existing randomizations
    if (!MOCK) return
    ;(async () => {
      let c = [], prev = null
      for (const p of SEED.filter((x) => x.rand_no)) {
        prev = await makeEntry(prev, 'RANDOMIZED', 'U-0002', { participant_id: p.id, randomization_number: p.rand_no, stratum_key: stratumKey(p) })
        c.push(prev)
      }
      setChain(c)
    })()
  }, [])

  // ---- API mode: load everything this role is allowed to see ----
  const fetchAll = async (path) => {
    let page = 1, items = [], total = 0
    do {
      const r = await api(`${path}${path.includes('?') ? '&' : '?'}page=${page}&page_size=100`)
      items = items.concat(r.items); total = r.total; page += 1
      if (!r.items.length) break
    } while (items.length < total)
    return items
  }
  const refresh = async (u = user) => {
    if (MOCK || !u) return
    try {
      setLoadErr('')
      const patient = u.role === 'PATIENT'
      const [plist, aelist] = await Promise.all([
        patient ? api(`/participants/${u.participant_id}`).then((p) => [p]) : fetchAll('/participants'),
        fetchAll('/adverse-events'),
      ])
      setParts(plist.map(fromApiParticipant))
      setAes(aelist.map(fromApiAE))
      if (patient) setVitals(toVitals(await api(`/participants/${u.participant_id}/measurements`)))
      else setDash(await api('/reports/enrollment'))
      if (u.role === 'SUPERVISOR') setChain(await fetchAll('/audit/entries'))
    } catch (e) { setLoadErr(e.message) }
  }
  useEffect(() => { refresh(user) }, [user])

  const login = async (username, password) => {
    if (MOCK) {
      const u = MOCK_USERS[username]
      if (!u) throw new Error('Unknown user. Try patient, coordinator, supervisor or supervisor_unblinded.')
      return setUser(u)
    }
    const r = await api('/auth/login', { method: 'POST', body: { username, password } })
    setToken(r.access_token)
    setUser(await api('/auth/me'))
  }
  const logout = () => {
    setToken(null); setUser(null); setDash(null); setLoadErr('')
    if (!MOCK) { setParts([]); setAes([]); setChain([]); setVitals([]) }
  }

  const addParticipant = async (f) => {
    const age = Number(f.age), hba1c = Number(f.hba1c)
    if (!MOCK) {
      // real workflow: register -> consent -> screening -> (optional) week-0 baseline data
      const created = await api('/participants', { method: 'POST', body: { site_id: f.site, age, sex: f.sex } })
      const id = created.participant_id
      let eligibility = 'PENDING_REVIEW', reason = null
      try {
        if (f.consent) {
          await api(`/participants/${id}/consent`, { method: 'POST', body: {} })
          const s = await api(`/participants/${id}/screening`, { method: 'POST', body: { t2dm_confirmed: !!f.t2dm, hba1c, therapy: f.therapy } })
          eligibility = s.result; reason = prettyReason(s.reason)
          if (f.baseline && s.result === 'ELIGIBLE')
            await api(`/participants/${id}/measurements`, { method: 'POST', body: { visit_week: 0, hba1c, fasting_glucose: Number(f.glucose), weight_kg: Number(f.weight) } })
        } else {
          reason = 'Consent must be recorded before screening'
        }
      } finally { await refresh() }
      return { id, eligibility, reason }
    }
    let reason = null
    if (!f.t2dm) reason = 'Type 2 diabetes not confirmed'
    else if (age < ELIGIBILITY.minAge || age > ELIGIBILITY.maxAge) reason = `Age outside ${ELIGIBILITY.minAge} to ${ELIGIBILITY.maxAge}`
    else if (hba1c < ELIGIBILITY.minHba1c || hba1c > ELIGIBILITY.maxHba1c) reason = `HbA1c outside ${ELIGIBILITY.minHba1c} to ${ELIGIBILITY.maxHba1c}%`
    const p = { id: `SUB-${String(parts.length + 1).padStart(3, '0')}`, site: f.site, age, sex: f.sex, hba1c, hba1c_cat: hba1cCat(hba1c), therapy: f.therapy,
      eligibility: reason ? 'SCREEN_FAILURE' : 'ELIGIBLE', reason, trial_status: reason ? 'SCREENING' : 'ENROLLED',
      consent: f.consent ? 'OBTAINED' : 'NOT_OBTAINED', baseline_complete: f.baseline }
    setParts([...parts, p])
    return p
  }
  const addAE = async (ae) => {
    if (!MOCK) {
      await api('/adverse-events', { method: 'POST', body: toApiAE(ae) })
      return refresh()
    }
    setAes([...aes, { ...ae, id: aes.length + 1, status: 'SUBMITTED', reported_at: new Date().toISOString().slice(0, 10) }])
  }

  const takeArm = (key) => {
    let b = blocks.current[key]
    if (!b || !b.length) b = blocks.current[key] = ['A', 'A', 'B', 'B'].slice(0, BLOCK_SIZE).sort(() => Math.random() - 0.5)
    return b.pop()
  }
  const randomize = async (id) => {
    if (!MOCK) {
      const r = await api('/randomization', { method: 'POST', body: { participant_id: id } })
      await refresh()
      return { message: r.message || 'Randomization recorded', randomization_number: r.randomization_number, arm: r.arm ?? null }
    }
    const p = parts.find((x) => x.id === id)
    if (!p || !prereqs(p).every(([, ok]) => ok)) throw new Error('Prerequisites not met')
    const rand_no = `RAND-${String(parts.filter((x) => x.rand_no).length + 1).padStart(4, '0')}`
    const arm = takeArm(stratumKey(p))
    setParts(parts.map((x) => (x.id === id ? { ...x, arm, rand_no, week: 0 } : x)))
    if (CHAINED_EVENT_TYPES.includes('RANDOMIZED'))
      setChain([...chain, await makeEntry(chain[chain.length - 1] || null, 'RANDOMIZED', user.id, { participant_id: id, randomization_number: rand_no, stratum_key: stratumKey(p) })])
    return { message: 'Randomization recorded', randomization_number: rand_no, arm: armOf(user, arm) }
  }
  return <Ctx.Provider value={{ user, login, logout, parts, aes, chain, setChain, vitals, dash, loadErr, refresh, addParticipant, addAE, randomize }}>{children}</Ctx.Provider>
}

/* ── Icons (inline SVG for zero deps) ── */
const Icon = ({ name, cls = 'w-4 h-4' }) => {
  const paths = {
    dashboard: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
    patients: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z',
    randomize: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
    reports: 'M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
    audit: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
    config: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z',
    logout: 'M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1',
    chevron: 'M9 5l7 7-7 7',
    user: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
    bell: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9',
    shield: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
  }
  return (
    <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      {name === 'config' ? (
        paths[name].split(' M').map((d, i) => <path key={i} strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={i === 0 ? d : 'M' + d} />)
      ) : (
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={paths[name] || ''} />
      )}
    </svg>
  )
}

const NAV = {
  PATIENT:      [['/app/', 'Dashboard', 'dashboard']],
  COORDINATOR:  [['/app/', 'Dashboard', 'dashboard'], ['/app/patients', 'Patients', 'patients'], ['/app/randomize', 'Randomize', 'randomize']],
  SUPERVISOR:   [['/app/', 'Dashboard', 'dashboard'], ['/app/patients', 'Patients', 'patients'], ['/app/reports', 'Reports', 'reports'], ['/app/audit', 'Audit', 'audit'], ['/app/config', 'Config', 'config']],
}
const ROLE_LABEL = { PATIENT: 'Patient', COORDINATOR: 'Coordinator', SUPERVISOR: 'Supervisor' }
const ROLE_BADGE_COLOR = {
  PATIENT: 'bg-sky-500/20 text-sky-200',
  COORDINATOR: 'bg-emerald-500/20 text-emerald-200',
  SUPERVISOR: 'bg-violet-500/20 text-violet-200',
}

function Shell({ children }) {
  const { user, logout } = useStore()
  const initials = user.username.slice(0, 2).toUpperCase()
  return (
    <div className="h-screen flex flex-col bg-slate-100">
      {/* ── Top header bar ── */}
      <header className="h-12 bg-[#1b4f5e] text-white flex items-center px-4 shrink-0 z-20 shadow-md">
        <div className="flex items-center gap-2 mr-6">
          <span className="text-lg font-bold tracking-widest text-white">TRACE</span>
          <span className="text-[10px] font-medium text-trace-mid/80 hidden sm:inline leading-tight">
            Clinical Trial Research &amp; Evaluation
          </span>
        </div>
        {/* Breadcrumb-style study badge */}
        <div className="flex items-center gap-1.5 text-xs text-white/60 mr-auto">
          <span className="hidden sm:inline">ARIA &gt; REGISTRY</span>
          <span className="inline-block bg-trace-mid/20 text-trace-mid text-[10px] font-bold px-2 py-0.5 rounded ml-2">VOL. 2A</span>
        </div>
        {/* Right actions */}
        <div className="flex items-center gap-3">
          <button className="relative text-white/60 hover:text-white transition-colors" aria-label="Notifications">
            <Icon name="bell" cls="w-5 h-5" />
            <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-amber-400 rounded-full pulse-dot" />
          </button>
          <div className="flex items-center gap-2 pl-3 border-l border-white/20">
            <div className="w-7 h-7 rounded-full bg-trace-mid/40 flex items-center justify-center text-xs font-bold text-white">
              {initials}
            </div>
            <div className="hidden sm:block">
              <div className="text-xs font-medium text-white leading-none">{user.username}</div>
              <div className={`text-[10px] mt-0.5 px-1.5 py-0.5 rounded-full font-medium ${ROLE_BADGE_COLOR[user.role]}`}>
                {ROLE_LABEL[user.role]}{user.role === 'SUPERVISOR' ? (user.unblinded ? ' · Unblinded' : ' · Blinded') : ''}
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* ── Sidebar ── */}
        <aside className="w-52 shrink-0 sidebar-grad text-white flex flex-col py-4 px-2 border-r border-white/5 shadow-xl z-10">
          {/* Nav section label */}
          <div className="px-3 mb-2">
            <span className="text-[10px] font-bold uppercase tracking-widest text-white/30">Area / Directory</span>
          </div>
          <nav className="flex flex-col gap-0.5 flex-1">
            {NAV[user.role].map(([to, label, icon]) => (
              <NavLink
                key={to}
                to={to}
                end
                className={({ isActive }) =>
                  isActive ? 'nav-link-active' : 'nav-link'
                }
              >
                <Icon name={icon} cls="w-4 h-4 shrink-0" />
                {label}
              </NavLink>
            ))}
          </nav>

          {/* Bottom: status + logout */}
          <div className="border-t border-white/10 pt-3 mt-2 px-2">
            <div className="flex items-center gap-1.5 mb-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 pulse-dot" />
              <span className="text-[10px] text-white/40 font-medium">NODE 04 · REGISTRY LIVE</span>
            </div>
            <button
              onClick={logout}
              className="flex items-center gap-2 text-xs text-white/50 hover:text-white transition-colors w-full px-1"
            >
              <Icon name="logout" cls="w-3.5 h-3.5" />
              Exit Session
            </button>
          </div>
        </aside>

        {/* ── Main content ── */}
        <main className="flex-1 min-w-0 bg-[#f0f4f2] flex flex-col overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  )
}

const Guard = ({ action, children }) => (can(useStore().user, action) ? children : <Denied />)

function Routed() {
  const { user, loadErr } = useStore()
  if (!user) return <Login />
  return (
    <Shell>
      {loadErr && <div role="alert" className="bg-red-50 text-red-700 border-b border-red-200 text-xs px-4 py-2">Could not load data from the server: {loadErr}</div>}
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/patients" element={<Guard action="view_participants"><Patients /></Guard>} />
        <Route path="/randomize" element={<Guard action="randomize"><Randomize /></Guard>} />
        <Route path="/reports" element={<Guard action="oversight"><Reports /></Guard>} />
        <Route path="/audit" element={<Guard action="audit"><Audit /></Guard>} />
        <Route path="/config" element={<Guard action="manage_users"><Config /></Guard>} />
        <Route path="*" element={<Navigate to="/app/" />} />
      </Routes>
    </Shell>
  )
}

export default function App() {
  return (
    <Provider>
      <HashRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/app/*" element={<Routed />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </HashRouter>
    </Provider>
  )
}
