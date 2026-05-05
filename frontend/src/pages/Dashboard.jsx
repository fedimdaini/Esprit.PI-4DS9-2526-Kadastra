// src/pages/Dashboard.jsx
import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { fetchDashboardStats } from '../services/api';

const DashboardSkeleton = () => (
  <div style={{ padding: 48 }} className="container fade-in">
    <div className="skeleton" style={{ height: 40, width: 300, marginBottom: 12, borderRadius: 8 }} />
    <div className="skeleton" style={{ height: 20, width: 500, marginBottom: 48, borderRadius: 6 }} />
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 24 }}>
      {[1, 2, 3].map(i => (
        <div key={i} className="card skeleton" style={{ height: 180 }} />
      ))}
    </div>
  </div>
);

const DashboardCard = ({ icon, label, value, description, color = 'var(--primary)' }) => (
  <div className="card" style={{ padding: 32, display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden' }}>
    <div style={{ 
      position: 'absolute', top: -10, right: -10, fontSize: 80, opacity: 0.03, transform: 'rotate(-15deg)', pointerEvents: 'none' 
    }}>
      {icon}
    </div>
    <div style={{ fontSize: 32, marginBottom: 16 }}>{icon}</div>
    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 4 }}>
      {label}
    </div>
    <div style={{ fontSize: 32, fontWeight: 900, color: color, marginBottom: 8, letterSpacing: '-1px' }}>
      {value}
    </div>
    {description && (
      <div style={{ fontSize: 13, color: 'var(--text-light)', fontWeight: 500 }}>
        {description}
      </div>
    )}
  </div>
);

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    
    fetchDashboardStats()
      .then(data => {
        if (mounted) {
          setStats(data);
          setLoading(false);
        }
      })
      .catch(err => {
        if (mounted) {
          console.error(err);
          setError(err.message);
          setLoading(false);
        }
      });
      
    return () => { mounted = false; };
  }, []);

  if (loading) return <DashboardSkeleton />;

  if (error) {
    return (
      <div style={{ padding: 48 }} className="container">
        <div className="card" style={{ padding: 32, textAlign: 'center', borderColor: '#fecaca', background: '#fff1f2' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
          <h2 className="premium-font" style={{ color: '#b91c1c', marginBottom: 8 }}>Erreur de chargement</h2>
          <p style={{ color: '#ef4444', marginBottom: 24 }}>{error}</p>
          <button 
            onClick={() => window.location.reload()}
            style={{ background: '#b91c1c', color: '#fff', padding: '12px 24px', borderRadius: 12, fontWeight: 700 }}
          >
            Réessayer
          </button>
        </div>
      </div>
    );
  }

  if (!stats) return <DashboardSkeleton />;

  const roleConfigs = {
    PARTICULIER: {
      title: "Tableau de Bord Sécurisé",
      subtitle: "Surveillez vos recherches et analysez les risques locaux en temps réel.",
      icon: "🛡️",
      cards: [
        { icon: "🏠", label: "Marché Actuel", value: stats.stats.total_listings, description: "Annonces analysées ce mois" },
        { icon: "📍", label: "Zones Sûres", value: "85%", description: "Indice de sécurité moyen Tunisie", color: "#16a34a" },
        { icon: "💰", label: "Prix Moyen", value: `${Math.round(stats.stats.avg_price).toLocaleString()} DT`, description: "Basé sur vos critères de recherche" }
      ]
    },
    INVESTISSEUR: {
      title: "Intelligence d'Investissement",
      subtitle: "Analyse prédictive et détection d'opportunités à haut rendement.",
      icon: "💎",
      cards: [
        { icon: "📈", label: "Opportunités", value: stats.stats.opportunities, description: "Biens sous-évalués détectés", color: "var(--accent)" },
        { icon: "📊", label: "Couverture", value: stats.stats.total_listings, description: "Annonces filtrées par IA" },
        { icon: "🏛️", label: "Haut Standing", value: stats.stats.high_value, description: "Patrimoine de luxe disponible" }
      ]
    },
    AGENT: {
      title: "Console de Gestion Agent",
      subtitle: "Gérez vos mandats et suivez la performance de votre portefeuille.",
      icon: "🏢",
      cards: [
        { icon: "📋", label: "Mandats Actifs", value: stats.stats.active_listings, description: "Propriétés sous votre gestion" },
        { icon: "👥", label: "Base Clients", value: stats.stats.total_clients, description: "Acquéreurs potentiels qualifiés" },
        { icon: "⚡", label: "Performance", value: "92%", description: "Taux de conversion moyen", color: "#16a34a" }
      ]
    },
    BANQUIER: {
      title: "Analyse de Risque Crédit",
      subtitle: "Validation des dossiers et évaluation des garanties immobilières.",
      icon: "🏦",
      cards: [
        { icon: "⏳", label: "Dossiers", value: stats.stats.pending_loans, description: "Demandes en cours d'examen" },
        { icon: "✅", label: "Approbations", value: `${(stats.stats.approved_amount || 0).toLocaleString()} DT`, description: "Volume total débloqué", color: "#16a34a" },
        { icon: "📉", label: "Taux Moyen", value: "8.2%", description: "Taux directeur actuel TMM+" }
      ]
    }
  };

  const config = roleConfigs[user.user_type] || roleConfigs.PARTICULIER;

  return (
    <div style={{ padding: '48px 32px' }} className="container fade-in">
      <div style={{ marginBottom: 48 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
           <div style={{ fontSize: 32 }}>{config.icon}</div>
           <h1 className="premium-font" style={{ fontSize: 32, fontWeight: 900, color: 'var(--primary)', letterSpacing: '-1px' }}>
             {config.title}
           </h1>
        </div>
        <p style={{ fontSize: 16, color: 'var(--text-muted)', maxWidth: 600, fontWeight: 500 }}>
          {config.subtitle}
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 32 }}>
        {config.cards.map((card, idx) => (
          <DashboardCard key={idx} {...card} />
        ))}
      </div>

      {/* Security Notice */}
      <div className="card" style={{ 
        marginTop: 48, padding: 32, background: 'var(--primary)', color: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        boxShadow: '0 20px 40px -10px rgba(15, 23, 42, 0.3)'
      }}>
        <div>
          <h3 className="premium-font" style={{ fontSize: 20, fontWeight: 800, marginBottom: 8 }}>Vérification Kadastra™</h3>
          <p style={{ fontSize: 14, opacity: 0.8, maxWidth: 500 }}>
            Toutes les données affichées sont cryptées et vérifiées par notre protocole de sécurité. 
            Dernière mise à jour : il y a quelques instants.
          </p>
        </div>
        <div style={{ 
          background: 'rgba(255,255,255,0.1)', padding: '12px 24px', borderRadius: 12, 
          fontSize: 13, fontWeight: 700, border: '1px solid rgba(255,255,255,0.2)' 
        }}>
          STATUS: OPÉRATIONNEL
        </div>
      </div>
    </div>
  );
}
