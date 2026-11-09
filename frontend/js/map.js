/**
 * map.js – Leaflet map integration.
 * Tiles via Geoapify (live) or OpenStreetMap (mock fallback).
 */

let mapInstance = null;
let markers = [];

export function initMap(containerId, center = [20.5937, 78.9629], zoom = 5) {
  if (typeof L === 'undefined') {
    console.warn('Leaflet not loaded');
    return null;
  }
  if (mapInstance) {
    mapInstance.remove();
    mapInstance = null;
  }
  mapInstance = L.map(containerId, { zoomControl: true }).setView(center, zoom);
  // Use OpenStreetMap tiles as mock fallback (no key needed)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors',
  }).addTo(mapInstance);
  return mapInstance;
}

export function plotItinerary(itinerary) {
  if (!mapInstance || !itinerary?.days) return;
  clearMarkers();

  const points = [];
  for (const day of itinerary.days) {
    for (const act of day.activities || []) {
      if (act.lat && act.lon) {
        const m = L.marker([act.lat, act.lon]).addTo(mapInstance);
        m.bindPopup(`<strong>${act.title}</strong><br>${act.location || ''}`);
        markers.push(m);
        points.push([act.lat, act.lon]);
      }
    }
  }

  if (points.length > 1) {
    const polyline = L.polyline(points, { color: '#2F6F6D', weight: 2, dashArray: '6 4' });
    polyline.addTo(mapInstance);
    mapInstance.fitBounds(polyline.getBounds(), { padding: [30, 30] });
  } else if (points.length === 1) {
    mapInstance.setView(points[0], 12);
  }
}

export function plotPlaces(places) {
  if (!mapInstance) return;
  clearMarkers();

  for (const p of places) {
    if (p.lat && p.lon) {
      const icon = L.divIcon({
        className: '',
        html: `<div style="width:10px;height:10px;border-radius:50%;background:#2F6F6D;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,0.3)"></div>`,
        iconSize: [10, 10],
        iconAnchor: [5, 5],
      });
      const m = L.marker([p.lat, p.lon], { icon }).addTo(mapInstance);
      m.bindPopup(`<strong>${p.name}</strong><br>${p.address || ''}`);
      markers.push(m);
    }
  }
}

function clearMarkers() {
  if (!mapInstance) return;
  for (const m of markers) mapInstance.removeLayer(m);
  markers = [];
}

export function getMapInstance() { return mapInstance; }
