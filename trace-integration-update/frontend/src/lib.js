// Shared contract (mirrors backend/shared/constants.py) + API client + mock data.
export const TRIAL_WEEKS = 16
export const VISIT_WEEKS = [0, 4, 8, 12, 16]
export const BLOCK_SIZE = 4
export const CHAINED_EVENT_TYPES = ['RANDOMIZED']
// Placeholder eligibility values until the Biotech member finalises them (spec open decision 4).
export const ELIGIBILITY = { minAge: 18, maxAge: 65, minHba1c: 7.0, maxHba1c: 10.5 }

const BASE = import.meta.env.VITE_API_BASE_URL
export const MOCK = !BASE || BASE === 'xxxx'
export const getToken = () => sessionStorage.getItem('trace_token')
export const setToken = (t) => (t ? sessionStorage.setItem('trace_token', t) : sessionStorage.removeItem('trace_token'))

export async function api(path, opts = {}) {
  const res = await fetch(BASE + path, {
    ...opts,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}`, ...(opts.headers || {}) },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw Object.assign(new Error(data.error || 'Request failed'), { code: res.status })
  return data
}

// Server-side CSV export (Module 3). The server applies the blinding rule to the arm column.
export async function downloadServerCsv() {
  const res = await fetch(BASE + '/exports/participants.csv', { headers: { Authorization: `Bearer ${getToken()}` } })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.error || 'Export failed')
  }
  const a = document.createElement('a')
  a.href = URL.createObjectURL(await res.blob())
  a.download = 'participants.csv'
  a.click()
}

// Permission matrix (Section 6, Module 4). UI convenience only; the backend is the real gate.
const C = 'COORDINATOR', S = 'SUPERVISOR', P = 'PATIENT'
const MATRIX = {
  view_participants: [C, S], enroll: [C], record_visit: [C], report_ae: [P, C], review_ae: [C],
  randomize: [C], ops_dashboard: [C, S], oversight: [S], export: [S], audit: [S], manage_users: [S],
}
export const can = (u, a) => !!u && (MATRIX[a] || []).includes(u.role)
export const canSeeArm = (u) => !!u && u.role === S && u.unblinded === true
export const armOf = (u, arm) => (canSeeArm(u) ? arm : null) // blinded users get null, never an error

export const MOCK_USERS = {
  patient: { id: 'U-0001', username: 'patient', role: P, participant_id: 'SUB-001', unblinded: false },
  coordinator: { id: 'U-0002', username: 'coordinator', role: C, unblinded: false },
  supervisor: { id: 'U-0003', username: 'supervisor', role: S, unblinded: false },
  supervisor_unblinded: { id: 'U-0004', username: 'supervisor_unblinded', role: S, unblinded: true },
}

export const hba1cCat = (v) => (Number(v) >= 8.5 ? 'HIGH' : 'LOW')
export const stratumKey = (p) => `${p.site}|${p.hba1c_cat}|${p.therapy}`
export const trialStatus = (p) => (p.trial_status === 'ENROLLED' && p.rand_no ? 'ACTIVE' : p.trial_status)
export const prereqs = (p) => [
  ['Eligibility is ELIGIBLE', p.eligibility === 'ELIGIBLE'],
  ['Consent recorded', p.consent === 'OBTAINED'],
  ['Baseline data complete', p.baseline_complete],
  ['Not already randomized', !p.rand_no],
]

export const SEED = [
  { id: 'SUB-001', site: 'SITE-01', age: 52, sex: 'F', hba1c: 9.1, hba1c_cat: 'HIGH', therapy: 'STABLE', eligibility: 'ELIGIBLE', trial_status: 'ENROLLED', consent: 'OBTAINED', baseline_complete: true, arm: 'A', rand_no: 'RAND-0001', week: 8 },
  { id: 'SUB-002', site: 'SITE-01', age: 47, sex: 'M', hba1c: 7.8, hba1c_cat: 'LOW', therapy: 'STABLE', eligibility: 'ELIGIBLE', trial_status: 'ENROLLED', consent: 'OBTAINED', baseline_complete: true, arm: 'B', rand_no: 'RAND-0002', week: 4 },
  { id: 'SUB-003', site: 'SITE-02', age: 58, sex: 'F', hba1c: 8.7, hba1c_cat: 'HIGH', therapy: 'STABLE', eligibility: 'ELIGIBLE', trial_status: 'ENROLLED', consent: 'OBTAINED', baseline_complete: true },
  { id: 'SUB-004', site: 'SITE-02', age: 39, sex: 'M', hba1c: 8.0, hba1c_cat: 'LOW', therapy: 'NONE', eligibility: 'PENDING_REVIEW', trial_status: 'SCREENING', consent: 'OBTAINED', baseline_complete: false },
  { id: 'SUB-005', site: 'SITE-01', age: 71, sex: 'M', hba1c: 9.0, hba1c_cat: 'HIGH', therapy: 'STABLE', eligibility: 'SCREEN_FAILURE', reason: 'Age above 65', trial_status: 'SCREENING', consent: 'OBTAINED', baseline_complete: false },
  { id: 'SUB-006', site: 'SITE-02', age: 44, sex: 'F', hba1c: 7.5, hba1c_cat: 'LOW', therapy: 'STABLE', eligibility: 'ELIGIBLE', trial_status: 'ENROLLED', consent: 'OBTAINED', baseline_complete: true },
  { id: 'SUB-007', site: 'SITE-01', age: 60, sex: 'M', hba1c: 8.9, hba1c_cat: 'HIGH', therapy: 'NONE', eligibility: 'ELIGIBLE', trial_status: 'ENROLLED', consent: 'NOT_OBTAINED', baseline_complete: true },
]
export const SEED_VITALS = [
  { week: 0, hba1c: 9.4, glucose: 168, weight: 82.0, bp: '134/86' },
  { week: 4, hba1c: 9.2, glucose: 160, weight: 81.4, bp: '132/84' },
  { week: 8, hba1c: 9.1, glucose: 155, weight: 80.9, bp: '130/82' },
]

// Hash chain (Section 3.7): SHA-256, genesis = 64 zeros, canonical JSON with sorted keys.
export const GENESIS = '0'.repeat(64)
const sha256 = async (s) => [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)))].map((b) => b.toString(16).padStart(2, '0')).join('')
const canon = (o) => JSON.stringify(o, (k, v) => (v && typeof v === 'object' && !Array.isArray(v) ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => (a < b ? -1 : 1))) : v))
export async function makeEntry(prev, event_type, actor_id, payload) {
  const e = { seq: prev ? prev.seq + 1 : 1, event_type, actor_id, payload, created_at: new Date().toISOString(), prev_hash: prev ? prev.hash : GENESIS }
  return { ...e, hash: await sha256(e.prev_hash + canon(e)) }
}
export async function verifyChain(chain) {
  let prev = GENESIS
  for (const { hash, ...rest } of chain) {
    if (rest.prev_hash !== prev || (await sha256(prev + canon(rest))) !== hash) return { ok: false, broken_seq: rest.seq }
    prev = hash
  }
  return { ok: true }
}
