"""
build_map.py — Génère carte.html avec données intégrées + barre de sécurité par ville.
Usage : python build_map.py
"""

import json
import pandas as pd

INPUT_FILE  = "geocoded.xlsx"
OUTPUT_FILE = "carte2.html"

# ── Poids par catégorie ───────────────────────────
CAT_WEIGHTS = {1: 2, 2: 10, 3: 8, 4: 3}
CAT_LABELS  = {1: "Drogue", 2: "Meurtre", 3: "Braquage / Vol", 4: "Agression diverse"}

# ── Lecture Excel ─────────────────────────────────
df = pd.read_excel(INPUT_FILE)
df.columns = [c.strip().lower() for c in df.columns]
df = df.fillna("")

rows, skipped = [], 0
for _, row in df.iterrows():
    try:
        lat = float(row["lat"]); lng = float(row["lng"])
        if lat == 0 and lng == 0: raise ValueError
        rows.append({
            "titre":     str(row.get("titre", "")),
            "categorie": int(row.get("categorie", 1)),
            "adresse":   str(row.get("lieux_extraits", "")),
            "url":       str(row.get("url", "")),
            "lat": lat, "lng": lng,
        })
    except (ValueError, KeyError):
        skipped += 1

DATA_JS    = json.dumps(rows,       ensure_ascii=False)
WEIGHTS_JS = json.dumps(CAT_WEIGHTS, ensure_ascii=False)
LABELS_JS  = json.dumps(CAT_LABELS,  ensure_ascii=False)

print(f"✅  {len(rows)} points  |  {skipped} ignorés")

