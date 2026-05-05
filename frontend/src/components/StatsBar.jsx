// src/components/StatsBar.jsx
import React from 'react';

export default function StatsBar({ stats }) {
  if (!stats) return null;

  const items = [
    { label: 'Total annonces', value: stats.total, color: '#1a56db', icon: '🏠' },
    { label: 'Mubawab', value: stats.mubawab, color: '#1a56db', icon: '🔵' },
    { label: 'Tayara', value: stats.tayara, color: '#0ea5e9', icon: '🩵' },
  ];

  return (
    <div style={{
      background: '#fff', borderBottom: '1px solid var(--border)',
      padding: '12px 0',
    }}>
      <div className="container" style={{ display: 'flex', gap: 32, alignItems: 'center', flexWrap: 'wrap' }}>
        {items.map(({ label, value, color, icon }) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 18 }}>{icon}</span>
            <div>
              <div style={{ fontSize: 18, fontWeight: 800, color, lineHeight: 1 }}>
                {value?.toLocaleString('fr-TN')}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 500 }}>{label}</div>
            </div>
          </div>
        ))}

        {stats.by_type && (
          <div style={{ display: 'flex', gap: 8, marginLeft: 'auto', flexWrap: 'wrap' }}>
            {stats.by_type.slice(0, 4).map(({ type_bien, count }) => (
              <span key={type_bien} style={{
                background: 'var(--bg)', border: '1px solid var(--border)',
                borderRadius: 99, padding: '3px 10px', fontSize: 12,
                color: 'var(--text-muted)', fontWeight: 500,
              }}>
                {type_bien} <b style={{ color: 'var(--text)' }}>{count}</b>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
