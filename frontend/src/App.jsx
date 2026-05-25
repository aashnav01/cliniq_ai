import React, { useState, useEffect } from 'react'
import Topbar from './components/Topbar'
import HandoverModule from './components/modules/HandoverModule'
import SoapModule from './components/modules/SoapModule'
import DifferentialDxModule from './components/modules/DifferentialDxModule'
import PrescriptionModule from './components/modules/PrescriptionModule'
import AnalyticsModule from './components/modules/AnalyticsModule'
import FhirModule from './components/modules/FhirModule'
import TimelineModule from './components/modules/TimelineModule'
import Loader from './components/Loader'

const API_URL = import.meta.env.VITE_API_URL || 'https://cliniq-ai-kqfz.onrender.com'

export default function App() {
  const [activeModule, setActiveModule] = useState('handover')
  const [loading, setLoading] = useState(false)
  const [loaderText, setLoaderText] = useState('Processing...')
  const [shiftId, setShiftId] = useState(() => {
    const saved = localStorage.getItem('cliniq_shift_id')
    return saved ? parseInt(saved) : null
  })
  const [shiftActive, setShiftActive] = useState(() => !!localStorage.getItem('cliniq_shift_id'))
  const [shiftSummary, setShiftSummary] = useState(null)
  const [backendOnline, setBackendOnline] = useState(true)
  const [pdfDownloading, setPdfDownloading] = useState(false)
  const [doctorInfo, setDoctorInfo] = useState(() => {
    const saved = localStorage.getItem('cliniq_doctor')
    return saved ? JSON.parse(saved) : { name: 'Doctor', specialty: 'General' }
  })

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then(r => r.ok ? setBackendOnline(true) : setBackendOnline(false))
      .catch(() => setBackendOnline(false))
  }, [])

  useEffect(() => {
    const theme = localStorage.getItem('cliniq_theme') || 'dark'
    document.body.classList.add(theme)
  }, [])

  useEffect(() => {
    const handler = (e) => {
      if (e.ctrlKey || e.metaKey) {
        if (e.key === '1') { e.preventDefault(); setActiveModule('handover') }
        if (e.key === '2') { e.preventDefault(); setActiveModule('soap') }
        if (e.key === '3') { e.preventDefault(); setActiveModule('ddx') }
        if (e.key === '4') { e.preventDefault(); setActiveModule('prescription') }
        if (e.key === '5') { e.preventDefault(); setActiveModule('analytics') }
        if (e.key === '6') { e.preventDefault(); setActiveModule('fhir') }
        if (e.key === '7') { e.preventDefault(); setActiveModule('timeline') }
      }
      if (e.key === '?' && !e.ctrlKey) {
        document.getElementById('shortcuts-modal')?.classList.toggle('active')
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const handleLoadingChange = (isLoading, text) => {
    setLoading(isLoading)
    if (text) setLoaderText(text)
  }

  const handleStartShift = async () => {
    try {
      const res = await fetch(`${API_URL}/api/shift/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doctor_name: doctorInfo.name, specialty: doctorInfo.specialty })
      })
      const data = await res.json()
      setShiftId(data.shift_id)
      setShiftActive(true)
      localStorage.setItem('cliniq_shift_id', data.shift_id)
      localStorage.setItem('cliniq_shift_start', new Date().toISOString())
    } catch {
      const localId = Date.now()
      setShiftId(localId)
      setShiftActive(true)
      localStorage.setItem('cliniq_shift_id', localId)
      localStorage.setItem('cliniq_shift_start', new Date().toISOString())
    }
  }

  const handleEndShift = async () => {
    if (!shiftId) return
    try {
      const res = await fetch(`${API_URL}/api/shift/end`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shift_id: shiftId })
      })
      const data = await res.json()
      setShiftSummary(data)

      // Auto-download discharge summary PDF
      downloadShiftPdf(shiftId)
    } catch {
      setShiftSummary({ local: true })
    }
    setShiftActive(false)
    localStorage.removeItem('cliniq_shift_id')
    localStorage.removeItem('cliniq_shift_start')
    setShiftId(null)
  }

  const downloadShiftPdf = async (sid) => {
    if (!sid) return
    setPdfDownloading(true)
    try {
      const res = await fetch(`${API_URL}/api/shift/${sid}/discharge-summary`)
      if (!res.ok) throw new Error('PDF generation failed')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `ClinIQ_Discharge_Summary_Shift${sid}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('PDF download failed:', err)
    } finally {
      setPdfDownloading(false)
    }
  }

  const handleDoctorUpdate = (info) => {
    setDoctorInfo(info)
    localStorage.setItem('cliniq_doctor', JSON.stringify(info))
  }

  return (
    <div>
      {!backendOnline && (
        <div style={{
          background: 'rgba(210,153,34,0.15)', borderBottom: '1px solid var(--warn)',
          padding: '8px 24px', fontSize: '12px', color: 'var(--warn)',
          display: 'flex', alignItems: 'center', gap: '8px'
        }}>
          ⚠ Backend offline — could not connect to API server. Features requiring AI will not work.
        </div>
      )}

      <Topbar
        activeModule={activeModule}
        onModuleChange={setActiveModule}
        shiftActive={shiftActive}
        onStartShift={handleStartShift}
        onEndShift={handleEndShift}
        doctorInfo={doctorInfo}
        onDoctorUpdate={handleDoctorUpdate}
      />

      <main className="app-body">
        {activeModule === 'handover' && <HandoverModule onLoadingChange={handleLoadingChange} shiftId={shiftId} />}
        {activeModule === 'soap' && <SoapModule onLoadingChange={handleLoadingChange} shiftId={shiftId} />}
        {activeModule === 'ddx' && <DifferentialDxModule onLoadingChange={handleLoadingChange} shiftId={shiftId} />}
        {activeModule === 'prescription' && <PrescriptionModule onLoadingChange={handleLoadingChange} shiftId={shiftId} />}
        {activeModule === 'analytics' && <AnalyticsModule />}
        {activeModule === 'fhir' && <FhirModule shiftId={shiftId} />}
        {activeModule === 'timeline' && <TimelineModule />}
      </main>

      <Loader loading={loading} text={loaderText} />

      {/* PDF downloading indicator */}
      {pdfDownloading && (
        <div style={{
          position: 'fixed', bottom: '24px', right: '24px',
          background: 'var(--surface2)', border: '1px solid var(--teal)',
          borderRadius: '12px', padding: '12px 20px',
          display: 'flex', alignItems: 'center', gap: '10px',
          color: 'var(--teal)', fontSize: '14px', fontWeight: 600,
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)', zIndex: 9999
        }}>
          <div className="spinner" style={{ width: '16px', height: '16px' }} />
          Generating Discharge PDF...
        </div>
      )}

      {/* Shift Summary Modal */}
      {shiftSummary && (
        <div className="modal-overlay" onClick={() => setShiftSummary(null)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Shift Complete</h2>
              <button className="modal-close" onClick={() => setShiftSummary(null)}>✕</button>
            </div>
            {shiftSummary.local ? (
              <p style={{ color: 'var(--text-muted)' }}>Shift ended. Backend was offline so detailed stats are unavailable.</p>
            ) : (
              <>
                <div className="shift-summary-grid">
                  <div className="stat-card"><div className="stat-num">{shiftSummary.summary?.total_analyses || 0}</div><div className="stat-label">Total Analyses</div></div>
                  <div className="stat-card"><div className="stat-num">{shiftSummary.summary?.handovers || 0}</div><div className="stat-label">Handovers</div></div>
                  <div className="stat-card"><div className="stat-num">{shiftSummary.summary?.soap_notes || 0}</div><div className="stat-label">SOAP Notes</div></div>
                  <div className="stat-card"><div className="stat-num">{shiftSummary.summary?.differentials || 0}</div><div className="stat-label">Differentials</div></div>
                  <div className="stat-card"><div className="stat-num">{shiftSummary.duration_minutes || 0}m</div><div className="stat-label">Shift Duration</div></div>
                  <div className="stat-card"><div className="stat-num">{shiftSummary.summary?.avg_processing_ms || 0}ms</div><div className="stat-label">Avg AI Response</div></div>
                </div>
                <div style={{ marginTop: '12px', padding: '10px 14px', background: 'rgba(8,145,178,0.1)', borderRadius: '8px', border: '1px solid var(--teal)', fontSize: '13px', color: 'var(--teal)' }}>
                  📄 Discharge summary PDF is downloading automatically...
                </div>
              </>
            )}
            <div style={{ marginTop: '16px' }}>
              <button className="btn-export" onClick={() => shiftSummary.shift_id && downloadShiftPdf(shiftSummary.shift_id)}>
                📄 Re-download PDF Summary
              </button>
              <button className="btn-ghost" style={{ width: '100%', marginTop: '8px' }} onClick={() => setShiftSummary(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Keyboard shortcuts modal */}
      <div id="shortcuts-modal" className="modal-overlay" onClick={() => document.getElementById('shortcuts-modal').classList.remove('active')}>
        <div className="modal-box" onClick={e => e.stopPropagation()}>
          <div className="modal-header"><h2>Keyboard Shortcuts</h2><button className="modal-close" onClick={() => document.getElementById('shortcuts-modal').classList.remove('active')}>✕</button></div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <tbody>
              {[
                ['Ctrl+1', 'Handover module'],
                ['Ctrl+2', 'SOAP module'],
                ['Ctrl+3', 'Differential Dx module'],
                ['Ctrl+4', 'Prescription Safety'],
                ['Ctrl+5', 'Analytics'],
                ['Ctrl+6', 'FHIR'],
                ['Ctrl+7', 'Patient Timeline'],
                ['Ctrl+Enter', 'Submit current form'],
                ['?', 'Toggle this panel'],
              ].map(([key, desc]) => (
                <tr key={key} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '10px', fontFamily: 'var(--font-mono)' }}><kbd style={{ background: 'var(--surface2)', border: '1px solid var(--border)', padding: '2px 6px', borderRadius: '3px' }}>{key}</kbd></td>
                  <td style={{ padding: '10px', color: 'var(--text-muted)' }}>{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
