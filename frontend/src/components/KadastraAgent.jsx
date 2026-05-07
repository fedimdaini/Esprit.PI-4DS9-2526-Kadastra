/**
 * KadastraAgent.jsx — v3
 * Floating AI investment chatbot.
 *
 * Modes:
 *   Normal  — plain French, simplified verdict, 4 metric pills
 *   Expert  — full financial metrics, IRR sweep, Monte Carlo, tax breakdown
 *
 * Attachments (via + button or 📊 IA on listing cards):
 *   1. Listing from listings page  (kadastra-attach-listing event)
 *   2. Property details form
 *   3. Investor profile form
 *
 * Chat intents (routed to /api/chat):
 *   deal_search    — "meilleures affaires à Sousse sous 300k"
 *   market_analysis — "analyse le marché de Tunis"
 *   portfolio_advice — "comment diversifier mon portefeuille"
 *
 * Analysis intents (routed to /api/analyze or /api/quick-analyze):
 *   anything with an attached property, or descriptive NL text
 */
import React, { useState, useRef, useEffect } from 'react';
import ListingModal from './ListingModal';

const API_BASE = process.env.REACT_APP_KADASTRA_API || 'http://localhost:8001';

// ─── Constants ─────────────────────────────────────────────────────────────
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

// Keywords that trigger a verdict explanation (no API call needed)
const EXPLAIN_KWS = [
  'pourquoi','expliquez','expliquer','explique','comment','que signifie',
  'que veut dire','c\'est quoi','clarif','détaille','détailler','why','explain',
  'dis moi plus','plus d\'info','développe',
];
function isExplainRequest(t) { return EXPLAIN_KWS.some(w => t.toLowerCase().includes(w)); }

// Keywords that trigger /api/chat instead of analysis
const CHAT_KWS = [
  'meilleur','meilleures','bon plan','bons plans','deal','affaire','opportunit',
  'moins cher','pas cher','annonce','cherche','trouve','liste','liste moi',
  'marché','market','statistique','stat','prix moyen','tendance','evolution',
  'portfolio','portefeuille','diversif','recommand','conseil',
];
const GUIDE_KWS = ['guide','aide','help','form','comment','quoi','how','remplir','expliqu','walk'];

function isChatIntent(t)  { return CHAT_KWS .some(w => t.toLowerCase().includes(w)); }
function isGuideRequest(t){ return GUIDE_KWS.some(w => t.toLowerCase().includes(w)); }

// ─── Data helpers ──────────────────────────────────────────────────────────
function listingToProperty(l) {
  // Django serializer returns the type as `type` (lowercase).
  // type_bien / Type are aliases used in other contexts — check all three.
  const rawType = l.type_bien || l.Type || l.type || '';

  // Detect rental from the type field OR from keywords in the title/description,
  // so even mis-classified DB entries are handled correctly.
  const titleLower = String(l.titre || l.title || '').toLowerCase();
  const isRental = /louer|location|locatif|locat/.test(rawType.toLowerCase())
                || /\bà louer\b|à l'année|location/.test(titleLower);

  // Map to the canonical ML type string
  let canonicalType = rawType;
  if (!canonicalType) {
    canonicalType = isRental ? 'Appartement a louer' : 'Appartement a vendre';
  } else if (isRental && /vendre/.test(canonicalType.toLowerCase())) {
    // DB has "vendre" but the listing is actually for rent — correct it
    canonicalType = canonicalType.replace(/a vendre/i, 'a louer');
  }

  return {
    Type: canonicalType,
    Adresse: l.adresse || l.Adresse || l.localisation || 'Tunis',
    price_numeric: l.price_numeric || parseFloat(String(l.prix||'').replace(/[^\d.]/g,'')) || 0,
    surface_numeric: l.surface_numeric || parseFloat(l.surface) || 0,
    pieces: parseFloat(l.pieces) || 0,
    chambres: parseFloat(l.chambres) || 0,
    sallesdebain: parseFloat(l.salles_de_bain || l.sallesdebain) || 0,
    neuf: l.neuf?1:0, parking: l.parking?1:0, ascenseur: l.ascenseur?1:0,
    meuble: l.meuble?1:0, balcon_terrasse: l.balcon_terrasse?1:0,
    climatisation: l.climatisation?1:0, chauffage: l.chauffage?1:0,
    jardin: l.jardin?1:0, piscine: l.piscine?1:0,
    // Pass friend's price analysis so ML service can cross-reference
    market_price_estimate: l.price_analysis?.predicted_price  || null,
    market_price_label:    l.price_analysis?.label            || null,
    market_price_delta_pct: l.price_analysis?.delta_pct       || null,
  };
}
/** Map a deal row (from /api/chat deal_search) to the shape expected by ListingModal */
function dealToListing(d) {
  return {
    titre:        d.titre || '',
    prix:         d.prix ? `${Number(d.prix).toLocaleString('fr-TN')} TND` : 'Prix à consulter',
    price_numeric: d.prix || 0,
    adresse:      d.adresse || '',
    localisation: d.adresse || '',
    description:  d.description || '',
    surface:      d.surface > 0 ? String(d.surface) : 'N/A',
    surface_numeric: d.surface || 0,
    chambres:     d.chambres > 0 ? String(d.chambres) : 'N/A',
    salles_de_bain: null,
    type:         d.type || '',
    type_bien:    d.type || '',
    source:       d.source || 'kadastra',
    lien:         d.lien || d.url || '#',
    first_image:  d.first_image || null,
  };
}

function propertyFormToPayload(f) {
  return {
    Type: f.Type, Adresse: f.Adresse || 'Tunis',
    price_numeric: parseFloat(f.price_numeric) || 0,
    surface_numeric: parseFloat(f.surface_numeric) || 0,
    pieces: parseFloat(f.pieces) || 0, chambres: parseFloat(f.chambres) || 0,
    sallesdebain: parseFloat(f.sallesdebain) || 0,
    neuf: f.neuf?1:0, parking: f.parking?1:0, ascenseur: f.ascenseur?1:0,
    meuble: f.meuble?1:0, balcon_terrasse: f.balcon_terrasse?1:0,
    climatisation: f.climatisation?1:0, chauffage: f.chauffage?1:0,
    jardin: f.jardin?1:0, piscine: f.piscine?1:0,
  };
}
function profileFormToPayload(f) {
  return {
    budget: parseFloat(f.budget) || 300000,
    holding_period_years: parseInt(f.holding_period_years) || 7,
    rental_income: 0, first_time_buyer: f.first_time_buyer,
    is_new_promoter: f.is_new_promoter, risk_tolerance: f.risk_tolerance,
  };
}

/** Map /api/analyze response → same flat shape as /api/quick-analyze */
function transformFullScenario(data) {
  const s  = data.scenario;
  const mc = s.simulator.mc_primary || s.simulator.mc_rental;  // honour scenario selection
  return {
    verdict:          s.verdict.recommendation,
    score:            s.verdict.score,
    primary_scenario: s.simulator.primary_scenario || 'locatif',
    financials: {
      gross_yield:           s.simulator.rental_yield.gross_yield,
      net_yield:             s.simulator.rental_yield.net_yield,
      irr_percent:           s.simulator.roi_rental.irr_percent,
      monthly_rent_estimate: s.simulator.rental_yield.estimated_monthly_rent,
      npv_p5:                mc.npv_p5,
      npv_p50:               mc.npv_p50,
      npv_p95:               mc.npv_p95,
      prob_positive_npv:     mc.prob_positive,
      initial_investment:    s.simulator.roi_rental.initial_investment,
      monthly_mortgage:      s.simulator.roi_rental.monthly_mortgage,
    },
    risk: {
      level:      s.risk.risk_level,
      score:      s.risk.overall_risk_score,
      flags:      s.risk.risk_flags,
      components: s.risk.component_scores,
      mitigation: s.risk.mitigation,
    },
    tax: {
      acquisition_fees_pct: s.tax.acquisition_costs.fees_pct,
      acquisition_fees_tnd: s.tax.acquisition_costs.total_fees,
      optimal_holding_years: s.tax.optimal_holding_years,
      cgt_note:             s.tax.cgt_cliff_note,
      annual_taxes:         s.tax.annual_tax_burden,
    },
    insights:        s.verdict.key_insights,
    explanations:    s.explanations,
    holding_sweep:   s.tax.holding_period_sweep,
    warnings:        data.warnings || [],
    elapsed_seconds: data.elapsed_seconds,
  };
}

