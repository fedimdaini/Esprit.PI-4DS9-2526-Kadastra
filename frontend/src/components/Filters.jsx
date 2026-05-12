// src/components/Filters.jsx
import React from 'react';
import { useLanguage } from '../i18n/LanguageContext';

const FilterLabel = ({ children, icon }) => (
  <div style={{ fontSize: 11, fontWeight: 800, color: 'var(--text)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8, textTransform: 'uppercase', letterSpacing: '1px', opacity: 0.8 }}>
    <span style={{ fontSize: 14, color: 'var(--primary)' }}>{icon}</span>
    {children}
  </div>
);

export default function Filters({ filters, onChange, options, onReset, total }) {
  const { t } = useLanguage();
  const update = (key, val) => onChange(f => ({ ...f, [key]: val, page: 1 }));

  return (
    <div style={{ width: 320, flexShrink: 0, position: 'sticky', top: 100 }}>
      <div className="card" style={{ padding: '32px 24px', background: '#fff', border: '1px solid var(--border-light)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
          <div>
            <h3 className="premium-font" style={{ fontSize: 22, fontWeight: 900, color: 'var(--primary)', letterSpacing: '-0.5px' }}>
              {t('filters.title1')} <span style={{ fontWeight: 400, opacity: 0.5 }}>{t('filters.title2')}</span>
            </h3>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, marginTop: 4 }}>{t('filters.subtitle')}</div>
          </div>
        </div>

        {/* Intelligence Counter */}
        <div style={{
          background: 'var(--primary)', padding: '20px', borderRadius: '16px',
          marginBottom: 32, boxShadow: '0 12px 24px -8px rgba(15, 23, 42, 0.3)',
          color: '#fff', position: 'relative', overflow: 'hidden'
        }}>
          <div style={{ position: 'absolute', top: -10, right: -10, fontSize: 60, opacity: 0.1 }}>📊</div>
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.7)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 4 }}>{t('filters.opportunities')}</div>
          <div style={{ fontSize: 24, fontWeight: 900, display: 'flex', alignItems: 'baseline', gap: 6 }}>
            {total.toLocaleString('fr-TN')}
            <span style={{ fontSize: 12, fontWeight: 500, opacity: 0.8 }}>{t('filters.units')}</span>
          </div>
          <div style={{ height: 4, width: '100%', background: 'rgba(255,255,255,0.1)', borderRadius: 2, marginTop: 12 }}>
            <div style={{ height: '100%', width: '70%', background: 'var(--accent)', borderRadius: 2 }} />
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
          {/* Source */}
          <div>
            <FilterLabel icon="⚖️">{t('filters.channel')}</FilterLabel>
            <select
              className="premium-input"
              style={{ width: '100%', background: 'var(--surface-alt)', border: '1px solid var(--border)' }}
              value={filters.source || 'all'}
              onChange={e => update('source', e.target.value)}
            >
              <option value="all">{t('filters.allChannels')}</option>
              <option value="mubawab">Mubawab Intelligence</option>
              <option value="tayara">Tayara Market</option>
            </select>
          </div>

          {/* Type */}
          <div>
            <FilterLabel icon="🏢">{t('filters.assetClass')}</FilterLabel>
            <select
              className="premium-input"
              style={{ width: '100%', background: 'var(--surface-alt)', border: '1px solid var(--border)' }}
              value={filters.type_bien || 'all'}
              onChange={e => update('type_bien', e.target.value)}
            >
              <option value="all">{t('filters.allClasses')}</option>
              {(options.types || []).map(tp => <option key={tp} value={tp}>{tp}</option>)}
            </select>
          </div>

          {/* Location */}
          <div>
            <FilterLabel icon="📍">{t('filters.sector')}</FilterLabel>
            <select
              className="premium-input"
              style={{ width: '100%', background: 'var(--surface-alt)', border: '1px solid var(--border)' }}
              value={filters.localisation || 'all'}
              onChange={e => update('localisation', e.target.value)}
            >
              <option value="all">{t('filters.national')}</option>
              {(options.cities || []).map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          {/* Budget */}
          <div>
            <FilterLabel icon="🏦">{t('filters.budget')}</FilterLabel>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <div style={{ position: 'relative', flex: 1 }}>
                <input
                  type="number"
                  placeholder={t('filters.min')}
                  className="premium-input"
                  style={{ width: '100%', paddingLeft: 12, background: 'var(--surface-alt)' }}
                  value={filters.min_prix || ''}
                  onChange={e => update('min_prix', e.target.value)}
                />
              </div>
              <div style={{ position: 'relative', flex: 1 }}>
                <input
                  type="number"
                  placeholder={t('filters.max')}
                  className="premium-input"
                  style={{ width: '100%', paddingLeft: 12, background: 'var(--surface-alt)' }}
                  value={filters.max_prix || ''}
                  onChange={e => update('max_prix', e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Surface */}
          <div>
            <FilterLabel icon="📐">{t('filters.area')}</FilterLabel>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <input
                type="number"
                placeholder={t('filters.min')}
                className="premium-input"
                style={{ width: '100%', background: 'var(--surface-alt)' }}
                value={filters.min_surface || ''}
                onChange={e => update('min_surface', e.target.value)}
              />
              <input
                type="number"
                placeholder={t('filters.max')}
                className="premium-input"
                style={{ width: '100%', background: 'var(--surface-alt)' }}
                value={filters.max_surface || ''}
                onChange={e => update('max_surface', e.target.value)}
              />
            </div>
          </div>

          {/* Bedrooms */}
          <div>
            <FilterLabel icon="🧩">{t('filters.rooms')}</FilterLabel>
            <div style={{ display: 'flex', gap: 4, background: 'var(--surface-alt)', padding: 4, borderRadius: 12, border: '1px solid var(--border)' }}>
              {['all', '1', '2', '3', '4+'].map(val => {
                const isActive = (filters.chambres || '') === (val === '4+' ? '4' : (val === 'all' ? '' : val));
                return (
                  <button
                    key={val}
                    onClick={() => update('chambres', val === 'all' ? '' : (val === '4+' ? '4' : val))}
                    style={{
                      flex: 1, padding: '10px 0', borderRadius: 8, fontSize: 11, fontWeight: 800,
                      background: isActive ? 'var(--primary)' : 'transparent',
                      color: isActive ? '#fff' : 'var(--text-muted)',
                      boxShadow: isActive ? '0 4px 12px rgba(15, 23, 42, 0.2)' : 'none',
                      transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                    }}
                  >
                    {val === 'all' ? t('filters.all') : val}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Reset */}
          <button
            onClick={onReset}
            style={{
              marginTop: 12, width: '100%', padding: '14px', borderRadius: 12,
              fontSize: 12, fontWeight: 800, color: 'var(--text-muted)',
              background: 'transparent', border: '1px dashed var(--border)',
              transition: 'all 0.2s', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8
            }}
            onMouseEnter={e => { e.target.style.background = 'var(--surface-alt)'; e.target.style.color = 'var(--primary)'; }}
            onMouseLeave={e => { e.target.style.background = 'transparent'; e.target.style.color = 'var(--text-muted)'; }}
          >
            {t('filters.reset')}
          </button>
        </div>
      </div>
    </div>
  );
}
