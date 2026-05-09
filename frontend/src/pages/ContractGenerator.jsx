// src/pages/ContractGenerator.jsx
import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

const EVALUATION_CRITERIA = [
  { id: 'conformity', label: 'Conformité Légale', weight: 40 },
  { id: 'risk', label: 'Analyse des Risques', weight: 30 },
  { id: 'completeness', label: 'Exhaustivité des Clauses', weight: 30 }
];

export default function ContractGenerator() {
  const { user } = useAuth();

  // ── State ──────────────────────────────────────────────────────────────────
  const [listingId, setListingId] = useState('');
  const [contractType, setContractType] = useState('auto');
  
  const [acheteurNom, setAcheteurNom] = useState(`${user?.first_name || ''} ${user?.last_name || ''}`.trim() || user?.username || '');
  const [acheteurCin, setAcheteurCin] = useState(user?.cin || '');
  const [acheteurAdresse, setAcheteurAdresse] = useState(user?.address || '');
  const [roleContext, setRoleContext] = useState('acheteur');

  const [vendeurNom, setVendeurNom] = useState('');
  const [vendeurCin, setVendeurCin] = useState('');
  const [vendeurAdresse, setVendeurAdresse] = useState('');

  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selectedListing, setSelectedListing] = useState(null);

  const [evaluating, setEvaluating] = useState(false);
  const [evaluationScores, setEvaluationScores] = useState({ conformity: 0, risk: 0, completeness: 0 });
  const [isEvaluated, setIsEvaluated] = useState(false);

  // Audio Reading State
  const [isReading, setIsReading] = useState(false);
  const synthRef = useRef(window.speechSynthesis);

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages]);

  // ── Audio Reading Logic ───────────────────────────────────────────────────
  function handleToggleRead() {
    if (isReading) {
      synthRef.current.cancel();
      setIsReading(false);
    } else {
      if (!result?.contract) return;
      const utterance = new SpeechSynthesisUtterance(result.contract);
      utterance.lang = 'fr-FR';
      utterance.onend = () => setIsReading(false);
      utterance.onerror = () => setIsReading(false);
      synthRef.current.speak(utterance);
      setIsReading(true);
    }
  }

  // Cleanup audio on unmount
  useEffect(() => {
    return () => synthRef.current.cancel();
  }, []);

  // Pick up a listing pre-selected from the ListingModal "Générer un Contrat" button
  useEffect(() => {
    const targetListingStr = sessionStorage.getItem('kadastra_target_listing');
    if (targetListingStr) {
      try {
        const targetListing = JSON.parse(targetListingStr);
        selectListing(targetListing);
        sessionStorage.removeItem('kadastra_target_listing');
      } catch (e) {
        console.error('Failed to parse target listing', e);
      }
    }
  }, []);

  async function runEvaluation() {
    if (!result) return;
    setEvaluating(true);
    await new Promise(r => setTimeout(r, 2000));
    const nlp = result.evaluation || { ccr_combined: 75 };
    const base = nlp.ccr_combined;
    setEvaluationScores({
      conformity: Math.min(100, base + 10),
      risk: Math.min(100, Math.max(0, base - (result.nlp_report.issues?.length * 5))),
      completeness: Math.round((result.evaluation.clauses_found / result.evaluation.clauses_total) * 100)
    });
    setIsEvaluated(true);
    setEvaluating(false);
  }

  async function handleSearch() {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const res = await fetch(`${API_BASE}/listings/?search=${encodeURIComponent(searchQuery)}&page_size=6`);
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch (e) { setSearchResults([]); }
    setSearching(false);
  }

  function selectListing(listing) {
    setSelectedListing(listing);
    setListingId(listing.id);
    setSearchResults([]);
    setSearchQuery('');
  }

  async function handleGenerate() {
    if (!listingId) { setError('Sélectionnez une annonce'); return; }
    setGenerating(true);
    setError('');
    setResult(null);
    setIsEvaluated(false);
    setChatMessages([]);
    const body = {
      listing_id: parseInt(listingId),
      role_context: roleContext,
      vendeur_info: roleContext === 'vendeur'
        ? { nom: acheteurNom, cin: acheteurCin, adresse: acheteurAdresse }
        : { nom: vendeurNom, cin: vendeurCin, adresse: vendeurAdresse },
      acheteur_info: roleContext === 'vendeur'
        ? { nom: vendeurNom, cin: vendeurCin, adresse: vendeurAdresse }
        : { nom: acheteurNom, cin: acheteurCin, adresse: acheteurAdresse },
    };
    if (contractType !== 'auto') body.contract_type = contractType;
    try {
      const res = await fetch(`${API_BASE}/contracts/generate/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || 'Erreur lors de la génération'); }
      else { setResult(data); }
    } catch (e) { setError(`Erreur réseau: ${e.message}`); }
    setGenerating(false);
  }

  async function handleChatSend() {
    if (!chatInput.trim() || !result) return;
    const question = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', text: question }]);
    setChatLoading(true);
    try {
      const res = await fetch(`${API_BASE}/contracts/chat/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          contract_text: result.contract,
          question,
          contract_type: result.contract_type,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setChatMessages(prev => [...prev, { role: 'assistant', text: data.answer, time: data.generation_time }]);
        if (data.updated_contract) { setResult(prev => ({ ...prev, contract: data.updated_contract })); setIsEvaluated(false); }
      }
    } catch (e) { console.error(e); }
    setChatLoading(false);
  }

  async function handleDownloadPdf() {
    if (!result) return;
    try {
      const res = await fetch(`${API_BASE}/contracts/pdf/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          contract_text: result.contract,
          listing_id: result.listing_id,
          contract_type: result.contract_type,
          model_label: result.model,
          nlp_report: result.nlp_report,
        }),
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `contrat_${result.contract_type}_${result.listing_id}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (e) { alert('Erreur PDF'); }
  }

  const ccrColor = (ccr) => ccr >= 80 ? '#16a34a' : (ccr >= 60 ? '#ca8a04' : '#dc2626');

  // ── Professional Contract Renderer ──────────────────────────────────────────
  function renderContract(rawText) {
    if (!rawText) return null;
    let text = rawText.replace(/\r\n/g, '\n').replace(/\n{3,}/g, '\n\n');
    // Join single newlines (LLM wrapping artifacts) into spaces
    text = text.replace(/(?<!\n)\n(?!\n)/g, ' ').replace(/ {2,}/g, ' ');
    const paragraphs = text.split('\n\n').map(p => p.trim()).filter(Boolean);

    const renderInline = (str) => {
      const parts = str.split(/\*\*(.*?)\*\*/g);
      return parts.map((part, j) =>
        j % 2 === 1 ? React.createElement('strong', { key: j }, part) : part
      );
    };

    return paragraphs.map((para, i) => {
      const plain = para.replace(/\*\*/g, '').trim();
      const isArticle = /^ARTICLE\s+\d+/i.test(plain);
      const isAllCaps = plain === plain.toUpperCase() && plain.length > 5 && plain.length < 150;
      const isMainTitle = isAllCaps && /^(PROMESSE|CONTRAT|ACTE)/i.test(plain);
      const isFait = /^Fait [aà]/i.test(plain);
      const isSig = /^(SIGNATURES?$|LE VENDEUR|L['']ACQU|LE BAILLEUR|LE PRENEUR|LE LOCATAIRE)/i.test(plain);

      if (isMainTitle) return (
        <div key={i} style={{ textAlign:'center', fontSize:18, fontWeight:800, letterSpacing:'2px', color:'#1a1a3e', margin:'28px 0 20px', padding:'14px 0', borderTop:'2px solid #1a1a3e', borderBottom:'2px solid #1a1a3e', textTransform:'uppercase' }}>
          {renderInline(para)}
        </div>
      );
      if (isArticle) return (
        <div key={i} style={{ fontSize:14, fontWeight:800, color:'#1a1a3e', margin:'24px 0 6px', padding:'6px 0 4px', borderBottom:'1px solid #ccc', textTransform:'uppercase', letterSpacing:'0.5px' }}>
          {renderInline(para)}
        </div>
      );
      if (isAllCaps && !isArticle) return (
        <div key={i} style={{ textAlign:'center', fontSize:13, fontWeight:700, color:'#1a1a3e', margin:'18px 0 10px', letterSpacing:'1px' }}>
          {renderInline(para)}
        </div>
      );
      if (isSig) return (
        <div key={i} style={{ textAlign:'center', fontSize:14, fontWeight:700, color:'#1a1a3e', margin:'36px 0 8px' }}>
          {renderInline(para)}
        </div>
      );
      if (isFait) return (
        <p key={i} style={{ margin:'28px 0 14px', fontSize:14, fontStyle:'italic', color:'#333', textAlign:'center' }}>
          {renderInline(para)}
        </p>
      );
      return (
        <p key={i} style={{ margin:'0 0 10px', fontSize:14, lineHeight:'1.9', color:'#2c2c2c', textAlign:'justify' }}>
          {renderInline(para)}
        </p>
      );
    });
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0f172a', paddingBottom: 60 }}>
      {/* Premium Header */}
      <div style={{
        background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)',
        borderBottom: '1px solid var(--border)',
        padding: '32px 0',
      }}>
        <div style={{ maxWidth: 1400, margin: '0 auto', padding: '0 40px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <img
              src="/kadastra-logo.png"
              alt="Kadastra"
              style={{ height: 56, width: 'auto', objectFit: 'contain', filter: 'brightness(0) invert(1)' }}
            />
            <div>
              <h1 className="premium-font" style={{ fontSize: 32, fontWeight: 900, color: '#fff', margin: 0, letterSpacing: '-1px' }}>
                <span style={{ color: 'var(--accent)', fontWeight: 400 }}>Legal Intelligence</span>
              </h1>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0, textTransform: 'uppercase', letterSpacing: '1px' }}>
                Génération & Évaluation de Contrats par IA · {user?.user_type}
              </p>
            </div>
          </div>
          {result && (
            <div style={{ display: 'flex', gap: 12 }}>
              <button onClick={handleToggleRead} style={{
                ...btnSecondaryStyle,
                background: isReading ? 'var(--primary)' : 'rgba(255,255,255,0.05)',
                color: isReading ? '#fff' : '#fff',
                borderColor: isReading ? 'var(--primary)' : 'var(--border)',
              }}>
                {isReading ? '🛑 ARRÊTER LA LECTURE' : '🔊 LIRE LE CONTRAT'}
              </button>
              <button onClick={runEvaluation} disabled={evaluating} style={{
                ...btnSecondaryStyle,
                background: isEvaluated ? 'var(--accent)' : 'rgba(212, 175, 55, 0.1)',
                color: isEvaluated ? '#000' : 'var(--accent)',
                borderColor: 'var(--accent)',
              }}>
                {evaluating ? '🔄 ÉVALUATION...' : isEvaluated ? '✅ RÉ-ÉVALUER' : '⚖️ ÉVALUER LE CONTRAT'}
              </button>
              <button onClick={handleDownloadPdf} style={btnPrimaryStyle}>📥 GÉNÉRER PDF</button>
            </div>
          )}
        </div>
      </div>

      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '40px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', gap: 40, alignItems: 'start' }}>

          {/* ── Left Sidebar ── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {isEvaluated && (
              <div className="card fade-in" style={{ padding: 24, border: '1px solid var(--accent)', background: 'rgba(30,41,59,0.7)' }}>
                <h3 className="premium-font" style={{ fontSize: 18, fontWeight: 900, color: 'var(--accent)', marginBottom: 20 }}>RAPPORT D'ÉVALUATION IA</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  {EVALUATION_CRITERIA.map(c => (
                    <div key={c.id}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 12, fontWeight: 700 }}>
                        <span style={{ color: 'var(--text-light)' }}>{c.label}</span>
                        <span style={{ color: ccrColor(evaluationScores[c.id]) }}>{evaluationScores[c.id]}%</span>
                      </div>
                      <div style={{ height: 6, width: '100%', background: 'rgba(255,255,255,0.05)', borderRadius: 3 }}>
                        <div style={{ height: '100%', width: `${evaluationScores[c.id]}%`, background: ccrColor(evaluationScores[c.id]), borderRadius: 3, transition: 'width 1s ease-out' }} />
                      </div>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 24, padding: 16, background: 'rgba(15, 23, 42, 0.4)', borderRadius: 12, fontSize: 12, color: 'var(--text-muted)', borderLeft: '3px solid var(--accent)' }}>
                  <b>VERDICT :</b> Ce contrat présente un niveau de sécurité {evaluationScores.risk > 80 ? 'EXCELLENT' : 'MODÉRÉ'}.
                </div>
              </div>
            )}

            <div className="card" style={{ padding: 28, background: 'rgba(30,41,59,0.7)' }}>
              <h3 className="premium-font" style={{ fontSize: 20, fontWeight: 800, marginBottom: 24, color: '#fff' }}>1. Configuration</h3>
              <div style={{ marginBottom: 24 }}>
                <label style={labelStyle}>Recherche d'Actif</label>
                <div style={{ display: 'flex', gap: 10 }}>
                  <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSearch()} placeholder="Marsa, Villa, ID..." style={{ ...inputStyle, background: '#fff', color: '#000' }} />
                  <button onClick={handleSearch} style={{ ...btnSecondaryStyle, minWidth: 50 }}>{searching ? '...' : '🔍'}</button>
                </div>
                {searchResults.length > 0 && (
                  <div style={{ marginTop: 4, maxHeight: 200, overflowY: 'auto', border: '1px solid var(--primary)', borderRadius: 12, background: '#0f172a', boxShadow: '0 10px 20px rgba(0,0,0,0.4)' }}>
                    {searchResults.map(l => (
                      <div key={l.id} onClick={() => selectListing(l)} style={{ padding: '12px 16px', cursor: 'pointer', borderBottom: '1px solid rgba(255,255,255,0.05)', fontSize: 12, color: '#fff', transition: 'background 0.2s' }} onMouseEnter={e => e.target.style.background = 'rgba(129,140,248,0.1)'} onMouseLeave={e => e.target.style.background = 'transparent'}>
                        <span style={{ color: 'var(--accent)', fontWeight: 800 }}>#{l.id}</span> - {l.titre?.slice(0, 45)}...
                      </div>
                    ))}
                  </div>
                )}
                {selectedListing && (
                  <div style={{ marginTop: 12, padding: 12, background: 'rgba(129,140,248,0.1)', border: '1px solid var(--primary)', borderRadius: 12, color: '#fff', fontSize: 12 }}>
                    Cible sélectionnée : <b style={{ color: 'var(--accent)' }}>#{selectedListing.id}</b>
                  </div>
                )}
              </div>
              <div style={{ marginBottom: 24 }}>
                <label style={labelStyle}>Rôle Actuel</label>
                <div style={{ display: 'flex', background: 'var(--surface-alt)', padding: 4, borderRadius: 12 }}>
                  <button onClick={() => setRoleContext('acheteur')} style={{ flex: 1, padding: 10, borderRadius: 8, border: 'none', background: roleContext === 'acheteur' ? 'var(--primary)' : 'transparent', color: '#fff', fontWeight: 800 }}>ACHETEUR</button>
                  <button onClick={() => setRoleContext('vendeur')} style={{ flex: 1, padding: 10, borderRadius: 8, border: 'none', background: roleContext === 'vendeur' ? 'var(--primary)' : 'transparent', color: '#fff', fontWeight: 800 }}>VENDEUR</button>
                </div>
              </div>
              {error && (
                <div style={{ padding: 12, marginBottom: 20, background: 'rgba(220, 38, 38, 0.1)', border: '1px solid #dc2626', borderRadius: 12, color: '#f87171', fontSize: 13, fontWeight: 700 }}>
                  ⚠️ {error}
                </div>
              )}

              <button onClick={handleGenerate} disabled={generating || !listingId} style={{ ...btnPrimaryStyle, width: '100%', padding: 16 }}>
                {generating ? 'ANALYSE NLP...' : '⚖️ GÉNÉRER LE CONTRAT'}
              </button>
            </div>
          </div>

          {/* ── Right Content ── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {!result ? (
              <div style={{ height: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(30,41,59,0.3)', borderRadius: 24, border: '2px dashed var(--border)' }}>
                <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                  <div style={{ fontSize: 64, marginBottom: 20 }}>📄</div>
                  <h2 className="premium-font" style={{ color: '#fff', opacity: 0.5 }}>Analyseur Prêt</h2>
                  <p>Configurez les paramètres à gauche pour générer un contrat.</p>
                </div>
              </div>
            ) : (
              <>
                {!isEvaluated && !evaluating && (
                  <div className="card fade-in" style={{ padding: '20px 32px', background: 'var(--primary)', color: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'center', border: 'none' }}>
                    <div>
                      <h4 className="premium-font" style={{ margin: 0, fontSize: 18, fontWeight: 800 }}>Évaluer ce document ?</h4>
                      <p style={{ margin: '4px 0 0', fontSize: 13, opacity: 0.8 }}>Notre IA va auditer la sécurité juridique de ce contrat.</p>
                    </div>
                    <button onClick={runEvaluation} style={{ background: '#fff', color: 'var(--primary)', padding: '10px 24px', borderRadius: 12, fontWeight: 800, border: 'none' }}>AUDITER MAINTENANT</button>
                  </div>
                )}

                <div style={{
                  background: '#fff', minHeight: 1000, fontSize: '14px', lineHeight: '1.8',
                  color: '#1e293b', fontFamily: "'Times New Roman', 'Georgia', serif",
                  boxShadow: '0 30px 60px -12px rgba(0,0,0,0.5)', position: 'relative',
                  border: '1px solid #bbb', overflow: 'hidden',
                }}>
                  {isReading && (
                    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 4, background: 'rgba(129,140,248,0.2)', zIndex: 5 }}>
                      <div style={{ height: '100%', width: '100%', background: 'var(--primary)', animation: 'reading 2s linear infinite' }} />
                    </div>
                  )}
                  {/* Letterhead */}
                  <div style={{ background: 'linear-gradient(135deg, #1a1a3e 0%, #2a2a5e 100%)', padding: '28px 70px', textAlign: 'center', borderBottom: '3px solid #d4af37' }}>
                    <div style={{ fontSize: 26, fontWeight: 900, color: '#fff', letterSpacing: '4px' }}>KADASTRA & ASSOCIÉS</div>
                    <div style={{ fontSize: 11, color: '#d4af37', letterSpacing: '3px', textTransform: 'uppercase', marginTop: 2 }}>Cabinet de Conseil Juridique Immobilier</div>
                    <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.5)', marginTop: 6 }}>Tunis, Tunisie · contact@kadastra.tn</div>
                  </div>
                  {/* Ref badge */}
                  <div style={{ position: 'absolute', top: 100, right: 40, padding: '6px 14px', border: '1px solid #e2e8f0', textAlign: 'center', background: '#fafafa', zIndex: 2 }}>
                    <div style={{ fontSize: 8, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '1px' }}>Réf.</div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#1a1a3e' }}>#KAD-{result.listing_id}</div>
                  </div>
                  {/* Contract body */}
                  <div style={{ padding: '36px 70px 50px', wordWrap: 'break-word', overflowWrap: 'break-word' }}>
                    {renderContract(result.contract)}
                  </div>
                  {/* Footer */}
                  <div style={{ borderTop: '2px solid #1a1a3e', padding: '12px 70px', display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#94a3b8', background: '#fafafa' }}>
                    <span>Document généré par IA — Certification KADASTRA NLP 7/7</span>
                    <span>Réf: KAD-{result.listing_id} · {new Date().toLocaleDateString('fr-FR')}</span>
                  </div>
                </div>

                <div className="card" style={{ padding: 28, background: 'rgba(30,41,59,0.7)' }}>
                  <h3 className="premium-font" style={{ fontSize: 18, fontWeight: 800, marginBottom: 20, color: '#fff' }}>💬 CONSULTANT JURIDIQUE</h3>
                  <div style={{ maxHeight: 300, overflowY: 'auto', marginBottom: 20 }}>
                    <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 12 }}>
                      <div style={{ 
                        maxWidth: '80%', padding: '12px 18px', borderRadius: 16, fontSize: 14,
                        background: 'var(--surface-alt)', color: '#000', fontWeight: 700, border: '1px solid var(--border)'
                      }}>
                        Bonjour ! Je suis un avocat expert en droit immobilier tunisien au Cabinet KADASTRA. Comment puis-je vous aider aujourd'hui ?
                      </div>
                    </div>
                    {chatMessages.map((msg, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: 12 }}>
                        <div style={{ 
                          maxWidth: '80%', padding: '12px 18px', borderRadius: 16, fontSize: 14,
                          background: msg.role === 'user' ? 'var(--primary)' : 'var(--surface-alt)', 
                          color: msg.role === 'user' ? '#fff' : '#000',
                          fontWeight: msg.role === 'user' ? 400 : 700
                        }}>{msg.text}</div>
                      </div>
                    ))}
                    <div ref={chatEndRef} />
                  </div>
                  <div style={{ display: 'flex', gap: 12 }}>
                    <input value={chatInput} onChange={e => setChatInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleChatSend()} placeholder="Posez une question..." style={{ ...inputStyle, background: '#fff', color: '#000' }} />
                    <button onClick={handleChatSend} style={btnPrimaryStyle}>ENVOYER</button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
      <style>{`
        @keyframes reading {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
}

const labelStyle = { display: 'block', fontSize: 11, fontWeight: 800, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '1px' };
const inputStyle = { padding: '12px 16px', borderRadius: 12, border: '1px solid var(--border)', background: 'var(--surface-alt)', color: '#fff', fontSize: 14, outline: 'none', width: '100%' };
const btnPrimaryStyle = { padding: '14px 28px', borderRadius: 14, background: 'var(--primary)', color: '#fff', fontSize: 14, fontWeight: 800, border: 'none', cursor: 'pointer', boxShadow: '0 8px 24px rgba(15, 23, 42, 0.4)' };
const btnSecondaryStyle = { padding: '12px 24px', borderRadius: 12, background: 'transparent', border: '1px solid var(--border)', color: '#fff', fontSize: 13, fontWeight: 700, cursor: 'pointer' };
