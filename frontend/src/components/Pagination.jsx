// src/components/Pagination.jsx
import React from 'react';

const NavButton = ({ direction, disabled, onClick }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    style={{
      padding: '8px 16px', borderRadius: 12, fontSize: 13, fontWeight: 800,
      background: '#fff', border: '1px solid var(--border)',
      color: disabled ? 'var(--text-muted)' : 'var(--primary)',
      opacity: disabled ? 0.4 : 1, cursor: disabled ? 'default' : 'pointer',
      display: 'flex', alignItems: 'center', gap: 8, transition: 'all 0.2s',
      boxShadow: disabled ? 'none' : 'var(--shadow-sm)'
    }}
    onMouseEnter={e => !disabled && (e.target.style.borderColor = 'var(--primary)')}
    onMouseLeave={e => !disabled && (e.target.style.borderColor = 'var(--border)')}
  >
    {direction === 'prev' && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M15 18l-6-6 6-6"/></svg>}
    {direction === 'prev' ? 'PRÉCÉDENT' : 'SUIVANT'}
    {direction === 'next' && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M9 18l6-6-6-6"/></svg>}
  </button>
);

export default function Pagination({ current, total, pageSize, onChange }) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;

  const pages = [];
  const delta = 2;
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= current - delta && i <= current + delta)) {
      pages.push(i);
    } else if (pages[pages.length - 1] !== '...') {
      pages.push('...');
    }
  }

  const btnStyle = (active) => ({
    minWidth: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center',
    borderRadius: 12, fontSize: 13, fontWeight: 800,
    background: active ? 'var(--primary)' : 'transparent',
    color: active ? '#fff' : 'var(--text-muted)',
    border: active ? '1px solid var(--primary)' : '1px solid transparent',
    cursor: 'pointer', transition: 'all 0.2s',
    boxShadow: active ? '0 8px 16px -4px rgba(15, 23, 42, 0.3)' : 'none'
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20, width: '100%' }}>
      {/* Visual Status */}
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>
        Page <span style={{ color: 'var(--primary)' }}>{current}</span> sur {totalPages} <span style={{ opacity: 0.3, margin: '0 8px' }}>|</span> Volume total : <span style={{ color: 'var(--primary)' }}>{total.toLocaleString()}</span> assets
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--surface-alt)', padding: '6px 12px', borderRadius: 16, border: '1px solid var(--border)' }}>
        <NavButton direction="prev" disabled={current === 1} onClick={() => current > 1 && onChange(current - 1)} />

        <div style={{ display: 'flex', gap: 4, margin: '0 8px' }}>
          {pages.map((p, i) => (
            p === '...'
              ? <span key={`e${i}`} style={{ alignSelf: 'center', color: 'var(--text-muted)', padding: '0 8px', fontWeight: 800 }}>···</span>
              : <button 
                  key={p} 
                  onClick={() => onChange(p)} 
                  style={btnStyle(p === current)}
                  onMouseEnter={e => ! (p === current) && (e.target.style.background = 'rgba(15, 23, 42, 0.05)')}
                  onMouseLeave={e => ! (p === current) && (e.target.style.background = 'transparent')}
                >
                  {p}
                </button>
          ))}
        </div>

        <NavButton direction="next" disabled={current === totalPages} onClick={() => current < totalPages && onChange(current + 1)} />
      </div>
    </div>
  );
}