// ─── Styles ────────────────────────────────────────────────────────────────
const S = {
  bubble: {
    position:'fixed', bottom:24, right:24, width:60, height:60,
    borderRadius:'50%', background:'linear-gradient(135deg,#3B82F6,#1D4ED8)',
    display:'flex', alignItems:'center', justifyContent:'center',
    cursor:'pointer', boxShadow:'0 4px 20px rgba(59,130,246,0.4)',
    zIndex:9999, border:'none', color:'white', fontSize:26, transition:'transform 0.2s',
  },
  panel: {
    position:'fixed', bottom:96, right:24, width:480, maxHeight:'80vh',
    borderRadius:16, background:'#0F172A', border:'1px solid #1E293B',
    boxShadow:'0 8px 40px rgba(0,0,0,0.6)', zIndex:9998,
    display:'flex', flexDirection:'column', overflow:'hidden',
    fontFamily:'-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
  },
  header: {
    padding:'12px 16px', background:'#1E293B', flexShrink:0,
    display:'flex', alignItems:'center', justifyContent:'space-between',
    borderBottom:'1px solid #0F172A',
  },
  messages: { flex:1, overflowY:'auto', padding:'12px 14px', display:'flex', flexDirection:'column', gap:10 },
  msgBot: {
    background:'#1E293B', borderRadius:'12px 12px 12px 4px',
    padding:'12px 14px', color:'#E2E8F0', fontSize:13, lineHeight:1.55, maxWidth:'94%',
  },
  msgUser: {
    background:'#3B82F6', borderRadius:'12px 12px 4px 12px',
    padding:'10px 14px', color:'white', fontSize:13, lineHeight:1.55,
    alignSelf:'flex-end', maxWidth:'85%',
  },
  inputRow: {
    padding:'10px 12px', borderTop:'1px solid #1E293B', flexShrink:0,
    display:'flex', gap:8, alignItems:'flex-end', position:'relative',
  },
  attachBtn: {
    background:'#1E293B', border:'1px solid #334155', borderRadius:8,
    color:'#94A3B8', fontSize:22, width:38, height:38, flexShrink:0,
    cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center',
  },
  textarea: {
    flex:1, background:'#1E293B', border:'1px solid #334155',
    borderRadius:8, padding:'9px 12px', color:'#E2E8F0', fontSize:13,
    outline:'none', resize:'none', lineHeight:1.4,
  },
  sendBtn: {
    background:'#3B82F6', border:'none', borderRadius:8, padding:'0 16px',
    color:'white', fontSize:13, fontWeight:700, cursor:'pointer',
    height:38, flexShrink:0, whiteSpace:'nowrap',
  },
  attachMenu: {
    position:'absolute', bottom:58, left:12, background:'#1E293B',
    border:'1px solid #334155', borderRadius:12, zIndex:10,
    boxShadow:'0 4px 20px rgba(0,0,0,0.4)', minWidth:240, overflow:'hidden',
  },
  menuItem: {
    padding:'11px 14px', cursor:'pointer', color:'#E2E8F0', fontSize:13,
    display:'flex', alignItems:'flex-start', gap:10, borderBottom:'1px solid #0F172A',
    transition:'background 0.15s',
  },
  chip: {
    display:'inline-flex', alignItems:'center', gap:6,
    background:'#1E3A5F', color:'#93C5FD', borderRadius:20,
    padding:'3px 10px', fontSize:11, fontWeight:600, marginRight:6, marginBottom:4,
  },
  chipRemove: {
    background:'none', border:'none', color:'#93C5FD',
    cursor:'pointer', padding:0, fontSize:15, lineHeight:1,
  },
  formOverlay: {
    position:'absolute', inset:0, background:'#0F172A', zIndex:20,
    display:'flex', flexDirection:'column', overflow:'hidden',
  },
  formHeader: {
    padding:'14px 18px', background:'#1E293B', flexShrink:0,
    display:'flex', alignItems:'center', justifyContent:'space-between',
  },
  formBody:   { flex:1, overflowY:'auto', padding:16 },
  formFooter: { padding:'12px 16px', borderTop:'1px solid #1E293B', flexShrink:0 },
  label:  { color:'#94A3B8', fontSize:10, fontWeight:700, letterSpacing:'0.06em', marginBottom:4, display:'block' },
  input:  { width:'100%', background:'#1E293B', border:'1px solid #334155', borderRadius:6, padding:'8px 10px', color:'#E2E8F0', fontSize:13, outline:'none', boxSizing:'border-box' },
  select: { width:'100%', background:'#1E293B', border:'1px solid #334155', borderRadius:6, padding:'8px 10px', color:'#E2E8F0', fontSize:13, outline:'none', boxSizing:'border-box' },
  metricRow: { display:'flex', justifyContent:'space-between', padding:'4px 0', borderBottom:'1px solid #1E293B', fontSize:12 },
  verdictBadge: (rec) => ({
    display:'inline-block', padding:'5px 14px', borderRadius:6,
    fontWeight:800, fontSize:14, marginBottom:10,
    background: rec==='STRONG BUY'?'#059669': rec==='CONSIDER'?'#D97706':
                rec==='CAUTIOUS'?'#EA580C':'#DC2626',
    color:'white',
  }),
  sweepBar: (irr, h) => ({
    height:5, borderRadius:3, marginTop:2, transition:'width 0.3s',
    background: irr>=h?'#059669': irr>0?'#3B82F6':'#DC2626',
    width:`${Math.min(Math.max((irr/20)*100, 3), 100)}%`,
  }),
  pill: {
    background:'#0F172A', border:'1px solid #334155', borderRadius:8,
    padding:'8px 10px', textAlign:'center',
  },
};

// ─── Shared micro-components ───────────────────────────────────────────────
function Toggle({ value, onChange }) {
  return (
    <button onClick={() => onChange(!value)}
      style={{ width:36, height:20, borderRadius:10, border:'none', cursor:'pointer',
        background:value?'#3B82F6':'#334155', position:'relative', flexShrink:0, transition:'background 0.2s' }}>
      <div style={{ position:'absolute', top:3, left:value?19:3, width:14, height:14,
        borderRadius:'50%', background:'white', transition:'left 0.2s' }}/>
    </button>
  );
}
function SectionTitle({ children }) {
  return <div style={{ fontSize:10, color:'#64748B', fontWeight:700,
    letterSpacing:'0.08em', marginTop:12, marginBottom:6 }}>{children}</div>;
}
function ToggleRow({ label, value, onChange }) {
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:10 }}>
      <span style={{ color:'#E2E8F0', fontSize:13 }}>{label}</span>
      <Toggle value={value} onChange={onChange}/>
    </div>
  );
}
function MetricPill({ label, value, accent }) {
  return (
    <div style={{ ...S.pill }}>
      <div style={{ fontSize:10, color:'#64748B', fontWeight:600, marginBottom:3 }}>{label}</div>
      <div style={{ fontSize:14, fontWeight:700, color: accent || '#E2E8F0' }}>{value}</div>
    </div>
  );
}
function WarningBanner({ warnings }) {
  if (!warnings || warnings.length === 0) return null;
  return (
    <div style={{ background:'#451A03', border:'1px solid #92400E', borderRadius:8,
      padding:'8px 12px', marginBottom:10, fontSize:12 }}>
      <span style={{ color:'#FCD34D', fontWeight:700 }}>⚠️ Avertissement</span>
      {warnings.map((w,i) => <div key={i} style={{ color:'#FDE68A', marginTop:4 }}>• {w}</div>)}
    </div>
  );
}

// ─── Property form ─────────────────────────────────────────────────────────
function PropertyForm({ form, setForm, onConfirm, onCancel }) {
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const features = [
    ['neuf','Neuf / récent'],['parking','Parking'],['ascenseur','Ascenseur'],
    ['meuble','Meublé'],['balcon_terrasse','Balcon / Terrasse'],
    ['climatisation','Climatisation'],['chauffage','Chauffage'],
    ['jardin','Jardin'],['piscine','Piscine'],
  ];
  return (
    <div style={S.formOverlay}>
      <div style={S.formHeader}>
        <span style={{ color:'#E2E8F0', fontWeight:700, fontSize:15 }}>🏠 Détails de la propriété</span>
        <button onClick={onCancel} style={{ background:'none', border:'none', color:'#94A3B8', cursor:'pointer', fontSize:18 }}>✕</button>
      </div>
      <div style={S.formBody}>
        <label style={S.label}>TYPE DE BIEN</label>
        <select style={{ ...S.select, marginBottom:12 }} value={form.Type} onChange={e=>set('Type',e.target.value)}>
          {PROPERTY_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <label style={S.label}>LOCALISATION (ville / quartier)</label>
        <input style={{ ...S.input, marginBottom:12 }} value={form.Adresse}
          onChange={e=>set('Adresse',e.target.value)} placeholder="ex: Tunis Lac, Sousse Centre…"/>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginBottom:4 }}>
          <div>
            <label style={S.label}>PRIX (TND)</label>
            <input style={S.input} type="number" value={form.price_numeric}
              onChange={e=>set('price_numeric',e.target.value)} placeholder="250 000"/>
          </div>
          <div>
            <label style={S.label}>SURFACE (m²)</label>
            <input style={S.input} type="number" value={form.surface_numeric}
              onChange={e=>set('surface_numeric',e.target.value)} placeholder="120"/>
          </div>
          <div>
            <label style={S.label}>PIÈCES</label>
            <input style={S.input} type="number" value={form.pieces}
              onChange={e=>set('pieces',e.target.value)} placeholder="4"/>
          </div>
          <div>
            <label style={S.label}>CHAMBRES</label>
            <input style={S.input} type="number" value={form.chambres}
              onChange={e=>set('chambres',e.target.value)} placeholder="3"/>
          </div>
        </div>
        <SectionTitle>ÉQUIPEMENTS & CARACTÉRISTIQUES</SectionTitle>
        {features.map(([k, lbl]) => (
          <ToggleRow key={k} label={lbl} value={!!form[k]} onChange={v=>set(k,v)}/>
        ))}
      </div>
      <div style={S.formFooter}>
        <button style={{ ...S.sendBtn, width:'100%' }} onClick={onConfirm} disabled={!form.price_numeric}>
          ✓ Joindre la propriété
        </button>
      </div>
    </div>
  );
}