# ── HTML ──────────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Carte des Incidents — Tunisie</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"/>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet"/>
  <style>
    :root {{
      --bg:#F7F5F2; --surface:#FFFFFF; --border:#E8E4DF;
      --text:#1A1714; --muted:#8C8580; --accent:#C4A882;
      --cat1:#D94F3D; --cat2:#E8943A; --cat3:#3A7BD5; --cat4:#4AAB6E;
      --shadow:0 4px 24px rgba(0,0,0,.08);
      --shadow-lg:0 8px 40px rgba(0,0,0,.13);
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{
      font-family:'DM Sans',sans-serif; background:var(--bg); color:var(--text);
      height:100vh; display:flex; flex-direction:column; overflow:hidden;
    }}

    /* ── HEADER ── */
    header {{
      background:var(--surface); border-bottom:1px solid var(--border);
      padding:13px 24px; display:flex; align-items:center; gap:18px;
      flex-shrink:0; z-index:1000; box-shadow:var(--shadow); flex-wrap:wrap;
    }}
    .logo {{ font-family:'Cormorant Garamond',serif; font-size:1.3rem; font-weight:600; white-space:nowrap; }}
    .logo span {{ color:var(--accent); }}

    .search-wrap {{
      display:flex; align-items:center; background:var(--bg);
      border:1.5px solid var(--border); border-radius:8px;
      padding:0 12px; gap:8px; flex:1; max-width:360px; min-width:180px;
      transition:border-color .2s;
    }}
    .search-wrap:focus-within {{ border-color:var(--accent); }}
    #searchInput {{
      border:none; background:transparent; outline:none;
      font-family:'DM Sans',sans-serif; font-size:.84rem;
      color:var(--text); width:100%; padding:10px 0;
    }}
    #searchInput::placeholder {{ color:var(--muted); }}
    #searchBtn {{
      background:var(--text); color:#fff; border:none; border-radius:6px;
      padding:7px 15px; font-family:'DM Sans',sans-serif; font-size:.78rem;
      font-weight:500; cursor:pointer; white-space:nowrap; transition:background .2s;
    }}
    #searchBtn:hover {{ background:var(--accent); }}

    .filter-wrap {{
      display:flex; align-items:center; background:var(--bg);
      border:1.5px solid var(--border); border-radius:8px;
      padding:0 12px; gap:8px; width:190px; transition:border-color .2s;
    }}
    .filter-wrap:focus-within {{ border-color:var(--accent); }}
    #filterInput {{
      border:none; background:transparent; outline:none;
      font-family:'DM Sans',sans-serif; font-size:.82rem;
      color:var(--text); width:100%; padding:9px 0;
    }}
    #filterInput::placeholder {{ color:var(--muted); }}

    .legend {{ display:flex; align-items:center; gap:14px; }}
    .legend-item {{
      display:flex; align-items:center; gap:6px; font-size:.72rem;
      color:var(--muted); cursor:pointer; user-select:none;
      white-space:nowrap; transition:opacity .2s;
    }}
    .legend-item.inactive {{ opacity:.3; }}
    .legend-dot {{ width:10px; height:10px; border-radius:50%; }}

    #counter {{
      background:var(--surface); border:1px solid var(--border);
      border-radius:20px; padding:5px 13px;
      font-size:.72rem; color:var(--muted); white-space:nowrap;
    }}
    #counter strong {{ color:var(--text); }}

    #map {{ flex:1 }}

    /* ── SECURITY PANEL ── */
    #secPanel {{
      position:fixed; bottom:32px; right:28px;
      width:320px; background:var(--surface);
      border:1px solid var(--border); border-radius:16px;
      box-shadow:var(--shadow-lg); z-index:2000;
      overflow:hidden;
      opacity:0; transform:translateY(20px) scale(.97);
      pointer-events:none;
      transition:opacity .35s ease, transform .35s ease;
    }}
    #secPanel.visible {{
      opacity:1; transform:translateY(0) scale(1); pointer-events:all;
    }}

    .sec-header {{
      padding:16px 18px 12px;
      border-bottom:1px solid var(--border);
      display:flex; align-items:flex-start; justify-content:space-between; gap:10px;
    }}
    .sec-city {{
      font-family:'Cormorant Garamond',serif;
      font-size:1.1rem; font-weight:600; line-height:1.3;
      color:var(--text); flex:1;
    }}
    .sec-radius {{
      font-size:.68rem; color:var(--muted); margin-top:3px;
    }}
    #secClose {{
      background:none; border:none; cursor:pointer; color:var(--muted);
      padding:2px; line-height:1; flex-shrink:0;
      transition:color .15s;
    }}
    #secClose:hover {{ color:var(--text); }}

    /* Score global */
    .sec-score-wrap {{ padding:16px 18px 14px; border-bottom:1px solid var(--border); }}
    .sec-score-label {{
      display:flex; justify-content:space-between; align-items:baseline;
      margin-bottom:8px;
    }}
    .sec-score-title {{ font-size:.72rem; font-weight:500; color:var(--muted); text-transform:uppercase; letter-spacing:.07em; }}
    .sec-score-value {{ font-family:'Cormorant Garamond',serif; font-size:1.5rem; font-weight:600; }}

    .score-bar-track {{
      height:10px; background:var(--border); border-radius:99px; overflow:hidden;
    }}
    .score-bar-fill {{
      height:100%; border-radius:99px;
      transition:width .7s cubic-bezier(.4,0,.2,1);
      width:0%;
    }}
    .sec-verdict {{
      margin-top:10px; font-size:.78rem; font-weight:500;
      display:flex; align-items:center; gap:6px;
    }}
    .verdict-dot {{ width:8px; height:8px; border-radius:50%; flex-shrink:0; }}

    /* Détail par catégorie */
    .sec-breakdown {{ padding:14px 18px 16px; }}
    .sec-breakdown-title {{
      font-size:.68rem; color:var(--muted); text-transform:uppercase;
      letter-spacing:.07em; font-weight:500; margin-bottom:10px;
    }}
    .sec-row {{
      display:flex; align-items:center; gap:10px;
      margin-bottom:9px; font-size:.78rem;
    }}
    .sec-row:last-child {{ margin-bottom:0; }}
    .sec-row-dot {{ width:8px; height:8px; border-radius:50%; flex-shrink:0; }}
    .sec-row-label {{ flex:1; color:var(--text); }}
    .sec-row-count {{
      font-size:.7rem; color:var(--muted);
      background:var(--bg); border:1px solid var(--border);
      border-radius:10px; padding:2px 8px; white-space:nowrap;
    }}
    .sec-row-pts {{
      font-size:.7rem; font-weight:600;
      min-width:44px; text-align:right;
    }}

    /* ── POPUP ── */
    .leaflet-popup-content-wrapper {{
      border-radius:12px !important; box-shadow:var(--shadow) !important;
      border:1px solid var(--border); padding:0 !important;
      overflow:hidden; min-width:220px; max-width:300px;
    }}
    .leaflet-popup-content {{ margin:0 !important; }}
    .leaflet-popup-tip-container {{ display:none; }}
    .popup-inner {{ padding:16px 18px; }}
    .popup-cat {{ font-size:.67rem; font-weight:500; letter-spacing:.09em; text-transform:uppercase; margin-bottom:5px; }}
    .popup-title {{ font-family:'Cormorant Garamond',serif; font-size:1.05rem; font-weight:600; line-height:1.3; margin-bottom:8px; }}
    .popup-addr {{ font-size:.73rem; color:var(--muted); margin-bottom:12px; line-height:1.4; }}
    .popup-link {{
      display:inline-flex; align-items:center; gap:6px; font-size:.76rem;
      font-weight:500; color:var(--text); text-decoration:none;
      border:1.5px solid var(--border); border-radius:6px; padding:6px 12px;
      transition:background .15s, border-color .15s;
    }}
    .popup-link:hover {{ background:var(--bg); border-color:var(--accent); }}

    /* ── TOAST ── */
    #toast {{
      position:fixed; bottom:24px; left:50%;
      transform:translateX(-50%) translateY(80px);
      background:var(--text); color:#fff; padding:10px 22px;
      border-radius:8px; font-size:.82rem; z-index:9999;
      transition:transform .3s; pointer-events:none;
    }}
    #toast.show {{ transform:translateX(-50%) translateY(0); }}
  </style>
