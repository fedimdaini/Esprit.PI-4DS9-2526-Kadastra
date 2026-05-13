/**
 * KadastraAgent.jsx — v4
 * ─────────────────────────────────────────────────────────────────────────────
 * Two distinct modes:
 *
 *   NORMAL MODE  — for renters, students, first-time buyers
 *     • Calls /api/analyze/normal → friendly verdict, LLM narrative
 *     • Focus: price fairness, location quality, comfort, security
 *     • NO IRR / Monte Carlo / yield jargon
 *     • Auto-suggested when "louer" listing is attached
 *
 *   EXPERT MODE  — for investors
 *     • Calls /api/analyze → full financial metrics, IRR sweep, Monte Carlo
 *     • Improved scoring distribution (70/46/27 thresholds)
 *     • LightGBM price cross-reference bonus/penalty
 *
 * LLM: Esprit LLaMA-3.1-70B (via /api/analyze/normal + /api/chat)
 * Market trend: /api/predict/forecast/map/ (Django backend)
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import ListingModal from './ListingModal';
import { useLanguage } from '../i18n/LanguageContext';

const API_BASE     = process.env.REACT_APP_KADASTRA_API || 'http://localhost:8001';
const DJANGO_API   = '';   // empty = use CRA proxy

// ─── Constants ────────────────────────────────────────────────────────────────
const PROPERTY_TYPES = [
  'Appartement a vendre','Appartement a louer',
  'Maison a vendre','Maison a louer',
  'Villa a vendre','Villa a louer',
  'Studio a vendre','Studio a louer',
  'Bureau a vendre','Bureau a louer',
  'Local commercial a vendre','Local commercial a louer',
  'Terrain a vendre',
];
const BLANK_PROPERTY = {
  Type:'Appartement a vendre', Adresse:'', price_numeric:'', surface_numeric:'',
  pieces:'', chambres:'', sallesdebain:'',
  neuf:false, parking:false, ascenseur:false, meuble:false,
  balcon_terrasse:false, climatisation:false, chauffage:false, jardin:false, piscine:false,
};
const BLANK_PROFILE = {
  budget:'', holding_period_years:7,
  first_time_buyer:true, is_new_promoter:false, risk_tolerance:'medium',
};

// Keyword detection helpers
const EXPLAIN_KWS = ['pourquoi','expliquez','expliquer','explique','comment','que signifie',
  'que veut dire','clarif','détaille','why','explain','plus d\'info','développe'];
const CHAT_KWS    = ['meilleur','meilleures','bon plan','bons plans','deal','affaire','opportunit',
  'moins cher','pas cher','annonce','cherche','trouve','liste','marché','market',
  'statistique','prix moyen','tendance','portfolio','portefeuille','diversif','conseil'];
const GUIDE_KWS   = ['guide','aide','help','form','comment','quoi','how','remplir','expliqu','walk'];

function isExplainRequest(t){ return EXPLAIN_KWS.some(w=>t.toLowerCase().includes(w)); }
function isChatIntent(t)    { return CHAT_KWS.some(w=>t.toLowerCase().includes(w)); }
function isGuideRequest(t)  { return GUIDE_KWS.some(w=>t.toLowerCase().includes(w)); }

// ─── Data helpers ─────────────────────────────────────────────────────────────
function listingToProperty(l) {
  const rawType   = l.type_bien || l.Type || l.type || '';
  const titleLow  = String(l.titre||l.title||'').toLowerCase();
  const isRental  = /louer|location|locatif/.test(rawType.toLowerCase())
                 || /\bà louer\b|à l'année|location/.test(titleLow);
  let canonicalType = rawType || (isRental ? 'Appartement a louer' : 'Appartement a vendre');
  if (isRental && /vendre/.test(canonicalType.toLowerCase()))
    canonicalType = canonicalType.replace(/a vendre/i, 'a louer');

  return {
    Type: canonicalType, Adresse: l.adresse||l.Adresse||l.localisation||'Tunis',
    price_numeric:   l.price_numeric || parseFloat(String(l.prix||'').replace(/[^\d.]/g,'')) || 0,
    surface_numeric: l.surface_numeric || parseFloat(l.surface) || 0,
    pieces:    parseFloat(l.pieces)||0,    chambres:  parseFloat(l.chambres)||0,
    sallesdebain: parseFloat(l.salles_de_bain||l.sallesdebain)||0,
    neuf:l.neuf?1:0, parking:l.parking?1:0, ascenseur:l.ascenseur?1:0,
    meuble:l.meuble?1:0, balcon_terrasse:l.balcon_terrasse?1:0,
    climatisation:l.climatisation?1:0, chauffage:l.chauffage?1:0,
    jardin:l.jardin?1:0, piscine:l.piscine?1:0,
    // LightGBM cross-reference
    market_price_estimate:  l.price_analysis?.predicted_price||null,
    market_price_label:     l.price_analysis?.label||null,
    market_price_delta_pct: l.price_analysis?.delta_pct||null,
  };
}

function dealToListing(d) {
  return {
    titre:d.titre||'', prix:d.prix?`${Number(d.prix).toLocaleString('fr-TN')} TND`:'Prix à consulter',
    price_numeric:d.prix||0, adresse:d.adresse||'', localisation:d.adresse||'',
    description:d.description||'', surface:d.surface>0?String(d.surface):'N/A',
    surface_numeric:d.surface||0, chambres:d.chambres>0?String(d.chambres):'N/A',
    salles_de_bain:null, type:d.type||'', type_bien:d.type||'',
    source:d.source||'kadastra', lien:d.lien||d.url||'#', first_image:d.first_image||null,
  };
}

function propertyFormToPayload(f) {
  return {
    Type:f.Type, Adresse:f.Adresse||'Tunis',
    price_numeric:parseFloat(f.price_numeric)||0, surface_numeric:parseFloat(f.surface_numeric)||0,
    pieces:parseFloat(f.pieces)||0, chambres:parseFloat(f.chambres)||0,
    sallesdebain:parseFloat(f.sallesdebain)||0,
    neuf:f.neuf?1:0, parking:f.parking?1:0, ascenseur:f.ascenseur?1:0, meuble:f.meuble?1:0,
    balcon_terrasse:f.balcon_terrasse?1:0, climatisation:f.climatisation?1:0,
    chauffage:f.chauffage?1:0, jardin:f.jardin?1:0, piscine:f.piscine?1:0,
  };
}
function profileFormToPayload(f) {
  return {
    budget:parseFloat(f.budget)||300000, holding_period_years:parseInt(f.holding_period_years)||7,
    rental_income:0, first_time_buyer:f.first_time_buyer,
    is_new_promoter:f.is_new_promoter, risk_tolerance:f.risk_tolerance,
  };
}
function transformFullScenario(data) {
  const s=data.scenario; const mc=s.simulator.mc_primary||s.simulator.mc_rental;
  return {
    verdict:s.verdict.recommendation, score:s.verdict.score,
    primary_scenario:s.simulator.primary_scenario||'locatif',
    financials:{
      gross_yield:s.simulator.rental_yield.gross_yield,
      net_yield:s.simulator.rental_yield.net_yield,
      irr_percent:s.simulator.roi_rental.irr_percent,
      monthly_rent_estimate:s.simulator.rental_yield.estimated_monthly_rent,
      npv_p5:mc.npv_p5, npv_p50:mc.npv_p50, npv_p95:mc.npv_p95,
      prob_positive_npv:mc.prob_positive,
      initial_investment:s.simulator.roi_rental.initial_investment,
      monthly_mortgage:s.simulator.roi_rental.monthly_mortgage,
    },
    risk:{level:s.risk.risk_level, score:s.risk.overall_risk_score,
          flags:s.risk.risk_flags, components:s.risk.component_scores, mitigation:s.risk.mitigation},
    tax:{acquisition_fees_pct:s.tax.acquisition_costs.fees_pct,
         acquisition_fees_tnd:s.tax.acquisition_costs.total_fees,
         optimal_holding_years:s.tax.optimal_holding_years,
         cgt_note:s.tax.cgt_cliff_note, annual_taxes:s.tax.annual_tax_burden},
    insights:s.verdict.key_insights, explanations:s.explanations,
    holding_sweep:s.tax.holding_period_sweep, warnings:data.warnings||[],
    elapsed_seconds:data.elapsed_seconds,
  };
}

// ─── Market trend fetcher ─────────────────────────────────────────────────────
const TYPE_TO_MAP = {
  'Appartement a vendre':'appartement','Appartement a louer':'appartement',
  'Maison a vendre':'maison','Maison a louer':'maison',
  'Villa a vendre':'maison','Villa a louer':'maison',
  'Terrain a vendre':'terrain',
  'Local commercial a vendre':'local','Local commercial a louer':'local',
  'Bureau a vendre':'local','Bureau a louer':'local',
  'Studio a vendre':'appartement','Studio a louer':'appartement',
};
const GOV_CITY_MAP = {
  tunis:'Tunis',lac:'Tunis',menzah:'Tunis',ennasr:'Tunis',ariana:'Ariana',
  'ben arous':'Ben Arous',manouba:'Manouba',sousse:'Sousse',sfax:'Sfax',
  nabeul:'Nabeul',hammamet:'Nabeul',bizerte:'Bizerte',monastir:'Monastir',
  mahdia:'Mahdia',gabes:'Gabes',mednine:'Mednine',kairouan:'Kairouan',
  zaghouan:'Zaghouan',beja:'Beja',jendouba:'Jendouba',kef:'Kef',
  gafsa:'Gafsa',tozeur:'Tozeur',kebili:'Kebili',kasserine:'Kasserine',
  'sidi bouzid':'Sidi Bouzid',tataouine:'Tataouine',
};
async function fetchMarketTrend(propType, adresse) {
  try {
    const typeBien   = TYPE_TO_MAP[propType] || 'appartement';
    const trans      = /louer/.test(propType||'') ? 'location' : 'vente';
    const validCombo = {appartement:['vente','location'],maison:['vente','location'],
                        terrain:['vente'],local:['vente']};
    if (!(validCombo[typeBien]||[]).includes(trans)) return null;

    const addrLow = (adresse||'').toLowerCase();
    let gov = null;
    for (const [city, g] of Object.entries(GOV_CITY_MAP)) {
      if (addrLow.includes(city)) { gov = g; break; }
    }
    if (!gov) return null;

    const res = await fetch(`${DJANGO_API}/api/predict/forecast/map/?type_bien=${typeBien}&transaction=${trans}`);
    if (!res.ok) return null;
    const data = await res.json();
    return (data.results||[]).find(r => r.gouvernorat === gov) || null;
  } catch { return null; }
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const S = {
  bubble:{ position:'fixed', bottom:24, right:24, width:60, height:60, borderRadius:'50%',
    background:'linear-gradient(135deg,#3B82F6,#1D4ED8)', display:'flex',
    alignItems:'center', justifyContent:'center', cursor:'pointer',
    boxShadow:'0 4px 20px rgba(59,130,246,0.4)', zIndex:9999, border:'none',
    color:'white', fontSize:26, transition:'transform 0.2s' },
  panel:{ position:'fixed', bottom:96, right:24, width:490, maxHeight:'82vh',
    borderRadius:16, background:'#0F172A', border:'1px solid #1E293B',
    boxShadow:'0 8px 40px rgba(0,0,0,0.6)', zIndex:9998, display:'flex',
    flexDirection:'column', overflow:'hidden',
    fontFamily:'-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif' },
  header:{ padding:'12px 16px', background:'#1E293B', flexShrink:0,
    display:'flex', alignItems:'center', justifyContent:'space-between',
    borderBottom:'1px solid #0F172A' },
  messages:{ flex:1, overflowY:'auto', padding:'12px 14px', display:'flex',
    flexDirection:'column', gap:10 },
  msgBot:{ background:'#1E293B', borderRadius:'12px 12px 12px 4px',
    padding:'12px 14px', color:'#E2E8F0', fontSize:13, lineHeight:1.55, maxWidth:'96%' },
  msgUser:{ background:'#3B82F6', borderRadius:'12px 12px 4px 12px',
    padding:'10px 14px', color:'white', fontSize:13, lineHeight:1.55,
    alignSelf:'flex-end', maxWidth:'85%' },
  inputRow:{ padding:'10px 12px', borderTop:'1px solid #1E293B', flexShrink:0,
    display:'flex', gap:8, alignItems:'flex-end', position:'relative' },
  attachBtn:{ background:'#1E293B', border:'1px solid #334155', borderRadius:8,
    color:'#94A3B8', fontSize:22, width:38, height:38, flexShrink:0,
    cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center' },
  textarea:{ flex:1, background:'#1E293B', border:'1px solid #334155',
    borderRadius:8, padding:'9px 12px', color:'#E2E8F0', fontSize:13,
    outline:'none', resize:'none', lineHeight:1.4 },
  sendBtn:{ background:'#3B82F6', border:'none', borderRadius:8, padding:'0 16px',
    color:'white', fontSize:13, fontWeight:700, cursor:'pointer',
    height:38, flexShrink:0, whiteSpace:'nowrap' },
  attachMenu:{ position:'absolute', bottom:58, left:12, background:'#1E293B',
    border:'1px solid #334155', borderRadius:12, zIndex:10,
    boxShadow:'0 4px 20px rgba(0,0,0,0.4)', minWidth:240, overflow:'hidden' },
  menuItem:{ padding:'11px 14px', cursor:'pointer', color:'#E2E8F0', fontSize:13,
    display:'flex', alignItems:'flex-start', gap:10, borderBottom:'1px solid #0F172A',
    transition:'background 0.15s' },
  chip:{ display:'inline-flex', alignItems:'center', gap:6, background:'#1E3A5F',
    color:'#93C5FD', borderRadius:20, padding:'3px 10px', fontSize:11,
    fontWeight:600, marginRight:6, marginBottom:4 },
  chipRemove:{ background:'none', border:'none', color:'#93C5FD',
    cursor:'pointer', padding:0, fontSize:15, lineHeight:1 },
  formOverlay:{ position:'absolute', inset:0, background:'#0F172A', zIndex:20,
    display:'flex', flexDirection:'column', overflow:'hidden' },
  formHeader:{ padding:'14px 18px', background:'#1E293B', flexShrink:0,
    display:'flex', alignItems:'center', justifyContent:'space-between' },
  formBody:{ flex:1, overflowY:'auto', padding:16 },
  formFooter:{ padding:'12px 16px', borderTop:'1px solid #1E293B', flexShrink:0 },
  label: { color:'#94A3B8', fontSize:10, fontWeight:700, letterSpacing:'0.06em',
           marginBottom:4, display:'block' },
  input: { width:'100%', background:'#1E293B', border:'1px solid #334155',
           borderRadius:6, padding:'8px 10px', color:'#E2E8F0', fontSize:13,
           outline:'none', boxSizing:'border-box' },
  select:{ width:'100%', background:'#1E293B', border:'1px solid #334155',
           borderRadius:6, padding:'8px 10px', color:'#E2E8F0', fontSize:13,
           outline:'none', boxSizing:'border-box' },
  metricRow:{ display:'flex', justifyContent:'space-between', padding:'4px 0',
              borderBottom:'1px solid #1E293B', fontSize:12 },
  pill:{ background:'#0F172A', border:'1px solid #334155', borderRadius:8,
         padding:'8px 10px', textAlign:'center' },
  sweepBar:(irr,h)=>({ height:5, borderRadius:3, marginTop:2,
    background:irr>=h?'#059669':irr>0?'#3B82F6':'#DC2626',
    width:`${Math.min(Math.max((irr/20)*100,3),100)}%` }),
};

// ─── Micro-components ─────────────────────────────────────────────────────────
function Toggle({ value, onChange }) {
  return (
    <button onClick={()=>onChange(!value)} style={{
      width:36,height:20,borderRadius:10,border:'none',cursor:'pointer',
      background:value?'#3B82F6':'#334155',position:'relative',flexShrink:0,transition:'background 0.2s'}}>
      <div style={{position:'absolute',top:3,left:value?19:3,width:14,height:14,
        borderRadius:'50%',background:'white',transition:'left 0.2s'}}/>
    </button>
  );
}
function SectionTitle({ children }) {
  return <div style={{fontSize:10,color:'#64748B',fontWeight:700,
    letterSpacing:'0.08em',marginTop:12,marginBottom:6}}>{children}</div>;
}
function ToggleRow({ label, value, onChange }) {
  return (
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:10}}>
      <span style={{color:'#E2E8F0',fontSize:13}}>{label}</span>
      <Toggle value={value} onChange={onChange}/>
    </div>
  );
}
function MetricPill({ label, value, accent }) {
  return (
    <div style={S.pill}>
      <div style={{fontSize:10,color:'#64748B',fontWeight:600,marginBottom:3}}>{label}</div>
      <div style={{fontSize:14,fontWeight:700,color:accent||'#E2E8F0'}}>{value}</div>
    </div>
  );
}
function WarningBanner({ warnings }) {
  if (!warnings?.length) return null;
  return (
    <div style={{background:'#451A03',border:'1px solid #92400E',borderRadius:8,
      padding:'8px 12px',marginBottom:10,fontSize:12}}>
      <span style={{color:'#FCD34D',fontWeight:700}}>⚠️ Avertissement</span>
      {warnings.map((w,i)=><div key={i} style={{color:'#FDE68A',marginTop:4}}>• {w}</div>)}
    </div>
  );
}

// Score progress bar (used in Normal result)
function ScoreBar({ label, score, max, color, emoji }) {
  const pct = Math.round((score / max) * 100);
  return (
    <div style={{marginBottom:10}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:4}}>
        <span style={{fontSize:12,color:'#94A3B8'}}>{emoji} {label}</span>
        <span style={{fontSize:11,fontWeight:700,color}}>
          {score}<span style={{color:'#475569',fontWeight:400}}>/{max}</span>
        </span>
      </div>
      <div style={{height:6,background:'#0F172A',borderRadius:3}}>
        <div style={{height:'100%',borderRadius:3,width:`${pct}%`,background:color,transition:'width 0.5s'}}/>
      </div>
    </div>
  );
}

// Market trend badge
function TrendBadge({ trend }) {
  if (!trend) return null;
  const pct     = trend.trend_pct;
  const isUp    = pct > 3;
  const isDown  = pct < -3;
  const color   = isUp?'#16a34a':isDown?'#dc2626':'#ca8a04';
  const bg      = isUp?'#064e3b':isDown?'#450a0a':'#451a03';
  const arrow   = isUp?'📈':isDown?'📉':'➡️';
  return (
    <div style={{display:'inline-flex',alignItems:'center',gap:6,
      background:bg,border:`1px solid ${color}`,borderRadius:8,
      padding:'4px 10px',fontSize:11,fontWeight:700,color,marginTop:8}}>
      {arrow} Marché {trend.gouvernorat}: {pct>0?'+':''}{pct}% (12m)
      {trend.estimated && <span style={{opacity:0.7,fontWeight:400}}> ∗est.</span>}
    </div>
  );
}

// ─── Property form ─────────────────────────────────────────────────────────────
function PropertyForm({ form, setForm, onConfirm, onCancel }) {
  const { t } = useLanguage();
  const set = (k,v)=>setForm(f=>({...f,[k]:v}));
  const features = [
    ['neuf',            t('features.neuf')],
    ['parking',         t('features.parking')],
    ['ascenseur',       t('features.ascenseur')],
    ['meuble',          t('features.meuble')],
    ['balcon_terrasse', t('features.balcon_terrasse')],
    ['climatisation',   t('features.climatisation')],
    ['chauffage',       t('features.chauffage')],
    ['jardin',          t('features.jardin')],
    ['piscine',         t('features.piscine')],
  ];
  return (
    <div style={S.formOverlay}>
      <div style={S.formHeader}>
        <span style={{color:'#E2E8F0',fontWeight:700,fontSize:15}}>{t('chat.propFormTitle')}</span>
        <button onClick={onCancel} style={{background:'none',border:'none',color:'#94A3B8',cursor:'pointer',fontSize:18}}>✕</button>
      </div>
      <div style={S.formBody}>
        <label style={S.label}>{t('chat.propType')}</label>
        <select style={{...S.select,marginBottom:12}} value={form.Type} onChange={e=>set('Type',e.target.value)}>
          {PROPERTY_TYPES.map(tp=><option key={tp} value={tp}>{tp}</option>)}
        </select>
        <label style={S.label}>{t('chat.propLocation')}</label>
        <input style={{...S.input,marginBottom:12}} value={form.Adresse}
          onChange={e=>set('Adresse',e.target.value)} placeholder={t('chat.propLocationPh')}/>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:4}}>
          {[[t('chat.propPrice'),'price_numeric','250 000'],[t('chat.propArea'),'surface_numeric','120'],
            [t('chat.propRooms'),'pieces','4'],[t('chat.propBedrooms'),'chambres','3']].map(([lbl,k,ph])=>(
            <div key={k}>
              <label style={S.label}>{lbl}</label>
              <input style={S.input} type="number" value={form[k]}
                onChange={e=>set(k,e.target.value)} placeholder={ph}/>
            </div>
          ))}
        </div>
        <SectionTitle>{t('chat.propFeatures')}</SectionTitle>
        {features.map(([k,lbl])=>(
          <ToggleRow key={k} label={lbl} value={!!form[k]} onChange={v=>set(k,v)}/>
        ))}
      </div>
      <div style={S.formFooter}>
        <button style={{...S.sendBtn,width:'100%'}} onClick={onConfirm} disabled={!form.price_numeric}>
          {t('chat.attachProperty2')}
        </button>
      </div>
    </div>
  );
}

// ─── Investor profile form ─────────────────────────────────────────────────────
function ProfileForm({ form, setForm, onConfirm, onCancel }) {
  const { t } = useLanguage();
  const set=(k,v)=>setForm(f=>({...f,[k]:v}));
  return (
    <div style={S.formOverlay}>
      <div style={S.formHeader}>
        <span style={{color:'#E2E8F0',fontWeight:700,fontSize:15}}>{t('chat.profileTitle')}</span>
        <button onClick={onCancel} style={{background:'none',border:'none',color:'#94A3B8',cursor:'pointer',fontSize:18}}>✕</button>
      </div>
      <div style={S.formBody}>
        <label style={S.label}>{t('chat.budget')}</label>
        <input style={{...S.input,marginBottom:14}} type="number" value={form.budget}
          onChange={e=>set('budget',e.target.value)} placeholder="300 000"/>
        <label style={S.label}>{t('chat.holding')} — {form.holding_period_years} {t('chat.holdingYears')}</label>
        <input type="range" min={1} max={15} value={form.holding_period_years}
          onChange={e=>set('holding_period_years',parseInt(e.target.value))}
          style={{width:'100%',accentColor:'#3B82F6',marginBottom:4}}/>
        <div style={{display:'flex',justifyContent:'space-between',color:'#64748B',fontSize:10,marginBottom:14}}>
          <span>1 {t('chat.holdingYears')}</span><span>8 {t('chat.holdingYears')}</span><span>15 {t('chat.holdingYears')}</span>
        </div>
        <label style={S.label}>{t('chat.riskTolerance')}</label>
        <select style={{...S.select,marginBottom:14}} value={form.risk_tolerance}
          onChange={e=>set('risk_tolerance',e.target.value)}>
          <option value="low">{t('chat.riskLow')}</option>
          <option value="medium">{t('chat.riskMed')}</option>
          <option value="high">{t('chat.riskHigh')}</option>
        </select>
        <SectionTitle>{t('chat.situation')}</SectionTitle>
        <ToggleRow label={t('chat.firstBuyer')} value={form.first_time_buyer} onChange={v=>set('first_time_buyer',v)}/>
        <ToggleRow label={t('chat.newPromoter')} value={form.is_new_promoter} onChange={v=>set('is_new_promoter',v)}/>
      </div>
      <div style={S.formFooter}>
        <button style={{...S.sendBtn,width:'100%'}} onClick={onConfirm}>{t('chat.attachProfile2')}</button>
      </div>
    </div>
  );
}

// ─── NORMAL MODE result card (consumer-friendly, zero financial jargon) ────────
function NormalModeResultCard({ data }) {
  const { t } = useLanguage();
  const {
    recommendation_fr, recommendation_color,
    price_listed, price_estimated, price_unit,
    price_diff_pct, price_verdict, price_verdict_color, price_factors,
    neighborhood_name, neighborhood_type, neighborhood_services,
    neighborhood_safety, neighborhood_safety_desc,
    neighborhood_safety_color, neighborhood_safety_icon,
    amenities,
    narrative,
    warnings, market_trend, elapsed_seconds,
    is_rental,
  } = data;

  const diffAbs  = Math.abs(price_diff_pct || 0);
  const diffSign = (price_diff_pct || 0) < 0 ? '-' : '+';
  const hasPriceComp = price_estimated != null;

  return (
    <div style={S.msgBot}>
      <WarningBanner warnings={warnings}/>

      {/* ── Recommendation badge ── */}
      <div style={{
        background: recommendation_color || '#059669',
        color:'white', borderRadius:12, padding:'12px 16px',
        fontWeight:900, fontSize:16, marginBottom:14,
        textAlign:'center', letterSpacing:'0.2px',
        boxShadow:`0 4px 20px ${recommendation_color||'#059669'}44`,
      }}>
        {recommendation_fr}
      </div>

      {/* ── LLM narrative — the main explanation ── */}
      {narrative && (
        <div style={{marginBottom:14}}>
          {narrative.split('\n').filter(l=>l.trim()).map((line,i)=>(
            <p key={i} style={{color:'#CBD5E1',fontSize:13,lineHeight:1.8,margin:'0 0 8px'}}>
              {line}
            </p>
          ))}
        </div>
      )}

      {/* ── Price comparison box ── */}
      <div style={{background:'#0F172A',borderRadius:12,padding:'14px',marginBottom:12,
        border:`1px solid ${hasPriceComp ? price_verdict_color+'44' : '#1E293B'}`}}>
        <div style={{fontSize:10,color:'#64748B',fontWeight:700,letterSpacing:'0.07em',marginBottom:10}}>
          {t('chat.priceComparison')}
        </div>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:10}}>
          <div style={{background:'#1E293B',borderRadius:8,padding:'10px 12px',textAlign:'center'}}>
            <div style={{fontSize:10,color:'#64748B',marginBottom:4}}>{t('chat.listedPrice')}</div>
            <div style={{fontSize:16,fontWeight:800,color:'#E2E8F0'}}>
              {(price_listed||0).toLocaleString('fr-TN')}
            </div>
            <div style={{fontSize:10,color:'#64748B'}}>{price_unit}</div>
          </div>
          <div style={{background:'#1E293B',borderRadius:8,padding:'10px 12px',textAlign:'center',
            border: hasPriceComp ? `1px solid ${price_verdict_color}44` : '1px solid #1E293B'}}>
            <div style={{fontSize:10,color:'#64748B',marginBottom:4}}>{t('chat.ourEstimate')}</div>
            {hasPriceComp ? (<>
              <div style={{fontSize:16,fontWeight:800,color:'#E2E8F0'}}>
                ~{(price_estimated||0).toLocaleString('fr-TN')}
              </div>
              <div style={{fontSize:10,color:'#64748B'}}>{price_unit}</div>
            </>) : (
              <div style={{fontSize:12,color:'#64748B',fontStyle:'italic'}}>{t('chat.notAvailable')}</div>
            )}
          </div>
        </div>
        {/* Verdict + diff */}
        {hasPriceComp && (
          <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',
            background:'#1E293B',borderRadius:8,padding:'8px 12px'}}>
            <span style={{color:price_verdict_color,fontWeight:700,fontSize:13}}>
              {price_verdict}
            </span>
            <span style={{color: (price_diff_pct||0)<0?'#4ade80':'#f87171',
              fontWeight:700, fontSize:13}}>
              {diffSign}{diffAbs.toFixed(1)}% {t('chat.vsMarket')}
            </span>
          </div>
        )}
      </div>

      {/* ── Why this price ── */}
      {(price_factors||[]).length > 0 && (
        <div style={{marginBottom:12}}>
          <div style={{fontSize:10,color:'#64748B',fontWeight:700,letterSpacing:'0.07em',marginBottom:8}}>
            {t('chat.whyEstimate')}
          </div>
          {price_factors.map((f,i)=>(
            <div key={i} style={{color:'#94A3B8',fontSize:12,lineHeight:1.8,paddingLeft:4}}>
              {f}
            </div>
          ))}
        </div>
      )}

      {/* ── Neighbourhood & safety ── */}
      <div style={{background:'#0F172A',borderRadius:12,padding:'12px 14px',marginBottom:12}}>
        <div style={{fontSize:10,color:'#64748B',fontWeight:700,letterSpacing:'0.07em',marginBottom:8}}>
          {t('chat.neighborhood')} — {neighborhood_name} ({neighborhood_type})
        </div>
        {/* Safety pill */}
        <div style={{display:'inline-flex',alignItems:'center',gap:6,
          background:`${neighborhood_safety_color}22`,
          border:`1px solid ${neighborhood_safety_color}66`,
          borderRadius:20,padding:'4px 12px',marginBottom:10,fontSize:12,
          color:neighborhood_safety_color,fontWeight:700}}>
          {neighborhood_safety_icon} {neighborhood_safety}
        </div>
        {neighborhood_safety_desc && (
          <div style={{fontSize:11,color:'#64748B',marginBottom:8,lineHeight:1.6}}>
            {neighborhood_safety_desc}
          </div>
        )}
        {/* Services list */}
        {(neighborhood_services||[]).map((s,i)=>(
          <div key={i} style={{color:'#94A3B8',fontSize:12,lineHeight:1.9}}>{s}</div>
        ))}
      </div>

      {/* ── Amenities ── */}
      {(amenities||[]).length > 0 && (
        <div style={{marginBottom:12}}>
          <div style={{fontSize:10,color:'#64748B',fontWeight:700,letterSpacing:'0.07em',marginBottom:8}}>
            {t('chat.amenitiesTitle')}
          </div>
          <div style={{display:'flex',flexWrap:'wrap',gap:6}}>
            {amenities.map((a,i)=>(
              <span key={i} style={{background:'#1E293B',color:'#93C5FD',fontSize:12,
                padding:'4px 10px',borderRadius:20,border:'1px solid #1E3A5F',fontWeight:500}}>
                {a}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Market trend badge ── */}
      {market_trend && <TrendBadge trend={market_trend}/>}

      {/* ── Footer ── */}
      <div style={{fontSize:10,color:'#334155',borderTop:'1px solid #1E293B',
        paddingTop:8,marginTop:10,display:'flex',justifyContent:'space-between'}}>
        <span>{t('chat.footerLabel')}</span>
        {elapsed_seconds!=null && <span>{elapsed_seconds}s</span>}
      </div>
    </div>
  );
}

// ─── EXPERT result card ────────────────────────────────────────────────────────
const EXPERT_VERDICT_STYLE = {
  'STRONG BUY':{ bg:'#059669', label:'STRONG BUY' },
  'CONSIDER':  { bg:'#D97706', label:'À CONSIDÉRER' },
  'CAUTIOUS':  { bg:'#EA580C', label:'PRUDENCE' },
  'AVOID':     { bg:'#DC2626', label:'À ÉVITER' },
};
const RISK_LABELS_FR = {
  location_risk:'Risque localisation',condition_risk:'État du bien',
  liquidity_risk:'Liquidité',price_risk:'Risque de prix',
  economic_risk:'Risque économique',regulatory_risk:'Risque réglementaire',
};

// Score component bar for expert mode header
function ExpertScoreMiniBar({ label, score, max, color }) {
  return (
    <div style={{flex:1,textAlign:'center'}}>
      <div style={{fontSize:9,color:'#64748B',marginBottom:2}}>{label}</div>
      <div style={{height:3,background:'#0F172A',borderRadius:2,margin:'0 2px'}}>
        <div style={{height:'100%',borderRadius:2,width:`${(score/max)*100}%`,background:color}}/>
      </div>
      <div style={{fontSize:9,color:'#94A3B8',marginTop:1}}>{score}/{max}</div>
    </div>
  );
}

function ExpertResultCard({ data }) {
  const hurdle=7.49;
  const {verdict,score,financials:f,risk,tax,insights,holding_sweep,explanations,warnings,
         primary_scenario,market_trend} = data;
  const vs = EXPERT_VERDICT_STYLE[verdict] || EXPERT_VERDICT_STYLE.CAUTIOUS;
  const scenarioLabel = primary_scenario==='revente'?'Revente':'Locatif';

  return (
    <div style={S.msgBot}>
      <WarningBanner warnings={warnings}/>

      {/* Verdict badge with score breakdown bars */}
      <div style={{background:vs.bg,borderRadius:10,padding:'10px 14px',marginBottom:12}}>
        <div style={{color:'white',fontWeight:900,fontSize:15,marginBottom:8}}>
          {vs.label} — {score}/100
        </div>
        <div style={{display:'flex',gap:4}}>
          <ExpertScoreMiniBar label="Rendement" score={Math.round(score*0.25)} max={25} color="#93c5fd"/>
          <ExpertScoreMiniBar label="Risque"    score={Math.round(score*0.25)} max={25} color="#6ee7b7"/>
          <ExpertScoreMiniBar label="IRR"       score={Math.round(score*0.30)} max={30} color="#fcd34d"/>
          <ExpertScoreMiniBar label="MC"        score={Math.round(score*0.20)} max={20} color="#c4b5fd"/>
        </div>
      </div>

      <SectionTitle>📈 RENDEMENT & FINANCEMENT</SectionTitle>
      {[
        ['Rendement locatif brut',    `${(f?.gross_yield||0).toFixed(2)}%`],
        ['Rendement locatif net',     `${(f?.net_yield||0).toFixed(2)}%`],
        ['Taux de rentabilité (IRR)', `${(f?.irr_percent||0).toFixed(2)}%`,
          (f?.irr_percent||0)>hurdle?'#4ADE80':'#F87171'],
        ['Loyer mensuel estimé',      `${(f?.monthly_rent_estimate||0).toLocaleString('fr-TN')} TND`],
        ['Apport initial (+ frais)',   `${(f?.initial_investment||0).toLocaleString('fr-TN')} TND`],
        ['Mensualité crédit',         `${(f?.monthly_mortgage||0).toLocaleString('fr-TN')} TND`],
      ].map(([k,v,c])=>(
        <div key={k} style={S.metricRow}>
          <span style={{color:'#94A3B8'}}>{k}</span>
          <span style={{color:c||'#E2E8F0',fontWeight:600}}>{v}</span>
        </div>
      ))}

      <SectionTitle>🎯 PROJECTIONS ({scenarioLabel})</SectionTitle>
      {[
        ['Scénario pessimiste',    `${(f?.npv_p5 ||0).toLocaleString('fr-TN')} TND`],
        ['Scénario médian',        `${(f?.npv_p50||0).toLocaleString('fr-TN')} TND`],
        ['Scénario optimiste',     `${(f?.npv_p95||0).toLocaleString('fr-TN')} TND`],
        ['Probabilité de gain net',`${(((f?.prob_positive_npv)||0)*100).toFixed(0)}%`,
          (f?.prob_positive_npv||0)>0.6?'#4ADE80':(f?.prob_positive_npv||0)>0.4?'#FBBF24':'#F87171'],
      ].map(([k,v,c])=>(
        <div key={k} style={S.metricRow}>
          <span style={{color:'#94A3B8'}}>{k}</span>
          <span style={{color:c||'#E2E8F0',fontWeight:600}}>{v}</span>
        </div>
      ))}

      <SectionTitle>⚠️ PROFIL DE RISQUE — {risk?.level} ({((risk?.score||0)*100).toFixed(0)}/100)</SectionTitle>
      {risk?.components && Object.entries(risk.components).map(([k,v])=>(
        <div key={k} style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:5}}>
          <span style={{color:'#94A3B8',fontSize:11}}>{RISK_LABELS_FR[k]||k.replace(/_/g,' ')}</span>
          <div style={{display:'flex',alignItems:'center',gap:6}}>
            <div style={{width:72,height:4,borderRadius:2,background:'#0F172A'}}>
              <div style={{width:`${v*100}%`,height:'100%',borderRadius:2,
                background:v<0.3?'#4ADE80':v<0.6?'#FBBF24':'#F87171'}}/>
            </div>
            <span style={{color:'#E2E8F0',fontSize:11,width:28,textAlign:'right'}}>
              {(v*100).toFixed(0)}%
            </span>
          </div>
        </div>
      ))}
      {(risk?.flags||[]).length>0 && (
        <div style={{marginTop:4}}>
          {risk.flags.map((fl,i)=>(
            <span key={i} style={{display:'inline-block',background:'#7F1D1D',color:'#FCA5A5',
              padding:'2px 7px',borderRadius:4,fontSize:11,margin:'2px 3px 2px 0'}}>{fl}</span>
          ))}
        </div>
      )}

      <SectionTitle>🏛️ FISCALITÉ</SectionTitle>
      {[
        ['Frais d\'acquisition', `${(tax?.acquisition_fees_pct||0).toFixed(2)}% — ${(tax?.acquisition_fees_tnd||0).toLocaleString('fr-TN')} TND`],
        ['Durée optimale',       `${tax?.optimal_holding_years} ans`],
        ['TIB annuelle',         `${(tax?.annual_taxes?.tib||0).toLocaleString('fr-TN')} TND`],
      ].map(([k,v])=>(
        <div key={k} style={S.metricRow}>
          <span style={{color:'#94A3B8'}}>{k}</span>
          <span style={{color:'#E2E8F0',fontWeight:600,fontSize:11}}>{v}</span>
        </div>
      ))}
      {tax?.cgt_note && <div style={{fontSize:11,color:'#64748B',marginTop:4}}>{tax.cgt_note}</div>}

      <SectionTitle>💡 POINTS CLÉS</SectionTitle>
      {(insights||[]).map((ins,i)=>(
        <span key={i} style={{display:'inline-block',background:'#1E3A5F',color:'#93C5FD',
          padding:'2px 8px',borderRadius:4,fontSize:11,margin:'2px 3px 2px 0'}}>{ins}</span>
      ))}

      {(holding_sweep||[]).length>0 && <>
        <SectionTitle>📊 RENTABILITÉ PAR DURÉE ({hurdle}% = seuil BCT)</SectionTitle>
        {holding_sweep.map(r=>(
          <div key={r.years} style={{display:'flex',alignItems:'center',gap:6,marginBottom:4}}>
            <span style={{width:30,fontSize:10,color:'#94A3B8',textAlign:'right'}}>{r.years}yr</span>
            <div style={{flex:1}}><div style={S.sweepBar(r.irr_pct,hurdle)}/></div>
            <span style={{width:44,fontSize:10,
              color:r.irr_pct>=hurdle?'#4ADE80':'#94A3B8',textAlign:'right',fontWeight:600}}>
              {r.irr_pct?.toFixed(1)}%
            </span>
          </div>
        ))}
      </>}

      {/* Market trend */}
      {market_trend && <TrendBadge trend={market_trend}/>}

      <div style={{marginTop:10,fontSize:10,color:'#475569',borderTop:'1px solid #1E293B',paddingTop:6}}>
        Sources: GlobalPropertyGuide Q2-2025 · BCT · Code IRPP-IS 2024 · LF2025
        {data.elapsed_seconds!=null && ` · ${data.elapsed_seconds}s`}
      </div>
    </div>
  );
}

