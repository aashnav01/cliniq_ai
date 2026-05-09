import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import useVoiceInput from '../../hooks/useVoiceInput'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const DRAFT_KEY = 'cliniq_draft_soap'
const HISTORY_KEY = 'cliniq_soap_history'

const SPECIALTIES = ['Cardiology', 'Gastroenterology', 'Neurology', 'Orthopaedics', 'Respiratory', 'General Surgery', 'General Medicine', 'Oncology', 'Nephrology', 'Endocrinology']

const GENERICS = {
  'crocin': 'Paracetamol', 'dolo': 'Paracetamol', 'combiflam': 'Ibuprofen + Paracetamol',
  'augmentin': 'Amoxicillin + Clavulanate', 'azithral': 'Azithromycin', 'pan': 'Pantoprazole',
  'atorva': 'Atorvastatin', 'ecosprin': 'Aspirin', 'metformin': 'Metformin (generic)',
  'amlodipine': 'Amlodipine (generic)', 'bisoprolol': 'Bisoprolol (generic)',
  'losartan': 'Losartan (generic)', 'atenolol': 'Atenolol (generic)'
}

function findGenerics(text) {
  if (!text) return []
  const found = []
  Object.entries(GENERICS).forEach(([brand, generic]) => {
    if (text.toLowerCase().includes(brand) && brand !== generic.split(' ')[0].toLowerCase()) {
      found.push({ brand, generic })
    }
  })
  return found
}