</head>
<body>

<header>
  <div class="logo">Carte<span>Incidents</span></div>

  <div class="search-wrap">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
    <input id="searchInput" type="text" placeholder="Ville, adresse ou lat, lng …" autocomplete="off"/>
    <button id="searchBtn">Analyser</button>
  </div>

  <div class="filter-wrap">
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
    </svg>
    <input id="filterInput" type="text" placeholder="Filtrer par titre…" autocomplete="off"/>
  </div>

  <div class="legend">
    <div class="legend-item" data-cat="1"><span class="legend-dot" style="background:var(--cat1)"></span>Drogue</div>
    <div class="legend-item" data-cat="2"><span class="legend-dot" style="background:var(--cat2)"></span>Meurtre</div>
    <div class="legend-item" data-cat="3"><span class="legend-dot" style="background:var(--cat3)"></span>Braquage</div>
    <div class="legend-item" data-cat="4"><span class="legend-dot" style="background:var(--cat4)"></span>Agression</div>
  </div>

  <div id="counter"><strong>{len(rows)}</strong> points</div>
</header>

<div id="map"></div>

<!-- SECURITY PANEL -->
<div id="secPanel">
  <div class="sec-header">
    <div>
      <div class="sec-city" id="secCity">—</div>
      <div class="sec-radius" id="secRadius"></div>
    </div>
    <button id="secClose" title="Fermer">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
  </div>

  <div class="sec-score-wrap">
    <div class="sec-score-label">
      <span class="sec-score-title">Indice de sécurité</span>
      <span class="sec-score-value" id="secScoreVal">—</span>
    </div>
    <div class="score-bar-track">
      <div class="score-bar-fill" id="secBar"></div>
    </div>
    <div class="sec-verdict" id="secVerdict"></div>
  </div>

  <div class="sec-breakdown">
    <div class="sec-breakdown-title">Détail par catégorie</div>
    <div id="secRows"></div>
  </div>
</div>

<div id="toast"></div>

<script>
// ── DONNÉES ───────────────────────────────────────
const ALL_ROWS  = {DATA_JS};
const WEIGHTS   = {WEIGHTS_JS};
const CAT_LABELS = {LABELS_JS};
const CAT_COLORS = {{1:'#D94F3D', 2:'#E8943A', 3:'#3A7BD5', 4:'#4AAB6E'}};

// Rayon d'analyse en km
const RADIUS_KM = 2;

// Score max de référence pour la barre (à ajuster selon vos données)
// On calcule dynamiquement le max observé pour normaliser
const SCORE_REF = 200;

// ── CARTE ─────────────────────────────────────────
const map = L.map('map', {{center:[33.8869,9.5375], zoom:7}});
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution:'© OSM © CARTO', subdomains:'abcd', maxZoom:19
}}).addTo(map);

let hiddenCats = new Set(), filterText = '', searchPin = null, zoneCircle = null;
const layer = L.layerGroup().addTo(map);

function bubbleIcon(color) {{
  const s = 14;
  return L.divIcon({{
    className:'', iconSize:[s,s], iconAnchor:[s/2,s/2], popupAnchor:[0,-(s/2+6)],
    html:`<div style="width:${{s}}px;height:${{s}}px;border-radius:50%;background:${{color}};
      border:2.5px solid rgba(255,255,255,.85);box-shadow:0 2px 8px rgba(0,0,0,.25);
      cursor:pointer;transition:transform .15s"
      onmouseenter="this.style.transform='scale(1.5)'"
      onmouseleave="this.style.transform='scale(1)'"></div>`
  }});
}}

