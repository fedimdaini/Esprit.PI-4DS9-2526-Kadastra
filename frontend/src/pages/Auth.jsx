// src/pages/Auth.jsx
import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../i18n/LanguageContext';

export default function AuthPage({ onSuccess }) {
  const { login, register } = useAuth();
  const { lang, toggleLanguage, t } = useLanguage();
  const [mode, setMode] = useState('login');
  const [formData, setFormData] = useState({
    username: '', password: '', password2: '', email: '', first_name: '', last_name: '',
    user_type: 'PARTICULIER', phone: '', agency_name: '', license_number: '', bank_name: '', branch: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const userTypes = [
    { value: 'PARTICULIER', label: t('auth.typeParticulier'), desc: t('auth.typePartDesc') },
    { value: 'INVESTISSEUR', label: t('auth.typeInvestisseur'), desc: t('auth.typeInvestDesc') },
    { value: 'AGENT', label: t('auth.typeAgent'), desc: t('auth.typeAgentDesc') },
    { value: 'BANQUIER', label: t('auth.typeBanquier'), desc: t('auth.typeBanquierDesc') },
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
        setError(t('auth.passwordMismatch'));
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
          <img src="/kadastra-logo.png" alt="Kadastra"
            style={{ height: 90, width: 'auto', objectFit: 'contain' }}/>
          {/* Language toggle on auth page */}
          <div style={{ marginTop: 12 }}>
            <button onClick={toggleLanguage} style={{
              padding:'4px 14px', borderRadius:20, fontSize:12, fontWeight:700, cursor:'pointer',
              background: lang==='fr'?'#EFF6FF':'#F0FDF4',
              border:`1.5px solid ${lang==='fr'?'#BFDBFE':'#BBF7D0'}`,
              color: lang==='fr'?'#1D4ED8':'#15803D',
            }}>
              {lang==='fr'?'🇫🇷 FR · switch to EN':'🇬🇧 EN · passer en FR'}
            </button>
          </div>
        </div>
        <p style={{ textAlign: 'center', color: '#64748b', marginBottom: 32, fontSize: 14 }}>
          {mode === 'login' ? t('auth.signIn') : t('auth.signUp')}
        </p>

        <form onSubmit={handleSubmit}>
          {error && (
            <div style={{ background: '#fee', border: '1px solid #fcc', borderRadius: 8, padding: 12, marginBottom: 20, fontSize: 13, color: '#c33' }}>
              {error}
            </div>
          )}

          <input required value={formData.username} onChange={set('username')} placeholder={t('auth.username')}
            style={{ width: '100%', padding: 12, marginBottom: 16, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />

          <input required type="password" value={formData.password} onChange={set('password')} placeholder={t('auth.password')}
            style={{ width: '100%', padding: 12, marginBottom: 16, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />

          {mode === 'register' && (<>
            <input required type="password" value={formData.password2} onChange={set('password2')} placeholder={t('auth.confirmPassword')}
              style={{ width: '100%', padding: 12, marginBottom: 16, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />

            <input required type="email" value={formData.email} onChange={set('email')} placeholder={t('auth.email')}
              style={{ width: '100%', padding: 12, marginBottom: 16, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />

            <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
              <input value={formData.first_name} onChange={set('first_name')} placeholder={t('auth.firstName')}
                style={{ flex: 1, padding: 12, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />
              <input value={formData.last_name} onChange={set('last_name')} placeholder={t('auth.lastName')}
                style={{ flex: 1, padding: 12, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#64748b', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '.5px' }}>
                {t('auth.accountType')}
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
              <input value={formData.agency_name} onChange={set('agency_name')} placeholder={t('auth.agencyName')}
                style={{ width: '100%', padding: 12, marginBottom: 12, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />
              <input value={formData.license_number} onChange={set('license_number')} placeholder={t('auth.licenseNumber')}
                style={{ width: '100%', padding: 12, marginBottom: 16, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />
            </>)}

            {formData.user_type === 'BANQUIER' && (<>
              <input value={formData.bank_name} onChange={set('bank_name')} placeholder={t('auth.bankName')}
                style={{ width: '100%', padding: 12, marginBottom: 12, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />
              <input value={formData.branch} onChange={set('branch')} placeholder={t('auth.branch')}
                style={{ width: '100%', padding: 12, marginBottom: 16, border: '1.5px solid #e2e8f0', borderRadius: 8 }} />
            </>)}
          </>)}

          <button disabled={loading} type="submit" style={{
            width: '100%', padding: 14, background: '#667eea', color: '#fff', borderRadius: 10, fontSize: 15, fontWeight: 700, marginBottom: 16,
            border: 'none', cursor: loading ? 'not-allowed' : 'pointer',
          }}>
            {loading ? t('app.loading') : (mode === 'login' ? t('auth.loginBtn') : t('auth.registerBtn'))}
          </button>
        </form>

        <div style={{ textAlign: 'center', fontSize: 14 }}>
          {mode === 'login' ? t('auth.noAccount') : t('auth.alreadyAccount')}
          {' '}
          <button onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }} style={{
            color: '#667eea', fontWeight: 600, background: 'none', padding: 0, border: 'none', cursor: 'pointer',
          }}>
            {mode === 'login' ? t('auth.registerLink') : t('auth.loginLink')}
          </button>
        </div>
      </div>
    </div>
  );
}
