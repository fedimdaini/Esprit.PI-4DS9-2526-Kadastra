// src/App.jsx
import React, { useState, useEffect, useCallback, useRef } from 'react';
import Navbar      from './components/Navbar';
import Filters     from './components/Filters';
import ListingCard from './components/ListingCard';
import Pagination  from './components/Pagination';
import ListingModal from './components/ListingModal';
import KadastraAgent from './components/KadastraAgent';
import { fetchListings, fetchStats, fetchFilterOptions } from './services/api';

const PAGE_SIZE  = 12;
const INIT_FILTERS = {
  source: 'all', type_bien: 'all', localisation: 'all',
  min_prix: '', max_prix: '', min_surface: '', max_surface: '',
  chambres: '', search: '', ordering: '-date_post', page: 1,
};

export default function App() {
  const [listings,  setListings]  = useState([]);
  const [total,     setTotal]     = useState(0);
  const [options,   setOptions]   = useState({ types: [], cities: [] });
  const [filters,   setFilters]   = useState(INIT_FILTERS);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState(null);
  const [selected,  setSelected]  = useState(null);
  const abortRef  = useRef(null);

  useEffect(() => {
    fetchFilterOptions().then(setOptions).catch(() => {});
    
    // Listen for global search events from the unified Navbar
    const handleGlobalSearch = (e) => {
      setFilters(f => ({ ...f, search: e.detail, page: 1 }));
    };
    window.addEventListener('kadastra-search', handleGlobalSearch);
    return () => window.removeEventListener('kadastra-search', handleGlobalSearch);
  }, []);

  const loadListings = useCallback(async () => {
    if (abortRef.current) abortRef.current.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setLoading(true);
    setError(null);
    try {
      const data = await fetchListings({ ...filters, page_size: PAGE_SIZE });
      if (!ctrl.signal.aborted) {
        if (Array.isArray(data)) {
          setListings(data);
          setTotal(data.length);
        } else {
          setListings(data.results || []);
          setTotal(data.count || 0);
        }
      }
    } catch (e) {
      if (!ctrl.signal.aborted) setError(e.message);
    } finally {
      if (!ctrl.signal.aborted) setLoading(false);
    }
  }, [filters]);

  useEffect(() => { loadListings(); }, [loadListings]);

  const handleSearch = (q) => setFilters(f => ({ ...f, search: q, page: 1 }));
  const handleReset  = () => setFilters(INIT_FILTERS);

  return (
    <div style={{ background: 'var(--bg)', minHeight: '100vh' }}>
      
      <div className="container" style={{ display: 'flex', gap: 48, padding: '48px 32px' }}>
        <Filters 
          filters={filters} 
          onChange={setFilters} 
          options={options} 
          onReset={handleReset} 
          total={total}
        />

        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Section Header */}
          <div style={{ 
            display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
            marginBottom: 32, paddingBottom: 16, borderBottom: '1.5px solid var(--border-light)' 
          }}>
            <div>
              <h1 className="premium-font" style={{ fontSize: 28, fontWeight: 800, color: 'var(--text)', marginBottom: 4, letterSpacing: '-0.5px' }}>
                Exploration Immobilière
              </h1>
              <p style={{ fontSize: 14, color: 'var(--text-muted)', fontWeight: 500 }}>
                {total > 0 ? `Découvrez les ${total.toLocaleString()} meilleures opportunités en Tunisie` : 'Recherche des meilleures opportunités...'}
              </p>
            </div>
            
            <div style={{ display: 'flex', gap: 12 }}>
              <select 
                className="premium-input" 
                style={{ minWidth: 180, fontWeight: 600 }}
                value={filters.ordering}
                onChange={e => setFilters(f => ({ ...f, ordering: e.target.value, page: 1 }))}
              >
                <option value="-date_post">Plus récentes</option>
                <option value="prix">Prix croissant</option>
                <option value="-prix">Prix décroissant</option>
                <option value="-surface">Plus grande surface</option>
              </select>
            </div>
          </div>

          {/* Error State */}
          {error && (
            <div className="card" style={{ padding: 24, background: '#fff1f2', borderColor: '#fecaca', color: '#b91c1c', marginBottom: 32 }}>
               <div style={{ fontWeight: 700, marginBottom: 8 }}>⚠️ Erreur de connexion</div>
               <div style={{ fontSize: 14 }}>Impossible de joindre le serveur. Assurez-vous que le backend Django est actif sur le port 8000.</div>
            </div>
          )}

          {/* Listings Grid */}
          {loading && filters.page === 1 ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 32 }}>
              {[1, 2, 3, 4, 5, 6].map(i => (
                <div key={i} className="card skeleton" style={{ height: 420 }} />
              ))}
            </div>
          ) : listings.length === 0 && !loading ? (
            <div style={{ textAlign: 'center', padding: '100px 0' }}>
              <div style={{ fontSize: 64, marginBottom: 24 }}>🔎</div>
              <h3 className="premium-font" style={{ fontSize: 24, fontWeight: 800, marginBottom: 8 }}>Aucun résultat</h3>
              <p style={{ color: 'var(--text-muted)' }}>Essayez d'élargir vos critères de recherche ou de réinitialiser les filtres.</p>
              <button onClick={handleReset} style={{ marginTop: 24, background: 'var(--primary)', color: '#fff', padding: '12px 32px', borderRadius: 12, fontWeight: 700 }}>Réinitialiser</button>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 32 }}>
              {listings.map(l => (
                <ListingCard key={l.id} listing={l} onClick={() => setSelected(l)} />
              ))}
            </div>
          )}

          {/* Pagination */}
          {!loading && total > PAGE_SIZE && (
            <div style={{ marginTop: 48, display: 'flex', justifyContent: 'center' }}>
              <Pagination 
                current={filters.page} 
                total={total}
                pageSize={PAGE_SIZE}
                onChange={p => {
                  setFilters(f => ({ ...f, page: p }));
                  window.scrollTo({ top: 0, behavior: 'smooth' });
                }} 
              />
            </div>
          )}
        </div>
      </div>

      {/* Modal Overlay */}
      {selected && (
        <ListingModal
          listing={selected}
          onClose={() => setSelected(null)}
        />
      )}

      {/* Kadastra AI Agent floating bubble */}
      <KadastraAgent />

      {/* Footer */}
      <footer style={{ background: '#fff', borderTop: '1px solid var(--border)', padding: '40px 0', marginTop: 80 }}>
        <div className="container" style={{ textAlign: 'center' }}>
          <img
            src="/kadastra-logo.png"
            alt="Kadastra"
            style={{ height: 64, width: 'auto', objectFit: 'contain', marginBottom: 10 }}
          />
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 0 }}>
            © {new Date().getFullYear()} Plateforme immobilière avancée. Tous droits réservés.
          </p>
        </div>
      </footer>
    </div>
  );
}