function buildPopup(row) {{
  const cat = row.categorie || 1;
  const link = row.url
    ? `<a class="popup-link" href="${{row.url}}" target="_blank" rel="noopener">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
          <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
        </svg>Voir la source</a>` : '';
  return `<div class="popup-inner">
    <div class="popup-cat" style="color:${{CAT_COLORS[cat]||'#888'}}">${{CAT_LABELS[cat]||'Catégorie '+cat}}</div>
    <div class="popup-title">${{row.titre||'—'}}</div>
    ${{row.adresse?`<div class="popup-addr">📍 ${{row.adresse}}</div>`:''}}
    ${{link}}
  </div>`;
}}

function render() {{
  layer.clearLayers();
  let count = 0;
  for (const row of ALL_ROWS) {{
    const cat = row.categorie || 1;
    if (hiddenCats.has(cat)) continue;
    if (filterText && !(row.titre||'').toLowerCase().includes(filterText)) continue;
    const marker = L.marker([row.lat, row.lng], {{icon:bubbleIcon(CAT_COLORS[cat]||'#888')}});
    marker.bindPopup(buildPopup(row), {{maxWidth:300}});
    layer.addLayer(marker);
    count++;
  }}
  document.querySelector('#counter strong').textContent = count;
}}
render();

// ── LÉGENDE ───────────────────────────────────────
document.querySelectorAll('.legend-item').forEach(el => {{
  el.addEventListener('click', () => {{
    const cat = parseInt(el.dataset.cat);
    if (hiddenCats.has(cat)) {{ hiddenCats.delete(cat); el.classList.remove('inactive'); }}
    else                      {{ hiddenCats.add(cat);    el.classList.add('inactive'); }}
    render();
  }});
}});

document.getElementById('filterInput').addEventListener('input', function() {{
  filterText = this.value.trim().toLowerCase();
  render();
}});

// ── DISTANCE (Haversine) km ───────────────────────
function distKm(lat1, lng1, lat2, lng2) {{
  const R = 6371, dLat = (lat2-lat1)*Math.PI/180, dLng = (lng2-lng1)*Math.PI/180;
  const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLng/2)**2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}}

// ── SCORE DE SÉCURITÉ ─────────────────────────────
function computeScore(centerLat, centerLng, radiusKm) {{
  const breakdown = {{1:{{count:0,pts:0}}, 2:{{count:0,pts:0}}, 3:{{count:0,pts:0}}, 4:{{count:0,pts:0}}}};
  let total = 0;

  for (const row of ALL_ROWS) {{
    if (distKm(centerLat, centerLng, row.lat, row.lng) <= radiusKm) {{
      const cat = row.categorie || 1;
      const pts = WEIGHTS[cat] || 1;
      breakdown[cat].count++;
      breakdown[cat].pts += pts;
      total += pts;
    }}
  }}
  return {{total, breakdown}};
}}

function getVerdict(pct) {{
  if (pct < 20)  return {{label:'Très sûr',     color:'#4AAB6E', emoji:'🟢'}};
  if (pct < 40)  return {{label:'Plutôt sûr',   color:'#8BC34A', emoji:'🟡'}};
  if (pct < 60)  return {{label:'Modéré',        color:'#E8943A', emoji:'🟠'}};
  if (pct < 80)  return {{label:'Peu sûr',       color:'#D94F3D', emoji:'🔴'}};
  return             {{label:'Dangereux',         color:'#9B1B1B', emoji:'🔴'}};
}}

function getBarGradient(pct) {{
  if (pct < 20)  return '#4AAB6E';
  if (pct < 40)  return '#8BC34A';
  if (pct < 60)  return '#E8943A';
  if (pct < 80)  return '#D94F3D';
  return                '#9B1B1B';
}}

