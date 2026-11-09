/**
 * api.js – all fetch calls to our own /api backend.
 * NO third-party calls. NO secrets in the browser.
 */

const API_BASE = 'http://localhost:8000';

function getToken() {
  return localStorage.getItem('wayfare_token') || '';
}

function authHeaders() {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function apiFetch(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(opts.headers || {}) },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Auth
  devLogin: () => apiFetch('/api/auth/dev-login'),
  getLoginUrl: () => apiFetch('/api/auth/login'),

  // Chat
  chat: (body) => apiFetch('/api/chat', { method: 'POST', body: JSON.stringify(body) }),

  // Planning
  extractPreferences: (message, context = '') =>
    apiFetch('/api/extract-preferences', { method: 'POST', body: JSON.stringify({ message, context }) }),
  planTrip: (preferences, sessionId) =>
    apiFetch('/api/plan', { method: 'POST', body: JSON.stringify({ preferences, session_id: sessionId }) }),

  // Trip CRUD
  getTrip: (tripId) => apiFetch(`/api/trips/${tripId}`),
  listTrips: () => apiFetch('/api/trips'),

  // Providers
  getWeather: (city) => apiFetch(`/api/weather/${encodeURIComponent(city)}`),
  searchTrains: (origin, dest, date) =>
    apiFetch(`/api/trains?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(dest)}${date ? `&date=${date}` : ''}`),
  searchFlights: (origin, dest, date) =>
    apiFetch(`/api/flights?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(dest)}${date ? `&date=${date}` : ''}`),
  searchBuses: (origin, dest) =>
    apiFetch(`/api/buses?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(dest)}`),
  searchStays: (city, checkIn, checkOut) =>
    apiFetch(`/api/stays?city=${encodeURIComponent(city)}&check_in=${checkIn}&check_out=${checkOut}`),
  findPlaces: (city, category = 'tourism') =>
    apiFetch(`/api/places?city=${encodeURIComponent(city)}&category=${category}`),
  convertCurrency: (amount, from, to) =>
    apiFetch(`/api/fx?amount=${amount}&from_currency=${from}&to_currency=${to}`),
  searchAirports: (query) => apiFetch(`/api/airports?query=${encodeURIComponent(query)}`),
  getVisaInfo: (country) => apiFetch(`/api/visa?destination_country=${encodeURIComponent(country)}`),
  getPhotos: (place) => apiFetch(`/api/photos/${encodeURIComponent(place)}`),

  // Compare
  comparePrices: (origin, destination, date) =>
    apiFetch('/api/compare', { method: 'POST', body: JSON.stringify({ origin, destination, date }) }),

  // Replan
  replan: (tripId, simulate = false, serviceId = '', serviceType = 'train', disruption = null) =>
    apiFetch('/api/replan', {
      method: 'POST',
      body: JSON.stringify({ trip_id: tripId, simulate, service_id: serviceId, service_type: serviceType, disruption }),
    }),
  approveReplan: (tripId, afterDays) =>
    apiFetch('/api/replan/approve', { method: 'POST', body: JSON.stringify({ trip_id: tripId, after_days: afterDays }) }),

  // Share
  shareTrip: (tripId, role = 'viewer') =>
    apiFetch('/api/share', { method: 'POST', body: JSON.stringify({ trip_id: tripId, role }) }),
  getSharedTrip: (token) => apiFetch(`/api/shared/${token}`),
  addComment: (token, text, itemRef = null) =>
    apiFetch(`/api/shared/${token}/comment`, { method: 'POST', body: JSON.stringify({ text, item_ref: itemRef }) }),
  updateChecklist: (token, itemId, done) =>
    apiFetch(`/api/shared/${token}/checklist/${itemId}`, { method: 'PUT', body: JSON.stringify({ done }) }),

  // Export
  exportTrip: (tripId) => apiFetch(`/api/export/${tripId}`, { method: 'POST' }),

  setToken: (t) => localStorage.setItem('wayfare_token', t),
  clearToken: () => localStorage.removeItem('wayfare_token'),
};
