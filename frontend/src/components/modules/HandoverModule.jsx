import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import useVoiceInput from '../../hooks/useVoiceInput'

const API_URL = import.meta.env.VITE_API_URL || 'https://cliniq-ai-kqfz.onrender.com'
const DRAFT_KEY = 'cliniq_draft_handover'

// NEWS2 score calculation
function calcNEWS2({ rr, spo2, temp, sbp, hr, avpu }) {
  let score = 0
  const r = parseFloat(rr), s = parseFloat(spo2), t = parseFloat(temp)
  const b = parseFloat(sbp), h = parseFloat(hr)
  if (r) { if (r <= 8) score += 3; else if (r <= 11) score += 1; else if (r <= 20) score += 0; else if (r <= 24) score += 2; else score += 3 }
  if (s) { if (s <= 91) score += 3; else if (s <= 93) score += 2; else if (s <= 95) score += 1 }
  if (t) { if (t <= 35.0) score += 3; else if (t <= 36.0) score += 1; else if (t <= 38.0) score += 0; else if (t <= 39.0) score += 1; else score += 2 }
  if (b) { if (b <= 90) score += 3; else if (b <= 100) score += 2; else if (b <= 110) score += 1; else if (b <= 219) score += 0; else score += 3 }
  if (h) { if (h <= 40) score += 3; else if (h <= 50) score += 1; else if (h <= 90) score += 0; else if (h <= 110) score += 1; else if (h <= 130) score += 2; else score += 3 }
  if (avpu && avpu !== 'A') score += 3
  return score
}

function NEWS2Color(score) {
  if (score >= 7) return 'var(--critical)'
  if (score >= 5) return 'var(--warn)'
  if (score >= 1) return 'var(--accent)'
  return 'var(--accent2)'
}