// ─── Investor profile form ─────────────────────────────────────────────────
function ProfileForm({ form, setForm, onConfirm, onCancel }) {
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  return (
    <div style={S.formOverlay}>
      <div style={S.formHeader}>
        <span style={{ color:'#E2E8F0', fontWeight:700, fontSize:15 }}>👤 Profil investisseur</span>
        <button onClick={onCancel} style={{ background:'none', border:'none', color:'#94A3B8', cursor:'pointer', fontSize:18 }}>✕</button>
      </div>
      <div style={S.formBody}>
        <label style={S.label}>BUDGET TOTAL (TND)</label>
        <input style={{ ...S.input, marginBottom:14 }} type="number" value={form.budget}
          onChange={e=>set('budget',e.target.value)} placeholder="300 000"/>
        <label style={S.label}>DURÉE DE DÉTENTION — {form.holding_period_years} ans</label>
        <input type="range" min={1} max={15} value={form.holding_period_years}
          onChange={e=>set('holding_period_years',parseInt(e.target.value))}
          style={{ width:'100%', accentColor:'#3B82F6', marginBottom:4 }}/>
        <div style={{ display:'flex', justifyContent:'space-between', color:'#64748B', fontSize:10, marginBottom:14 }}>
          <span>1 an</span><span>8 ans</span><span>15 ans</span>
        </div>
        <label style={S.label}>TOLÉRANCE AU RISQUE</label>
        <select style={{ ...S.select, marginBottom:14 }} value={form.risk_tolerance}
          onChange={e=>set('risk_tolerance',e.target.value)}>
          <option value="low">Faible — sécurité prioritaire</option>
          <option value="medium">Moyen — équilibre rendement / risque</option>
          <option value="high">Élevé — rendement maximal</option>
        </select>
        <SectionTitle>SITUATION</SectionTitle>
        <ToggleRow label="Primo-accédant" value={form.first_time_buyer} onChange={v=>set('first_time_buyer',v)}/>
        <ToggleRow label="Achat auprès d'un promoteur neuf" value={form.is_new_promoter} onChange={v=>set('is_new_promoter',v)}/>
      </div>
      <div style={S.formFooter}>
        <button style={{ ...S.sendBtn, width:'100%' }} onClick={onConfirm}>
          ✓ Joindre le profil
        </button>
      </div>
    </div>
  );
}

// ─── NORMAL result card — plain French, zero jargon ────────────────────────
const VERDICT_LABELS = {
  'STRONG BUY': '✅ Excellent investissement',
  'CONSIDER':   '🟡 À considérer',
  'CAUTIOUS':   '🟠 Prudence recommandée',
  'AVOID':      '🔴 À éviter',
};

function buildNormalExplanation(verdict, score, f, risk, tax, scenario) {
  const lines = [];
  // Score sentence
  if (score >= 75)
    lines.push(`Ce bien obtient une note de ${score}/100 et cumule des indicateurs très favorables.`);
  else if (score >= 50)
    lines.push(`Avec une note de ${score}/100, ce bien présente un potentiel intéressant mais quelques points méritent attention.`);
  else if (score >= 30)
    lines.push(`Note de ${score}/100 : des risques significatifs ou un rendement limité pèsent sur l'attractivité de ce bien.`);
  else
    lines.push(`Note de ${score}/100 : la combinaison de risques élevés et de faible rendement rend cet investissement peu recommandé.`);

  // Yield sentence
  const gy = f?.gross_yield || 0;
  if (gy > 7.5)       lines.push(`Le loyer potentiel représente un rendement de ${gy.toFixed(1)}% du prix, bien au-dessus de la moyenne nationale (5.4%) — c'est un bon signe.`);
  else if (gy > 5)    lines.push(`Le loyer potentiel représente ${gy.toFixed(1)}% du prix, dans la moyenne tunisienne.`);
  else                lines.push(`Le loyer potentiel de ${gy.toFixed(1)}% est en dessous de la moyenne nationale (~5.4%).`);

  // Scenario sentence
  if (scenario === 'revente')
    lines.push("Analyse réalisée en scénario de revente : l'investisseur achète, conserve quelques années, puis revend avec plus-value.");
  else
    lines.push("Analyse réalisée en scénario locatif : l'investisseur perçoit des loyers tout au long de la détention.");

  // Risk sentence
  if (risk?.level === 'Low')
    lines.push("Le profil de risque est faible — c'est rassurant pour un placement à long terme.");
  else if (risk?.level === 'Medium') {
    lines.push(`Risque modéré.${risk?.flags?.[0] ? ' Point d\'attention : ' + risk.flags[0] + '.' : ''}`);
  } else {
    lines.push(`Risque élevé. ${(risk?.flags || []).slice(0,2).join(', ')}.`);
  }

  // Tax tip
  if (tax?.optimal_holding_years >= 10)
    lines.push(`Conseil fiscal : conserver ce bien au moins ${tax.optimal_holding_years} ans permet de réduire l'impôt sur la plus-value de moitié.`);

  return lines;
}

function NormalResultCard({ data }) {
  const { verdict, score, financials: f, risk, tax, warnings, primary_scenario } = data;
  const label     = VERDICT_LABELS[verdict] || verdict;
  const riskColor = risk?.level==='Low'?'#4ADE80': risk?.level==='Medium'?'#FBBF24':'#F87171';
  const riskLabel = risk?.level==='Low'?'🟢 Faible': risk?.level==='Medium'?'🟡 Moyen':'🔴 Élevé';
  const lines     = buildNormalExplanation(verdict, score, f, risk, tax, primary_scenario);

  return (
    <div style={S.msgBot}>
      <WarningBanner warnings={warnings}/>

      <div style={S.verdictBadge(verdict)}>{label}</div>

      {lines.map((l,i) => (
        <p key={i} style={{ color:'#CBD5E1', fontSize:13, lineHeight:1.7,
          marginTop: i===0?6:4, marginBottom:0 }}>{l}</p>
      ))}

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginTop:14, marginBottom:10 }}>
        <MetricPill label="Loyer mensuel estimé"
          value={`${(f?.monthly_rent_estimate||0).toLocaleString('fr-TN')} TND`}
          accent="#93C5FD"/>
        <MetricPill label="Rendement annuel brut"
          value={`${(f?.gross_yield||0).toFixed(1)}%`}
          accent={(f?.gross_yield||0) > 7 ? '#4ADE80' : (f?.gross_yield||0) > 5 ? '#FBBF24' : '#F87171'}/>
        <MetricPill label="Niveau de risque"
          value={riskLabel}
          accent={riskColor}/>
        <MetricPill label="Durée de détention idéale"
          value={`${tax?.optimal_holding_years || '—'} ans`}
          accent="#E2E8F0"/>
      </div>

      {(risk?.mitigation||[]).length > 0 && (
        <div style={{ marginBottom:8 }}>
          <div style={{ color:'#94A3B8', fontSize:11, marginBottom:4 }}>💡 Recommandations :</div>
          {risk.mitigation.map((m,i) =>
            <div key={i} style={{ color:'#86EFAC', fontSize:12, marginBottom:2 }}>• {m}</div>
          )}
        </div>
      )}

      <div style={{ fontSize:10, color:'#475569', borderTop:'1px solid #1E293B', paddingTop:6, marginTop:8 }}>
        Score: {score}/100
        {data.elapsed_seconds != null && ` · Analyse en ${data.elapsed_seconds}s`}
      </div>
    </div>
  );
}

// ─── EXPERT result card — financial metrics, zero data-science terms ────────
const RISK_LABELS = {
  location_risk:   'Risque localisation',
  condition_risk:  'État du bien',
  liquidity_risk:  'Liquidité',
  price_risk:      'Risque de prix',
  economic_risk:   'Risque économique',
  regulatory_risk: 'Risque réglementaire',
};