// ─── Comparative bar chart for deals ─────────────────────────────────────────
function CompareDealsChart({ deals }) {
  if (!deals||deals.length===0) return null;
  const colors=['#3B82F6','#10B981','#F59E0B','#EF4444','#8B5CF6','#EC4899'];
  const maxPrix=Math.max(...deals.map(d=>d.prix||0),1);
  const maxPm2=Math.max(...deals.map(d=>d.prix_m2||0),1);
  const maxScore=Math.max(...deals.map(d=>Math.abs(d.value_score||0)),1);
  const Bar=({pct,color})=>(
    <div style={{height:5,background:'#1E293B',borderRadius:3,flex:1}}>
      <div style={{height:'100%',borderRadius:3,width:`${Math.max(pct,2)}%`,background:color}}/>
    </div>
  );
  const Row=({label,right,pct,color})=>(
    <div style={{marginBottom:5}}>
      <div style={{display:'flex',justifyContent:'space-between',marginBottom:2}}>
        <span style={{fontSize:10,color:'#94A3B8',maxWidth:180,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{label}</span>
        <span style={{fontSize:10,color:'#E2E8F0',fontWeight:600,flexShrink:0,marginLeft:4}}>{right}</span>
      </div>
      <Bar pct={pct} color={color}/>
    </div>
  );
  return (
    <div style={{background:'#0F172A',borderRadius:10,padding:'12px 14px',marginTop:8}}>
      <div style={{fontSize:10,color:'#64748B',fontWeight:700,marginBottom:10,letterSpacing:'0.06em'}}>COMPARATIF DES OFFRES</div>
      <div style={{fontSize:10,color:'#94A3B8',marginBottom:6,fontWeight:600}}>PRIX (TND)</div>
      {deals.map((d,i)=><Row key={i} label={`${i+1}. ${d.titre||d.adresse}`}
        right={(d.prix||0).toLocaleString('fr-TN')} pct={((d.prix||0)/maxPrix)*100} color={colors[i%6]}/>)}
      {deals.some(d=>d.prix_m2>0)&&<>
        <div style={{fontSize:10,color:'#94A3B8',marginBottom:6,marginTop:12,fontWeight:600}}>PRIX/m²</div>
        {deals.filter(d=>d.prix_m2>0).map((d,i)=><Row key={i} label={`${i+1}. ${d.titre||d.adresse}`}
          right={(d.prix_m2||0).toLocaleString('fr-TN')} pct={((d.prix_m2||0)/maxPm2)*100} color={colors[i%6]}/>)}
      </>}
      <div style={{fontSize:10,color:'#94A3B8',marginBottom:6,marginTop:12,fontWeight:600}}>SCORE D'OPPORTUNITÉ</div>
      {deals.map((d,i)=>(
        <div key={i} style={{marginBottom:5}}>
          <div style={{display:'flex',justifyContent:'space-between',marginBottom:2}}>
            <span style={{fontSize:10,color:'#94A3B8',maxWidth:180,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{i+1}. {d.titre||d.adresse}</span>
            <span style={{fontSize:10,fontWeight:700,color:d.value_score>0?'#4ADE80':'#F87171',flexShrink:0,marginLeft:4}}>
              {d.value_score>0?'+':''}{d.value_score}%
            </span>
          </div>
          <div style={{height:5,background:'#1E293B',borderRadius:3}}>
            <div style={{height:'100%',borderRadius:3,
              width:`${Math.max((Math.abs(d.value_score||0)/maxScore)*100,2)}%`,
              background:d.value_score>0?'#4ADE80':'#F87171'}}/>
          </div>
        </div>
      ))}
      <div style={{fontSize:10,color:'#475569',marginTop:10,paddingTop:8,borderTop:'1px solid #1E293B'}}>
        Cliquez sur une propriété pour l'analyser avec l'IA
      </div>
    </div>
  );
}

// ─── Chat result cards ─────────────────────────────────────────────────────────
function DealSearchCard({ data, onSelectDeal }) {
  const {deals,total_found,filters,llm_comment}=data;
  const loc=filters?.location||'Tunisie';
  const budget=filters?.budget;
  const [showChart,setShowChart]=useState(false);
  const [hoveredIdx,setHoveredIdx]=useState(null);
  return (
    <div style={S.msgBot}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:8}}>
        <strong style={{color:'#E2E8F0',fontSize:14}}>🏆 Meilleures affaires — {loc}</strong>
        <span style={{color:'#64748B',fontSize:11}}>{total_found} annonces</span>
      </div>
      {budget&&<div style={{color:'#64748B',fontSize:11,marginBottom:8}}>Budget: ≤ {budget.toLocaleString('fr-TN')} TND</div>}
      {llm_comment&&(
        <div style={{background:'#1E3A5F',borderRadius:8,padding:'8px 10px',marginBottom:10,fontSize:12,color:'#CBD5E1',lineHeight:1.6}}>
          {llm_comment}
        </div>
      )}
      {deals.length===0
        ?<div style={{color:'#94A3B8',fontSize:13}}>Aucune annonce trouvée. Élargissez la zone ou le budget.</div>
        :deals.map((d,i)=>(
        <div key={i} onClick={()=>onSelectDeal&&onSelectDeal(d)}
          onMouseEnter={()=>setHoveredIdx(i)} onMouseLeave={()=>setHoveredIdx(null)}
          style={{background:hoveredIdx===i?'#1A2A40':'#0F172A',borderRadius:8,
            padding:'10px 12px',marginBottom:8,
            border:hoveredIdx===i?'1px solid #3B82F6':'1px solid #1E293B',
            cursor:onSelectDeal?'pointer':'default',transition:'all 0.15s'}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:4}}>
            <div style={{flex:1,marginRight:8}}>
              <div style={{color:'#E2E8F0',fontSize:12,fontWeight:700,lineHeight:1.4}}>{d.titre}</div>
              <div style={{color:'#64748B',fontSize:11,marginTop:2}}>{d.adresse}</div>
            </div>
            <div style={{textAlign:'right',flexShrink:0}}>
              <div style={{color:'#3B82F6',fontWeight:800,fontSize:13}}>{d.prix.toLocaleString('fr-TN')} TND</div>
              {d.surface>0&&<div style={{color:'#64748B',fontSize:10}}>{d.prix_m2.toLocaleString('fr-TN')} TND/m²</div>}
            </div>
          </div>
          <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
            <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
              {d.surface>0&&<span style={{color:'#94A3B8',fontSize:10}}>📐 {d.surface} m²</span>}
              {d.chambres>0&&<span style={{color:'#94A3B8',fontSize:10}}>🛏 {d.chambres}</span>}
              {(d.features||[]).slice(0,3).map(ft=>(
                <span key={ft} style={{background:'#1E293B',color:'#94A3B8',fontSize:10,padding:'1px 5px',borderRadius:3}}>{ft}</span>
              ))}
            </div>
            <div style={{fontSize:10,fontWeight:700,color:d.value_score>0?'#4ADE80':'#F87171'}}>
              {d.value_score>0?'+':''}{d.value_score}%
            </div>
          </div>
          {hoveredIdx===i&&onSelectDeal&&(
            <div style={{fontSize:10,color:'#3B82F6',marginTop:5,textAlign:'center',fontWeight:600}}>
              Cliquez pour voir les détails →
            </div>
          )}
        </div>
      ))}
      {deals.length>1&&(
        <button onClick={()=>setShowChart(s=>!s)} style={{
          width:'100%',padding:'8px',borderRadius:8,marginTop:4,marginBottom:4,
          background:showChart?'#1E3A5F':'#1E293B',
          border:`1px solid ${showChart?'#3B82F6':'#334155'}`,
          color:showChart?'#93C5FD':'#94A3B8',
          fontSize:11,fontWeight:700,cursor:'pointer',transition:'all 0.2s'}}>
          📊 {showChart?'Masquer le comparatif':'Comparer les offres'}
        </button>
      )}
      {showChart&&<CompareDealsChart deals={deals}/>}
      <div style={{fontSize:10,color:'#475569',marginTop:6}}>
        Score = écart au prix médian local · Plus le score est élevé, meilleure est l'affaire
      </div>
    </div>
  );
}

function MarketAnalysisCard({ data }) {
  if (data.error) return <div style={S.msgBot}><span style={{color:'#FCA5A5'}}>⚠️ {data.error}</span></div>;
  const {location,total_listings,median_price,median_price_per_m2,
         appreciation_rate_pct,gross_yield_pct,bct_tmm_pct,mortgage_rate_pct,type_breakdown,llm_comment}=data;
  return (
    <div style={S.msgBot}>
      <strong style={{color:'#E2E8F0',fontSize:14}}>📊 Marché — {location}</strong>
      <div style={{color:'#64748B',fontSize:11,marginBottom:10}}>{total_listings} annonces analysées</div>
      {llm_comment&&(
        <div style={{background:'#1E3A5F',borderRadius:8,padding:'8px 10px',marginBottom:10,fontSize:12,color:'#CBD5E1',lineHeight:1.6}}>
          {llm_comment}
        </div>
      )}
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:12}}>
        <MetricPill label="Prix médian" value={`${(median_price||0).toLocaleString('fr-TN')} TND`} accent="#93C5FD"/>
        <MetricPill label="Prix médian/m²" value={`${(median_price_per_m2||0).toLocaleString('fr-TN')} TND`} accent="#93C5FD"/>
        <MetricPill label="Appréciation/an" value={`${appreciation_rate_pct}%`} accent="#4ADE80"/>
        <MetricPill label="Rendement locatif" value={`${gross_yield_pct}%`} accent="#FBBF24"/>
        <MetricPill label="TMM BCT" value={`${bct_tmm_pct}%`} accent="#94A3B8"/>
        <MetricPill label="Taux crédit moy." value={`${mortgage_rate_pct}%`} accent="#94A3B8"/>
      </div>
      {type_breakdown&&Object.keys(type_breakdown).length>0&&<>
        <SectionTitle>PAR TYPE DE BIEN</SectionTitle>
        {Object.entries(type_breakdown).slice(0,6).map(([t,s])=>(
          <div key={t} style={{display:'flex',justifyContent:'space-between',padding:'3px 0',
            borderBottom:'1px solid #1E293B',fontSize:11}}>
            <span style={{color:'#94A3B8'}}>{t}</span>
            <span style={{color:'#E2E8F0'}}>{s.count} ann. · {(s.median_price||0).toLocaleString('fr-TN')} TND</span>
          </div>
        ))}
      </>}
    </div>
  );
}

