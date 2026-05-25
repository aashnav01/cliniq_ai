import React, { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import useVoiceInput from '../../hooks/useVoiceInput'

const API_URL = import.meta.env.VITE_API_URL || 'https://cliniq-ai-kqfz.onrender.com'
const DRAFT_KEY = 'cliniq_draft_ddx'

export default function DifferentialDxModule({ onLoadingChange, shiftId }) {
  const [form, setForm] = useState({ age: '', gender: '', symptoms: '', duration: '', history: '' })
  const [output, setOutput] = useState(null)
  const [error, setError] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [pushback, setPushback] = useState({})
  const [processingTime, setProcessingTime] = useState(null)
  const [generatedAt, setGeneratedAt] = useState(null)
  const [symptomChips, setSymptomChips] = useState([])
  const [activeChips, setActiveChips] = useState({})
  const debounceRef = useRef(null)
  
  const [language, setLanguage] = useState('english')
  const getLangCode = (lang) => {
    const map = { english: 'en-IN', hindi: 'hi-IN', tamil: 'ta-IN', telugu: 'te-IN', bengali: 'bn-IN', marathi: 'mr-IN' }
    return map[lang] || 'en-IN'
  }

  const handleVoiceComplete = (text) => {
    setForm(prev => ({ ...prev, symptoms: prev.symptoms + (prev.symptoms && !prev.symptoms.endsWith(' ') ? ' ' : '') + text.trim() }))
  }
  const { isListening, isTranscribing, toggleListening, transcript, error: voiceError } = useVoiceInput(handleVoiceComplete, getLangCode(language))

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null')
      if (saved) setForm(saved)
    } catch {}
  }, [])

  useEffect(() => {
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      if (form.symptoms) localStorage.setItem(DRAFT_KEY, JSON.stringify(form))
    }, 2000)
  }, [form])

  const buildPresentation = (overrideSymptoms) => {
    const parts = []
    if (form.age) parts.push(`${form.age}-year-old`)
    if (form.gender) parts.push(form.gender)
    const syms = overrideSymptoms !== undefined ? overrideSymptoms : form.symptoms
    if (syms) parts.push(`presenting with ${syms}`)
    if (form.duration) parts.push(`for ${form.duration}`)
    if (form.history) parts.push(`History/findings: ${form.history}`)
    return parts.join(', ')
  }

  const handleProcess = async (overridePresentation) => {
    const pres = overridePresentation || buildPresentation()
    if (!pres.trim()) { setError('Please enter at least symptoms'); return }
    onLoadingChange(true, 'Generating differential...')
    setError(null)
    try {
      const res = await axios.post(`${API_URL}/api/analyze/ddx`, { clinical_presentation: pres, shift_id: shiftId })
      setOutput(res.data)
      setProcessingTime(res.data.processing_time_ms)
      setGeneratedAt(new Date().toLocaleTimeString())
      setFeedback(null)
      setPushback({})
      localStorage.removeItem(DRAFT_KEY)
      // Parse symptom chips from input
      const chips = form.symptoms.split(/,|;/).map(s => s.trim()).filter(Boolean)
      setSymptomChips(chips)
      const init = {}
      chips.forEach(c => { init[c] = true })
      setActiveChips(init)
    } catch (e) {
      const detail = e.response?.data?.detail; setError(typeof detail === 'string' ? detail : (detail ? JSON.stringify(detail) : 'Analysis failed. Is the backend running?'))
    } finally {
      onLoadingChange(false)
    }
  }

  const handleSample = () => {
    setForm({ age: '72', gender: 'male', symptoms: 'sudden chest pain, radiating to back, diaphoresis', duration: '30 minutes', history: 'HR 105, BP 165/95 left arm, 145/85 right arm. Asymmetric pulses. CXR: widened mediastinum.' })
  }

  const handleChipToggle = (chip) => {
    const next = { ...activeChips, [chip]: !activeChips[chip] }
    setActiveChips(next)
    const active = Object.entries(next).filter(([, v]) => v).map(([k]) => k).join(', ')
    const pres = buildPresentation(active)
    handleProcess(pres)
  }

  const handlePushback = async (rank, reason) => {
    if (!reason.trim()) return
    const pres = buildPresentation() + `\n\nNote: Diagnosis #${rank} seems unlikely because: ${reason}`
    await handleProcess(pres)
  }

  const handleFeedback = async (val) => {
    setFeedback(val)
    if (output?.id) {
      try { await axios.post(`${API_URL}/api/feedback`, { analysis_id: output.id, value: val }) } catch {}
    }
  }

  const confColor = (c) => c >= 75 ? 'var(--accent2)' : c >= 50 ? 'var(--warn)' : 'var(--critical)'

  return (
    <section className="module active">
      <div className="module-header">
        <div>
          <h1>Differential Diagnosis Assistant</h1>
          <p className="subtitle">Enter patient details. AI returns ranked differentials with investigation guidance.</p>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <label className="panel-label">Patient & Symptom Input</label>
          <div className="form-grid">
            <div className="form-field">
              <label>Age</label>
              <input type="number" value={form.age} onChange={e => setForm({ ...form, age: e.target.value })} placeholder="e.g. 72" />
            </div>
            <div className="form-field">
              <label>Gender</label>
              <select value={form.gender} onChange={e => setForm({ ...form, gender: e.target.value })}>
                <option value="">Select...</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div className="form-field full" style={{ position: 'relative' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label>Presenting Symptoms</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>🎙️ Dictation Language:</span>
                  <select value={language} onChange={e => setLanguage(e.target.value)}
                    style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: '6px', color: 'var(--text)', padding: '4px 8px', fontSize: '12px', outline: 'none' }}>
                    <option value="english">English</option>
                    <option value="hindi">हिंदी Hindi</option>
                    <option value="tamil">தமிழ் Tamil</option>
                    <option value="telugu">తెలుగు Telugu</option>
                    <option value="bengali">বাংলা Bengali</option>
                    <option value="marathi">मराठी Marathi</option>
                  </select>
                </div>
              </div>
              <input type="text" value={isListening ? form.symptoms + (form.symptoms && !form.symptoms.endsWith(' ') ? ' ' : '') + transcript : form.symptoms} onChange={e => setForm({ ...form, symptoms: e.target.value })} placeholder="e.g. chest pain, dyspnoea, diaphoresis" />
            </div>
            {isListening && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '5px', fontSize: '11px', color: 'var(--critical)' }}>
                <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--critical)', display: 'inline-block', animation: 'pulse 1s infinite' }} />
                Recording… click Stop to send to Groq Whisper AI
              </div>
            )}
            {isTranscribing && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '5px', fontSize: '11px', color: 'var(--warn)' }}>
                <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--warn)', display: 'inline-block', animation: 'pulse 0.6s infinite' }} />
                Groq Whisper is transcribing…
              </div>
            )}
            {voiceError && <div className="error-msg" style={{ marginTop: '5px', fontSize: '11px' }}>🎙️ {voiceError}</div>}
            <div className="form-field full">
              <label>Duration</label>
              <input type="text" value={form.duration} onChange={e => setForm({ ...form, duration: e.target.value })} placeholder="e.g. 30 minutes, sudden onset" />
            </div>
            <div className="form-field full">
              <label>Vitals, History & Test Results</label>
              <textarea className="small-textarea" value={form.history} onChange={e => setForm({ ...form, history: e.target.value })} placeholder="e.g. HTN, BP asymmetric, CXR widened mediastinum" />
            </div>
          </div>
          <div className="btn-row">
            <button className="btn-primary" onClick={() => handleProcess()}>✦ Generate Differential</button>
            <button
              className={`btn-mic ${isListening ? 'btn-mic--recording' : ''} ${isTranscribing ? 'btn-mic--transcribing' : ''}`}
              onClick={toggleListening}
              disabled={isTranscribing}
              title={isTranscribing ? 'Transcribing with Groq Whisper…' : isListening ? 'Stop — send to Whisper AI' : 'Dictate symptoms (Groq Whisper)'}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 1a4 4 0 0 1 4 4v7a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4zm-1 16.93V21H9v2h6v-2h-2v-3.07A8 8 0 0 0 20 12h-2a6 6 0 0 1-12 0H4a8 8 0 0 0 7 7.93z"/>
              </svg>
              {isTranscribing ? 'Transcribing…' : isListening ? 'Stop Recording' : 'Dictate Symptoms'}
              {isListening && <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'currentColor', display: 'inline-block', animation: 'pulse 1s infinite', marginLeft: '2px' }} />}
            </button>
            <button className="btn-ghost" onClick={handleSample}>Load Sample</button>
          </div>
          {error && <div className="error-msg">⚠ {error}</div>}
          {form.symptoms && !output && <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>Draft auto-saved</div>}

          {/* Symptom chips — appear after first run */}
          {symptomChips.length > 0 && (
            <div style={{ marginTop: '14px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px' }}>Toggle symptoms to update differential:</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {symptomChips.map(chip => (
                  <button key={chip} onClick={() => handleChipToggle(chip)}
                    style={{
                      padding: '4px 10px', borderRadius: '12px', fontSize: '12px', cursor: 'pointer',
                      background: activeChips[chip] ? 'var(--accent)' : 'var(--surface2)',
                      color: activeChips[chip] ? '#000' : 'var(--text-muted)',
                      border: `1px solid ${activeChips[chip] ? 'var(--accent)' : 'var(--border)'}`,
                      transition: 'all 0.15s'
                    }}>
                    {chip}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="panel">
          <label className="panel-label">
            Ranked Differentials
            {generatedAt && <span className="timestamp"> · {generatedAt}</span>}
            {processingTime && <span className="timestamp"> · {processingTime}ms</span>}
          </label>
          <div className="output-area">
            {!output ? (
              <div className="empty-state">Differential diagnosis will appear here.</div>
            ) : (
              <div>
                {output.data?.chief_complaint && (
                  <div style={{ padding: '10px 12px', background: 'var(--surface2)', borderRadius: 'var(--radius)', marginBottom: '12px', fontSize: '13px' }}>
                    <strong>Presentation:</strong> {output.data.chief_complaint}
                  </div>
                )}

                {(output.data?.differentials || []).map((d, i) => (
                  <DDxCard key={i} d={d} confColor={confColor} onPushback={handlePushback}
                    pushback={pushback[d.rank]} setPushback={(v) => setPushback({ ...pushback, [d.rank]: v })} />
                ))}

                {output.data?.most_likely && (
                  <div style={{ padding: '10px 12px', background: 'rgba(63,185,80,0.1)', border: '1px solid var(--accent2)', borderRadius: 'var(--radius)', marginTop: '8px', fontSize: '13px' }}>
                    <strong style={{ color: 'var(--accent2)' }}>🎯 Most Likely:</strong> {output.data.most_likely}
                  </div>
                )}

                {(output.data?.critical_exclusions || []).length > 0 && (
                  <div style={{ padding: '10px 12px', background: 'rgba(255,107,107,0.1)', border: '1px solid var(--critical)', borderRadius: 'var(--radius)', marginTop: '8px', fontSize: '13px' }}>
                    <strong style={{ color: 'var(--critical)' }}>🚨 Critical Exclusions:</strong> {output.data.critical_exclusions.join(', ')}
                  </div>
                )}

                {/* ICD-10 from DDx */}
                {output.data?.top_icd10?.length > 0 && (
                  <div className="icd10-section" style={{ marginTop: '12px' }}>
                    <div className="icd10-header">🏷 Top ICD-10 Billing Codes</div>
                    <div className="icd10-strip">
                      {output.data.top_icd10.map((c, ci) => (
                        <div key={ci} className="icd-chip-card">
                          <span className="icd-code">{c.code}</span>
                          <span className="icd-desc">{c.description}</span>
                          <span className="icd-conf">{c.confidence}%</span>
                          <button className="icd-copy-btn" title="Copy code"
                            onClick={() => navigator.clipboard?.writeText(c.code)}>
                            ⧉
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="feedback-row">
                  <span className="feedback-label">Was this helpful?</span>
                  <button className={`feedback-btn ${feedback === 'up' ? 'active-up' : ''}`} onClick={() => handleFeedback('up')}>👍</button>
                  <button className={`feedback-btn ${feedback === 'down' ? 'active-down' : ''}`} onClick={() => handleFeedback('down')}>👎</button>
                </div>
              </div>
            )}
          </div>
          <div className="disclaimer">⚠ AI-assisted — always verify clinically</div>
        </div>
      </div>
    </section>
  )
}

function DDxCard({ d, confColor, onPushback, pushback, setPushback }) {
  const [showPushback, setShowPushback] = useState(false)
  const color = confColor(d.confidence || 50)
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '12px', marginBottom: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--accent)', padding: '2px 7px', borderRadius: '6px', fontSize: '11px', fontWeight: '600' }}>#{d.rank}</span>
          <strong style={{ fontSize: '16px', fontWeight: '600' }}>{d.diagnosis}</strong>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '14px', fontWeight: '600', color }}>{d.confidence}%</div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>confidence</div>
        </div>
      </div>
      <div style={{ background: 'var(--surface2)', borderRadius: '4px', height: '8px', marginBottom: '8px', overflow: 'hidden' }}>
        <div style={{ background: color, height: '100%', width: `${d.confidence}%`, borderRadius: '4px', transition: 'width 0.4s ease' }} />
      </div>
      {d.reasoning && <p style={{ fontSize: '13px', lineHeight: '1.6', marginBottom: '8px', color: 'var(--text)' }}>{d.reasoning}</p>}
      {d.red_flag && (
        <div style={{ background: 'rgba(255,107,107,0.1)', border: '1px solid var(--critical)', borderRadius: '4px', padding: '5px 8px', marginBottom: '8px', fontSize: '12px', color: 'var(--critical)' }}>
          🚩 {d.red_flag}
        </div>
      )}
      {((d.confirm_tests || []).length > 0 || (d.rule_out_tests || []).length > 0) && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginBottom: '8px' }}>
          {(d.confirm_tests || []).map((t, i) => (
            <span key={i} style={{ background: 'rgba(34,197,94,0.12)', border: '1px solid #22c55e', color: '#22c55e', padding: '2px 8px', borderRadius: '10px', fontSize: '11px' }}>✓ {t}</span>
          ))}
          {(d.rule_out_tests || []).map((t, i) => (
            <span key={i} style={{ background: 'rgba(59,130,246,0.1)', border: '1px solid var(--accent)', color: 'var(--accent)', padding: '2px 8px', borderRadius: '10px', fontSize: '11px' }}>✗ {t}</span>
          ))}
        </div>
      )}
      {/* Per-diagnosis ICD-10 */}
      {d.icd10_codes?.length > 0 && (
        <div style={{ marginBottom: '8px' }}>
          {d.icd10_codes.slice(0, 2).map((c, ci) => (
            <span key={ci} className="icd-chip" style={{ marginRight: '6px', marginBottom: '4px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              {c.code} <span style={{ opacity: 0.7 }}>{c.description}</span>
              <button className="icd-copy-btn" style={{ padding: '0 4px' }} onClick={() => navigator.clipboard?.writeText(c.code)}>⧉</button>
            </span>
          ))}
        </div>
      )}
      <button onClick={() => setShowPushback(!showPushback)} style={{ background: 'none', border: '1px solid var(--border)', borderRadius: '4px', color: 'var(--text-muted)', fontSize: '11px', padding: '3px 8px', cursor: 'pointer' }}>
        {showPushback ? 'Cancel' : '↩ This is unlikely because...'}
      </button>
      {showPushback && (
        <div style={{ display: 'flex', gap: '6px', marginTop: '8px' }}>
          <input value={pushback || ''} onChange={e => setPushback(e.target.value)} placeholder="Your clinical reasoning..."
            style={{ flex: 1, background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: '4px', color: 'var(--text)', padding: '6px 8px', fontSize: '12px' }} />
          <button className="btn-ghost small" onClick={() => { onPushback(d.rank, pushback); setShowPushback(false) }}>Re-run</button>
        </div>
      )}
    </div>
  )
}

