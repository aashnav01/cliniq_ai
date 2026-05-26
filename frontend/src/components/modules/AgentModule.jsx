import React, { useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'https://cliniq-ai-kqfz.onrender.com'

export default function AgentModule({ onLoadingChange }) {
  const [query, setQuery] = useState('')
  const [response, setResponse] = useState(null)
  const [error, setError] = useState(null)

  const handleRunAgent = async () => {
    if (!query.trim()) return alert('Please enter a query.')
    
    setError(null)
    onLoadingChange(true, 'Asking Clinical Agent...')
    
    try {
      const res = await fetch(`${API_URL}/api/agent/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim() })
      })
      
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`HTTP ${res.status}: ${errText}`)
      }
      
      const data = await res.json()
      setResponse(data)
    } catch (e) {
      setError(e.message)
    } finally {
      onLoadingChange(false)
    }
  }

  return (
    <section className="module active">
      <div className="module-header">
        <div>
          <h1>Clinical AI Agent</h1>
          <p className="subtitle">Ask natural language queries about patient data (e.g. "show all critical red flags from today").</p>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <label className="panel-label">Agent Query</label>
          <textarea 
            className="big-textarea" 
            style={{ minHeight: '120px' }} 
            placeholder="e.g. show all critical red flags from today"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="btn-row" style={{ marginTop: '12px' }}>
            <button className="btn-primary" onClick={handleRunAgent}>✦ Ask Agent</button>
          </div>
        </div>

        <div className="panel">
          <label className="panel-label">Response</label>
          <div className="output-area" style={{ flex: 1 }}>
            {error && (
              <div className="empty-state" style={{ color: 'var(--danger)' }}>
                Error: {error}
              </div>
            )}
            
            {!response && !error && (
              <div className="empty-state">Agent response will appear here.</div>
            )}
            
            {response && !error && (
              <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '16px', animation: 'fadeIn 0.3s ease' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 600, fontSize: '14px' }}>Agent Insight</span>
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.7' }}>
                  <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--accent)', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Interpreted as: {response.interpreted_as || 'N/A'}
                  </div>
                  <div style={{ fontSize: '14px', color: 'var(--text)', marginBottom: '16px', lineHeight: 1.6 }}>
                    {response.insight || 'No insight provided.'}
                  </div>
                  <div style={{ display: 'flex', gap: '12px', fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    <span style={{ background: 'var(--surface2)', padding: '2px 6px', borderRadius: '4px', border: '1px solid var(--border)' }}>
                      Count: {response.count !== undefined ? response.count : 'N/A'}
                    </span>
                    <span style={{ background: 'var(--surface2)', padding: '2px 6px', borderRadius: '4px', border: '1px solid var(--border)' }}>
                      Collection: {response.collection_queried || 'N/A'}
                    </span>
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'center', marginTop: '16px', borderTop: '1px solid var(--border)', paddingTop: '12px' }}>
                  <span style={{ fontSize: '10px', color: 'var(--accent2)', fontFamily: 'var(--font-mono)', fontWeight: 500 }}>
                    ✦ Powered by Gemini 2.0 Flash + MongoDB Atlas
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
