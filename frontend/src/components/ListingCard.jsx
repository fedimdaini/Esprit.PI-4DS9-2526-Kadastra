// src/components/ListingCard.jsx
import React from 'react';

const CardStat = ({ icon, label, value }) => {
  if (!value || value === 'N/A') return null;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--text-muted)', fontSize: 13, fontWeight: 500 }}>
      <span style={{ fontSize: 15 }}>{icon}</span>
      <span>{value}</span>
    </div>
  );
};

function fireKadastraAttach(listing) {
  window.dispatchEvent(new CustomEvent('kadastra-attach-listing', { detail: listing }));
}

// Price-analysis pill config  (label → [bg, text, border])
const PILL_STYLE = {
  great:     { bg: '#d1fae5', color: '#065f46', border: '#6ee7b7' },
  fair:      { bg: '#eff6ff', color: '#1d4ed8', border: '#bfdbfe' },
  high:      { bg: '#fff7ed', color: '#c2410c', border: '#fed7aa' },
  very_high: { bg: '#fff1f2', color: '#be123c', border: '#fecdd3' },
};

export default function ListingCard({ listing, onClick }) {
  const {
    titre, prix, adresse, localisation, pieces, chambres, salles_de_bain, surface,
    source, first_image,
    price_numeric, original_currency, price_analysis,
  } = listing;

  // Build the display price string — only real prices from the database
  const displayPrice = (() => {
    if (original_currency === 'EUR' && price_numeric && prix)
      return `${prix} ≈ ${price_numeric.toLocaleString('fr-TN')} TND`;
    if (prix && prix !== 'N/A') return prix;
    return 'Prix à consulter';
  })();

  return (
    <div className="card fade-in" onClick={onClick} style={{ cursor: 'pointer', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* Image Area */}
      <div style={{ height: 220, position: 'relative', overflow: 'hidden', background: '#f1f5f9' }}>
        {first_image ? (
          <img 
            src={first_image} 
            alt={titre}
            referrerPolicy="no-referrer"
            style={{ width: '100%', height: '100%', objectFit: 'cover', transition: 'transform 0.5s ease' }}
            onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.08)'}
            onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
            onError={(e) => {
              e.target.onerror = null; 
              e.target.src = "https://images.unsplash.com/photo-1560518883-ce09059eeffa?auto=format&fit=crop&q=80&w=600";
            }}
          />
        ) : (
          <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
             <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" strokeWidth="1"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
          </div>
        )}

        {/* Badges */}
        <div style={{ position: 'absolute', top: 12, left: 12, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <span className={`badge badge-${source}`} style={{ boxShadow: '0 4px 10px rgba(0,0,0,0.1)' }}>
            {source === 'mubawab' ? 'Mubawab' : 'Tayara'}
          </span>
          {original_currency === 'EUR' && price_numeric && (
            <span style={{
              background: 'linear-gradient(135deg,#0EA5E9,#0284C7)',
              color: 'white', fontSize: 10, fontWeight: 700,
              padding: '3px 8px', borderRadius: 6,
              boxShadow: '0 4px 10px rgba(0,0,0,0.1)',
            }}>
              € → TND
            </span>
          )}
        </div>
      </div>

      {/* Content Area */}
      <div style={{ padding: 20, flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-light)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
          </svg>
          <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {adresse || localisation || 'Tunisie'}
          </span>
        </div>

        <h3 className="premium-font" style={{ 
          fontSize: 16, fontWeight: 700, color: 'var(--text)', 
          marginBottom: 12, lineHeight: 1.4, height: '2.8em',
          overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical'
        }}>
          {titre}
        </h3>

        <div style={{ display: 'flex', gap: 14, marginBottom: 16, flexWrap: 'wrap' }}>
          <CardStat icon="📐" value={surface && surface !== 'N/A' ? `${surface} m²` : null} />
          <CardStat icon="🛏️" value={chambres} />
          <CardStat icon="🚿" value={salles_de_bain} />
        </div>

        <div style={{ marginTop: 'auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-light)', paddingTop: 14 }}>
          <div>
            <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--primary)', letterSpacing: '-0.5px' }}>
              {displayPrice}
            </div>
            {price_analysis && (() => {
              const ps = PILL_STYLE[price_analysis.label] || PILL_STYLE.fair;
              return (
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  background: ps.bg, color: ps.color,
                  border: `1px solid ${ps.border}`,
                  borderRadius: 99, padding: '2px 10px',
                  fontSize: 11, fontWeight: 700, marginTop: 6,
                }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: ps.color, flexShrink: 0 }}/>
                  {price_analysis.label_fr}
                </span>
              );
            })()}
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              onClick={(e) => { e.stopPropagation(); fireKadastraAttach(listing); }}
              title="Analyser avec Kadastra AI"
              style={{
                background: 'linear-gradient(135deg,#3B82F6,#1D4ED8)',
                border: 'none', borderRadius: 8, padding: '6px 12px',
                color: 'white', fontSize: 12, fontWeight: 700, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 4,
                whiteSpace: 'nowrap',
              }}
            >
              Ask AI
            </button>
            <div style={{
              width: 32, height: 32, borderRadius: '50%', background: 'var(--primary-light)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--primary)'
            }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}