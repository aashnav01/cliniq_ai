import React, { useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'https://cliniq-ai-kqfz.onrender.com'

export default function FhirModule({ shiftId }) {
  const [activeTab, setActiveTab] = useState('patient')
  const [patientForm, setPatientForm] = useState({ family_name: '', given_name: '', birth_date: '', gender: 'unknown', identifier: '' })
  const [bundle, setBundle] = useState(null)
  const [patientResult, setPatientResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const createPatient = async (e) => {
    e.preventDefault()
    setLoading(true); setError(null); setPatientResult(null)
    try {
      const res = await fetch(`${API_URL}/fhir/Patient`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patientForm)
      })
      if (!res.ok) throw new Error(await res.text())
      setPatientResult(await res.json())
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  const exportBundle = async () => {
    if (!shiftId) { setError('No active shift — start a shift first'); return }
    setLoading(true); setError(null); setBundle(null)
    try {
      const res = await fetch(`${API_URL}/fhir/shift/${shiftId}/bundle`)
      if (!res.ok) throw new Error(await res.text())
      setBundle(await res.json())
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  const downloadBundle = () => {
    if (!bundle) return
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ClinIQ_FHIR_Bundle_Shift${shiftId}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="module-container">
      <div className="module-header">
        <div>
          <h1 className="module-title">🏥 FHIR R4 Integration</h1>
          <p className="module-subtitle">HL7 FHIR R4 — create patients, export clinical documents, EHR handoff bundles</p>
        </div>
      </div>

      <div className="fhir-tab-bar">
        {[['patient', '👤 Create Patient'], ['bundle', '📦 Export Bundle'], ['metadata', 'ℹ Capability']].map(([tab, label]) => (
          <button key={tab} className={`fhir-tab ${activeTab === tab ? 'active' : ''}`} onClick={() => setActiveTab(tab)}>
            {label}
          </button>
        ))}
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {/* Create Patient */}
      {activeTab === 'patient' && (
        <div className="two-col-layout">
          <div className="input-panel">
            <form onSubmit={createPatient}>
              <div className="form-group">
                <label className="form-label">Family Name *</label>
                <input className="form-input" required value={patientForm.family_name}
                  onChange={e => setPatientForm(p => ({ ...p, family_name: e.target.value }))} placeholder="Smith" />
              </div>
              <div className="form-group">
                <label className="form-label">Given Name *</label>
                <input className="form-input" required value={patientForm.given_name}
                  onChange={e => setPatientForm(p => ({ ...p, given_name: e.target.value }))} placeholder="John" />
              </div>
              <div className="form-group">
                <label className="form-label">Date of Birth</label>
                <input className="form-input" type="date" value={patientForm.birth_date}
                  onChange={e => setPatientForm(p => ({ ...p, birth_date: e.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">Gender</label>
                <select className="form-input" value={patientForm.gender}
                  onChange={e => setPatientForm(p => ({ ...p, gender: e.target.value }))}>
                  <option value="unknown">Unknown</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">MRN / Identifier</label>
                <input className="form-input" value={patientForm.identifier}
                  onChange={e => setPatientForm(p => ({ ...p, identifier: e.target.value }))} placeholder="MRN-001234" />
              </div>
              <button className="btn-primary" type="submit" disabled={loading} style={{ width: '100%' }}>
                {loading ? 'Creating...' : '+ Create FHIR Patient'}
              </button>
            </form>
          </div>
          <div className="results-panel">
            {patientResult ? (
              <div>
                <div className="rx-verdict rx-safe">✅ Patient created successfully</div>
                <div className="fhir-resource-box">
                  <div className="fhir-resource-label">FHIR Patient Resource</div>
                  <pre className="fhir-json">{JSON.stringify(patientResult, null, 2)}</pre>
                </div>
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-icon">👤</div>
                <p>Create a FHIR R4 Patient resource. The patient will be stored and can be referenced in SOAP notes, prescriptions, and bundles.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Export Bundle */}
      {activeTab === 'bundle' && (
        <div>
          <div className="card" style={{ marginBottom: '16px' }}>
            <h3 className="section-label">Export Current Shift as FHIR Bundle</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginBottom: '12px' }}>
              Exports the complete shift (Encounter + all SOAP notes + DDx reports + MedicationStatements) as an HL7 FHIR R4 Bundle.
              {shiftId ? ` Shift #${shiftId} is active.` : ' No active shift — start a shift first.'}
            </p>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button className="btn-primary" onClick={exportBundle} disabled={loading || !shiftId}>
                {loading ? 'Exporting...' : '📦 Export FHIR Bundle'}
              </button>
              {bundle && (
                <button className="btn-ghost" onClick={downloadBundle}>
                  ⬇ Download JSON
                </button>
              )}
            </div>
          </div>

          {bundle && (
            <div className="fhir-resource-box">
              <div className="fhir-resource-label">
                Bundle · {bundle.entry?.length || 0} resources · {bundle.type}
              </div>
              <pre className="fhir-json">{JSON.stringify(bundle, null, 2)}</pre>
            </div>
          )}
        </div>
      )}

      {/* Capability Statement */}
      {activeTab === 'metadata' && <FhirCapability />}
    </div>
  )
}

function FhirCapability() {
  const [cap, setCap] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/fhir/metadata`)
      setCap(await res.json())
    } catch {}
    finally { setLoading(false) }
  }

  return (
    <div>
      {!cap && (
        <div className="empty-state">
          <div className="empty-icon">ℹ</div>
          <button className="btn-primary" onClick={load} disabled={loading}>
            {loading ? 'Loading...' : 'Load Capability Statement'}
          </button>
        </div>
      )}
      {cap && (
        <div className="fhir-resource-box">
          <div className="fhir-resource-label">CapabilityStatement · FHIR R4</div>
          <pre className="fhir-json">{JSON.stringify(cap, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}