export default function SoapModule({ onLoadingChange, shiftId }) {
  const [input, setInput] = useState('')
  const [output, setOutput] = useState(null)
  const [drugData, setDrugData] = useState(null)
  const [referralLetter, setReferralLetter] = useState(null)
  const [selectedSpecialty, setSelectedSpecialty] = useState('')
  const [showReferral, setShowReferral] = useState(false)
  const [rapidMode, setRapidMode] = useState(false)
  const [language, setLanguage] = useState('english')
  
  const getLangCode = (lang) => {
    const map = { english: 'en-IN', hindi: 'hi-IN', tamil: 'ta-IN', telugu: 'te-IN', bengali: 'bn-IN', marathi: 'mr-IN' }
    return map[lang] || 'en-IN'
  }
  const [error, setError] = useState(null)
  const [copyText, setCopyText] = useState('⧉ Copy Note')
  const [feedback, setFeedback] = useState(null)
  const [dismissedFlags, setDismissedFlags] = useState({})
  const [processingTime, setProcessingTime] = useState(null)
  const [generatedAt, setGeneratedAt] = useState(null)
  const [history, setHistory] = useState(() => {
    try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') } catch { return [] }
  })
  const [showHistory, setShowHistory] = useState(false)
  const debounceRef = useRef(null)

  const handleVoiceComplete = (text) => {
    setInput(prev => prev + (prev && !prev.endsWith(' ') ? ' ' : '') + text.trim())
  }
  const { isListening, toggleListening, transcript } = useVoiceInput(handleVoiceComplete, getLangCode(language))

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
    if (!input.trim()) { setError('Please enter consultation notes'); return }
    onLoadingChange(true, rapidMode ? 'Expanding rapid notes...' : 'Structuring SOAP note...')
    setError(null)
    setDrugData(null)
    setReferralLetter(null)
    try {
      const endpoint = rapidMode ? '/api/analyze/rapid' : '/api/analyze/soap'
      const body = rapidMode
        ? { brief_notes: input, language, shift_id: shiftId }
        : { raw_notes: input, shift_id: shiftId }

      const res = await axios.post(`${API_URL}${endpoint}`, body)
      setOutput(res.data)
      setProcessingTime(res.data.processing_time_ms)
      setGeneratedAt(new Date().toLocaleTimeString())
      setFeedback(null)
      setDismissedFlags({})
      localStorage.removeItem(DRAFT_KEY)

      // Save to local history
      const entry = {
        id: res.data.id,
        preview: input.slice(0, 80),
        time: new Date().toLocaleTimeString(),
        data: res.data
      }
      const next = [entry, ...history].slice(0, 20)
      setHistory(next)
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next))

      // Auto run drug interaction check
      const plan = res.data.data?.plan
      if (plan) {
        try {
          const drugRes = await axios.post(`${API_URL}/api/analyze/drug-interactions`, { plan_text: plan })
          setDrugData(drugRes.data)
        } catch {}
      }
    } catch (e) {
      setError(e.response?.data?.detail || 'Processing failed. Is the backend running?')
    } finally {
      onLoadingChange(false)
    }
  }

  const handleSample = () => {
    if (rapidMode) {
      setInput('58F chest tightness 2d HTN amlodipine HR irreg BP 148/90 sats 96 likely AF plan ECG trop bisoprolol')
    } else {
      setInput(`58F c/o chest tightness x2d, worse on exertion, some SOB, no fever. Ex-smoker. HTN on amlodipine. HR 92 irregular, BP 148/90, sats 96%. Likely AF with demand ischaemia. Plan: ECG, trop, echo refer, hold amlodipine, start bisoprolol 2.5mg, apixaban after ruling out thrombus.`)
    }
  }

  const handleCopy = () => {
    if (!output?.data) return
    const { subjective, objective, assessment, plan } = output.data
    const text = `SOAP NOTE\n\nSubjective:\n${subjective || ''}\n\nObjective:\n${objective || ''}\n\nAssessment:\n${assessment || ''}\n\nPlan:\n${plan || ''}`
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        setCopyText('✓ Copied!')
        setTimeout(() => setCopyText('⧉ Copy Note'), 2000)
      })
    } else {
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      setCopyText('✓ Copied!')
      setTimeout(() => setCopyText('⧉ Copy Note'), 2000)
    }
  }

  const handleFeedback = async (val) => {
    setFeedback(val)
    if (output?.id) {
      try { await axios.post(`${API_URL}/api/feedback`, { analysis_id: output.id, value: val }) } catch {}
    }
  }

  const handleReferral = async () => {
    if (!selectedSpecialty || !output?.data) return
    onLoadingChange(true, 'Drafting referral letter...')
    try {
      const res = await axios.post(`${API_URL}/api/analyze/referral`, { soap_data: output.data, specialty: selectedSpecialty })
      setReferralLetter(res.data.data?.letter)
    } catch (e) {
      setError('Referral generation failed')
    } finally {
      onLoadingChange(false)
    }
  }

  const dismissFlag = (idx, reason) => {
    setDismissedFlags({ ...dismissedFlags, [idx]: reason || 'Dismissed' })
  }

  const soapColors = { subjective: '#3b82f6', objective: '#3b82f6', assessment: '#3b82f6', plan: '#3b82f6' }
  const sevConfig = {
    critical: { color: 'var(--critical)', icon: '🔴' },
    warning: { color: 'var(--warn)', icon: '🟠' },
    watch: { color: 'var(--accent)', icon: '🟡' }
  }

  return (
    <section className="module active">
      <div className="module-header">
        <div>
          <h1>Consultation Note Processor</h1>
          <p className="subtitle">Type raw notes. AI structures to SOAP + flags red alerts + checks drug interactions.</p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', marginRight: '10px' }}>
            <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text)' }}>⚡ Rapid Mode</span>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Shorthand to full notes</span>
          </div>
          <label className="toggle-switch">
            <input type="checkbox" checked={rapidMode} onChange={e => setRapidMode(e.target.checked)} />
            <span className="toggle-slider"></span>
          </label>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <label className="panel-label" style={{ marginBottom: 0 }}>{rapidMode ? '⚡ Rapid Consultation (5–10 words)' : 'Raw Consultation Notes'}</label>
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
          <div style={{ position: 'relative' }}>
            <textarea className="big-textarea" value={isListening ? input + (input && !input.endsWith(' ') ? ' ' : '') + transcript : input} onChange={e => setInput(e.target.value)}
              placeholder={rapidMode ? 'e.g. 58F chest pain 2d HTN bisoprolol sats 96' : 'e.g. 58F c/o chest tightness x2d, worse on exertion...'}
              style={{ width: '100%', ...(rapidMode ? { minHeight: '100px', fontFamily: 'var(--font-mono)', fontSize: '15px' } : {}) }} />
            <button 
              onClick={toggleListening} 
              style={{ 
                position: 'absolute', bottom: '12px', right: '12px', 
                background: isListening ? 'var(--critical)' : 'var(--surface2)', 
                color: isListening ? '#fff' : 'var(--text)', 
                border: `1px solid ${isListening ? 'var(--critical)' : 'var(--border)'}`, 
                borderRadius: '50%', width: '36px', height: '36px', 
                display: 'flex', alignItems: 'center', justifyContent: 'center', 
                cursor: 'pointer', transition: 'all 0.2s', boxShadow: isListening ? '0 0 12px rgba(255, 107, 107, 0.5)' : 'none'
              }}
              title={isListening ? 'Stop dictating' : 'Start dictating'}
            >
              🎙️
            </button>
          </div>
          <div className="btn-row">
            <button className="btn-primary" onClick={handleProcess}>✦ {rapidMode ? 'Expand Note' : 'Process Note'}</button>
            <button className="btn-ghost" onClick={handleSample}>Load Sample</button>
            {history.length > 0 && (
              <button className="btn-ghost" onClick={() => setShowHistory(!showHistory)}>
                {showHistory ? 'Hide' : '🕐'} History ({history.length})
              </button>
            )}
          </div>
          {error && <div className="error-msg">⚠ {error}</div>}
          {input && !output && <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>Draft auto-saved</div>}

          {showHistory && (
            <div className="history-panel">
              <div className="panel-label" style={{ marginBottom: '8px' }}>Recent Notes</div>
              {history.map((h, i) => (
                <div key={i} className="history-item" onClick={() => { setOutput(h.data); setShowHistory(false) }}>
                  <div style={{ fontSize: '12px', color: 'var(--text)' }}>{h.preview}...</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{h.time}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <label className="panel-label">
            SOAP Note + Red Flags
            {generatedAt && <span className="timestamp"> · {generatedAt}</span>}
            {processingTime && <span className="timestamp"> · {processingTime}ms</span>}
          </label>
          <div className="output-area">
            {!output ? (
              <div className="empty-state">Processed note will appear here.</div>
            ) : (
              <div>
                {['subjective','objective','assessment','plan'].map(key => output.data?.[key] && (
                  <div key={key} style={{ background: 'rgba(59,130,246,0.04)', border: '1px solid var(--border)', borderRadius: '10px', padding: '12px', marginBottom: '10px' }}>
                    <strong style={{ color: '#3b82f6', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em' }}>{key}</strong>
                    <p style={{ marginTop: '6px', fontSize: '13px', lineHeight: '1.6' }}>{output.data[key]}</p>
                    {key === 'plan' && findGenerics(output.data[key]).map((g, i) => (
                      <div key={i} style={{ marginTop: '6px', fontSize: '11px', color: 'var(--accent2)', background: 'rgba(63,185,80,0.08)', padding: '4px 8px', borderRadius: '4px' }}>
                        💊 {g.brand} → Generic: <strong>{g.generic}</strong> (Jan Aushadhi available)
                      </div>
                    ))}
                  </div>
                ))}

                {output.data?.patient_summary && (
                  <div style={{ background: 'rgba(88,166,255,0.08)', border: '1px solid rgba(88,166,255,0.3)', borderRadius: 'var(--radius)', padding: '12px', marginBottom: '10px' }}>
                    <strong style={{ color: 'var(--accent)', fontSize: '11px', textTransform: 'uppercase' }}>Patient Summary ({language})</strong>
                    <p style={{ marginTop: '6px', fontSize: '13px' }}>{output.data.patient_summary}</p>
                  </div>
                )}

                {(output.data?.red_flags || []).length > 0 && (
                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', margin: '14px 0 8px', borderTop: '1px solid var(--border)', paddingTop: '12px' }}>
                      ⚠ Red Flags ({output.data.red_flags.length})
                    </div>
                    {output.data.red_flags.map((flag, idx) => {
                      const cfg = sevConfig[flag.severity] || sevConfig.watch
                      if (dismissedFlags[idx]) {
                        return (
                          <div key={idx} style={{ fontSize: '12px', color: 'var(--text-muted)', padding: '6px 10px', borderRadius: '4px', border: '1px solid var(--border)', marginBottom: '6px', textDecoration: 'line-through' }}>
                            {flag.title} — <em>Dismissed: {dismissedFlags[idx]}</em>
                          </div>
                        )
                      }
                      return (
                        <DismissibleFlag key={idx} flag={flag} cfg={cfg} idx={idx} onDismiss={dismissFlag} />
                      )
                    })}
                  </div>
                )}

                {drugData?.data?.interactions?.length > 0 && (
                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', margin: '14px 0 8px', borderTop: '1px solid var(--border)', paddingTop: '12px' }}>
                      💊 Drug Interactions ({drugData.data.interactions.length})
                    </div>
                    {drugData.data.interactions.map((d, i) => (
                      <div key={i} style={{ border: '1px solid var(--warn)', borderLeft: '4px solid var(--warn)', borderRadius: 'var(--radius)', padding: '10px 12px', marginBottom: '8px', fontSize: '13px' }}>
                        <strong style={{ color: 'var(--warn)' }}>⚡ {d.drugs?.join(' + ')}</strong>
                        <p style={{ marginTop: '4px', color: 'var(--text-muted)', fontSize: '12px' }}>{d.description}</p>
                      </div>
                    ))}
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

          {output && (
            <>
              <div className="btn-row">
                <button className="btn-ghost small" onClick={handleCopy}>{copyText}</button>
                <button className="btn-ghost small" onClick={() => setShowReferral(!showReferral)}>📄 Referral</button>
              </div>
              {showReferral && (
                <div style={{ marginTop: '12px', padding: '12px', background: 'var(--surface2)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px' }}>Generate Referral Letter</div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <select value={selectedSpecialty} onChange={e => setSelectedSpecialty(e.target.value)}
                      style={{ flex: 1, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '6px', color: 'var(--text)', padding: '7px', fontSize: '13px' }}>
                      <option value="">Select specialty...</option>
                      {SPECIALTIES.map(s => <option key={s}>{s}</option>)}
                    </select>
                    <button className="btn-primary" style={{ fontSize: '12px' }} onClick={handleReferral} disabled={!selectedSpecialty}>Generate</button>
                  </div>
                  {referralLetter && (
                    <div style={{ marginTop: '10px' }}>
                      <textarea readOnly value={referralLetter} style={{ width: '100%', minHeight: '140px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '6px', color: 'var(--text)', padding: '10px', fontSize: '12px', fontFamily: 'var(--font-mono)', resize: 'vertical' }} />
                      <button className="btn-ghost small" style={{ marginTop: '6px' }} onClick={() => navigator.clipboard?.writeText(referralLetter)}>⧉ Copy Letter</button>
                    </div>
                  )}
                </div>
              )}
              <button className="btn-export" onClick={() => window.print()}>
                📄 Export Professional PDF
              </button>
            </>
          )}
          <div className="disclaimer">⚠ AI-assisted — always verify clinically</div>
        </div>
      </div>
    </section>
  )
}

function DismissibleFlag({ flag, cfg, idx, onDismiss }) {
  const [dismissing, setDismissing] = useState(false)
  const [reason, setReason] = useState('')
  return (
    <div style={{ border: `1px solid ${cfg.color}`, borderLeft: `4px solid ${cfg.color}`, borderRadius: 'var(--radius)', padding: '10px 12px', marginBottom: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
            <span>{flag.icon || cfg.icon}</span>
            <strong style={{ color: cfg.color, fontSize: '13px' }}>{flag.title}</strong>
            <span style={{ fontSize: '10px', background: cfg.color, color: '#fff', padding: '1px 5px', borderRadius: '3px', textTransform: 'uppercase' }}>{flag.severity}</span>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0, lineHeight: '1.5' }}>{flag.explanation}</p>
        </div>
        <button onClick={() => setDismissing(!dismissing)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '14px', marginLeft: '8px' }}>✕</button>
      </div>
      {dismissing && (
        <div style={{ marginTop: '8px', display: 'flex', gap: '6px' }}>
          <input value={reason} onChange={e => setReason(e.target.value)} placeholder="Reason for dismissal..."
            style={{ flex: 1, background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: '4px', color: 'var(--text)', padding: '5px 8px', fontSize: '12px' }} />
          <button className="btn-ghost small" onClick={() => onDismiss(idx, reason || 'No reason given')}>Dismiss</button>
        </div>
      )}
    </div>
  )
}
