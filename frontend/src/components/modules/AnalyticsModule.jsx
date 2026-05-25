import React, { useState, useEffect } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'https://cliniq-ai-kqfz.onrender.com'

function BarChart({ data, max, color, label }) {
  return (
    <div className="analytics-bar-row">
      <span className="bar-label">{label}</span>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: max ? `${(data / max) * 100}%` : '0%', background: color }} />
      </div>
      <span className="bar-value">{data}</span>
    </div>
  )
}

export default function AnalyticsModule() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_URL}/api/analytics/shift`)
      if (!res.ok) throw new Error('Failed to load analytics')
      setData(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const typeColors = {
    soap: '#0891b2',
    handover: '#7c3aed',
    differential_diagnosis: '#059669',
    rapid: '#d97706',
    prescription_safety: '#dc2626',
  }
  const typeLabels = {
    soap: 'SOAP Notes',
    handover: 'Handovers',
    differential_diagnosis: 'Differential Dx',
    rapid: 'Rapid Notes',
    prescription_safety: 'Rx Safety Checks',
  }

  const maxCount = data ? Math.max(...Object.values(data.by_type || {}).map(t => t.count), 1) : 1
  const maxMs = data ? Math.max(...Object.values(data.by_type || {}).map(t => t.avg_ms), 1) : 1

  return (
    <div className="module-container">
      <div className="module-header">
        <div>
          <h1 className="module-title">📊 Shift Analytics</h1>
          <p className="module-subtitle">Real-time metrics from your clinical data</p>
        </div>
        <button className="btn-ghost" onClick={load} disabled={loading} style={{ padding: '8px 16px' }}>
          {loading ? '⟳' : '↻ Refresh'}
        </button>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {loading && (
        <div className="empty-state"><div className="spinner" /><p>Loading analytics...</p></div>
      )}

      {data && !loading && (
        <>
          {/* KPI cards */}
          <div className="analytics-kpi-grid">
            <div className="kpi-card">
              <div className="kpi-value">{data.total_analyses}</div>
              <div className="kpi-label">Total Analyses</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-value">{data.total_shifts}</div>
              <div className="kpi-label">Shifts Recorded</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-value">{data.avg_processing_ms}ms</div>
              <div className="kpi-label">Avg AI Response</div>
            </div>
            <div className="kpi-card" style={{ borderColor: data.red_flags?.critical > 0 ? '#ef4444' : undefined }}>
              <div className="kpi-value" style={{ color: data.red_flags?.critical > 0 ? '#ef4444' : undefined }}>
                {data.red_flags?.critical || 0}
              </div>
              <div className="kpi-label">Critical Red Flags</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-value">{data.total_prescriptions || 0}</div>
              <div className="kpi-label">Prescriptions Checked</div>
            </div>
            <div className="kpi-card" style={{ borderColor: data.critical_prescriptions > 0 ? '#ef4444' : undefined }}>
              <div className="kpi-value" style={{ color: data.critical_prescriptions > 0 ? '#ef4444' : undefined }}>
                {data.critical_prescriptions || 0}
              </div>
              <div className="kpi-label">Dangerous Rx Flags</div>
            </div>
          </div>

          <div className="analytics-charts-grid">
            {/* By type */}
            <div className="card">
              <h3 className="section-label">Analyses by Type</h3>
              {Object.entries(data.by_type || {}).map(([type, stats]) => (
                <BarChart
                  key={type}
                  data={stats.count}
                  max={maxCount}
                  color={typeColors[type] || '#64748b'}
                  label={typeLabels[type] || type}
                />
              ))}
              {Object.keys(data.by_type || {}).length === 0 && (
                <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>No analyses yet.</p>
              )}
            </div>

            {/* Avg response time */}
            <div className="card">
              <h3 className="section-label">Avg AI Response Time (ms)</h3>
              {Object.entries(data.by_type || {}).map(([type, stats]) => (
                <BarChart
                  key={type}
                  data={stats.avg_ms}
                  max={maxMs}
                  color={typeColors[type] || '#64748b'}
                  label={typeLabels[type] || type}
                />
              ))}
            </div>

            {/* Red flags */}
            <div className="card">
              <h3 className="section-label">Patient Safety</h3>
              <div className="safety-donut-grid">
                <div className="safety-stat">
                  <div className="safety-num" style={{ color: '#ef4444' }}>{data.red_flags?.critical || 0}</div>
                  <div className="safety-lbl">Critical Flags</div>
                </div>
                <div className="safety-stat">
                  <div className="safety-num" style={{ color: '#f59e0b' }}>{(data.red_flags?.total || 0) - (data.red_flags?.critical || 0)}</div>
                  <div className="safety-lbl">Warning Flags</div>
                </div>
                <div className="safety-stat">
                  <div className="safety-num" style={{ color: '#10b981' }}>{data.total_analyses - (data.red_flags?.total || 0)}</div>
                  <div className="safety-lbl">Clean Analyses</div>
                </div>
              </div>
            </div>

            {/* Feedback */}
            <div className="card">
              <h3 className="section-label">Doctor Feedback</h3>
              {Object.entries(data.by_type || {}).map(([type, stats]) => {
                const up = stats.feedback_up || 0
                const down = stats.feedback_down || 0
                const total = up + down
                return (
                  <div key={type} className="feedback-row">
                    <span className="bar-label">{typeLabels[type] || type}</span>
                    <span>👍 {up}</span>
                    <span>👎 {down}</span>
                    {total > 0 && <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                      {Math.round((up / total) * 100)}% positive
                    </span>}
                  </div>
                )
              })}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
