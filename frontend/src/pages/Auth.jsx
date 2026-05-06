// src/pages/Auth.jsx
import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

export default function AuthPage({ onSuccess }) {
  const { login, register } = useAuth();
  const [mode, setMode] = useState('login');
  const [formData, setFormData] = useState({
    username: '', password: '', password2: '', email: '', first_name: '', last_name: '',
    user_type: 'PARTICULIER', phone: '', agency_name: '', license_number: '', bank_name: '', branch: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const userTypes = [
    { value: 'PARTICULIER', label: '👤 Particulier', desc: 'Acheter ou vendre un bien' },
    { value: 'INVESTISSEUR', label: '💼 Investisseur', desc: 'Investir dans l\'immobilier' },
    { value: 'AGENT', label: '🏢 Agent immobilier', desc: 'Gérer des annonces' },
    { value: 'BANQUIER', label: '🏦 Banquier', desc: 'Financer des transactions' },
  ];

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (mode === 'login') {
      const result = await login(formData.username, formData.password);
      if (result.success) onSuccess();
      else setError(result.error);
    } else {
      if (formData.password !== formData.password2) {
        setError('Les mots de passe ne correspondent pas');
        setLoading(false);
        return;
      }
      const result = await register(formData);
      if (result.success) onSuccess();
      else setError(JSON.stringify(result.errors));
    }
    setLoading(false);
  }

  function set(key) {
    return (e) => setFormData({ ...formData, [key]: e.target.value });
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    }}>
      <div style={{
        background: '#fff', borderRadius: 16, padding: 40, width: '100%', maxWidth: 480,
        boxShadow: '0 20px 60px rgba(0,0,0,.3)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <img
            src="/kadastra-logo.png"
            alt="Kadastra"
            style={{ height: 90, width: 'auto', objectFit: 'contain' }}
          />
        </div>
        <p style={{ textAlign: 'center', color: '#64748b', marginBottom: 32, fontSize: 14 }}>
          {mode === 'login' ? 'Connectez-vous à votre compte' : 'Créez votre compte'}
        </p>

        <form onSubmit={handleSubmit}>
          {error && (
            <div style={{ background: '#fee', border: '1px solid #fcc', borderRadius: 8, padding: 12, marginBottom: 20, fontSize: 13, color: '#c33' }}>
              {error}
            </div>
          )}

          <input required value={formData.username} onChange={set('username')} placeholder="Nom d'utilisateur"
            style={{ width: '100%', padding: 12, marginBottom: 16, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />

          <input required type="password" value={formData.password} onChange={set('password')} placeholder="Mot de passe"
            style={{ width: '100%', padding: 12, marginBottom: 16, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />

          {mode === 'register' && (<>
            <input required type="password" value={formData.password2} onChange={set('password2')} placeholder="Confirmer mot de passe"
              style={{ width: '100%', padding: 12, marginBottom: 16, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />

            <input required type="email" value={formData.email} onChange={set('email')} placeholder="Email"
              style={{ width: '100%', padding: 12, marginBottom: 16, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />

            <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
              <input value={formData.first_name} onChange={set('first_name')} placeholder="Prénom"
                style={{ flex: 1, padding: 12, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />
              <input value={formData.last_name} onChange={set('last_name')} placeholder="Nom"
                style={{ flex: 1, padding: 12, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#64748b', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '.5px' }}>
                Type de compte
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {userTypes.map(t => (
                  <button key={t.value} type="button" onClick={() => setFormData({ ...formData, user_type: t.value })} style={{
                    padding: 14, borderRadius: 10, border: '2px solid', textAlign: 'left',
                    borderColor: formData.user_type === t.value ? '#667eea' : '#e2e8f0',
                    background: formData.user_type === t.value ? '#f0f4ff' : '#fff',
                  }}>
                    <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 2 }}>{t.label}</div>
                    <div style={{ fontSize: 11, color: '#64748b' }}>{t.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {formData.user_type === 'AGENT' && (<>
              <input value={formData.agency_name} onChange={set('agency_name')} placeholder="Nom de l'agence"
                style={{ width: '100%', padding: 12, marginBottom: 12, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />
              <input value={formData.license_number} onChange={set('license_number')} placeholder="Numéro de licence"
                style={{ width: '100%', padding: 12, marginBottom: 16, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />
            </>)}

            {formData.user_type === 'BANQUIER' && (<>
              <input value={formData.bank_name} onChange={set('bank_name')} placeholder="Nom de la banque"
                style={{ width: '100%', padding: 12, marginBottom: 12, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />
              <input value={formData.branch} onChange={set('branch')} placeholder="Agence"
                style={{ width: '100%', padding: 12, marginBottom: 16, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />
            </>)}
          </>)}

          <button disabled={loading} type="submit" style={{
            width: '100%', padding: 14, background: '#667eea', color: '#fff', borderRadius: 10, fontSize: 15, fontWeight: 700, marginBottom: 16,
          }}>
            {loading ? 'Chargement...' : (mode === 'login' ? 'Se connecter' : 'S\'inscrire')}
          </button>
        </form>

        <div style={{ textAlign: 'center', fontSize: 14 }}>
          {mode === 'login' ? 'Pas encore de compte?' : 'Déjà un compte?'}
          {' '}
          <button onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }} style={{
            color: '#667eea', fontWeight: 600, background: 'none', padding: 0,
          }}>
            {mode === 'login' ? 'S\'inscrire' : 'Se connecter'}
          </button>
        </div>
      </div>
    </div>
  );
}
