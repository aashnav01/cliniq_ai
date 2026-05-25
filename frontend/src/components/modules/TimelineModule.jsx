import React, { useState, useEffect } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'https://cliniq-ai-kqfz.onrender.com'

const TYPE_COLORS = {
  soap: '#0891b2',
  handover: '#7c3aed',
  differential_diagnosis: '#059669',
  rapid: '#d97706',
  prescription: '#dc2626',
  default: '#64748b'
}

const TYPE_ICONS = {
  soap: '📋',
  handover: '🔄',
  differential_diagnosis: '🧠',
  rapid: '⚡',
  prescription: '💊',
  default: '📄'
}

export default function TimelineModule() {
  const [patients, setPatients] = useState([])
  const [selectedPatient, setSelectedPatient] = useState(null)
  const [timeline, setTimeline] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [expandedItems, setExpandedItems] = useState(new Set())

  useEffect(() => {
    fetch(`${API_URL}/api/patients`)
      .then(r => r.json())
      .then(setPatients)
      .catch(() => {})
  }, [])

  const loadTimeline = async (patientId) => {
    setLoading(true)
    setError(null)
    setTimeline(null)
    try {
      const res = await fetch(`${API_URL}/api/patient/${patientId}/timeline`)
      if (!res.ok) throw new Error('Failed to load timeline')
      const data = await res.json()
      setTimeline(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const toggleExpand = (id) => {
    setExpandedItems(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const formatTime = (ts) => {
    if (!ts) return '—'
    try {
      return new Date(ts).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
    } catch { return ts }
  }

  return (
    <div className="module-container">
      <div className="module-header">
        <div>
          <h1 className="module-title">📅 Patient Timeline</h1>
          <p className="module-subtitle">Complete chronological audit log — every analysis, prescription, and flag for a patient</p>
        </div>
      </div>

      {/* Patient selector */}
      <div className="timeline-selector">
        <select
          className="form-input"
          style={{ maxWidth: '380px' }}
          value={selectedPatient || ''}
          onChange={e => {
            const id = parseInt(e.target.value)
            setSelectedPatient(id)
            if (id) loadTimeline(id)
          }}
        >
          <option value="">— Select a patient —</option>
          {patients.map(p => (
            <option key={p.id} value={p.id}>
              {p.name}{p.mrn ? ` (MRN: ${p.mrn})` : ''}
            </option>
          ))}
        </select>
        {patients.length === 0 && (
          <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '8px' }}>
            No patients found. Create patients via the FHIR module or Prescription module.
          </p>
        )}
      </div>

      {loading && (
        <div className="empty-state">
          <div className="spinner" />
          <p>Loading timeline...</p>
        </div>
      )}

      {error && <div className="error-banner">⚠ {error}</div>}

      {timeline && (
        <>
          {/* Patient card */}
          <div className="timeline-patient-card">
            <div className="timeline-patient-name">{timeline.patient.name}</div>
            {timeline.patient.mrn && <span className="drug-chip">MRN: {timeline.patient.mrn}</span>}
            {timeline.patient.allergies?.map((a, i) => (
              <span key={i} className="flag-type-badge" style={{ background: 'rgba(239,68,68,0.15)', color: '#ef4444' }}>
                ⚠ {a}
              </span>
            ))}
            <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: '13px' }}>
              {timeline.count} event{timeline.count !== 1 ? 's' : ''}
            </span>
          </div>

          {/* Timeline */}
          <div className="timeline-track">
            {timeline.timeline.map((item, idx) => {
              const color = TYPE_COLORS[item.analysis_type || item.type] || TYPE_COLORS.default
              const icon = TYPE_ICONS[item.analysis_type || item.type] || TYPE_ICONS.default
              const isExpanded = expandedItems.has(idx)
              const key = `item-${idx}`

              return (
                <div key={key} className="timeline-item">
                  <div className="timeline-dot" style={{ background: color }} />
                  <div className="timeline-line" style={{ background: `${color}33` }} />
                  <div className="timeline-content">
                    <div className="timeline-item-header" onClick={() => toggleExpand(idx)}>
                      <span className="timeline-icon">{icon}</span>
                      <span className="timeline-type" style={{ color }}>
                        {item.analysis_type?.replace('_', ' ') || item.type}
                      </span>
                      <span className="timeline-time">{formatTime(item.timestamp)}</span>
                      {item.type === 'prescription' && item.has_critical_flags && (
                        <span className="flag-type-badge" style={{ background: 'rgba(239,68,68,0.2)', color: '#ef4444' }}>🔴 Critical Flag</span>
                      )}
                      {item.feedback === 'up' && <span title="Rated helpful">👍</span>}
                      <span className="timeline-expand">{isExpanded ? '▲' : '▼'}</span>
                    </div>

                    <p className="timeline-summary">{item.summary || item.drugs?.join(', ')}</p>

                    {isExpanded && (
                      <div className="timeline-detail">
                        {item.type === 'analysis' && item.data && (
                          <>
                            {item.data.news2 && (
                              <div className={`news2-badge news2-${item.data.news2.color}`}>
                                NEWS2: {item.data.news2.score} — {item.data.news2.action}
                              </div>
                            )}
                            {item.data.red_flags?.length > 0 && (
                              <div style={{ marginTop: '8px' }}>
                                {item.data.red_flags.map((f, fi) => (
                                  <div key={fi} className={`flag-card flag-${f.severity}`} style={{ marginBottom: '4px' }}>
                                    <strong>{f.title}</strong>: {f.explanation}
                                  </div>
                                ))}
                              </div>
                            )}
                            {item.data.icd10?.suggestions?.length > 0 && (
                              <div className="icd10-strip" style={{ marginTop: '8px' }}>
                                {item.data.icd10.suggestions.map((c, ci) => (
                                  <span key={ci} className="icd-chip">{c.code} — {c.description}</span>
                                ))}
                              </div>
                            )}
                          </>
                        )}
                        {item.type === 'prescription' && (
                          <div style={{ marginTop: '8px' }}>
                            <strong>Drugs:</strong> {item.drugs?.join(', ')}
                            <br />
                            <strong>Safety:</strong> <span style={{ color: item.overall_safety === 'dangerous' ? '#ef4444' : item.overall_safety === 'caution' ? '#f59e0b' : '#10b981' }}>{item.overall_safety?.toUpperCase()}</span>
                            {item.flags_count > 0 && ` · ${item.flags_count} flag(s)`}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}

      {!timeline && !loading && !selectedPatient && (
        <div className="empty-state">
          <div className="empty-icon">📅</div>
          <p>Select a patient to view their complete clinical timeline</p>
        </div>
      )}
    </div>
  )
}
