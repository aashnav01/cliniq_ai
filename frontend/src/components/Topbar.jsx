import React, { useState, useEffect } from 'react'

export default function Topbar({ activeModule, onModuleChange, shiftActive, onStartShift, onEndShift, doctorInfo, onDoctorUpdate }) {
  const [isDark, setIsDark] = useState(() => localStorage.getItem('cliniq_theme') !== 'light')
  const [editingDoctor, setEditingDoctor] = useState(false)
  const [editForm, setEditForm] = useState(doctorInfo)
  const [shiftElapsed, setShiftElapsed] = useState('')

  const modules = [
    { id: 'handover', label: '01 Handover' },
    { id: 'soap', label: '02 Consultation' },
    { id: 'ddx', label: '03 Differential Dx' },
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
      <div className="logo" style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '24px', fontWeight: 800, color: 'var(--text)', letterSpacing: '-0.5px' }}>
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ dropShadow: '0 0 8px rgba(59,130,246,0.5)' }}>
          <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
        </svg>
        <span style={{ fontFamily: 'var(--font-sans)' }}>Clin<span style={{ color: 'var(--accent)', background: 'linear-gradient(135deg, var(--accent) 0%, #60a5fa 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>IQ</span></span>
      </div>
      <nav className="module-tabs">
        {modules.map(mod => (
          <button key={mod.id} className={`tab ${activeModule === mod.id ? 'active' : ''}`} onClick={() => onModuleChange(mod.id)}>
            {mod.label}
          </button>
        ))}
      </nav>
      <div className="topbar-right">
        {shiftActive ? (
          <>
            <span className="shift-badge">🟢 Shift {shiftElapsed && `· ${shiftElapsed}`}</span>
            <button className="btn-ghost" style={{ fontSize: '11px', padding: '4px 10px' }} onClick={onEndShift}>End Shift</button>
          </>
        ) : (
          <button className="btn-primary" style={{ fontSize: '11px', padding: '4px 12px' }} onClick={onStartShift}>Start Shift</button>
        )}
        <button className="icon-btn" onClick={toggleTheme} title="Toggle theme">{isDark ? '☀' : '🌙'}</button>
        <button className="icon-btn" onClick={() => document.getElementById('shortcuts-modal')?.classList.toggle('active')} title="Keyboard shortcuts" style={{ fontSize: '12px' }}>?</button>
        <div className="doctor-pill" onClick={() => { setEditForm(doctorInfo); setEditingDoctor(true) }} style={{ cursor: 'pointer' }} title="Click to edit profile">
          Dr. {doctorInfo.name} · {doctorInfo.specialty} <span style={{ opacity: 0.5, fontSize: '11px', marginLeft: '3px' }}>✏</span>
        </div>
      </div>

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
