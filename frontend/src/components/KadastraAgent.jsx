/**
 * KadastraAgent.jsx
 * 
 * AI Agent pop-up component for Kadastra investment analysis.
 * Drop this file into your React src/components/ directory.
 * 
 * Usage: import KadastraAgent from './components/KadastraAgent';
 *        Add <KadastraAgent /> anywhere in your App.
 * 
 * Requires: npm install recharts (for the IRR chart)
 * 
 * API endpoint: configured via REACT_APP_KADASTRA_API env var
 * or defaults to http://localhost:8001
 */
import React, { useState, useRef, useEffect } from 'react';

const API_BASE = process.env.REACT_APP_KADASTRA_API || 'http://localhost:8001';

// ── Styles (inline to avoid CSS file dependency) ─────────────────────────
const styles = {
  bubble: {
    position: 'fixed', bottom: 24, right: 24, width: 60, height: 60,
    borderRadius: '50%', background: 'linear-gradient(135deg, #3B82F6, #1D4ED8)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    cursor: 'pointer', boxShadow: '0 4px 20px rgba(59,130,246,0.4)',
    zIndex: 9999, transition: 'transform 0.2s',
    border: 'none', color: 'white', fontSize: 26,
  },
  panel: {
    position: 'fixed', bottom: 96, right: 24, width: 420, maxHeight: '70vh',
    borderRadius: 16, background: '#0F172A', border: '1px solid #1E293B',
    boxShadow: '0 8px 40px rgba(0,0,0,0.5)', zIndex: 9998,
    display: 'flex', flexDirection: 'column', overflow: 'hidden',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  header: {
    padding: '16px 20px', background: '#1E293B', display: 'flex',
    alignItems: 'center', justifyContent: 'space-between',
  },
  title: { color: '#E2E8F0', fontSize: 16, fontWeight: 700, margin: 0 },
  subtitle: { color: '#94A3B8', fontSize: 11, margin: 0 },
  close: {
    background: 'none', border: 'none', color: '#94A3B8', fontSize: 20,
    cursor: 'pointer', padding: 4,
  },
  messages: {
    flex: 1, overflowY: 'auto', padding: 16, display: 'flex',
    flexDirection: 'column', gap: 12, maxHeight: '50vh',
  },
  msgBot: {
    background: '#1E293B', borderRadius: '12px 12px 12px 4px', padding: 14,
    color: '#E2E8F0', fontSize: 13, lineHeight: 1.5, maxWidth: '90%',
  },
  msgUser: {
    background: '#3B82F6', borderRadius: '12px 12px 4px 12px', padding: 14,
    color: 'white', fontSize: 13, lineHeight: 1.5, alignSelf: 'flex-end',
    maxWidth: '85%',
  },
  inputArea: {
    padding: '12px 16px', borderTop: '1px solid #1E293B',
    display: 'flex', gap: 8,
  },
  input: {
    flex: 1, background: '#1E293B', border: '1px solid #334155',
    borderRadius: 8, padding: '10px 14px', color: '#E2E8F0', fontSize: 13,
    outline: 'none', resize: 'none',
  },
  sendBtn: {
    background: '#3B82F6', border: 'none', borderRadius: 8, padding: '0 16px',
    color: 'white', fontSize: 14, cursor: 'pointer', fontWeight: 600,
    whiteSpace: 'nowrap',
  },
  verdictBadge: (rec) => ({
    display: 'inline-block', padding: '4px 12px', borderRadius: 6,
    fontWeight: 700, fontSize: 14, marginBottom: 8,
    background: rec === 'STRONG BUY' ? '#059669' :
                rec === 'CONSIDER' ? '#D97706' :
                rec === 'CAUTIOUS' ? '#EA580C' : '#DC2626',
    color: 'white',
  }),
  metricRow: {
    display: 'flex', justifyContent: 'space-between', padding: '3px 0',
    borderBottom: '1px solid #334155', fontSize: 12,
  },
  metricLabel: { color: '#94A3B8' },
  metricValue: { color: '#E2E8F0', fontWeight: 600 },
  flagChip: {
    display: 'inline-block', background: '#7F1D1D', color: '#FCA5A5',
    padding: '2px 8px', borderRadius: 4, fontSize: 11, margin: '2px 4px 2px 0',
  },
  insightChip: {
    display: 'inline-block', background: '#1E3A5F', color: '#93C5FD',
    padding: '2px 8px', borderRadius: 4, fontSize: 11, margin: '2px 4px 2px 0',
  },
  sweepBar: (irr, hurdle) => ({
    height: 6, borderRadius: 3, marginTop: 2,
    background: irr >= hurdle ? '#059669' : irr > 0 ? '#3B82F6' : '#DC2626',
    width: `${Math.min(Math.max(irr / 10 * 100, 5), 100)}%`,
    transition: 'width 0.3s',
  }),
  loading: {
    display: 'flex', alignItems: 'center', gap: 8, color: '#94A3B8', fontSize: 13,
  },
};

// ── Component ────────────────────────────────────────────────────────────
export default function KadastraAgent() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    { role: 'bot', content: 'welcome' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setLoading(true);

    try {
      const resp = await fetch(`${API_BASE}/api/quick-analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      const data = await resp.json();
      if (resp.ok) {
        setMessages(prev => [...prev, { role: 'bot', content: 'result', data }]);
      } else {
        setMessages(prev => [...prev, {
          role: 'bot', content: 'error',
          data: { message: data.detail || data.error || 'Analysis failed' }
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'bot', content: 'error',
        data: { message: `Connection error: ${err.message}` }
      }]);
    }
    setLoading(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ── Render helpers ───────────────────────────────────────────────────
  const renderWelcome = () => (
    <div style={styles.msgBot}>
      <strong>Kadastra AI Agent</strong>
      <p style={{ margin: '8px 0 4px' }}>
        Describe a property and I'll analyze its investment potential.
      </p>
      <p style={{ margin: 0, color: '#94A3B8', fontSize: 11 }}>
        Example: "Appartement 120m² à Tunis Lac, 250 000 TND, neuf avec parking, budget 300 000 TND, hold 7 ans"
      </p>
    </div>
  );

  const renderResult = (data) => {
    const hurdle = data.tax?.cgt_note ? 7.49 : 7.49;
    return (
      <div style={styles.msgBot}>
        {/* Verdict */}
        <div style={styles.verdictBadge(data.verdict)}>
          {data.verdict} — {data.score}/100
        </div>

        {/* Financials */}
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 11, color: '#64748B', marginBottom: 4, fontWeight: 600 }}>
            FINANCIALS
          </div>
          {[
            ['Gross Yield', `${data.financials?.gross_yield?.toFixed(2)}%`],
            ['Net Yield', `${data.financials?.net_yield?.toFixed(2)}%`],
            ['IRR', `${data.financials?.irr_percent?.toFixed(2)}%`],
            ['Monthly Rent Est.', `${data.financials?.monthly_rent_estimate?.toLocaleString()} TND`],
            ['NPV (median)', `${data.financials?.npv_p50?.toLocaleString()} TND`],
            ['P(NPV>0)', `${(data.financials?.prob_positive_npv * 100)?.toFixed(0)}%`],
          ].map(([k, v]) => (
            <div key={k} style={styles.metricRow}>
              <span style={styles.metricLabel}>{k}</span>
              <span style={styles.metricValue}>{v}</span>
            </div>
          ))}
        </div>

        {/* Risk */}
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 11, color: '#64748B', marginBottom: 4, fontWeight: 600 }}>
            RISK — {data.risk?.level} ({data.risk?.score?.toFixed(3)})
          </div>
          {data.risk?.flags?.length > 0 && (
            <div>{data.risk.flags.map((f, i) => (
              <span key={i} style={styles.flagChip}>{f}</span>
            ))}</div>
          )}
        </div>

        {/* Tax */}
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 11, color: '#64748B', marginBottom: 4, fontWeight: 600 }}>
            TAX
          </div>
          <div style={styles.metricRow}>
            <span style={styles.metricLabel}>Acquisition Fees</span>
            <span style={styles.metricValue}>{data.tax?.acquisition_fees_pct?.toFixed(2)}%</span>
          </div>
          <div style={styles.metricRow}>
            <span style={styles.metricLabel}>Optimal Hold</span>
            <span style={styles.metricValue}>{data.tax?.optimal_holding_years} years</span>
          </div>
        </div>

        {/* Insights */}
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 11, color: '#64748B', marginBottom: 4, fontWeight: 600 }}>
            KEY INSIGHTS
          </div>
          {data.insights?.map((ins, i) => (
            <span key={i} style={styles.insightChip}>{ins}</span>
          ))}
        </div>

        {/* Holding Period Sweep (mini chart) */}
        {data.holding_sweep && (
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 11, color: '#64748B', marginBottom: 4, fontWeight: 600 }}>
              IRR BY HOLDING PERIOD
            </div>
            {data.holding_sweep.map((r) => (
              <div key={r.years} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                <span style={{ width: 24, fontSize: 10, color: '#94A3B8', textAlign: 'right' }}>
                  {r.years}yr
                </span>
                <div style={{ flex: 1 }}>
                  <div style={styles.sweepBar(r.irr_pct, hurdle)} />
                </div>
                <span style={{ width: 40, fontSize: 10, color: '#E2E8F0', textAlign: 'right' }}>
                  {r.irr_pct.toFixed(1)}%
                </span>
              </div>
            ))}
            <div style={{ fontSize: 10, color: '#EF4444', marginTop: 4 }}>
              ── BCT hurdle: {hurdle}% ──
            </div>
          </div>
        )}

        {/* Sources */}
        <div style={{ marginTop: 12, fontSize: 10, color: '#64748B' }}>
          Sources: GlobalPropertyGuide Q2-2025, BCT TMM Sept-2025, Code IRPP-IS 2024, LF2025
        </div>
        <div style={{ fontSize: 10, color: '#475569', marginTop: 2 }}>
          Analysis completed in {data.elapsed_seconds}s
        </div>
      </div>
    );
  };

  const renderError = (data) => (
    <div style={{ ...styles.msgBot, borderLeft: '3px solid #DC2626' }}>
      <strong style={{ color: '#FCA5A5' }}>Error</strong>
      <p style={{ margin: '4px 0 0', color: '#E2E8F0' }}>{data.message}</p>
    </div>
  );

  const renderMessage = (msg, idx) => {
    if (msg.role === 'user') {
      return <div key={idx} style={styles.msgUser}>{msg.content}</div>;
    }
    if (msg.content === 'welcome') return <div key={idx}>{renderWelcome()}</div>;
    if (msg.content === 'result') return <div key={idx}>{renderResult(msg.data)}</div>;
    if (msg.content === 'error') return <div key={idx}>{renderError(msg.data)}</div>;
    return <div key={idx} style={styles.msgBot}>{msg.content}</div>;
  };

  // ── Main render ────────────────────────────────────────────────────
  return (
    <>
      {/* Floating bubble */}
      <button
        style={styles.bubble}
        onClick={() => setOpen(!open)}
        onMouseEnter={(e) => e.target.style.transform = 'scale(1.1)'}
        onMouseLeave={(e) => e.target.style.transform = 'scale(1)'}
        title="Kadastra AI Agent"
      >
        {open ? '✕' : '🏠'}
      </button>

      {/* Chat panel */}
      {open && (
        <div style={styles.panel}>
          {/* Header */}
          <div style={styles.header}>
            <div>
              <p style={styles.title}>🏠 Kadastra Agent</p>
              <p style={styles.subtitle}>Real Estate Investment AI</p>
            </div>
            <button style={styles.close} onClick={() => setOpen(false)}>✕</button>
          </div>

          {/* Messages */}
          <div style={styles.messages}>
            {messages.map(renderMessage)}
            {loading && (
              <div style={styles.loading}>
                <span className="kadastra-spinner" />
                Analyzing investment scenario...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div style={styles.inputArea}>
            <textarea
              style={styles.input}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe a property... (e.g., Appart 120m² Tunis Lac 250k TND)"
              rows={1}
            />
            <button
              style={{ ...styles.sendBtn, opacity: loading ? 0.5 : 1 }}
              onClick={sendMessage}
              disabled={loading}
            >
              Send
            </button>
          </div>
        </div>
      )}

      {/* Spinner CSS */}
      <style>{`
        .kadastra-spinner {
          width: 16px; height: 16px; border: 2px solid #334155;
          border-top: 2px solid #3B82F6; border-radius: 50%;
          animation: kadastra-spin 0.8s linear infinite;
        }
        @keyframes kadastra-spin { to { transform: rotate(360deg); } }
      `}</style>
    </>
  );
}
