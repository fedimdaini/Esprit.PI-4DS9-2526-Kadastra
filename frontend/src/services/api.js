// src/services/api.js
const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

function buildUrl(endpoint, params = {}) {
  const url = new URL(`${BASE_URL}/${endpoint}`);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== '' && v !== 'all') {
      url.searchParams.append(k, v);
    }
  });
  return url.toString();
}

export async function fetchListings(filters = {}) {
  const res = await fetch(buildUrl('listings/', filters));
  if (!res.ok) throw new Error('Erreur réseau');
  return res.json();
}

export async function fetchListing(id) {
  const res = await fetch(buildUrl(`listings/${id}/`));
  if (!res.ok) throw new Error('Annonce introuvable');
  return res.json();
}

export async function fetchStats() {
  const res = await fetch(buildUrl('stats/'));
  if (!res.ok) throw new Error('Erreur stats');
  return res.json();
}

export async function fetchFilterOptions() {
  const res = await fetch(buildUrl('filter-options/'));
  if (!res.ok) throw new Error('Erreur options');
  return res.json();
}

export async function fetchDashboardStats() {
  const url = `${BASE_URL}/auth/dashboard-stats/`;
  const res = await fetch(url, { 
    headers: { 'Accept': 'application/json' },
    credentials: 'include'
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error('Session expirée. Veuillez vous reconnecter.');
    throw new Error(`Échec du chargement (Erreur ${res.status})`);
  }
  return res.json();
}