function ExpertResultCard({ data }) {
  const hurdle = 7.49;
  const {
    verdict, score, financials: f, risk, tax,
    insights, holding_sweep, explanations, warnings, primary_scenario,
  } = data;
  const scenarioLabel = primary_scenario === 'revente' ? 'Revente' : 'Locatif';

  return (
    <div style={S.msgBot}>
      <WarningBanner warnings={warnings}/>

      <div style={S.verdictBadge(verdict)}>{verdict} — {score}/100</div>

      <SectionTitle>📈 RENDEMENT & FINANCEMENT</SectionTitle>
      {[
        ['Rendement locatif brut',   `${(f?.gross_yield||0).toFixed(2)}%`],
        ['Rendement locatif net',    `${(f?.net_yield||0).toFixed(2)}%`],
        ['Taux de rentabilité annuel',`${(f?.irr_percent||0).toFixed(2)}%`,
          (f?.irr_percent||0) > hurdle ? '#4ADE80' : '#F87171'],
        ['Loyer mensuel estimé',     `${(f?.monthly_rent_estimate||0).toLocaleString('fr-TN')} TND`],
        ['Apport initial (+ frais)', `${(f?.initial_investment||0).toLocaleString('fr-TN')} TND`],
        ['Mensualité crédit',        `${(f?.monthly_mortgage||0).toLocaleString('fr-TN')} TND`],
      ].map(([k,v,c]) => (
        <div key={k} style={S.metricRow}>
          <span style={{ color:'#94A3B8' }}>{k}</span>
          <span style={{ color: c||'#E2E8F0', fontWeight:600 }}>{v}</span>
        </div>
      ))}

      <SectionTitle>🎯 PROJECTIONS DE SCÉNARIOS ({scenarioLabel})</SectionTitle>
      {[
        ['Scénario pessimiste', `${(f?.npv_p5 ||0).toLocaleString('fr-TN')} TND`],
        ['Scénario médian',     `${(f?.npv_p50||0).toLocaleString('fr-TN')} TND`],
        ['Scénario optimiste',  `${(f?.npv_p95||0).toLocaleString('fr-TN')} TND`],
        ['Probabilité de gain net',
          `${(((f?.prob_positive_npv)||0)*100).toFixed(0)}%`,
          (f?.prob_positive_npv||0)>0.6?'#4ADE80': (f?.prob_positive_npv||0)>0.4?'#FBBF24':'#F87171'],
      ].map(([k,v,c]) => (
        <div key={k} style={S.metricRow}>
          <span style={{ color:'#94A3B8' }}>{k}</span>
          <span style={{ color: c||'#E2E8F0', fontWeight:600 }}>{v}</span>
        </div>
      ))}

      <SectionTitle>⚠️ PROFIL DE RISQUE — {risk?.level} ({((risk?.score||0)*100).toFixed(0)}/100)</SectionTitle>
      {risk?.components && Object.entries(risk.components).map(([k,v]) => (
        <div key={k} style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:5 }}>
          <span style={{ color:'#94A3B8', fontSize:11 }}>{RISK_LABELS[k] || k.replace(/_/g,' ')}</span>
          <div style={{ display:'flex', alignItems:'center', gap:6 }}>
            <div style={{ width:72, height:4, borderRadius:2, background:'#0F172A' }}>
              <div style={{ width:`${v*100}%`, height:'100%', borderRadius:2,
                background: v<0.3?'#4ADE80': v<0.6?'#FBBF24':'#F87171' }}/>
            </div>
            <span style={{ color:'#E2E8F0', fontSize:11, width:28, textAlign:'right' }}>
              {(v*100).toFixed(0)}%
            </span>
          </div>
        </div>
      ))}
      {(risk?.flags||[]).length > 0 && (
        <div style={{ marginTop:4 }}>
          {risk.flags.map((fl,i) =>
            <span key={i} style={{ display:'inline-block', background:'#7F1D1D', color:'#FCA5A5',
              padding:'2px 7px', borderRadius:4, fontSize:11, margin:'2px 3px 2px 0' }}>{fl}</span>
          )}
        </div>
      )}

      <SectionTitle>🏛️ FISCALITÉ</SectionTitle>
      {[
        ['Frais d\'acquisition',
          `${(tax?.acquisition_fees_pct||0).toFixed(2)}% — ${(tax?.acquisition_fees_tnd||0).toLocaleString('fr-TN')} TND`],
        ['Durée de détention optimale', `${tax?.optimal_holding_years} ans`],
        ['Taxe foncière annuelle (TIB)', `${(tax?.annual_taxes?.tib||0).toLocaleString('fr-TN')} TND`],
      ].map(([k,v]) => (
        <div key={k} style={S.metricRow}>
          <span style={{ color:'#94A3B8' }}>{k}</span>
          <span style={{ color:'#E2E8F0', fontWeight:600, fontSize:11 }}>{v}</span>
        </div>
      ))}
      {tax?.cgt_note && <div style={{ fontSize:11, color:'#64748B', marginTop:4 }}>{tax.cgt_note}</div>}

      <SectionTitle>💡 POINTS CLÉS</SectionTitle>
      {(insights||[]).map((ins,i) => (
        <span key={i} style={{ display:'inline-block', background:'#1E3A5F', color:'#93C5FD',
          padding:'2px 8px', borderRadius:4, fontSize:11, margin:'2px 3px 2px 0' }}>{ins}</span>
      ))}

      {(holding_sweep||[]).length > 0 && <>
        <SectionTitle>📊 RENTABILITÉ PAR DURÉE DE DÉTENTION</SectionTitle>
        {holding_sweep.map(r => (
          <div key={r.years} style={{ display:'flex', alignItems:'center', gap:6, marginBottom:4 }}>
            <span style={{ width:30, fontSize:10, color:'#94A3B8', textAlign:'right' }}>{r.years}yr</span>
            <div style={{ flex:1 }}><div style={S.sweepBar(r.irr_pct, hurdle)}/></div>
            <span style={{ width:44, fontSize:10,
              color: r.irr_pct>=hurdle?'#4ADE80':'#94A3B8', textAlign:'right', fontWeight:600 }}>
              {r.irr_pct?.toFixed(1)}%
            </span>
          </div>
        ))}
        <div style={{ fontSize:10, color:'#EF4444', marginTop:2 }}>
          ── Seuil taux directeur BCT: {hurdle}% ──
        </div>
      </>}

      {explanations && (() => {
        // Show only financial-relevant explanations, translate keys
        const friendlyKeys = {
          rendement_locatif: 'Rendement locatif',
          rentabilite_levier: 'Rentabilité avec financement',
          fiscalite: 'Cadre fiscal',
          duree_conseille: 'Durée recommandée',
          probabilite_gain: 'Probabilité de gain',
        };
        const entries = Object.entries(explanations)
          .filter(([k]) => friendlyKeys[k])
          .map(([k,v]) => [friendlyKeys[k], v]);
        if (!entries.length) return null;
        return <>
          <SectionTitle>📋 ANALYSE DÉTAILLÉE</SectionTitle>
          {entries.map(([k,v]) => (
            <div key={k} style={{ fontSize:11, color:'#64748B', marginBottom:4 }}>
              <span style={{ color:'#475569', fontWeight:600 }}>{k} : </span>
              {typeof v === 'object'
                ? Object.entries(v).map(([kk,vv]) => `${kk} ${vv}`).join(' · ')
                : v}
            </div>
          ))}
        </>;
      })()}

      <div style={{ marginTop:10, fontSize:10, color:'#475569', borderTop:'1px solid #1E293B', paddingTop:6 }}>
        Sources: GlobalPropertyGuide Q2-2025 · BCT · Code IRPP-IS 2024 · LF2025
        {data.elapsed_seconds != null && ` · ${data.elapsed_seconds}s`}
      </div>
    </div>
  );
}

