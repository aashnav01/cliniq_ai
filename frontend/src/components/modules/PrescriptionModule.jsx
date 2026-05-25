import React, { useState, useRef } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'https://cliniq-ai-kqfz.onrender.com'

export default function PrescriptionModule({ onLoadingChange, shiftId }) {
  const [drugs, setDrugs] = useState('')
  const [patientName, setPatientName] = useState('')
  const [allergies, setAllergies] = useState('')
  const [weight, setWeight] = useState('')
  const [renal, setRenal] = useState('normal')
  const [hepatic, setHepatic] = useState('normal')
  const [age, setAge] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    const drugList = drugs.split('\n').map(d => d.trim()).filter(Boolean)
    if (!drugList.length) return

    setError(null)
    setResult(null)
    onLoadingChange(true, 'Checking prescription safety...')

    try {
      const res = await fetch(`${API_URL}/api/analyze/prescription-safety`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          drugs: drugList,
          shift_id: shiftId,
          patient_context: {
            allergies: allergies.split(',').map(a => a.trim()).filter(Boolean),
            weight_kg: weight ? parseFloat(weight) : null,
            renal_function: renal,
            hepatic_function: hepatic,
            age: age || null,
          }
        })
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      onLoadingChange(false)
    }
  }

  const overallClass = result?.data?.overall_safety === 'dangerous' ? 'rx-dangerous'
    : result?.data?.overall_safety === 'caution' ? 'rx-caution' : 'rx-safe'

  const severityIcon = { critical: '🔴', warning: '🟡', watch: '🔵' }
  const severityClass = { critical: 'flag-critical', warning: 'flag-warning', watch: 'flag-watch' }

  return (
    <div className="module-container">
      <div className="module-header">
        <div>
          <h1 className="module-title">💊 Prescription Safety Checker</h1>
          <p className="module-subtitle">Deep safety check: interactions, renal/hepatic dosing, allergies, contraindications</p>
        </div>
      </div>

      <div className="two-col-layout">
        {/* Input */}
        <div className="input-panel">
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Medications (one per line) *</label>
              <textarea
                ref={inputRef}
                className="form-textarea"
                rows={6}
                placeholder={"warfarin 5mg once daily\naspirin 75mg once daily\nramipril 10mg once daily"}
                value={drugs}
                onChange={e => setDrugs(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Patient Allergies (comma-separated)</label>
              <input
                className="form-input"
                placeholder="penicillin, sulfa, NSAIDs"
                value={allergies}
                onChange={e => setAllergies(e.target.value)}
              />
            </div>

            <div className="rx-context-grid">
              <div className="form-group">
                <label className="form-label">Weight (kg)</label>
                <input className="form-input" type="number" placeholder="70" value={weight} onChange={e => setWeight(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Age</label>
                <input className="form-input" type="number" placeholder="65" value={age} onChange={e => setAge(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Renal Function</label>
                <select className="form-input" value={renal} onChange={e => setRenal(e.target.value)}>
                  <option value="normal">Normal</option>
                  <option value="mild">Mild impairment</option>
                  <option value="moderate">Moderate (eGFR 30-59)</option>
                  <option value="severe">Severe (eGFR 15-29)</option>
                  <option value="dialysis">Dialysis / ESRD</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Hepatic Function</label>
                <select className="form-input" value={hepatic} onChange={e => setHepatic(e.target.value)}>
                  <option value="normal">Normal</option>
                  <option value="mild">Mild (Child-Pugh A)</option>
                  <option value="moderate">Moderate (Child-Pugh B)</option>
                  <option value="severe">Severe (Child-Pugh C)</option>
                </select>
              </div>
            </div>

            <button className="btn-primary" type="submit" style={{ width: '100%', marginTop: '8px' }}>
              🔍 Check Safety
            </button>
          </form>
        </div>

        {/* Results */}
        <div className="results-panel">
          {error && <div className="error-banner">⚠ {error}</div>}

          {result && (
            <>
              {/* Overall verdict */}
              <div className={`rx-verdict ${overallClass}`}>
                {result.data.overall_safety === 'dangerous' && '🔴 DANGEROUS — Do not prescribe without review'}
                {result.data.overall_safety === 'caution' && '🟡 CAUTION — Review flagged issues before prescribing'}
                {result.data.overall_safety === 'safe' && '🟢 SAFE — No major issues detected'}
              </div>

              {/* Summary */}
              {result.data.summary && (
                <div className="card" style={{ marginBottom: '12px' }}>
                  <p style={{ margin: 0, fontSize: '13px', lineHeight: 1.6 }}>{result.data.summary}</p>
                </div>
              )}

              {/* Flags */}
              {result.data.flags?.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                  <h3 className="section-label">Safety Flags ({result.data.flags.length})</h3>
                  {result.data.flags.map((flag, i) => (
                    <div key={i} className={`flag-card ${severityClass[flag.severity] || 'flag-watch'}`}>
                      <div className="flag-header">
                        <span>{severityIcon[flag.severity] || '🔵'}</span>
                        <strong>{flag.title}</strong>
                        <span className="flag-type-badge">{flag.type?.replace('_', ' ')}</span>
                      </div>
                      {flag.drugs_involved?.length > 0 && (
                        <div className="flag-drugs">
                          {flag.drugs_involved.map((d, j) => <span key={j} className="drug-chip">{d}</span>)}
                        </div>
                      )}
                      <p className="flag-detail">{flag.detail}</p>
                      {flag.recommendation && (
                        <div className="flag-rec">
                          <strong>Action:</strong> {flag.recommendation}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Dose adjustments */}
              {result.data.dose_adjustments?.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                  <h3 className="section-label">Dose Adjustments Required</h3>
                  {result.data.dose_adjustments.map((adj, i) => (
                    <div key={i} className="dose-adj-card">
                      <strong>{adj.drug}</strong>
                      <div className="dose-adj-row">
                        <span className="dose-current">{adj.current || 'Current dose'}</span>
                        <span className="dose-arrow">→</span>
                        <span className="dose-recommended">{adj.recommended}</span>
                      </div>
                      <p className="dose-reason">{adj.reason}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Safe drugs */}
              {result.data.safe_drugs?.length > 0 && (
                <div>
                  <h3 className="section-label">✅ No Issues Found</h3>
                  <div className="safe-drugs-list">
                    {result.data.safe_drugs.map((d, i) => <span key={i} className="safe-drug-chip">{d}</span>)}
                  </div>
                </div>
              )}

              <div className="processing-badge" style={{ marginTop: '12px' }}>
                ⚡ {result.processing_time_ms}ms
              </div>
            </>
          )}

          {!result && !error && (
            <div className="empty-state">
              <div className="empty-icon">💊</div>
              <p>Enter medications above to check for interactions, allergy conflicts, and dose adjustments</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