function PortfolioAdviceCard({ data }) {
  const {reference_asset,recommendations,portfolio_analysis,budget}=data;
  return (
    <div style={S.msgBot}>
      <strong style={{color:'#E2E8F0',fontSize:14}}>🗂️ Conseil de diversification</strong>
      <div style={{color:'#94A3B8',fontSize:12,marginTop:4,marginBottom:10}}>Budget: {(budget||0).toLocaleString('fr-TN')} TND</div>
      {reference_asset&&(
        <div style={{background:'#0F172A',borderRadius:6,padding:'8px 10px',marginBottom:10}}>
          <div style={{color:'#64748B',fontSize:10,marginBottom:2}}>ACTIF DE RÉFÉRENCE</div>
          <div style={{color:'#E2E8F0',fontSize:12}}>{reference_asset.type}</div>
          <div style={{color:'#94A3B8',fontSize:11}}>{reference_asset.location}</div>
        </div>
      )}
      {portfolio_analysis?.diversification_score&&(
        <div style={{marginBottom:10}}>
          <div style={{color:'#94A3B8',fontSize:11}}>Score de diversification actuel</div>
          <div style={{display:'flex',alignItems:'center',gap:8,marginTop:4}}>
            <div style={{flex:1,height:6,background:'#0F172A',borderRadius:3}}>
              <div style={{width:`${portfolio_analysis.diversification_score}%`,height:'100%',borderRadius:3,background:'#3B82F6'}}/>
            </div>
            <span style={{color:'#E2E8F0',fontWeight:700,fontSize:12}}>{portfolio_analysis.diversification_score}/100</span>
          </div>
        </div>
      )}
      {(recommendations||[]).length>0?<>
        <SectionTitle>OPPORTUNITÉS COMPLÉMENTAIRES</SectionTitle>
        {recommendations.map((r,i)=>(
          <div key={i} style={{background:'#0F172A',borderRadius:6,padding:'8px 10px',marginBottom:6}}>
            <div style={{color:'#E2E8F0',fontSize:12,fontWeight:600}}>{r.Type}</div>
            <div style={{color:'#64748B',fontSize:11}}>{r.Adresse} · {(r.price||0).toLocaleString('fr-TN')} TND</div>
            <div style={{color:'#93C5FD',fontSize:10,marginTop:2}}>{r.reason}</div>
          </div>
        ))}
      </>:<div style={{color:'#94A3B8',fontSize:12}}>Précisez un budget et une localisation pour des recommandations ciblées.</div>}
    </div>
  );
}

