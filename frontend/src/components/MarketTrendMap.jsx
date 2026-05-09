// frontend/src/components/MarketTrendMap.jsx
import React, { useEffect, useState, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default icon paths (CRA asset pipeline)
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl:       require('leaflet/dist/images/marker-icon.png'),
  shadowUrl:     require('leaflet/dist/images/marker-shadow.png'),
});

// ── Governorate centre coordinates ────────────────────────────────────────────
const GOVERNORATE_COORDS = {
  Tunis:        [36.8065, 10.1815],
  Ariana:       [36.8925, 10.1240],
  'Ben Arous':  [36.7538, 10.2189],
  Manouba:      [36.8079, 10.0952],
  Nabeul:       [36.4560, 10.7370],
  Zaghouan:     [36.4029, 10.1427],
  Bizerte:      [37.2744,  9.8739],
  Beja:         [36.7257,  9.1817],
  Jendouba:     [36.5010,  8.7802],
  Kef:          [36.1740,  8.7149],
  Siliana:      [36.0850,  9.3740],
  Sousse:       [35.8255, 10.6360],
  Monastir:     [35.7640, 10.8110],
  Mahdia:       [35.5040, 11.0620],
  Sfax:         [34.7400, 10.7600],
  Kairouan:     [35.6780, 10.0960],
  Kasserine:    [35.1670,  8.8330],
  'Sidi Bouzid':[35.0380,  9.4850],
  Gabes:        [33.8810, 10.0980],
  Mednine:      [33.3550, 10.5050],
  Tataouine:    [32.9290, 10.4510],
  Gafsa:        [34.4250,  8.7840],
  Tozeur:       [33.9190,  8.1330],
  Kebili:       [33.7040,  8.9710],
};

// ── Valid type/transaction combinations (terrain/local location don't exist) ──
const VALID_COMBINATIONS = {
  appartement: ['vente', 'location'],
  maison:      ['vente', 'location'],
  terrain:     ['vente'],
  local:       ['vente'],
};

// ── Colour scale: red (≤-30%) ↔ yellow (0%) ↔ green (≥+30%) ─────────────────
const getColor = (pct) => {
  const t = Math.min(1, Math.max(0, (pct + 30) / 60));
  const r = Math.round(255 * (1 - t));
  const g = Math.round(255 * t);
  return `rgb(${r}, ${g}, 60)`;
};

// ── Marker radius: 10px base + scale with |pct| (max +14px) ──────────────────
const getRadius = (pct) => Math.round(10 + Math.min(14, Math.abs(pct) / 4));

// ── Format a price number for display ─────────────────────────────────────────
const fmtPrice = (v) => (v != null ? `${Math.round(v).toLocaleString('fr-TN')} TND` : 'N/D');

// ── Build a custom circle divIcon ─────────────────────────────────────────────
const buildIcon = (pct, estimated) => {
  const r      = getRadius(pct);
  const color  = getColor(pct);
  const border = estimated ? '2px dashed rgba(255,255,255,0.9)' : '2px solid rgba(255,255,255,0.95)';
  const html   = `
    <div style="
      width:${r * 2}px; height:${r * 2}px;
      background:${color};
      border-radius:50%;
      border:${border};
      box-shadow:0 3px 10px rgba(0,0,0,0.35);
      opacity:0.88;
      display:flex; align-items:center; justify-content:center;
      font-size:${Math.max(9, r - 5)}px;
      font-weight:800;
      color:rgba(0,0,0,0.7);
      text-shadow:0 0 3px rgba(255,255,255,0.9);
      font-family:system-ui,sans-serif;
    ">${estimated ? '∗' : ''}</div>`;
  return L.divIcon({
    html,
    iconSize:   [r * 2, r * 2],
    iconAnchor: [r, r],
    className:  'kadastra-trend-marker',
  });
};

