// src/components/ListingModal.jsx
import React, { useEffect, useMemo } from 'react';

function fireKadastraAttach(listing) {
  window.dispatchEvent(new CustomEvent('kadastra-attach-listing', { detail: listing }));
}

export default function ListingModal({ listing, onClose }) {
  useEffect(() => {
    const handler = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', handler);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', handler);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  const phoneNumber = useMemo(() => {
    if (!listing?.description) return null;
    const phoneRegex = /(\+?\d{1,3}[\s.-]?)?\(?\d{1,4}\)?[\s.-]?\d{1,4}[\s.-]?\d{1,9}/g;
    const matches = listing.description.match(phoneRegex);
    return matches ? matches[0] : null;
  }, [listing?.description]);

  if (!listing) return null;
  const { titre, lien, prix, adresse, localisation, description, chambres, salles_de_bain, surface, type: type_bien, source, first_image } = listing;

  const fields = [
    { icon: '📍', label: 'Localisation', value: adresse || localisation },
    { icon: '📐', label: 'Surface', value: surface && surface !== 'N/A' ? `${surface} m²` : null },
    { icon: '🛏️', label: 'Chambres', value: chambres && chambres !== 'N/A' ? chambres : null },
    { icon: '🚿', label: 'Salles de bain', value: salles_de_bain && salles_de_bain !== 'N/A' ? salles_de_bain : null },
    { icon: '📞', label: 'Contact', value: phoneNumber },
  ].filter(f => f.value != null && f.value !== '');

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 10000,
        background: 'rgba(15,23,42,0.8)', backdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 40,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        className="fade-in"
        style={{
          background: '#fff', borderRadius: '24px',
          width: '100%', maxWidth: 750, maxHeight: '90vh',
          overflow: 'auto', boxShadow: 'var(--shadow-lg)',
          position: 'relative'
        }}
      >
        {/* Header Image */}
        <div style={{ height: 350, position: 'relative', overflow: 'hidden', background: '#f1f5f9' }}>
          {first_image ? (
            <img 
              src={first_image} 
              alt={titre} 
              referrerPolicy="no-referrer"
              style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
              onError={(e) => {
                e.target.onerror = null;
                e.target.src = "https://images.unsplash.com/photo-1560518883-ce09059eeffa?auto=format&fit=crop&q=80&w=800";
              }}
            />
          ) : (
            <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
               <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" strokeWidth="1"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
            </div>
          )}
          
          <button onClick={onClose} style={{
            position: 'absolute', top: 20, right: 20,
            background: 'rgba(255,255,255,0.9)', border: 'none', borderRadius: '50%',
            width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', fontSize: 24, fontWeight: 300, boxShadow: 'var(--shadow)'
          }}>×</button>

          <div style={{
            position: 'absolute', bottom: 20, left: 20,
            background: 'rgba(15, 23, 42, 0.7)', backdropFilter: 'blur(10px)',
            color: '#fff', fontSize: 12, fontWeight: 700,
            padding: '6px 16px', borderRadius: '99px', textTransform: 'uppercase',
            border: '1px solid rgba(255,255,255,0.2)'
          }}>
            {source?.toUpperCase() || 'KADASTRA'}
          </div>
        </div>

        {/* Content */}
        <div style={{ padding: '32px 40px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
            <div style={{ flex: 1, marginRight: 20 }}>
              <div style={{ color: 'var(--primary)', fontSize: 13, fontWeight: 800, textTransform: 'uppercase', marginBottom: 8, letterSpacing: '1px' }}>
                {type_bien || 'Annonce Immobilière'}
              </div>
              <h2 className="premium-font" style={{ fontSize: 28, fontWeight: 800, color: 'var(--text)', lineHeight: 1.2 }}>
                {titre}
              </h2>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 32, fontWeight: 900, color: 'var(--primary)', letterSpacing: '-1px' }}>
                {prix || '—'}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 }}>Prix Total</div>
            </div>
          </div>

          {/* Specs Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 16, marginBottom: 32 }}>
            {fields.map(({ icon, label, value }) => (
              <div key={label} style={{ background: 'var(--surface-alt)', padding: '16px', borderRadius: '16px', border: '1px solid var(--border-light)' }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', marginBottom: 4 }}>
                  {icon} {label}
                </div>
                <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)' }}>
                  {value}
                </div>
              </div>
            ))}
          </div>

          {/* Description */}
          <div style={{ marginBottom: 40 }}>
            <h3 className="premium-font" style={{ fontSize: 18, fontWeight: 800, marginBottom: 12 }}>Description</h3>
            <p style={{ fontSize: 15, color: 'var(--text-muted)', lineHeight: 1.8, whiteSpace: 'pre-line' }}>
              {description}
            </p>
          </div>

          {/* Security Map */}
          <div style={{ marginBottom: 40 }}>
            <h3 className="premium-font" style={{ fontSize: 18, fontWeight: 800, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 10 }}>
              🛡️ Analyse de Sécurité <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-muted)', background: 'var(--surface-alt)', padding: '4px 10px', borderRadius: 8 }}>Périmètre 2km</span>
            </h3>
            <div style={{ borderRadius: '20px', overflow: 'hidden', border: '1px solid var(--border)', height: 400, boxShadow: 'var(--shadow-premium)' }}>
              <iframe
                src={`http://127.0.0.1:8000/api/contracts/map/?minimal=1&q=${encodeURIComponent(adresse || localisation || titre)}`}
                style={{ width: '100%', height: '100%', border: 'none' }}
                title="Security Analysis"
              />
            </div>
          </div>

          {/* CTA */}
          <div style={{ display: 'flex', gap: 12 }}>
            <button
              onClick={() => { fireKadastraAttach(listing); onClose(); }}
              style={{
                flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                background: 'var(--accent, #f59e0b)', color: '#fff', padding: '18px', borderRadius: '16px',
                fontWeight: 800, fontSize: 15, border: 'none', cursor: 'pointer',
                boxShadow: '0 10px 20px -5px rgba(245,158,11,0.4)', transition: 'transform 0.2s'
              }}
              onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-2px)'}
              onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
            >
              🤖 Analyser avec l'IA
            </button>
            {lien && lien !== '#' && (
              <a href={lien} target="_blank" rel="noopener noreferrer" style={{
                flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                background: 'var(--primary)', color: '#fff', padding: '18px', borderRadius: '16px',
                fontWeight: 800, fontSize: 15, textDecoration: 'none', boxShadow: '0 10px 20px -5px rgba(99, 102, 241, 0.4)',
                transition: 'transform 0.2s'
              }}
                onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-2px)'}
                onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
              >
                Consulter l'annonce
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}