// ─── Verdict explanation card ─────────────────────────────────────────────
function ExplanationCard({ data }) {
  const { verdict, score, financials: f, risk, tax, primary_scenario } = data;
  const lines = buildNormalExplanation(verdict, score, f, risk, tax, primary_scenario);
  // Add extra detail for the explanation request
  const irr = f?.irr_percent || 0;
  const prob = (f?.prob_positive_npv || 0) * 100;
  const holdYr = tax?.optimal_holding_years;
  return (
    <div style={S.msgBot}>
      <strong style={{ color:'#E2E8F0', fontSize:14 }}>💬 Pourquoi ce verdict ?</strong>
      <div style={{ marginTop:8 }}>
        {lines.map((l,i) => (
          <p key={i} style={{ color:'#CBD5E1', fontSize:13, lineHeight:1.7,
            marginTop: i===0?4:6, marginBottom:0 }}>{l}</p>
        ))}
        {irr > 0 && (
          <p style={{ color:'#CBD5E1', fontSize:13, lineHeight:1.7, marginTop:6, marginBottom:0 }}>
            Le taux de rentabilité annuel calculé est de <strong style={{ color:'#93C5FD' }}>{irr.toFixed(1)}%</strong>.
            {irr > 7.49
              ? ` C'est supérieur au taux directeur de la Banque Centrale (7.49%), ce qui signifie que l'investissement crée de la valeur au-delà de ce que rapporte un placement sans risque.`
              : ` C'est inférieur au taux directeur de la Banque Centrale (7.49%), ce qui signifie que le rendement ne compense pas complètement le coût de l'emprunt.`}
          </p>
        )}
        {prob > 0 && (
          <p style={{ color:'#CBD5E1', fontSize:13, lineHeight:1.7, marginTop:6, marginBottom:0 }}>
            Sur des milliers de projections en faisant varier les loyers, l'appréciation et les taux,{' '}
            <strong style={{ color: prob>60?'#4ADE80':prob>40?'#FBBF24':'#F87171' }}>
              {prob.toFixed(0)}% des scénarios
            </strong>{' '}
            aboutissent à un gain net positif.
          </p>
        )}
        {holdYr && (
          <p style={{ color:'#CBD5E1', fontSize:13, lineHeight:1.7, marginTop:6, marginBottom:0 }}>
            La durée de détention optimale calculée est de <strong style={{ color:'#FBBF24' }}>{holdYr} ans</strong>.
            {holdYr >= 10
              ? " Dépasser 10 ans permet de réduire la taxe sur la plus-value de 10% à 5%."
              : " Revendre trop tôt augmente la facture fiscale sur la plus-value."}
          </p>
        )}
      </div>
      <div style={{ fontSize:10, color:'#475569', borderTop:'1px solid #1E293B', paddingTop:6, marginTop:10 }}>
        Score global : {score}/100
      </div>
    </div>
  );
}

// ─── Comparative bar chart for deals ──────────────────────────────────────
function CompareDealsChart({ deals }) {
  if (!deals || deals.length === 0) return null;
  const colors   = ['#3B82F6','#10B981','#F59E0B','#EF4444','#8B5CF6','#EC4899'];
  const maxPrix  = Math.max(...deals.map(d => d.prix  || 0), 1);
  const maxPm2   = Math.max(...deals.map(d => d.prix_m2 || 0), 1);
  const maxScore = Math.max(...deals.map(d => Math.abs(d.value_score || 0)), 1);

  const Bar = ({ pct, color }) => (
    <div style={{ height:5, background:'#1E293B', borderRadius:3, flex:1 }}>
      <div style={{ height:'100%', borderRadius:3, width:`${Math.max(pct,2)}%`, background:color, transition:'width 0.4s' }}/>
    </div>
  );
  const Row = ({ label, right, pct, color }) => (
    <div style={{ marginBottom:5 }}>
      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:2 }}>
        <span style={{ fontSize:10, color:'#94A3B8', maxWidth:180, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{label}</span>
        <span style={{ fontSize:10, color:'#E2E8F0', fontWeight:600, flexShrink:0, marginLeft:4 }}>{right}</span>
      </div>
      <Bar pct={pct} color={color}/>
    </div>
  );

  return (
    <div style={{ background:'#0F172A', borderRadius:10, padding:'12px 14px', marginTop:8 }}>
      <div style={{ fontSize:10, color:'#64748B', fontWeight:700, marginBottom:10, letterSpacing:'0.06em' }}>COMPARATIF DES OFFRES</div>

      <div style={{ fontSize:10, color:'#94A3B8', marginBottom:6, fontWeight:600 }}>PRIX (TND)</div>
      {deals.map((d,i) => <Row key={i}
        label={`${i+1}. ${d.titre || d.adresse}`}
        right={(d.prix||0).toLocaleString('fr-TN')}
        pct={((d.prix||0)/maxPrix)*100}
        color={colors[i%colors.length]}/>)}

      {deals.some(d => d.prix_m2 > 0) && <>
        <div style={{ fontSize:10, color:'#94A3B8', marginBottom:6, marginTop:12, fontWeight:600 }}>PRIX/m² (TND)</div>
        {deals.filter(d => d.prix_m2 > 0).map((d,i) => <Row key={i}
          label={`${i+1}. ${d.titre || d.adresse}`}
          right={(d.prix_m2||0).toLocaleString('fr-TN')}
          pct={((d.prix_m2||0)/maxPm2)*100}
          color={colors[i%colors.length]}/>)}
      </>}

      <div style={{ fontSize:10, color:'#94A3B8', marginBottom:6, marginTop:12, fontWeight:600 }}>SCORE D'OPPORTUNITÉ (%)</div>
      {deals.map((d,i) => (
        <div key={i} style={{ marginBottom:5 }}>
          <div style={{ display:'flex', justifyContent:'space-between', marginBottom:2 }}>
            <span style={{ fontSize:10, color:'#94A3B8', maxWidth:180, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{i+1}. {d.titre || d.adresse}</span>
            <span style={{ fontSize:10, fontWeight:700, color: d.value_score>0?'#4ADE80':'#F87171', flexShrink:0, marginLeft:4 }}>
              {d.value_score>0?'+':''}{d.value_score}%
            </span>
          </div>
          <div style={{ height:5, background:'#1E293B', borderRadius:3 }}>
            <div style={{ height:'100%', borderRadius:3,
              width:`${Math.max((Math.abs(d.value_score||0)/maxScore)*100,2)}%`,
              background: d.value_score>0?'#4ADE80':'#F87171', transition:'width 0.4s' }}/>
          </div>
        </div>
      ))}

      <div style={{ fontSize:10, color:'#475569', marginTop:10, paddingTop:8, borderTop:'1px solid #1E293B' }}>
        Cliquez sur une propriété pour l'analyser avec l'IA
      </div>
    </div>
  );
}

// ─── Chat result cards ─────────────────────────────────────────────────────
function DealSearchCard({ data, onSelectDeal }) {
  const { deals, total_found, filters, llm_comment } = data;
  const loc    = filters?.location || 'Tunisie';
  const budget = filters?.budget;
  const [showChart,  setShowChart]  = useState(false);
  const [hoveredIdx, setHoveredIdx] = useState(null);

  return (
    <div style={S.msgBot}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:8 }}>
        <strong style={{ color:'#E2E8F0', fontSize:14 }}>🏆 Meilleures affaires — {loc}</strong>
        <span style={{ color:'#64748B', fontSize:11 }}>{total_found} annonces</span>
      </div>
      {budget && <div style={{ color:'#64748B', fontSize:11, marginBottom:8 }}>Budget: ≤ {budget.toLocaleString('fr-TN')} TND</div>}

      {llm_comment && (
        <div style={{ background:'#1E3A5F', borderRadius:8, padding:'8px 10px', marginBottom:10, fontSize:12, color:'#CBD5E1', lineHeight:1.6 }}>
          {llm_comment}
        </div>
      )}

      {deals.length === 0 ? (
        <div style={{ color:'#94A3B8', fontSize:13 }}>Aucune annonce trouvée. Essayez d'élargir la zone ou le budget.</div>
      ) : deals.map((d,i) => (
        <div key={i}
          onClick={() => onSelectDeal && onSelectDeal(d)}
          onMouseEnter={() => setHoveredIdx(i)}
          onMouseLeave={() => setHoveredIdx(null)}
          style={{
            background: hoveredIdx===i ? '#1A2A40' : '#0F172A',
            borderRadius:8, padding:'10px 12px', marginBottom:8,
            border: hoveredIdx===i ? '1px solid #3B82F6' : '1px solid #1E293B',
            cursor: onSelectDeal ? 'pointer' : 'default',
            transition:'background 0.15s, border-color 0.15s',
          }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:4 }}>
            <div style={{ flex:1, marginRight:8 }}>
              <div style={{ color:'#E2E8F0', fontSize:12, fontWeight:700, lineHeight:1.4 }}>{d.titre}</div>
              <div style={{ color:'#64748B', fontSize:11, marginTop:2 }}>{d.adresse}</div>
            </div>
            <div style={{ textAlign:'right', flexShrink:0 }}>
              <div style={{ color:'#3B82F6', fontWeight:800, fontSize:13 }}>
                {d.prix.toLocaleString('fr-TN')} TND
              </div>
              {d.surface > 0 && (
                <div style={{ color:'#64748B', fontSize:10 }}>{d.prix_m2.toLocaleString('fr-TN')} TND/m²</div>
              )}
            </div>
          </div>
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
            <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
              {d.surface > 0 && <span style={{ color:'#94A3B8', fontSize:10 }}>📐 {d.surface} m²</span>}
              {d.chambres > 0 && <span style={{ color:'#94A3B8', fontSize:10 }}>🛏 {d.chambres}</span>}
              {(d.features||[]).slice(0,3).map(ft => (
                <span key={ft} style={{ background:'#1E293B', color:'#94A3B8', fontSize:10,
                  padding:'1px 5px', borderRadius:3 }}>{ft}</span>
              ))}
            </div>
            <div style={{ fontSize:10, fontWeight:700, color: d.value_score>0?'#4ADE80':'#F87171' }}>
              Score: {d.value_score>0?'+':''}{d.value_score}%
            </div>
          </div>
          {hoveredIdx===i && onSelectDeal && (
            <div style={{ fontSize:10, color:'#3B82F6', marginTop:5, textAlign:'center', fontWeight:600 }}>
              Cliquez pour voir les détails →
            </div>
          )}
        </div>
      ))}

      {deals.length > 1 && (
        <button
          onClick={() => setShowChart(s => !s)}
          style={{
            width:'100%', padding:'8px', borderRadius:8, marginTop:4, marginBottom:4,
            background: showChart?'#1E3A5F':'#1E293B',
            border:`1px solid ${showChart?'#3B82F6':'#334155'}`,
            color: showChart?'#93C5FD':'#94A3B8',
            fontSize:11, fontWeight:700, cursor:'pointer', transition:'all 0.2s',
          }}>
          📊 {showChart ? 'Masquer le comparatif' : 'Comparer les offres'}
        </button>
      )}
      {showChart && <CompareDealsChart deals={deals}/>}

      <div style={{ fontSize:10, color:'#475569', marginTop:6 }}>
        Score = écart au prix moyen du marché local · Plus le score est élevé, meilleure est l'affaire
      </div>
    </div>
  );
}

