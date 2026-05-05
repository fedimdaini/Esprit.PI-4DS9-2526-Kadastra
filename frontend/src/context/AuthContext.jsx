// src/context/AuthContext.jsx
import React, { createContext, useState, useContext, useEffect } from 'react';

const AuthContext = createContext(null);

const API_BASE = 'http://localhost:8000/api/auth';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Vérifier si l'utilisateur est connecté au chargement
    checkAuth();
  }, []);

  async function checkAuth() {
    try {
      const res = await fetch(`${API_BASE}/me/`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
      }
    } catch (e) {
      console.log('Not authenticated');
    } finally {
      setLoading(false);
    }
  }

  async function login(username, password) {
    const res = await fetch(`${API_BASE}/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (res.ok) {
      setUser(data.user);
      return { success: true };
    }
    return { success: false, error: data.error || 'Erreur de connexion' };
  }

  async function register(formData) {
    const res = await fetch(`${API_BASE}/register/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(formData),
    });
    const data = await res.json();
    if (res.ok) {
      setUser(data.user);
      return { success: true };
    }
    return { success: false, errors: data };
  }

  async function logout() {
    await fetch(`${API_BASE}/logout/`, {
      method: 'POST',
      credentials: 'include',
    });
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