// ── Gradient bar for legend ───────────────────────────────────────────────────
const GradientLegend = () => (
  <div style={{
    position:'absolute', bottom:28, right:16, zIndex:1000,
    background:'rgba(15,23,42,0.82)', backdropFilter:'blur(10px)',
    borderRadius:12, padding:'10px 18px',
    color:'#fff', fontSize:11, fontFamily:'system-ui,sans-serif',
    display:'flex', flexDirection:'column', gap:6,
    border:'1px solid rgba(255,255,255,0.1)',
    boxShadow:'0 4px 20px rgba(0,0,0,0.4)',
  }}>
    <div style={{ fontWeight:800, letterSpacing:'0.5px', marginBottom:2, fontSize:12 }}>
      TENDANCE 12 MOIS
    </div>
    <div style={{ display:'flex', alignItems:'center', gap:10 }}>
      <span style={{ fontSize:10, opacity:0.8 }}>−30%</span>
      <div style={{
        width:100, height:8,
        background:'linear-gradient(90deg, #ef4444, #facc15, #22c55e)',
        borderRadius:4,
      }}/>
      <span style={{ fontSize:10, opacity:0.8 }}>+30%</span>
    </div>
    <div style={{ display:'flex', gap:14, marginTop:2, fontSize:10, opacity:0.75 }}>
      <span>🔴 Baisse</span>
      <span>🟡 Stable</span>
      <span>🟢 Hausse</span>
    </div>
    <div style={{ marginTop:2, fontSize:10, opacity:0.6 }}>
      ∗ = estimation régionale &nbsp;|&nbsp; taille ∝ amplitude
    </div>
  </div>
);

