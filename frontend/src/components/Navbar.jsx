// src/components/Navbar.jsx
import React from 'react';

export default function Navbar({ onSearch, view, setView, user, logout }) {
  if (!user) return null;
  return (
    <nav style={{
      background: '#fff', borderBottom: '1px solid var(--border)',
      padding: '0 32px', position: 'sticky', top: 0, zIndex: 1500,
      height: 72, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      boxShadow: 'var(--shadow-sm)'
    }}>
      {/* Left: Logo */}
      <div style={{ display: 'flex', alignItems: 'center', minWidth: 200 }}>
        <img
          src="/kadastra-logo.png"
          alt="Kadastra"
          style={{ height: 52, width: 'auto', objectFit: 'contain' }}
        />
      </div>

      {/* Center: Search */}
      <div style={{ flex: 1, maxWidth: 450, position: 'relative' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          background: 'var(--surface-alt)', borderRadius: '12px',
          padding: '0 16px', border: '1px solid var(--border)',
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2.5">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            type="text"
            placeholder="Rechercher..."
            onChange={(e) => onSearch(e.target.value)}
            style={{
              flex: 1, border: 'none', background: 'transparent',
              fontSize: 14, fontWeight: 500, padding: '10px 0', outline: 'none'
            }}
          />
        </div>
      </div>

      {/* Right: Nav & User */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 24, minWidth: 400, justifyContent: 'flex-end' }}>
        <div style={{ display: 'flex', background: 'var(--surface-alt)', padding: 4, borderRadius: 12 }}>
          {[
            { id: 'listings', label: 'Annonces', icon: '🏠' },
            { id: 'dashboard', label: 'Stats', icon: '📊' },
            { id: 'contracts', label: 'Contrats', icon: '⚖️' },
            { id: 'map', label: 'Carte', icon: '🗺️' }
          ].map(item => (
            <button key={item.id} onClick={() => setView(item.id)} style={{
              padding: '8px 16px', borderRadius: 10, fontSize: 13, fontWeight: 700,
              background: view === item.id ? 'var(--accent)' : 'transparent',
              color: view === item.id ? '#000' : 'var(--text-muted)',
              transition: 'all 0.2s',
            }}>
              {item.label}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ textAlign: 'right', lineHeight: 1.2 }}>
            <div style={{ fontSize: 13, fontWeight: 800 }}>{user.first_name || user.username}</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{user.user_type}</div>
          </div>
          <div style={{
            width: 38, height: 38, borderRadius: '12px',
            background: 'var(--primary)', color: '#fff',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 15, fontWeight: 800, border: '2px solid var(--accent)'
          }}>
            {(user.first_name || user.username || 'U')[0].toUpperCase()}
          </div>
          <button onClick={logout} style={{
            marginLeft: 8, padding: '8px', borderRadius: 10,
            background: '#fff1f2', color: '#e11d48',
            border: '1px solid #fecaca'
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          </button>
        </div>
      </div>
    </nav>
  );
}