export default function HandoverModule({ onLoadingChange, shiftId }) {
  const [input, setInput] = useState('')
  const [output, setOutput] = useState(null)
  const [error, setError] = useState(null)
  const [reviewed, setReviewed] = useState(() => {
    try { return JSON.parse(localStorage.getItem('cliniq_reviewed') || '{}') } catch { return {} }
  })
  const [tasks, setTasks] = useState(() => {
    try { return JSON.parse(localStorage.getItem('cliniq_tasks') || '{}') } catch { return {} }
  })
  const [showNEWS2, setShowNEWS2] = useState(false)
  const [news2, setNEWS2] = useState({ rr: '', spo2: '', temp: '', sbp: '', hr: '', avpu: 'A' })
  const [news2Score, setNEWS2Score] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [language, setLanguage] = useState('english')
  const getLangCode = (lang) => {
    const map = { english: 'en-IN', hindi: 'hi-IN', tamil: 'ta-IN', telugu: 'te-IN', bengali: 'bn-IN', marathi: 'mr-IN' }
    return map[lang] || 'en-IN'
  }
  const [processingTime, setProcessingTime] = useState(null)
  const [generatedAt, setGeneratedAt] = useState(null)
  const debounceRef = useRef(null)

  const handleVoiceComplete = (text) => {
    setInput(prev => prev + (prev && !prev.endsWith(' ') ? ' ' : '') + text.trim())
  }
  const { isListening, isTranscribing, toggleListening, transcript, error: voiceError } = useVoiceInput(handleVoiceComplete, getLangCode(language))

  // Auto-save draft
  useEffect(() => {
    const saved = localStorage.getItem(DRAFT_KEY)
    if (saved && !input) setInput(saved)
  }, [])

  useEffect(() => {
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      if (input) localStorage.setItem(DRAFT_KEY, input)
    }, 2000)
  }, [input])

  const handleProcess = async () => {
    if (!input.trim()) { setError('Please enter handover notes'); return }
    onLoadingChange(true, 'Parsing handover notes...')
    setError(null)
    try {
      const res = await axios.post(`${API_URL}/api/analyze/handover`, { raw_notes: input, shift_id: shiftId })
      setOutput(res.data)
      setProcessingTime(res.data.processing_time_ms)
      setGeneratedAt(new Date().toLocaleTimeString())
      setFeedback(null)
      localStorage.removeItem(DRAFT_KEY)
    } catch (e) {
      const detail = e.response?.data?.detail; setError(typeof detail === 'string' ? detail : (detail ? JSON.stringify(detail) : 'Processing failed. Is the backend running?'))
    } finally {
      onLoadingChange(false)
    }
  }

  const handleSample = () => {
    setInput(`Bed 4 - Mr Patel, 68M, admitted chest pain, trop rising x2, on heparin infusion. Cardiology aware. Bed 7 - Mrs Chen, 45F, post lap chole day 1, doing well, obs stable, for d/c tomorrow if tolerating diet. Bed 2 - John D, 72M, COPD exac, sats 88% on 2L, nebs Q4H, ABG done - resp acidosis, worsening overnight, may need NIV. Bed 11 - Sarah M, 31F, migraine, obs fine, for d/c once pain controlled.`)
  }

  const toggleReviewed = (name) => {
    const key = `${shiftId}_${name}`
    const next = { ...reviewed, [key]: !reviewed[key] }
    setReviewed(next)
    localStorage.setItem('cliniq_reviewed', JSON.stringify(next))
  }

  const toggleTask = (patient, task) => {
    const key = `${shiftId}_${patient}_${task}`
    const next = { ...tasks, [key]: !tasks[key] }
    setTasks(next)
    localStorage.setItem('cliniq_tasks', JSON.stringify(next))
  }

  const handleNEWS2Calc = () => {
    const score = calcNEWS2(news2)
    setNEWS2Score(score)
  }

  const handleFeedback = async (val) => {
    setFeedback(val)
    if (output?.id) {
      try { await axios.post(`${API_URL}/api/feedback`, { analysis_id: output.id, value: val }) } catch {}
    }
  }

  const urgencyClass = (u, news2Override) => {
    if (news2Override !== null && news2Override >= 7) return 'urgency-critical'
    if (u === 'critical') return 'urgency-critical'
    if (u === 'high') return 'urgency-high'
    return 'urgency-stable'
  }

  const taskList = ['Bloods pending', 'Imaging pending', 'Specialist review', 'Follow-up call', 'Medication review']

  return (
    <section className="module active">
      <div className="module-header">
        <div>
          <h1>Shift Handover Briefing</h1>
          <p className="subtitle">Paste raw handover notes — messy, abbreviated, anything goes.</p>
        </div>
        <button className="btn-primary" style={{ fontSize: '12px' }} onClick={() => setShowNEWS2(!showNEWS2)}>
          {showNEWS2 ? 'Hide' : '⊕ NEWS2'} Score
        </button>
      </div>

      {showNEWS2 && (
        <div className="news2-panel">
          <label className="panel-label">NEWS2 Early Warning Score Calculator</label>
          <div className="news2-grid">
            {[
              { key: 'rr', label: 'Resp Rate', placeholder: '/min' },
              { key: 'spo2', label: 'SpO₂', placeholder: '%' },
              { key: 'temp', label: 'Temp', placeholder: '°C' },
              { key: 'sbp', label: 'Systolic BP', placeholder: 'mmHg' },
              { key: 'hr', label: 'Heart Rate', placeholder: 'bpm' },
            ].map(f => (
              <div key={f.key} className="news2-field">
                <label>{f.label}</label>
                <input type="number" placeholder={f.placeholder} value={news2[f.key]}
                  onChange={e => setNEWS2({ ...news2, [f.key]: e.target.value })} />
              </div>
            ))}
            <div className="news2-field">
              <label>Consciousness</label>
              <select value={news2.avpu} onChange={e => setNEWS2({ ...news2, avpu: e.target.value })}>
                <option value="A">Alert</option>
                <option value="C">Confused</option>
                <option value="V">Voice</option>
                <option value="P">Pain</option>
                <option value="U">Unresponsive</option>
              </select>
            </div>
          </div>
          <div className="btn-row">
            <button className="btn-primary" onClick={handleNEWS2Calc}>Calculate NEWS2</button>
            {news2Score !== null && (
              <span style={{ color: NEWS2Color(news2Score), fontFamily: 'var(--font-mono)', fontSize: '14px', alignSelf: 'center' }}>
                Score: {news2Score} {news2Score >= 7 ? '🔴 HIGH RISK' : news2Score >= 5 ? '🟡 MEDIUM RISK' : '🟢 LOW RISK'}
              </span>
            )}
          </div>
        </div>
      )}

      <div className="two-col">
        <div className="panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <label className="panel-label" style={{ marginBottom: 0 }}>Raw Handover Notes</label>
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
          <textarea className="big-textarea" value={isListening ? input + (input && !input.endsWith(' ') ? ' ' : '') + transcript : input} onChange={e => setInput(e.target.value)}
            placeholder="e.g. Bed 4 - Mr Patel, 68M, admitted chest pain..." style={{ width: '100%' }} />
          {isListening && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '6px', fontSize: '12px', color: 'var(--critical)' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--critical)', display: 'inline-block', animation: 'pulse 1s infinite' }} />
              Recording… click Stop to send to Groq Whisper AI
            </div>
          )}
          {isTranscribing && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '6px', fontSize: '12px', color: 'var(--warn)' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--warn)', display: 'inline-block', animation: 'pulse 0.6s infinite' }} />
              Groq Whisper is transcribing your dictation…
            </div>
          )}
          {voiceError && <div className="error-msg" style={{ marginTop: '6px' }}>🎙️ {voiceError}</div>}
          <div className="btn-row">
            <button className="btn-primary" onClick={handleProcess}>✦ Generate Briefing</button>
            <button
              className={`btn-mic ${isListening ? 'btn-mic--recording' : ''} ${isTranscribing ? 'btn-mic--transcribing' : ''}`}
              onClick={toggleListening}
              disabled={isTranscribing}
              title={isTranscribing ? 'Transcribing with Groq Whisper…' : isListening ? 'Stop — send to Whisper AI' : 'Start voice dictation (Groq Whisper)'}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 1a4 4 0 0 1 4 4v7a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4zm-1 16.93V21H9v2h6v-2h-2v-3.07A8 8 0 0 0 20 12h-2a6 6 0 0 1-12 0H4a8 8 0 0 0 7 7.93z"/>
              </svg>
              {isTranscribing ? 'Transcribing…' : isListening ? 'Stop Recording' : 'Dictate'}
              {isListening && <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'currentColor', display: 'inline-block', animation: 'pulse 1s infinite', marginLeft: '2px' }} />}
            </button>
            <button className="btn-ghost" onClick={handleSample}>Load Sample</button>
          </div>
          {error && <div className="error-msg">⚠ {error}</div>}
          {input && !output && <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>Draft auto-saved</div>}
        </div>

        <div className="panel">
          <label className="panel-label">
            Structured Briefing
            {generatedAt && <span className="timestamp"> · {generatedAt}</span>}
            {processingTime && <span className="timestamp"> · {processingTime}ms</span>}
          </label>
          <div className="output-area">
            {!output ? (
              <div className="empty-state">Briefing will appear here after processing.</div>
            ) : (
              <div>
                {(output.data?.patients || []).map((p, i) => {
                  const revKey = `${shiftId}_${p.name}`
                  const isReviewed = reviewed[revKey]
                  return (
                    <div key={i} className={`patient-card ${isReviewed ? 'reviewed' : ''}`}>
                      <div className="card-header">
                        <span className="patient-name">{p.name}{p.bed ? ` · ${p.bed}` : ''}{p.age ? ` · ${p.age}` : ''}</span>
                        <span className={`urgency-badge ${urgencyClass(p.urgency, null)}`}>{p.urgency || 'stable'}</span>
                      </div>
                      <div className="card-body">
                        {p.summary && <div><strong>Status:</strong> {p.summary}</div>}
                        {p.events && <div><strong>Events:</strong> {p.events}</div>}
                        {p.medications && <div><strong>Medications:</strong> {p.medications}</div>}
                        {p.watchFor && <div className="watch-flag">⚑ Watch for: {p.watchFor}</div>}
                      </div>
                      <div className="task-list">
                        {taskList.map(task => {
                          const tKey = `${shiftId}_${p.name}_${task}`
                          return (
                            <label key={task} className="task-item">
                              <input type="checkbox" checked={!!tasks[tKey]} onChange={() => toggleTask(p.name, task)} />
                              <span>{task}</span>
                            </label>
                          )
                        })}
                      </div>
                      <div className="card-footer">
                        <button className={`mark-reviewed-btn ${isReviewed ? 'reviewed' : ''}`} onClick={() => toggleReviewed(p.name)}>
                          {isReviewed ? '✓ Reviewed' : 'Mark Reviewed'}
                        </button>
                      </div>
                    </div>
                  )
                })}
                <div className="feedback-row">
                  <span className="feedback-label">Was this helpful?</span>
                  <button className={`feedback-btn ${feedback === 'up' ? 'active-up' : ''}`} onClick={() => handleFeedback('up')}>👍</button>
                  <button className={`feedback-btn ${feedback === 'down' ? 'active-down' : ''}`} onClick={() => handleFeedback('down')}>👎</button>
                </div>
              </div>
            )}
          </div>
          {output && (
            <button className="btn-export" onClick={() => window.print()}>
              📄 Export Professional PDF
            </button>
          )}
          <div className="disclaimer">⚠ AI-assisted — always verify clinically</div>
        </div>
      </div>
    </section>
  )
}

