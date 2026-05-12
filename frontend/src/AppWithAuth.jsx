// src/AppWithAuth.jsx - Version avec authentification + Contrats
import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LanguageProvider } from './i18n/LanguageContext';
import AuthPage from './pages/Auth';
import Dashboard from './pages/Dashboard';
import ContractGenerator from './pages/ContractGenerator';
import SecurityMap from './pages/SecurityMap';
import Navbar from './components/Navbar';
import App from './App';  // Original app (listings)

function MainRouter() {
  const { user, logout, loading } = useAuth();
  const [view, setView] = useState('listings');  // 'listings', 'dashboard', 'contracts', 'map'

  // ── Hooks must be declared before any conditional returns ──────────────────
  // Listen for navigation events from ListingModal "Générer un Contrat" button
  React.useEffect(() => {
    const handleGotoContract = () => setView('contracts');
    window.addEventListener('kadastra-goto-contract', handleGotoContract);
    return () => window.removeEventListener('kadastra-goto-contract', handleGotoContract);
  }, []);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0f172a' }}>
        <div style={{ fontSize: 18, color: '#64748b' }}>Loading…</div>
      </div>
    );
  }

  if (!user) {
    return <AuthPage onSuccess={() => window.location.reload()} />;
  }

  // Unified Navbar for all views
  const GlobalNav = () => (
    <Navbar 
      user={user} 
      logout={logout} 
      view={view} 
      setView={setView} 
      onSearch={(q) => {
        if (view !== 'listings') setView('listings');
        // We'll handle search via custom event or direct state if possible
        window.dispatchEvent(new CustomEvent('kadastra-search', { detail: q }));
      }}
    />
  );

  if (view === 'contracts') {
    return (
      <div style={{ background: '#f8fafc', minHeight: '100vh' }}>
        <GlobalNav />
        <main className="fade-in">
          <ContractGenerator />
        </main>
      </div>
    );
  }

  if (view === 'dashboard') {
    return (
      <div style={{ background: '#f8fafc', minHeight: '100vh' }}>
        <GlobalNav />
        <main className="fade-in">
          <Dashboard />
        </main>
      </div>
    );
  }

  if (view === 'map') {
    return (
      <div style={{ background: '#f8fafc', minHeight: '100vh' }}>
        <GlobalNav />
        <main className="fade-in">
          <SecurityMap />
        </main>
      </div>
    );
  }

  // Listings view
  return (
    <div style={{ background: '#f8fafc', minHeight: '100vh' }}>
      <GlobalNav />
      <App />
    </div>
  );
}

export default function AppWithAuth() {
  return (
    <LanguageProvider>
      <AuthProvider>
        <MainRouter />
      </AuthProvider>
    </LanguageProvider>
  );
}