// ── Main component ────────────────────────────────────────────────────────────
const MarketTrendMap = () => {
  const [typeBien,    setTypeBien]    = useState('appartement');
  const [transaction, setTransaction] = useState('vente');
  const [trends,      setTrends]      = useState({});
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchTrends = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/predict/forecast/map/?type_bien=${typeBien}&transaction=${transaction}`
      );
      if (!res.ok) throw new Error(`Erreur serveur ${res.status}`);
      const data = await res.json();
      const map = {};
      (data.results || []).forEach(r => { map[r.gouvernorat] = r; });
      setTrends(map);
      setLastUpdated(new Date().toLocaleTimeString('fr-FR', { hour:'2-digit', minute:'2-digit' }));
    } catch (err) {
      console.error(err);
      setError('Impossible de charger les tendances. Vérifiez que le serveur est actif.');
    } finally {
      setLoading(false);
    }
  }, [typeBien, transaction]);

  useEffect(() => { fetchTrends(); }, [fetchTrends]);

  // Guard: if current transaction is not valid for the type, reset to 'vente'
  useEffect(() => {
    const valid = VALID_COMBINATIONS[typeBien] || ['vente'];
    if (!valid.includes(transaction)) setTransaction('vente');
  }, [typeBien, transaction]);

  const validTransactions = VALID_COMBINATIONS[typeBien] || ['vente'];

  return (
    <div style={{ height:'100%', position:'relative', fontFamily:'system-ui,sans-serif' }}>

      {/* ── Floating glass control panel ───────────────────────────────────── */}
      <div style={{
        position:'absolute', top:14, right:14, zIndex:1000,
        background:'rgba(255,255,255,0.92)', backdropFilter:'blur(12px)',
        borderRadius:16, padding:'12px 18px',
        boxShadow:'0 8px 24px rgba(0,0,0,0.18)',
        border:'1px solid rgba(200,210,230,0.6)',
        display:'flex', gap:14, alignItems:'center', flexWrap:'wrap',
        fontSize:13, fontWeight:500,
        maxWidth:'calc(100% - 28px)',
      }}>
        {/* Type */}
        <div style={{ display:'flex', flexDirection:'column', gap:3 }}>
          <label style={{ fontSize:10, fontWeight:700, textTransform:'uppercase', color:'#64748b', letterSpacing:'0.5px' }}>
            Type de bien
          </label>
          <select
            value={typeBien}
            onChange={e => setTypeBien(e.target.value)}
            style={{ padding:'6px 12px', borderRadius:8, border:'1px solid #cbd5e1', background:'white', fontSize:13, cursor:'pointer' }}
          >
            <option value="appartement">Appartement</option>
            <option value="maison">Maison / Villa</option>
            <option value="terrain">Terrain</option>
            <option value="local">Local commercial</option>
          </select>
        </div>

        {/* Transaction */}
        <div style={{ display:'flex', flexDirection:'column', gap:3 }}>
          <label style={{ fontSize:10, fontWeight:700, textTransform:'uppercase', color:'#64748b', letterSpacing:'0.5px' }}>
            Transaction
          </label>
          <select
            value={transaction}
            onChange={e => setTransaction(e.target.value)}
            style={{ padding:'6px 12px', borderRadius:8, border:'1px solid #cbd5e1', background:'white', fontSize:13, cursor:'pointer' }}
          >
            {validTransactions.map(t => (
              <option key={t} value={t}>{t === 'vente' ? 'Vente' : 'Location'}</option>
            ))}
          </select>
        </div>

        {/* Refresh button */}
        <div style={{ display:'flex', flexDirection:'column', gap:3, paddingTop:16 }}>
          <button
            onClick={fetchTrends}
            disabled={loading}
            title="Actualiser les données"
            style={{
              background: loading ? '#94a3b8' : '#3b82f6',
              border:'none', borderRadius:8,
              width:36, height:36,
              display:'flex', alignItems:'center', justifyContent:'center',
              cursor: loading ? 'default' : 'pointer',
              color:'white', fontSize:18,
              transition:'background 0.2s, transform 0.2s',
              boxShadow: loading ? 'none' : '0 2px 8px rgba(59,130,246,0.4)',
            }}
            onMouseEnter={e => { if (!loading) e.currentTarget.style.background = '#2563eb'; }}
            onMouseLeave={e => { if (!loading) e.currentTarget.style.background = '#3b82f6'; }}
          >
            <span style={{ display:'inline-block', animation: loading ? 'spin 1s linear infinite' : 'none' }}>
              ↻
            </span>
          </button>
        </div>

        {/* Timestamp */}
        {lastUpdated && (
          <div style={{ fontSize:10, color:'#94a3b8', alignSelf:'flex-end', paddingBottom:2 }}>
            Mis à jour {lastUpdated}
          </div>
        )}
      </div>

      {/* ── Loading overlay ────────────────────────────────────────────────── */}
      {loading && (
        <div style={{
          position:'absolute', top:'50%', left:'50%',
          transform:'translate(-50%,-50%)',
          background:'rgba(15,23,42,0.8)', backdropFilter:'blur(8px)',
          color:'white', padding:'12px 24px', borderRadius:12, zIndex:2000,
          fontSize:14, fontWeight:600, letterSpacing:'0.3px',
          boxShadow:'0 4px 20px rgba(0,0,0,0.4)',
        }}>
          ⏳ Chargement des tendances…
        </div>
      )}

      {/* ── Error banner ───────────────────────────────────────────────────── */}
      {error && (
        <div style={{
          position:'absolute', bottom:80, left:'50%', transform:'translateX(-50%)',
          background:'#ef4444', color:'white',
          padding:'8px 20px', borderRadius:8, zIndex:2000,
          fontSize:12, fontWeight:600, boxShadow:'0 4px 12px rgba(0,0,0,0.3)',
          maxWidth:'80%', textAlign:'center',
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* ── Gradient legend ────────────────────────────────────────────────── */}
      <GradientLegend />

      {/* ── Map ────────────────────────────────────────────────────────────── */}
      <MapContainer
        center={[34.1, 9.6]}
        zoom={6}
        style={{ height:'100%', width:'100%' }}
        zoomControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />

        {Object.entries(GOVERNORATE_COORDS).map(([gov, coords]) => {
          const data = trends[gov];
          if (!data) return null;

          const { trend_pct, current_price_m2, future_price_m2, estimated } = data;
          const icon    = buildIcon(trend_pct, estimated);
          const pctStr  = trend_pct > 0 ? `+${trend_pct}%` : `${trend_pct}%`;
          const trendColor = trend_pct > 3 ? '#16a34a' : trend_pct < -3 ? '#dc2626' : '#ca8a04';
          const label   = trend_pct > 3 ? '📈 Hausse' : trend_pct < -3 ? '📉 Baisse' : '➡️ Stable';

          return (
            <Marker key={gov} position={coords} icon={icon}>
              {/* ── Hover tooltip ── */}
              <Tooltip
                sticky
                direction="top"
                offset={[0, -(getRadius(trend_pct) + 4)]}
                opacity={1}
              >
                <div style={{ minWidth:160, fontFamily:'system-ui,sans-serif' }}>
                  <div style={{ fontWeight:800, fontSize:13, marginBottom:4, color:'#1e293b' }}>
                    {gov} {estimated && <span style={{ fontSize:10, color:'#64748b' }}>(estimé)</span>}
                  </div>
                  <div style={{ color:trendColor, fontWeight:700, fontSize:13, marginBottom:4 }}>
                    {label} {pctStr}
                  </div>
                  <div style={{ fontSize:11, color:'#475569', lineHeight:1.7 }}>
                    <div>📍 Actuel&nbsp;: <strong>{fmtPrice(current_price_m2)}/m²</strong></div>
                    <div>🔮 Prévu (12m)&nbsp;: <strong>{fmtPrice(future_price_m2)}/m²</strong></div>
                    {estimated && (
                      <div style={{ marginTop:4, color:'#94a3b8', fontSize:10, fontStyle:'italic' }}>
                        ∗ Estimation par moyenne régionale
                      </div>
                    )}
                  </div>
                </div>
              </Tooltip>

              {/* ── Click popup ── */}
              <Popup minWidth={200}>
                <div style={{ fontFamily:'system-ui,sans-serif', padding:'2px 0' }}>
                  <div style={{ fontWeight:900, fontSize:15, color:'#1e293b', marginBottom:6 }}>
                    {gov}
                    {estimated && (
                      <span style={{ marginLeft:6, fontSize:10, background:'#f1f5f9', color:'#64748b', padding:'2px 6px', borderRadius:4, fontWeight:600 }}>
                        estimé
                      </span>
                    )}
                  </div>
                  <div style={{ color:trendColor, fontWeight:800, fontSize:16, marginBottom:8 }}>
                    {pctStr} &nbsp;{label}
                  </div>
                  <hr style={{ margin:'0 0 8px', border:'none', borderTop:'1px solid #e2e8f0' }}/>
                  <table style={{ width:'100%', fontSize:12, borderCollapse:'collapse' }}>
                    <tbody>
                      <tr>
                        <td style={{ color:'#64748b', paddingBottom:3 }}>Prix actuel</td>
                        <td style={{ fontWeight:700, textAlign:'right' }}>{fmtPrice(current_price_m2)}/m²</td>
                      </tr>
                      <tr>
                        <td style={{ color:'#64748b' }}>Prévu dans 12 mois</td>
                        <td style={{ fontWeight:700, textAlign:'right', color:trendColor }}>{fmtPrice(future_price_m2)}/m²</td>
                      </tr>
                    </tbody>
                  </table>
                  {estimated && (
                    <div style={{ marginTop:8, fontSize:10, color:'#94a3b8', fontStyle:'italic' }}>
                      ∗ Donnée estimée par moyenne régionale faute de données directes.
                    </div>
                  )}
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>

      <style>{`
        .kadastra-trend-marker { background: transparent !important; border: none !important; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};

export default MarketTrendMap;
