import React, { useState, useEffect } from 'react'

export default function Topbar({ activeModule, onModuleChange, shiftActive, onStartShift, onEndShift, doctorInfo, onDoctorUpdate }) {
  const [isDark, setIsDark] = useState(() => localStorage.getItem('cliniq_theme') !== 'light')
  const [editingDoctor, setEditingDoctor] = useState(false)
  const [editForm, setEditForm] = useState(doctorInfo)
  const [shiftElapsed, setShiftElapsed] = useState('')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const modules = [
    { id: 'handover',     label: '01 Handover',      icon: '🔄' },
    { id: 'soap',         label: '02 Consultation',  icon: '📋' },
    { id: 'ddx',          label: '03 Differential',  icon: '🧠' },
    { id: 'prescription', label: '04 Rx Safety',     icon: '💊' },
    { id: 'analytics',   label: '05 Analytics',     icon: '📊' },
    { id: 'fhir',         label: '06 FHIR',          icon: '🏥' },
    { id: 'timeline',     label: '07 Timeline',      icon: '📅' },
  ]

  useEffect(() => {
    if (!shiftActive) { setShiftElapsed(''); return }
    const tick = () => {
      const start = localStorage.getItem('cliniq_shift_start')
      if (!start) return
      const mins = Math.floor((Date.now() - new Date(start)) / 60000)
      const hrs = Math.floor(mins / 60)
      setShiftElapsed(hrs > 0 ? `${hrs}h ${mins % 60}m` : `${mins}m`)
    }
    tick()
    const interval = setInterval(tick, 30000)
    return () => clearInterval(interval)
  }, [shiftActive])

  const toggleTheme = () => {
    const newDark = !isDark
    setIsDark(newDark)
    document.body.classList.toggle('dark', newDark)
    document.body.classList.toggle('light', !newDark)
    localStorage.setItem('cliniq_theme', newDark ? 'dark' : 'light')
  }

  const saveDoctor = () => {
    onDoctorUpdate(editForm)
    setEditingDoctor(false)
  }

  return (
    <header className="topbar">
      <div className="topbar-main">
        {/* Logo */}
        <div className="logo">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
          </svg>
          <span style={{ fontFamily: 'var(--font-sans)' }}>
            Clin<span style={{ color: 'var(--accent)', background: 'linear-gradient(135deg, var(--accent) 0%, #60a5fa 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>IQ</span>
          </span>
        </div>

        {/* Nav tabs */}
        <nav className="module-tabs">
          {modules.map(mod => (
            <button
              key={mod.id}
              className={`tab ${activeModule === mod.id ? 'active' : ''}`}
              onClick={() => { onModuleChange(mod.id); setMobileMenuOpen(false) }}
              title={mod.label}
            >
              <span className="tab-icon">{mod.icon}</span>
              <span className="tab-label">{mod.label}</span>
            </button>
          ))}
        </nav>

        {/* Right controls */}
        <div className="topbar-right">
          {shiftActive ? (
            <>
              <span className="shift-badge">🟢 {shiftElapsed && `${shiftElapsed}`}</span>
              <button className="btn-danger-sm" onClick={onEndShift}>End Shift</button>
            </>
          ) : (
            <button className="btn-primary" style={{ fontSize: '11px', padding: '5px 14px' }} onClick={onStartShift}>
              ▶ Start Shift
            </button>
          )}
          <button className="icon-btn" onClick={toggleTheme} title="Toggle theme">{isDark ? '☀' : '🌙'}</button>
          <button className="icon-btn" onClick={() => document.getElementById('shortcuts-modal')?.classList.toggle('active')} title="Keyboard shortcuts" style={{ fontSize: '12px' }}>?</button>
          <div className="doctor-pill" onClick={() => { setEditForm(doctorInfo); setEditingDoctor(true) }} title="Edit profile">
            <span className="doctor-avatar">{(doctorInfo.name || 'D')[0].toUpperCase()}</span>
            <span className="doctor-name">Dr. {doctorInfo.name}</span>
            <span className="doctor-spec">{doctorInfo.specialty}</span>
          </div>
        </div>
      </div>

      {/* Doctor edit modal */}
      {editingDoctor && (
        <div className="modal-overlay" onClick={() => setEditingDoctor(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()} style={{ maxWidth: '340px' }}>
            <div className="modal-header"><h2>Edit Profile</h2><button className="modal-close" onClick={() => setEditingDoctor(false)}>✕</button></div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>Name</label>
                <input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })}
                  style={{ width: '100%', background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: '6px', color: 'var(--text)', padding: '8px', fontSize: '13px' }} />
              </div>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>Specialty</label>
                <input value={editForm.specialty} onChange={e => setEditForm({ ...editForm, specialty: e.target.value })}
                  style={{ width: '100%', background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: '6px', color: 'var(--text)', padding: '8px', fontSize: '13px' }} />
              </div>
            </div>
            <div className="btn-row" style={{ marginTop: '16px' }}>
              <button className="btn-primary" onClick={saveDoctor}>Save</button>
              <button className="btn-ghost" onClick={() => setEditingDoctor(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </header>
  )
}