// ─── Welcome card (redesigned) ─────────────────────────────────────────────────
function WelcomeCard({ onSelectNormal, onSelectExpert, expertMode }) {
  const { t } = useLanguage();
  return (
    <div style={S.msgBot}>
      <div style={{textAlign:'center',marginBottom:14}}>
        <img src="/kadastra-logo.png" alt="Kadastra"
          style={{height:36,width:'auto',objectFit:'contain',filter:'brightness(0) invert(1)',marginBottom:8}}/>
        <div style={{color:'#E2E8F0',fontSize:15,fontWeight:700}}>{t('chat.title')}</div>
        <div style={{color:'#94A3B8',fontSize:12,marginTop:2}}>{t('chat.subtitle')}</div>
      </div>

      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:14}}>
        {/* Normal mode path */}
        <button onClick={onSelectNormal} style={{
          background:!expertMode?'rgba(16,185,129,0.1)':'#1E293B',
          border:`2px solid ${!expertMode?'#10b981':'#334155'}`,
          borderRadius:12,padding:'14px 10px',cursor:'pointer',
          color:'white',textAlign:'center',transition:'all 0.2s',
        }}>
          <div style={{fontSize:24,marginBottom:6}}>🏠</div>
          <div style={{fontSize:12,fontWeight:700,color:!expertMode?'#6ee7b7':'#E2E8F0',marginBottom:4}}>
            {t('chat.normalMode')}
          </div>
          <div style={{fontSize:10,color:'#64748B',lineHeight:1.5}}>
            {t('chat.normalDesc')}
          </div>
        </button>

        {/* Expert mode path */}
        <button onClick={onSelectExpert} style={{
          background:expertMode?'rgba(59,130,246,0.1)':'#1E293B',
          border:`2px solid ${expertMode?'#3b82f6':'#334155'}`,
          borderRadius:12,padding:'14px 10px',cursor:'pointer',
          color:'white',textAlign:'center',transition:'all 0.2s',
        }}>
          <div style={{fontSize:24,marginBottom:6}}>📊</div>
          <div style={{fontSize:12,fontWeight:700,color:expertMode?'#93c5fd':'#E2E8F0',marginBottom:4}}>
            {t('chat.expertMode')}
          </div>
          <div style={{fontSize:10,color:'#64748B',lineHeight:1.5}}>
            {t('chat.expertDesc')}
          </div>
        </button>
      </div>

      {!expertMode ? (
        <div style={{background:'rgba(16,185,129,0.08)',border:'1px solid rgba(16,185,129,0.2)',
          borderRadius:10,padding:'10px 12px',fontSize:12,color:'#94A3B8',lineHeight:1.7}}>
          <strong style={{color:'#6ee7b7',display:'block',marginBottom:4}}>{t('chat.normalActive')}</strong>
          {t('chat.normalHint')} <strong style={{color:'#6ee7b7'}}>{t('chat.clickAnalyze2')}</strong>.
        </div>
      ) : (
        <div style={{background:'rgba(59,130,246,0.08)',border:'1px solid rgba(59,130,246,0.2)',
          borderRadius:10,padding:'10px 12px',fontSize:12,color:'#94A3B8',lineHeight:1.7}}>
          <strong style={{color:'#93c5fd',display:'block',marginBottom:4}}>{t('chat.expertActive')}</strong>
          {t('chat.expertHint')}
        </div>
      )}

      <div style={{color:'#475569',fontSize:11,marginTop:10,lineHeight:1.7,textAlign:'center'}}>
        <em>{t('chat.exampleHint')}</em>
      </div>
    </div>
  );
}