function showSecurityPanel(cityName, lat, lng) {{
  const {{total, breakdown}} = computeScore(lat, lng, RADIUS_KM);
  const pct   = Math.min(100, Math.round(total / SCORE_REF * 100));
  const verdict = getVerdict(pct);

  // En-tête
  document.getElementById('secCity').textContent = cityName.split(',')[0];
  document.getElementById('secRadius').textContent = `Périmètre analysé : ${{RADIUS_KM}} km`;

  // Barre
  const bar = document.getElementById('secBar');
  bar.style.width = '0%';
  bar.style.background = getBarGradient(pct);
  setTimeout(() => {{ bar.style.width = pct + '%'; }}, 60);

  // Score
  document.getElementById('secScoreVal').textContent = total + ' pts';
  document.getElementById('secScoreVal').style.color = verdict.color;

  // Verdict
  document.getElementById('secVerdict').innerHTML =
    `<span class="verdict-dot" style="background:${{verdict.color}}"></span>
     <span style="color:${{verdict.color}}">${{verdict.emoji}} ${{verdict.label}}</span>
     <span style="color:var(--muted);font-size:.72rem;margin-left:auto">${{Object.values(breakdown).reduce((s,b)=>s+b.count,0)}} incident(s)</span>`;

  // Détail
  const rows = document.getElementById('secRows');
  rows.innerHTML = '';
  for (const cat of [1,2,3,4]) {{
    const b = breakdown[cat];
    const row = document.createElement('div');
    row.className = 'sec-row';
    row.innerHTML = `
      <span class="sec-row-dot" style="background:${{CAT_COLORS[cat]}}"></span>
      <span class="sec-row-label">${{CAT_LABELS[cat]}}</span>
      <span class="sec-row-count">${{b.count}} cas</span>
      <span class="sec-row-pts" style="color:${{CAT_COLORS[cat]}}">${{b.pts}} pts</span>`;
    rows.appendChild(row);
  }}

  document.getElementById('secPanel').classList.add('visible');
}}

document.getElementById('secClose').addEventListener('click', () => {{
  document.getElementById('secPanel').classList.remove('visible');
  if (zoneCircle) {{ map.removeLayer(zoneCircle); zoneCircle = null; }}
}});

// ── RECHERCHE ─────────────────────────────────────
const pinIcon = L.divIcon({{
  className:'', iconSize:[28,38], iconAnchor:[14,38], popupAnchor:[0,-40],
  html:`<svg xmlns="http://www.w3.org/2000/svg" width="28" height="38" viewBox="0 0 30 40">
    <path d="M15 0C6.716 0 0 6.716 0 15c0 10 15 25 15 25s15-15 15-25C30 6.716 23.284 0 15 0z" fill="#1A1714"/>
    <circle cx="15" cy="15" r="7" fill="#F7F5F2"/><circle cx="15" cy="15" r="4" fill="#C4A882"/>
  </svg>`
}});

function placePin(lat, lng, label) {{
  if (searchPin)  map.removeLayer(searchPin);
  if (zoneCircle) map.removeLayer(zoneCircle);

  searchPin = L.marker([lat,lng], {{icon:pinIcon, zIndexOffset:1000}})
    .bindPopup(`<div style="padding:12px 14px;font-size:.82rem;font-family:'DM Sans',sans-serif;max-width:240px">${{label.split(',')[0]}}</div>`)
    .addTo(map).openPopup();

  // Cercle du périmètre analysé
  zoneCircle = L.circle([lat,lng], {{
    radius: RADIUS_KM * 1000,
    color: '#C4A882', weight: 1.5,
    fillColor: '#C4A882', fillOpacity: .06,
    dashArray: '6 4',
  }}).addTo(map);

  map.flyTo([lat,lng], 13, {{duration:1.2}});
  showSecurityPanel(label, lat, lng);
}}

async function doSearch() {{
  const raw = document.getElementById('searchInput').value.trim();
  if (!raw) return;

  const gps = raw.match(/^(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)$/);
  if (gps) {{ placePin(+gps[1], +gps[2], `${{gps[1]}}, ${{gps[2]}}`); return; }}

  showToast('Recherche…', 60000);
  try {{
    const res  = await fetch(
      `https://nominatim.openstreetmap.org/search?q=${{encodeURIComponent(raw+', Tunisie')}}&format=json&limit=1&countrycodes=tn`,
      {{headers:{{'Accept-Language':'fr'}}}}
    );
    const data = await res.json();
    hideToast();
    if (data.length) placePin(+data[0].lat, +data[0].lon, data[0].display_name);
    else showToast('Lieu introuvable.', 3000);
  }} catch {{ hideToast(); showToast('Erreur réseau.', 3000); }}
}}

document.getElementById('searchBtn').addEventListener('click', doSearch);
document.getElementById('searchInput').addEventListener('keydown', e => {{ if(e.key==='Enter') doSearch(); }});

let toastTimer;
function showToast(msg, ms) {{
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer);
  if (ms < 60000) toastTimer = setTimeout(hideToast, ms);
}}
function hideToast() {{ document.getElementById('toast').classList.remove('show'); }}
</script>
</body>
</html>"""

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"📄  Fichier généré : {OUTPUT_FILE}")
