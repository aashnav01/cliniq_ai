import React from 'react'

export default function Loader({ loading, text }) {
  return (
    <div className={`loader-overlay ${loading ? 'active' : ''}`}>
      <div className="loader-box">
        <div className="loader-spinner"></div>
        <div className="loader-text">{text || 'Processing...'}</div>
        <div className="loader-sub">⚠ AI-assisted — verify clinically</div>
      </div>
    </div>
  )
}