function GuideCard({ onOpenProp, onOpenProfile }) {
  const { t } = useLanguage();
  return (
    <div style={S.msgBot}>
      <strong style={{color:'#E2E8F0'}}>{t('chat.guideTitle')}</strong>
      <p style={{margin:'8px 0 10px',color:'#CBD5E1',fontSize:13}}>
        {t('chat.guideDesc')}
      </p>
      <div style={{display:'flex',flexDirection:'column',gap:8}}>
        <button onClick={onOpenProp} style={{background:'#1E3A5F',border:'1px solid #3B82F6',
          borderRadius:8,color:'#93C5FD',fontSize:13,padding:'9px 14px',cursor:'pointer',fontWeight:700,textAlign:'left'}}>
          {t('chat.guideStep1')}
        </button>
        <button onClick={onOpenProfile} style={{background:'#1E293B',border:'1px solid #334155',
          borderRadius:8,color:'#E2E8F0',fontSize:13,padding:'9px 14px',cursor:'pointer',fontWeight:600,textAlign:'left'}}>
          {t('chat.guideStep2')}
        </button>
        <div style={{fontSize:11,color:'#64748B',marginTop:2}}>
          {t('chat.guideThenClick')} <strong style={{color:'#3B82F6'}}>{t('chat.analyzeBtn')}</strong>.
        </div>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function KadastraAgent() {
  const { t } = useLanguage();
  const [open,       setOpen]       = useState(false);
  const [messages,   setMessages]   = useState([{ role:'bot', content:'welcome' }]);
  const [input,      setInput]      = useState('');
  const [loading,    setLoading]    = useState(false);
  const [showMenu,   setShowMenu]   = useState(false);
  const [activeForm, setActiveForm] = useState(null);
  const [expertMode, setExpertMode] = useState(false);
  const [selectedDeal, setSelectedDeal] = useState(null);

  const [attachedListing,  setAttachedListing]  = useState(null);
  const [attachedProperty, setAttachedProperty] = useState(null);
  const [attachedProfile,  setAttachedProfile]  = useState(null);
  const [propDraft,        setPropDraft]         = useState({...BLANK_PROPERTY});
  const [profileDraft,     setProfileDraft]      = useState({...BLANK_PROFILE});

  const endRef = useRef(null);
  useEffect(()=>{ endRef.current?.scrollIntoView({behavior:'smooth'}); },[messages]);

  // Listen for listing attach from ListingCard "📊 IA" button
  useEffect(()=>{
    const handler=(e)=>{
      const listing=e.detail;
      setAttachedListing(listing);
      setAttachedProperty(null);
      setOpen(true);
      // Auto-suggest Normal mode for rentals
      const type=(listing.type_bien||listing.type||listing.Type||'').toLowerCase();
      if (/louer|location/.test(type)) setExpertMode(false);
      setMessages(prev=>[...prev,{role:'bot',content:'listing-attached',data:listing}]);
    };
    window.addEventListener('kadastra-attach-listing',handler);
    return ()=>window.removeEventListener('kadastra-attach-listing',handler);
  },[]);

  const openProp    = ()=>{ setActiveForm('property'); setShowMenu(false); };
  const openProfile = ()=>{ setActiveForm('profile');  setShowMenu(false); };
  const confirmProp = ()=>{
    if (!propDraft.price_numeric) return;
    setAttachedProperty(propertyFormToPayload(propDraft));
    setAttachedListing(null);
    setActiveForm(null);
  };
  const confirmProfile = ()=>{
    setAttachedProfile(profileFormToPayload(profileDraft));
    setActiveForm(null);
  };

  const effectiveProperty = attachedListing ? listingToProperty(attachedListing) : attachedProperty;

  const sendMessage = useCallback(async () => {
    const text=input.trim();
    const hasProp=!!effectiveProperty, hasProfile=!!attachedProfile;
    if (!text && !hasProp) return;
    if (loading) return;

    // Guided mode
    if (text && isGuideRequest(text) && !hasProp) {
      setInput('');
      setMessages(prev=>[...prev,{role:'user',content:text},{role:'bot',content:'guide'}]);
      return;
    }

    // Explanation of last result
    if (text && isExplainRequest(text)) {
      const lastResult=[...messages].reverse().find(m=>m.content==='result'||m.content==='normal-result');
      if (lastResult) {
        setInput('');
        setMessages(prev=>[...prev,
          {role:'user',content:text},
          {role:'bot',content:'explanation',data:lastResult.data},
        ]);
        return;
      }
    }

    setInput('');
    if (text) setMessages(prev=>[...prev,{role:'user',content:text}]);
    setLoading(true);

    try {
      // ── Chat intent (deal search / market / portfolio) — both modes ───
      if (text && !hasProp && isChatIntent(text)) {
        const resp=await fetch(`${API_BASE}/api/chat`,{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({text}),
        });
        const raw=await resp.json();
        if (!resp.ok) throw new Error(raw.detail||'Chat failed');
        setMessages(prev=>[...prev,{role:'bot',content:'chat',data:raw}]);
        setLoading(false);
        return;
      }

      // ── Analysis ───────────────────────────────────────────────────────
      const defaultProfile={
        budget:300000,holding_period_years:7,rental_income:0,
        first_time_buyer:true,is_new_promoter:false,risk_tolerance:'medium',
      };

      if (!expertMode) {
        // ── NORMAL MODE → /api/analyze/normal ──────────────────────────
        let prop=hasProp ? effectiveProperty : null;
        if (!prop && text) {
          // Quick NL parse: create a minimal prop from text
          const nl=text.toLowerCase();
          prop={
            Type: /louer|location/.test(nl)?'Appartement a louer':'Appartement a vendre',
            Adresse:'Tunis',price_numeric:0,surface_numeric:0,
            pieces:0,chambres:0,sallesdebain:0,
            neuf:0,parking:0,ascenseur:0,meuble:0,balcon_terrasse:0,
            climatisation:0,chauffage:0,jardin:0,piscine:0,
          };
          const pm=nl.match(/(\d[\d\s]*)\s*(?:tnd|dt)/);
          if (pm) prop.price_numeric=parseFloat(pm[1].replace(/\s/g,''));
          const sm=nl.match(/(\d+)\s*m[²2]?/);
          if (sm) prop.surface_numeric=parseFloat(sm[1]);
        }
        if (!prop || (!prop.price_numeric && !hasProp)) {
          setMessages(prev=>[...prev,{role:'bot',content:'chat',data:{
            type:'general',data:{message: t('chat.noPropertyMsg')},
          }}]);
          setLoading(false);
          return;
        }

        const resp=await fetch(`${API_BASE}/api/analyze/normal`,{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({property:prop,profile:hasProfile?attachedProfile:defaultProfile}),
        });
        const raw=await resp.json();
        if (!resp.ok) {
          if (raw.detail?.type==='validation_error') {
            setMessages(prev=>[...prev,{role:'bot',content:'validation-error',data:raw.detail}]);
            setLoading(false); return;
          }
          throw new Error(raw.detail||'Analyse échouée');
        }

        // Enrich with market trend
        const trend=await fetchMarketTrend(prop.Type,prop.Adresse);
        raw.market_trend=trend;

        setMessages(prev=>[...prev,{role:'bot',content:'normal-result',data:raw}]);

      } else {
        // ── EXPERT MODE → /api/analyze or /api/quick-analyze ───────────
        let data;
        if (hasProp) {
          const resp=await fetch(`${API_BASE}/api/analyze`,{
            method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({property:effectiveProperty,profile:hasProfile?attachedProfile:defaultProfile}),
          });
          const raw=await resp.json();
          if (!resp.ok) {
            if (raw.detail?.type==='validation_error') {
              setMessages(prev=>[...prev,{role:'bot',content:'validation-error',data:raw.detail}]);
              setLoading(false); return;
            }
            throw new Error(raw.detail||'Analyse échouée');
          }
          data=transformFullScenario(raw);
        } else if (text) {
          const resp=await fetch(`${API_BASE}/api/quick-analyze`,{
            method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({text}),
          });
          const raw=await resp.json();
          if (!resp.ok) {
            if (raw.detail?.type==='validation_error') {
              setMessages(prev=>[...prev,{role:'bot',content:'validation-error',data:raw.detail}]);
              setLoading(false); return;
            }
            throw new Error(raw.detail||'Analyse échouée');
          }
          data=raw;
        } else {
          setLoading(false); return;
        }

        // Enrich with market trend
        const prop=effectiveProperty||{Type:'Appartement a vendre',Adresse:'Tunis'};
        const trend=await fetchMarketTrend(prop.Type,prop.Adresse);
        data.market_trend=trend;

        setMessages(prev=>[...prev,{role:'bot',content:'result',data}]);
      }

    } catch(err) {
      setMessages(prev=>[...prev,{role:'bot',content:'error',data:{message:err.message}}]);
    }
    setLoading(false);
  }, [input, effectiveProperty, attachedProfile, loading, expertMode, messages]);

  const handleKey=(e)=>{ if (e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();} };

  // Build explanation for last result (used in expert explanation card)
  function buildExpertExplanation(data) {
    if (!data) return [];
    const lines=[];
    const score=data.score||0;
    if (score>=70) lines.push(`Score ${score}/100 — indicateurs très favorables pour l'investissement.`);
    else if (score>=46) lines.push(`Score ${score}/100 — potentiel intéressant avec quelques points de vigilance.`);
    else if (score>=27) lines.push(`Score ${score}/100 — risques significatifs ou rendement limité.`);
    else lines.push(`Score ${score}/100 — combinaison risques élevés / rendement insuffisant.`);
    const gy=data.financials?.gross_yield||0;
    lines.push(`Rendement brut ${gy.toFixed(1)}% ${gy>7.25?'(supérieur à la moyenne de Tunis ✓)':gy>5.43?'(dans la moyenne nationale)':'(sous la moyenne nationale)'}.`);
    const irr=data.financials?.irr_percent||0;
    const hurdle=7.49;
    lines.push(`IRR ${irr.toFixed(1)}% ${irr>hurdle?`— supérieur au seuil BCT (${hurdle}%) ✓`:`— sous le seuil BCT (${hurdle}%)`}.`);
    const prob=(data.financials?.prob_positive_npv||0)*100;
    if (prob>0) lines.push(`${prob.toFixed(0)}% des simulations Monte Carlo aboutissent à un gain net positif.`);
    return lines;
  }

  const renderMessage=(msg,idx)=>{
    if (msg.role==='user') return <div key={idx} style={S.msgUser}>{msg.content}</div>;
    switch(msg.content) {

      case 'welcome':
        return <WelcomeCard key={idx}
          onSelectNormal={()=>{ setExpertMode(false); setMessages([{role:'bot',content:'welcome'}]); }}
          onSelectExpert={()=>{ setExpertMode(true);  setMessages([{role:'bot',content:'welcome'}]); }}
          expertMode={expertMode}/>;

      case 'guide':
        return <GuideCard key={idx} onOpenProp={openProp} onOpenProfile={openProfile}/>;

      case 'listing-attached': {
        const l=msg.data; const pa=l.price_analysis;
        const PA_CHIP={
          great:{bg:'#064e3b',color:'#6ee7b7'},fair:{bg:'#1e3a8a',color:'#93c5fd'},
          high:{bg:'#7c2d12',color:'#fdba74'},very_high:{bg:'#881337',color:'#fda4af'},
        };
        const chip=pa?(PA_CHIP[pa.label]||PA_CHIP.fair):null;
        const isRental=/louer|location/.test((l.type_bien||l.type||'').toLowerCase());
        return (
          <div key={idx} style={S.msgBot}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
              <span style={{color:'#93C5FD',fontWeight:700,fontSize:13}}>{t('chat.listingAttached')}</span>
              <span style={{fontSize:10,padding:'2px 8px',borderRadius:99,
                background:isRental?'rgba(16,185,129,0.15)':'rgba(59,130,246,0.15)',
                color:isRental?'#6ee7b7':'#93c5fd',fontWeight:600}}>
                {isRental ? t('chat.normalModeBadge') : t('chat.expertModeBadge')}
              </span>
            </div>
            <div style={{fontSize:12,color:'#94A3B8',marginBottom:6}}>
              <strong style={{color:'#E2E8F0'}}>{l.titre||l.Type||'—'}</strong>
              {(l.adresse||l.Adresse)&&<><br/>{l.adresse||l.Adresse}</>}
              {l.prix&&<> · <strong style={{color:'#3B82F6'}}>{l.prix}</strong></>}
            </div>
            {pa&&(
              <div style={{background:'#0F172A',borderRadius:8,padding:'8px 10px',marginBottom:6}}>
                <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:4}}>
                  <span style={{fontSize:10,color:'#64748B',fontWeight:700}}>ANALYSE DE PRIX · IA</span>
                  <span style={{background:chip.bg,color:chip.color,borderRadius:99,
                    padding:'2px 8px',fontSize:10,fontWeight:700}}>{pa.label_fr}</span>
                </div>
                <div style={{display:'flex',justifyContent:'space-between',fontSize:11}}>
                  <span style={{color:'#94A3B8'}}>Prix estimé marché</span>
                  <span style={{color:'#E2E8F0',fontWeight:700}}>~{pa.predicted_price.toLocaleString('fr-TN')} TND</span>
                </div>
                <div style={{display:'flex',justifyContent:'space-between',fontSize:11,marginTop:2}}>
                  <span style={{color:'#94A3B8'}}>Écart</span>
                  <span style={{fontWeight:700,color:pa.delta_pct>20?'#F87171':pa.delta_pct<-10?'#4ADE80':'#94A3B8'}}>
                    {pa.delta_pct>0?'+':''}{pa.delta_pct}%
                  </span>
                </div>
              </div>
            )}
            <div style={{fontSize:11,color:'#64748B'}}>
              {isRental ? t('chat.rentalHint') : t('chat.saleHint')}
              {' '}{t('chat.clickAnalyze')} <strong style={{color:isRental?'#6ee7b7':'#3B82F6'}}>{t('chat.clickAnalyze2')}</strong>.
            </div>
          </div>
        );
      }

      case 'normal-result':
        return <NormalModeResultCard key={idx} data={msg.data}/>;

      case 'result':
        return <ExpertResultCard key={idx} data={msg.data}/>;

      case 'explanation': {
        const d=msg.data;
        // Detect if it's a normal result or expert result
        if (d.recommendation_fr) {
          // Normal mode explanation
          return (
            <div key={idx} style={S.msgBot}>
              <strong style={{color:'#E2E8F0',fontSize:14}}>💬 Explication de l'analyse</strong>
              <div style={{marginTop:8,color:'#CBD5E1',fontSize:13,lineHeight:1.75}}>
                <p>Verdict : <strong style={{color:d.recommendation_color}}>{d.recommendation_fr}</strong></p>
                {d.price_estimated && (
                  <p><strong>Prix :</strong> Affiché {(d.price_listed||0).toLocaleString('fr-TN')} {d.price_unit} · Estimation ~{(d.price_estimated||0).toLocaleString('fr-TN')} {d.price_unit} → {d.price_verdict}</p>
                )}
                {(d.price_factors||[]).map((f,i)=><p key={i} style={{color:'#94A3B8'}}>• {f}</p>)}
                <p><strong>Quartier :</strong> {d.neighborhood_name} ({d.neighborhood_type}) · {d.neighborhood_safety}</p>
                {(d.amenities||[]).length>0 && <p><strong>Équipements :</strong> {d.amenities.join(', ')}</p>}
              </div>
            </div>
          );
        }
        // Expert mode explanation
        const lines=buildExpertExplanation(d);
        return (
          <div key={idx} style={S.msgBot}>
            <strong style={{color:'#E2E8F0',fontSize:14}}>💬 Pourquoi ce verdict ?</strong>
            <div style={{marginTop:8}}>
              {lines.map((l,i)=>(
                <p key={i} style={{color:'#CBD5E1',fontSize:13,lineHeight:1.7,marginTop:i>0?6:4,marginBottom:0}}>{l}</p>
              ))}
            </div>
            <div style={{fontSize:10,color:'#475569',borderTop:'1px solid #1E293B',paddingTop:6,marginTop:10}}>
              Score global: {d.score}/100
            </div>
          </div>
        );
      }

      case 'chat': {
        const d=msg.data;
        if (d.type==='deal_search')
          return <DealSearchCard key={idx} data={{...d.data,llm_comment:d.llm_comment}}
            onSelectDeal={(deal)=>setSelectedDeal(dealToListing(deal))}/>;
        if (d.type==='market_analysis')
          return <MarketAnalysisCard key={idx} data={{...d.data,llm_comment:d.llm_comment}}/>;
        if (d.type==='portfolio_advice')
          return <PortfolioAdviceCard key={idx} data={d.data}/>;
        return (
          <div key={idx} style={S.msgBot}>
            {(d.data?.message||'').split('\n').map((line,i)=>(
              <div key={i} style={{marginBottom:4}}
                dangerouslySetInnerHTML={{__html:line.replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>')}}/>
            ))}
          </div>
        );
      }

      case 'validation-error':
        return (
          <div key={idx} style={{...S.msgBot,borderLeft:'3px solid #EF4444'}}>
            <strong style={{color:'#FCA5A5',fontSize:13}}>⛔ Saisie invalide</strong>
            {(msg.data.errors||[]).map((e,i)=><div key={i} style={{color:'#FCA5A5',fontSize:12,marginTop:4}}>• {e}</div>)}
            {(msg.data.warnings||[]).length>0&&(
              <div style={{marginTop:8}}>
                {msg.data.warnings.map((w,i)=><div key={i} style={{color:'#FDE68A',fontSize:12,marginTop:3}}>⚠️ {w}</div>)}
              </div>
            )}
            <div style={{color:'#64748B',fontSize:11,marginTop:8}}>
              Vérifiez le prix, la surface et la localisation puis réessayez.
            </div>
          </div>
        );

      case 'error':
        return (
          <div key={idx} style={{...S.msgBot,borderLeft:'3px solid #DC2626'}}>
            <strong style={{color:'#FCA5A5'}}>Erreur</strong>
            <p style={{margin:'4px 0 0',color:'#E2E8F0',fontSize:12}}>{msg.data.message}</p>
          </div>
        );

      default:
        return <div key={idx} style={S.msgBot}>{msg.content}</div>;
    }
  };

  const hasAttachment=!!effectiveProperty||!!attachedProfile;

  // Determine send button label and placeholder
  const isRentalAttached=effectiveProperty&&/louer|location/.test((effectiveProperty.Type||'').toLowerCase());
  const sendLabel=effectiveProperty ? t('chat.analyzeBtn') : t('chat.analyzeBtn');
  const placeholder=expertMode
    ? t('chat.placeholderExpert')
    : (effectiveProperty ? t('chat.placeholderExpert') : t('chat.placeholderNormal'));

  return (
    <>
      {selectedDeal&&<ListingModal listing={selectedDeal} onClose={()=>setSelectedDeal(null)}/>}

      {/* Floating bubble */}
      <button style={S.bubble} onClick={()=>setOpen(o=>!o)}
        onMouseEnter={e=>e.currentTarget.style.transform='scale(1.1)'}
        onMouseLeave={e=>e.currentTarget.style.transform='scale(1)'}
        title="Kadastra AI">
        {open
          ?<span style={{fontSize:22,lineHeight:1}}>✕</span>
          :<img src="/kadastra-logo.png" alt="K" style={{width:36,height:36,objectFit:'contain',filter:'brightness(0) invert(1)'}}/>}
      </button>

      {open&&(
        <div style={S.panel}>
          {/* Header */}
          <div style={S.header}>
            <div style={{display:'flex',alignItems:'center',gap:8}}>
              <img src="/kadastra-logo.png" alt="Kadastra"
                style={{height:28,width:'auto',objectFit:'contain',filter:'brightness(0) invert(1)'}}/>
              <div>
                <p style={{color:'#E2E8F0',fontSize:14,fontWeight:700,margin:0}}>Kadastra Agent</p>
                <p style={{color:'#94A3B8',fontSize:9,margin:0}}>
                  {expertMode ? t('chat.expertModeBadge') : t('chat.normalModeBadge')}
                </p>
              </div>
            </div>
            <div style={{display:'flex',alignItems:'center',gap:7}}>
              <span style={{fontSize:10,color:expertMode?'#64748B':'#10b981',fontWeight:expertMode?400:700}}>🏠</span>
              <Toggle value={expertMode} onChange={v=>{
                setExpertMode(v);
                setMessages([{role:'bot',content:'welcome'}]);
              }}/>
              <span style={{fontSize:10,color:expertMode?'#3B82F6':'#64748B',fontWeight:expertMode?700:400}}>📊</span>
              <button onClick={()=>setOpen(false)}
                style={{background:'none',border:'none',color:'#94A3B8',cursor:'pointer',fontSize:18,marginLeft:6}}>✕</button>
            </div>
          </div>

          {/* Mode banner */}
          {expertMode?(
            <div style={{background:'#1E3A5F',padding:'3px 14px',fontSize:10,color:'#93C5FD',
              fontWeight:700,letterSpacing:'0.06em',borderBottom:'1px solid #0F172A'}}>
              {t('chat.expertModeBadge').toUpperCase()} · IRR · Monte Carlo
            </div>
          ):(
            <div style={{background:'rgba(16,185,129,0.1)',padding:'3px 14px',fontSize:10,color:'#6ee7b7',
              fontWeight:700,letterSpacing:'0.06em',borderBottom:'1px solid rgba(16,185,129,0.15)'}}>
              {t('chat.normalModeBadge').toUpperCase()} · Prix · Quartier · Sécurité
            </div>
          )}

          {/* Messages */}
          <div style={S.messages}>
            {messages.map(renderMessage)}
            {loading&&(
              <div style={{display:'flex',alignItems:'center',gap:8,color:'#94A3B8',fontSize:13}}>
                <span className="kadastra-spinner"/>
                {effectiveProperty
                  ? t('chat.analyzeBtn') + '…'
                  : t('app.loading')}
              </div>
            )}
            <div ref={endRef}/>
          </div>

          {/* Attachment chips */}
          {hasAttachment&&(
            <div style={{padding:'6px 14px 0',display:'flex',flexWrap:'wrap'}}>
              {effectiveProperty&&(
                <span style={S.chip}>
                  🏠 {effectiveProperty.Type?.split(' ')[0]}
                  {effectiveProperty.price_numeric
                    ?` · ${Number(effectiveProperty.price_numeric).toLocaleString('fr-TN')} TND`:''}
                  <button style={S.chipRemove}
                    onClick={()=>{ setAttachedListing(null); setAttachedProperty(null); }}>×</button>
                </span>
              )}
              {attachedProfile&&(
                <span style={S.chip}>
                  👤 {attachedProfile.holding_period_years}ans · {attachedProfile.risk_tolerance}
                  <button style={S.chipRemove} onClick={()=>setAttachedProfile(null)}>×</button>
                </span>
              )}
            </div>
          )}

          {/* Input row */}
          <div style={S.inputRow}>
            {showMenu&&(
              <div style={S.attachMenu}>
                {[
                  {icon:'🏠',label:t('chat.attachProperty'),sub:'Type, prix, surface…',fn:openProp},
                  ...(expertMode?[{icon:'👤',label:t('chat.attachProfile'),sub:'Budget, durée, risque…',fn:openProfile}]:[]),
                ].map(({icon,label,sub,fn})=>(
                  <div key={label} style={S.menuItem}
                    onMouseEnter={e=>e.currentTarget.style.background='#0F172A'}
                    onMouseLeave={e=>e.currentTarget.style.background='transparent'}
                    onClick={fn}>
                    <span style={{fontSize:18}}>{icon}</span>
                    <div>
                      <div style={{fontWeight:600,fontSize:13}}>{label}</div>
                      <div style={{fontSize:11,color:'#64748B'}}>{sub}</div>
                    </div>
                  </div>
                ))}
                <div style={{...S.menuItem,borderBottom:'none',color:'#64748B',fontSize:11,cursor:'default'}}>
                  📋 {t('chat.clickAnalyze')} <strong style={{color:'#93C5FD'}}>{t('chat.clickAnalyze2')}</strong>
                </div>
              </div>
            )}

            <button style={S.attachBtn} title="Joindre propriété"
              onClick={()=>setShowMenu(s=>!s)}>+</button>

            <textarea style={S.textarea} rows={1} value={input}
              onChange={e=>setInput(e.target.value)} onKeyDown={handleKey}
              placeholder={placeholder}/>

            <button style={{...S.sendBtn,opacity:loading?0.5:1}}
              onClick={sendMessage} disabled={loading}>
              {sendLabel}
            </button>
          </div>

          {/* Form overlays */}
          {activeForm==='property'&&(
            <PropertyForm form={propDraft} setForm={setPropDraft}
              onConfirm={confirmProp} onCancel={()=>setActiveForm(null)}/>
          )}
          {activeForm==='profile'&&(
            <ProfileForm form={profileDraft} setForm={setProfileDraft}
              onConfirm={confirmProfile} onCancel={()=>setActiveForm(null)}/>
          )}
        </div>
      )}

      <style>{`
        .kadastra-spinner{
          width:15px;height:15px;border:2px solid #334155;
          border-top-color:#3B82F6;border-radius:50%;
          animation:kspin 0.8s linear infinite;display:inline-block;
        }
        @keyframes kspin{to{transform:rotate(360deg);}}
      `}</style>
    </>
  );
}