function MarketAnalysisCard({ data }) {
  if (data.error) return (
    <div style={S.msgBot}>
      <span style={{ color:'#FCA5A5' }}>⚠️ {data.error}</span>
    </div>
  );

  const { location, total_listings, median_price, median_price_per_m2,
          appreciation_rate_pct, gross_yield_pct, bct_tmm_pct, mortgage_rate_pct,
          type_breakdown, llm_comment } = data;

  return (
    <div style={S.msgBot}>
      <strong style={{ color:'#E2E8F0', fontSize:14 }}>📊 Marché — {location}</strong>
      <div style={{ color:'#64748B', fontSize:11, marginBottom:10 }}>{total_listings} annonces analysées</div>

      {llm_comment && (
        <div style={{ background:'#1E3A5F', borderRadius:8, padding:'8px 10px', marginBottom:10, fontSize:12, color:'#CBD5E1', lineHeight:1.6 }}>
          {llm_comment}
        </div>
      )}

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginBottom:12 }}>
        <MetricPill label="Prix médian" value={`${(median_price||0).toLocaleString('fr-TN')} TND`} accent="#93C5FD"/>
        <MetricPill label="Prix médian/m²" value={`${(median_price_per_m2||0).toLocaleString('fr-TN')} TND`} accent="#93C5FD"/>
        <MetricPill label="Appréciation/an" value={`${appreciation_rate_pct}%`} accent="#4ADE80"/>
        <MetricPill label="Rendement locatif brut" value={`${gross_yield_pct}%`} accent="#FBBF24"/>
        <MetricPill label="TMM BCT" value={`${bct_tmm_pct}%`} accent="#94A3B8"/>
        <MetricPill label="Taux crédit moy." value={`${mortgage_rate_pct}%`} accent="#94A3B8"/>
      </div>

      {type_breakdown && Object.keys(type_breakdown).length > 0 && <>
        <SectionTitle>PAR TYPE DE BIEN</SectionTitle>
        {Object.entries(type_breakdown).slice(0,6).map(([t,s]) => (
          <div key={t} style={{ display:'flex', justifyContent:'space-between', padding:'3px 0',
            borderBottom:'1px solid #1E293B', fontSize:11 }}>
            <span style={{ color:'#94A3B8' }}>{t}</span>
            <span style={{ color:'#E2E8F0' }}>
              {s.count} ann. · méd. {(s.median_price||0).toLocaleString('fr-TN')} TND
            </span>
          </div>
        ))}
      </>}
    </div>
  );
}

function PortfolioAdviceCard({ data }) {
  const { reference_asset, recommendations, portfolio_analysis, budget } = data;
  return (
    <div style={S.msgBot}>
      <strong style={{ color:'#E2E8F0', fontSize:14 }}>🗂️ Conseil de diversification</strong>
      <div style={{ color:'#94A3B8', fontSize:12, marginTop:4, marginBottom:10 }}>
        Budget disponible: {(budget||0).toLocaleString('fr-TN')} TND
      </div>

      {reference_asset && (
        <div style={{ background:'#0F172A', borderRadius:6, padding:'8px 10px', marginBottom:10 }}>
          <div style={{ color:'#64748B', fontSize:10, marginBottom:2 }}>ACTIF DE RÉFÉRENCE</div>
          <div style={{ color:'#E2E8F0', fontSize:12 }}>{reference_asset.type}</div>
          <div style={{ color:'#94A3B8', fontSize:11 }}>{reference_asset.location}</div>
        </div>
      )}

      {portfolio_analysis && portfolio_analysis.diversification_score && (
        <div style={{ marginBottom:10 }}>
          <div style={{ color:'#94A3B8', fontSize:11 }}>Score de diversification actuel</div>
          <div style={{ display:'flex', alignItems:'center', gap:8, marginTop:4 }}>
            <div style={{ flex:1, height:6, background:'#0F172A', borderRadius:3 }}>
              <div style={{ width:`${portfolio_analysis.diversification_score}%`, height:'100%',
                borderRadius:3, background:'#3B82F6' }}/>
            </div>
            <span style={{ color:'#E2E8F0', fontWeight:700, fontSize:12 }}>
              {portfolio_analysis.diversification_score}/100
            </span>
          </div>
        </div>
      )}

      {(recommendations||[]).length > 0 ? <>
        <SectionTitle>OPPORTUNITÉS COMPLÉMENTAIRES</SectionTitle>
        {recommendations.map((r,i) => (
          <div key={i} style={{ background:'#0F172A', borderRadius:6, padding:'8px 10px', marginBottom:6 }}>
            <div style={{ color:'#E2E8F0', fontSize:12, fontWeight:600 }}>{r.Type}</div>
            <div style={{ color:'#64748B', fontSize:11 }}>{r.Adresse} · {(r.price||0).toLocaleString('fr-TN')} TND</div>
            <div style={{ color:'#93C5FD', fontSize:10, marginTop:2 }}>{r.reason}</div>
          </div>
        ))}
      </> : (
        <div style={{ color:'#94A3B8', fontSize:12 }}>
          Précisez un budget et une localisation pour des recommandations ciblées.
        </div>
      )}
    </div>
  );
}

// ─── Welcome & Guide cards ─────────────────────────────────────────────────
function WelcomeCard({ onOpenProp, onOpenProfile }) {
  return (
    <div style={S.msgBot}>
      <strong style={{ color:'#E2E8F0', fontSize:14 }}>Kadastra AI Agent</strong>
      <p style={{ margin:'8px 0 10px', color:'#CBD5E1', fontSize:13 }}>
        Analysez le potentiel d'investissement de n'importe quel bien immobilier tunisien.
      </p>
      <div style={{ display:'flex', flexDirection:'column', gap:7 }}>
        <button onClick={onOpenProp} style={{ background:'#1E3A5F', border:'1px solid #3B82F6',
          borderRadius:8, color:'#93C5FD', fontSize:12, padding:'8px 12px',
          cursor:'pointer', textAlign:'left', fontWeight:600 }}>
          🏠 Remplir le formulaire propriété
        </button>
        <button onClick={onOpenProfile} style={{ background:'#1E293B', border:'1px solid #334155',
          borderRadius:8, color:'#E2E8F0', fontSize:12, padding:'8px 12px',
          cursor:'pointer', textAlign:'left' }}>
          👤 Définir votre profil investisseur
        </button>
        <div style={{ color:'#64748B', fontSize:11, marginTop:2, lineHeight:1.6 }}>
          <em style={{ color:'#94A3B8' }}>Essayez aussi:</em><br/>
          "Meilleures affaires à Sousse sous 300 000 TND"<br/>
          "Analyse le marché de Tunis"<br/>
          Ou cliquez <strong style={{ color:'#93C5FD' }}>Ask AI</strong> sur n'importe quelle annonce.
        </div>
      </div>
    </div>
  );
}

