// frontend/src/pages/SecurityMap.jsx
import React, { useState } from 'react';
import MarketTrendMap from '../components/MarketTrendMap';
import { useLanguage } from '../i18n/LanguageContext';

const SecurityMap = () => {
  const { t } = useLanguage();
  const [activeTab, setActiveTab] = useState('incidents');

  const TABS = [
    { id: 'incidents', label: t('map.tabSecurity') },
    { id: 'market',    label: t('map.tabTrends')   },
  ];

  return (
    <div style={{ width: '100%', height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>

      {/* ── Tab bar ──────────────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex',
        gap: 4,
        padding: '10px 16px',
        background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        flexShrink: 0,
      }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '9px 20px',
              background: activeTab === tab.id
                ? 'rgba(99,102,241,0.15)'
                : 'transparent',
              color: activeTab === tab.id ? '#818cf8' : 'rgba(255,255,255,0.5)',
              border: activeTab === tab.id
                ? '1px solid rgba(99,102,241,0.4)'
                : '1px solid transparent',
              borderRadius: 10,
              fontWeight: activeTab === tab.id ? 700 : 500,
              fontSize: 13,
              cursor: 'pointer',
              transition: 'all 0.2s',
              letterSpacing: '0.2px',
            }}
            onMouseEnter={e => {
              if (activeTab !== tab.id) {
                e.currentTarget.style.color = 'rgba(255,255,255,0.8)';
                e.currentTarget.style.background = 'rgba(255,255,255,0.05)';
              }
            }}
            onMouseLeave={e => {
              if (activeTab !== tab.id) {
                e.currentTarget.style.color = 'rgba(255,255,255,0.5)';
                e.currentTarget.style.background = 'transparent';
              }
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Content ──────────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {activeTab === 'incidents' && (
          <iframe
            src="http://127.0.0.1:8000/api/contracts/map/"
            style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
            title={t('map.tabSecurity')}
          />
        )}
        {activeTab === 'market' && <MarketTrendMap />}
      </div>
    </div>
  );
};

export default SecurityMap;
