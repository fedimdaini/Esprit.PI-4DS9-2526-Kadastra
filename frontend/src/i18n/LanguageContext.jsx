import React, { createContext, useContext, useState, useCallback } from 'react';
import translations from './translations';

const LanguageContext = createContext(null);

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(
    () => localStorage.getItem('kadastra_lang') || 'fr'
  );

  const toggleLanguage = useCallback(() => {
    setLang(prev => {
      const next = prev === 'fr' ? 'en' : 'fr';
      localStorage.setItem('kadastra_lang', next);
      return next;
    });
  }, []);

  /**
   * t('nav.listings') → "Annonces" (fr) or "Listings" (en)
   * Supports dot-notation keys into the translations object.
   * Falls back gracefully: unknown key → returns the key itself.
   */
  const t = useCallback((key) => {
    const parts = key.split('.');
    let node = translations;
    for (const part of parts) {
      if (!node || typeof node !== 'object') return key;
      node = node[part];
    }
    if (!node || typeof node !== 'object') return key;
    return node[lang] || node['fr'] || key;
  }, [lang]);

  return (
    <LanguageContext.Provider value={{ lang, toggleLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error('useLanguage must be used within LanguageProvider');
  return ctx;
}