function GuideCard({ onOpenProp, onOpenProfile }) {
  return (
    <div style={S.msgBot}>
      <strong style={{ color:'#E2E8F0' }}>Mode guidé</strong>
      <p style={{ margin:'8px 0 10px', color:'#CBD5E1', fontSize:13 }}>
        Remplissez les deux formulaires pour une analyse complète et précise.
      </p>
      <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
        <button onClick={onOpenProp} style={{ background:'#1E3A5F', border:'1px solid #3B82F6',
          borderRadius:8, color:'#93C5FD', fontSize:13, padding:'9px 14px',
          cursor:'pointer', fontWeight:700, textAlign:'left' }}>
          Étape 1 — 🏠 Détails de la propriété
        </button>
        <button onClick={onOpenProfile} style={{ background:'#1E293B', border:'1px solid #334155',
          borderRadius:8, color:'#E2E8F0', fontSize:13, padding:'9px 14px',
          cursor:'pointer', fontWeight:600, textAlign:'left' }}>
          Étape 2 — 👤 Votre profil investisseur
        </button>
        <div style={{ fontSize:11, color:'#64748B', marginTop:2 }}>
          Puis cliquez <strong style={{ color:'#3B82F6' }}>Analyser</strong> pour lancer le scénario complet.
        </div>
      </div>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────
export default function KadastraAgent() {
  const [open,       setOpen]       = useState(false);
  const [messages,   setMessages]   = useState([{ role:'bot', content:'welcome' }]);
  const [input,      setInput]      = useState('');
  const [loading,    setLoading]    = useState(false);
  const [showMenu,   setShowMenu]   = useState(false);
  const [activeForm, setActiveForm] = useState(null);  // 'property' | 'profile'
  const [expertMode, setExpertMode] = useState(false); // false = Normal, true = Expert

  const [selectedDeal,     setSelectedDeal]     = useState(null);  // deal modal

  const [attachedListing,  setAttachedListing]  = useState(null);
  const [attachedProperty, setAttachedProperty] = useState(null);
  const [attachedProfile,  setAttachedProfile]  = useState(null);
  const [propDraft,        setPropDraft]         = useState({ ...BLANK_PROPERTY });
  const [profileDraft,     setProfileDraft]      = useState({ ...BLANK_PROFILE });

  const endRef = useRef(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior:'smooth' }); }, [messages]);

  // Listen for listing attach from ListingCard "📊 IA" button
  useEffect(() => {
    const handler = (e) => {
      setAttachedListing(e.detail);
      setAttachedProperty(null);
      setOpen(true);
      setMessages(prev => [...prev, { role:'bot', content:'listing-attached', data: e.detail }]);
    };
    window.addEventListener('kadastra-attach-listing', handler);
    return () => window.removeEventListener('kadastra-attach-listing', handler);
  }, []);

  const openProp    = () => { setActiveForm('property'); setShowMenu(false); };
  const openProfile = () => { setActiveForm('profile');  setShowMenu(false); };
  const confirmProp = () => {
    if (!propDraft.price_numeric) return;
    setAttachedProperty(propertyFormToPayload(propDraft));
    setAttachedListing(null);
    setActiveForm(null);
  };
  const confirmProfile = () => {
    setAttachedProfile(profileFormToPayload(profileDraft));
    setActiveForm(null);
  };

  const effectiveProperty = attachedListing
    ? listingToProperty(attachedListing)
    : attachedProperty;

  const sendMessage = async () => {
    const text   = input.trim();
    const hasProp    = !!effectiveProperty;
    const hasProfile = !!attachedProfile;
    if (!text && !hasProp) return;
    if (loading) return;

    // Guided mode (no API)
    if (text && isGuideRequest(text) && !hasProp) {
      setInput('');
      setMessages(prev => [...prev, { role:'user', content:text }]);
      setMessages(prev => [...prev, { role:'bot',  content:'guide' }]);
      return;
    }

    // Explanation request — find last result message and explain it locally (no API)
    if (text && isExplainRequest(text)) {
      const lastResult = [...messages].reverse().find(m => m.content === 'result');
      if (lastResult) {
        setInput('');
        setMessages(prev => [...prev,
          { role:'user', content: text },
          { role:'bot',  content:'explanation', data: lastResult.data },
        ]);
        return;
      }
    }

    setInput('');
    if (text) setMessages(prev => [...prev, { role:'user', content:text }]);
    setLoading(true);

    try {
      // ── Chat intent (deal search / market / portfolio) ──
      if (text && !hasProp && isChatIntent(text)) {
        const resp = await fetch(`${API_BASE}/api/chat`, {
          method:'POST', headers:{ 'Content-Type':'application/json' },
          body: JSON.stringify({ text }),
        });
        const raw = await resp.json();
        if (!resp.ok) throw new Error(raw.detail || 'Chat failed');
        setMessages(prev => [...prev, { role:'bot', content:'chat', data: raw }]);
        setLoading(false);
        return;
      }

      // ── Investment analysis ──
      const defaultProfile = {
        budget:300000, holding_period_years:7, rental_income:0,
        first_time_buyer:true, is_new_promoter:false, risk_tolerance:'medium',
      };

      let data;
      if (hasProp) {
        const resp = await fetch(`${API_BASE}/api/analyze`, {
          method:'POST', headers:{ 'Content-Type':'application/json' },
          body: JSON.stringify({
            property: effectiveProperty,
            profile:  hasProfile ? attachedProfile : defaultProfile,
          }),
        });
        const raw = await resp.json();
        if (!resp.ok) {
          // If validation error — format nicely
          if (raw.detail?.type === 'validation_error') {
            setMessages(prev => [...prev, {
              role:'bot', content:'validation-error',
              data: raw.detail,
            }]);
            setLoading(false);
            return;
          }
          throw new Error(raw.detail || 'Analyse échouée');
        }
        data = transformFullScenario(raw);
      } else {
        const resp = await fetch(`${API_BASE}/api/quick-analyze`, {
          method:'POST', headers:{ 'Content-Type':'application/json' },
          body: JSON.stringify({ text }),
        });
        const raw = await resp.json();
        if (!resp.ok) {
          if (raw.detail?.type === 'validation_error') {
            setMessages(prev => [...prev, {
              role:'bot', content:'validation-error',
              data: raw.detail,
            }]);
            setLoading(false);
            return;
          }
          throw new Error(raw.detail || 'Analyse échouée');
        }
        data = raw;
      }

      setMessages(prev => [...prev, { role:'bot', content:'result', data }]);
    } catch (err) {
      setMessages(prev => [...prev, { role:'bot', content:'error', data:{ message:err.message } }]);
    }
    setLoading(false);
  };

  const handleKey = (e) => {
    if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const renderMessage = (msg, idx) => {
    if (msg.role === 'user') return <div key={idx} style={S.msgUser}>{msg.content}</div>;

    switch (msg.content) {
      case 'welcome':
        return <WelcomeCard key={idx} onOpenProp={openProp} onOpenProfile={openProfile}/>;
      case 'guide':
        return <GuideCard key={idx} onOpenProp={openProp} onOpenProfile={openProfile}/>;

      case 'listing-attached': {
        const pa = msg.data.price_analysis;
        const PA_CHIP = {
          great:     { bg:'#064e3b', color:'#6ee7b7' },
          fair:      { bg:'#1e3a8a', color:'#93c5fd' },
          high:      { bg:'#7c2d12', color:'#fdba74' },
          very_high: { bg:'#881337', color:'#fda4af' },
        };
        const chip = pa ? (PA_CHIP[pa.label] || PA_CHIP.fair) : null;
        return (
          <div key={idx} style={S.msgBot}>
            <span style={{ color:'#93C5FD', fontWeight:700 }}>📎 Annonce attachée</span>
            <div style={{ fontSize:12, color:'#94A3B8', marginTop:5 }}>
              <strong style={{ color:'#E2E8F0' }}>{msg.data.titre || msg.data.Type || '—'}</strong>
              {(msg.data.adresse||msg.data.Adresse) && <><br/>{msg.data.adresse||msg.data.Adresse}</>}
              {msg.data.prix && <> · <strong style={{ color:'#3B82F6' }}>{msg.data.prix}</strong></>}
            </div>
            {pa && (
              <div style={{ marginTop:8, background:'#0F172A', borderRadius:8, padding:'8px 10px' }}>
                <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:4 }}>
                  <span style={{ fontSize:10, color:'#64748B', fontWeight:700 }}>ANALYSE DE PRIX · IA</span>
                  <span style={{
                    background: chip.bg, color: chip.color,
                    borderRadius:99, padding:'2px 8px', fontSize:10, fontWeight:700,
                  }}>{pa.label_fr}</span>
                </div>
                <div style={{ display:'flex', justifyContent:'space-between', fontSize:11 }}>
                  <span style={{ color:'#94A3B8' }}>Prix estimé marché</span>
                  <span style={{ color:'#E2E8F0', fontWeight:700 }}>
                    ~{pa.predicted_price.toLocaleString('fr-TN')} TND
                  </span>
                </div>
                <div style={{ display:'flex', justifyContent:'space-between', fontSize:11, marginTop:2 }}>
                  <span style={{ color:'#94A3B8' }}>Écart</span>
                  <span style={{ fontWeight:700, color: pa.delta_pct > 20 ? '#F87171' : pa.delta_pct < -10 ? '#4ADE80' : '#94A3B8' }}>
                    {pa.delta_pct > 0 ? '+' : ''}{pa.delta_pct}%
                  </span>
                </div>
              </div>
            )}
            <div style={{ fontSize:11, color:'#64748B', marginTop:6 }}>
              Cliquez <strong style={{ color:'#3B82F6' }}>Analyser</strong>, ou précisez budget / durée avant.
            </div>
          </div>
        );
      }

      case 'result':
        return expertMode
          ? <ExpertResultCard key={idx} data={msg.data}/>
          : <NormalResultCard key={idx} data={msg.data}/>;

      case 'explanation':
        return <ExplanationCard key={idx} data={msg.data}/>;

      case 'chat': {
        const d = msg.data;
        if (d.type === 'deal_search')
          return <DealSearchCard key={idx} data={{ ...d.data, llm_comment: d.llm_comment }}
            onSelectDeal={(deal) => setSelectedDeal(dealToListing(deal))}/>;
        if (d.type === 'market_analysis')
          return <MarketAnalysisCard key={idx} data={{ ...d.data, llm_comment: d.llm_comment }}/>;
        if (d.type === 'portfolio_advice')
          return <PortfolioAdviceCard key={idx} data={d.data}/>;
        // general
        return (
          <div key={idx} style={S.msgBot}>
            {(d.data?.message || '').split('\n').map((line, i) => (
              <div key={i} style={{ marginBottom:4 }}
                dangerouslySetInnerHTML={{ __html: line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }}/>
            ))}
          </div>
        );
      }

      case 'validation-error': return (
        <div key={idx} style={{ ...S.msgBot, borderLeft:'3px solid #EF4444' }}>
          <strong style={{ color:'#FCA5A5', fontSize:13 }}>⛔ Saisie invalide</strong>
          {(msg.data.errors||[]).map((e,i) =>
            <div key={i} style={{ color:'#FCA5A5', fontSize:12, marginTop:4 }}>• {e}</div>
          )}
          {(msg.data.warnings||[]).length > 0 && (
            <div style={{ marginTop:8 }}>
              {(msg.data.warnings||[]).map((w,i) =>
                <div key={i} style={{ color:'#FDE68A', fontSize:12, marginTop:3 }}>⚠️ {w}</div>
              )}
            </div>
          )}
          <div style={{ color:'#64748B', fontSize:11, marginTop:8 }}>
            Vérifiez le prix, la surface et la localisation puis réessayez.
          </div>
        </div>
      );

      case 'error': return (
        <div key={idx} style={{ ...S.msgBot, borderLeft:'3px solid #DC2626' }}>
          <strong style={{ color:'#FCA5A5' }}>Erreur</strong>
          <p style={{ margin:'4px 0 0', color:'#E2E8F0', fontSize:12 }}>{msg.data.message}</p>
        </div>
      );

      default:
        return <div key={idx} style={S.msgBot}>{msg.content}</div>;
    }
  };

  const hasAttachment = !!effectiveProperty || !!attachedProfile;

  return (
    <>
      {/* Deal detail modal — rendered as top-level sibling to avoid panel overflow clipping */}
      {selectedDeal && (
        <ListingModal listing={selectedDeal} onClose={() => setSelectedDeal(null)}/>
      )}

      {/* Floating bubble */}
      <button style={S.bubble} onClick={() => setOpen(o => !o)}
        onMouseEnter={e=>e.currentTarget.style.transform='scale(1.1)'}
        onMouseLeave={e=>e.currentTarget.style.transform='scale(1)'}
        title="Kadastra AI Agent">
        {open
          ? <span style={{ fontSize: 22, lineHeight: 1 }}>✕</span>
          : <img src="/kadastra-logo.png" alt="Kadastra" style={{ width: 36, height: 36, objectFit: 'contain', filter: 'brightness(0) invert(1)' }}/>
        }
      </button>

      {open && (
        <div style={S.panel}>
          {/* Header */}
          <div style={S.header}>
            <div>
              <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                <img src="/kadastra-logo.png" alt="Kadastra" style={{ height:30, width:'auto', objectFit:'contain', filter:'brightness(0) invert(1)' }}/>
                <div>
                  <p style={{ color:'#E2E8F0', fontSize:15, fontWeight:700, margin:0 }}>Kadastra Agent</p>
                  <p style={{ color:'#94A3B8', fontSize:10, margin:0 }}>Analyse d'investissement immobilier TN</p>
                </div>
              </div>
            </div>
            {/* Mode toggle */}
            <div style={{ display:'flex', alignItems:'center', gap:7 }}>
              <span style={{ fontSize:11, color: expertMode?'#64748B':'#94A3B8', fontWeight: expertMode?400:600 }}>
                Normal
              </span>
              <Toggle value={expertMode} onChange={setExpertMode}/>
              <span style={{ fontSize:11, color: expertMode?'#3B82F6':'#64748B', fontWeight: expertMode?700:400 }}>
                Expert
              </span>
              <button onClick={() => setOpen(false)}
                style={{ background:'none', border:'none', color:'#94A3B8', cursor:'pointer', fontSize:18, marginLeft:6 }}>✕</button>
            </div>
          </div>

          {/* Mode badge */}
          {expertMode && (
            <div style={{ background:'#1E3A5F', padding:'4px 14px', fontSize:10, color:'#93C5FD',
              fontWeight:700, letterSpacing:'0.06em', borderBottom:'1px solid #0F172A' }}>
              MODE EXPERT · Métriques complètes · IRR sweep · Monte Carlo
            </div>
          )}

          {/* Messages */}
          <div style={S.messages}>
            {messages.map(renderMessage)}
            {loading && (
              <div style={{ display:'flex', alignItems:'center', gap:8, color:'#94A3B8', fontSize:13 }}>
                <span className="kadastra-spinner"/>
                {effectiveProperty
                  ? 'Calcul du scénario d\'investissement…'
                  : 'Recherche en cours…'}
              </div>
            )}
            <div ref={endRef}/>
          </div>

          {/* Attachment chips */}
          {hasAttachment && (
            <div style={{ padding:'6px 14px 0', display:'flex', flexWrap:'wrap' }}>
              {effectiveProperty && (
                <span style={S.chip}>
                  🏠 {effectiveProperty.Type?.split(' ')[0]}
                  {effectiveProperty.price_numeric
                    ? ` · ${Number(effectiveProperty.price_numeric).toLocaleString('fr-TN')} TND` : ''}
                  <button style={S.chipRemove}
                    onClick={() => { setAttachedListing(null); setAttachedProperty(null); }}>×</button>
                </span>
              )}
              {attachedProfile && (
                <span style={S.chip}>
                  👤 {attachedProfile.holding_period_years}ans · {attachedProfile.risk_tolerance}
                  <button style={S.chipRemove} onClick={() => setAttachedProfile(null)}>×</button>
                </span>
              )}
            </div>
          )}

          {/* Input row */}
          <div style={S.inputRow}>
            {showMenu && (
              <div style={S.attachMenu}>
                {[
                  { icon:'🏠', label:'Détails de la propriété', sub:'Type, prix, surface, équipements…', fn:openProp },
                  { icon:'👤', label:'Profil investisseur',      sub:'Budget, durée, tolérance au risque…', fn:openProfile },
                ].map(({ icon, label, sub, fn }) => (
                  <div key={label} style={S.menuItem}
                    onMouseEnter={e=>e.currentTarget.style.background='#0F172A'}
                    onMouseLeave={e=>e.currentTarget.style.background='transparent'}
                    onClick={fn}>
                    <span style={{ fontSize:18 }}>{icon}</span>
                    <div>
                      <div style={{ fontWeight:600, fontSize:13 }}>{label}</div>
                      <div style={{ fontSize:11, color:'#64748B' }}>{sub}</div>
                    </div>
                  </div>
                ))}
                <div style={{ ...S.menuItem, borderBottom:'none', color:'#64748B', fontSize:11, cursor:'default' }}>
                  📋 Ou cliquez <strong style={{ color:'#93C5FD' }}>Ask AI</strong> sur une annonce
                </div>
              </div>
            )}

            <button style={S.attachBtn} title="Joindre propriété ou profil"
              onClick={() => setShowMenu(s => !s)}>+</button>

            <textarea style={S.textarea} rows={1} value={input}
              onChange={e => setInput(e.target.value)} onKeyDown={handleKey}
              placeholder={effectiveProperty
                ? 'Précisez budget, durée… ou envoyez directement'
                : 'Décrivez un bien, cherchez des affaires, analysez un marché…'}
            />

            <button style={{ ...S.sendBtn, opacity: loading?0.5:1 }}
              onClick={sendMessage} disabled={loading}>
              {effectiveProperty ? 'Analyser' : 'Envoyer'}
            </button>
          </div>

          {/* Form overlays */}
          {activeForm==='property' && (
            <PropertyForm form={propDraft} setForm={setPropDraft}
              onConfirm={confirmProp} onCancel={() => setActiveForm(null)}/>
          )}
          {activeForm==='profile' && (
            <ProfileForm form={profileDraft} setForm={setProfileDraft}
              onConfirm={confirmProfile} onCancel={() => setActiveForm(null)}/>
          )}
        </div>
      )}

      <style>{`
        .kadastra-spinner {
          width:15px; height:15px; border:2px solid #334155;
          border-top-color:#3B82F6; border-radius:50%;
          animation:kspin 0.8s linear infinite; display:inline-block;
        }
        @keyframes kspin { to { transform:rotate(360deg); } }
      `}</style>
    </>
  );
}
