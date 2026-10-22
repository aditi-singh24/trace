// Pure helpers that translate backend (API) shapes into the shapes the pages already use.
// No browser APIs in here, so they can be unit-tested with plain Node.

const REASONS = {
  age_in_range: 'Age outside the allowed range',
  t2dm_confirmed: 'Type 2 diabetes not confirmed',
  hba1c_in_range: 'HbA1c outside the allowed range',
}
export const prettyReason = (r) =>
  r ? r.replace(/^Failed:\s*/, '').split(',').map((x) => REASONS[x.trim()] || x.trim()).join('; ') : null

export const fromApiParticipant = (p) => ({
  id: p.participant_id,
  site: p.site_id,
  age: p.age,
  sex: p.sex,
  hba1c: p.baseline_hba1c,
  hba1c_cat: p.hba1c_cat,
  therapy: p.therapy,
  eligibility: p.eligibility_status,
  reason: prettyReason(p.eligibility_reason),
  trial_status: p.trial_status,
  consent: p.consent_status,
  baseline_complete: p.baseline_complete,
  arm: p.arm ?? null,                       // null unless the server says this user may see it
  rand_no: p.randomization_number || null,
  week: p.current_week ?? 0,
})

export const fromApiAE = (a) => ({
  id: a.id,
  participant_id: a.participant_id,
  severity: a.severity,
  serious: a.serious,
  relationship: a.relationship_to_treatment || 'NOT_RELATED',
  description: a.description,
  onset: a.onset_date,
  status: a.status,
  reported_at: (a.reported_at || '').slice(0, 10),
})

export const toApiAE = (ae) => ({
  participant_id: ae.participant_id,
  onset_date: ae.onset,
  severity: ae.severity,
  serious: !!ae.serious,
  relationship_to_treatment: ae.relationship || null,
  description: ae.description,
})

// Measurements -> [{week, hba1c, glucose, weight, bp}], one row per visit week (latest non-empty value wins).
export const toVitals = (measurements) => {
  const byWeek = {}
  for (const m of measurements) {
    const cur = (byWeek[m.visit_week] = byWeek[m.visit_week] || {})
    for (const [k, v] of Object.entries(m)) if (v !== null && v !== undefined) cur[k] = v
  }
  return Object.keys(byWeek).map(Number).sort((a, b) => a - b).map((w) => {
    const m = byWeek[w]
    return {
      week: w,
      hba1c: m.hba1c ?? null,
      glucose: m.fasting_glucose ?? null,
      weight: m.weight_kg ?? null,
      bp: m.systolic != null && m.diastolic != null ? `${m.systolic}/${m.diastolic}` : null,
    }
  })
}
