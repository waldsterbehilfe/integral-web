import streamlit as st
import osmnx as ox
import folium
import io, re, os, random, shutil
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import streamlit.components.v1 as components

# --- 1. SETUP & PERSISTENCE ---
st.set_page_config(page_title="INTEGRAL PRO", layout="wide", page_icon="📈")

# Pfade & Cache
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "persistent_geocache")
os.makedirs(CACHE_DIR, exist_ok=True)
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR

# Geocoder Setup
geolocator = Nominatim(user_agent="integral_pro_v56")
reverse = RateLimiter(geolocator.reverse, min_delay_seconds=1.1) # Etwas langsamer für Stabilität

# Session State Initialisierung
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'fehler_liste' not in st.session_state: st.session_state.fehler_liste = []
if 'run_processing' not in st.session_state: st.session_state.run_processing = False

# --- 2. SIDEBAR (Wartung & Farben) ---
with st.sidebar:
    st.title("⚙️ Einstellungen")
    bg_toggle = st.checkbox("Hintergrundbild", value=True)
    st.divider()
    
    selected_colors = {}
    if st.session_state.ort_sammlung:
        st.subheader("🎨 Ebenen-Farben")
        for ort in sorted(st.session_state.ort_sammlung.keys()):
            # Key-Sicherung für Streamlit
            selected_colors[ort] = st.color_picker(f"{ort}", "#FF0000", key=f"col_{ort}")
    
    st.divider()
    if st.button("🗑️ Geocache leeren", use_container_width=True):
        shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR, exist_ok=True)
        st.rerun()

# Hintergrund-CSS
if bg_toggle:
    st.markdown(f"<style>.stApp {{background-image: url('https://raw.githubusercontent.com/waldsterbehilfe/integral-web/main/hintergrund.png'); background-size: cover; background-attachment: fixed;}}</style>", unsafe_allow_html=True)

# --- 3. LOGIK-KERN ---
def verarbeite_strasse(strasse):
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    query = f"{s_clean}, Marburg-Biedenkopf"
    try:
        # 1. Geometrie holen
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=400)
        if gdf.empty: return {"success": False, "original": strasse}
        
        # 2. Filter auf Linien & Name
        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
        if 'name' in gdf.columns:
            gdf = gdf[gdf['name'].str.contains(s_clean, case=False, na=False)]
        
        if gdf.empty: return {"success": False, "original": strasse}

        # 3. Ortsteil bestimmen (Zentroid nutzen)
        gdf = gdf.to_crs(epsg=4326) # WICHTIG: Einheitliches System
        centroid = gdf.geometry.unary_union.centroid
        ortsteil = "Unbekannt"
        
        try:
            location = reverse((centroid.y, centroid.x), language='de')
            if location and 'address' in location.raw:
                a = location.raw['address']
                ortsteil = a.get('village') or a.get('suburb') or a.get('hamlet') or a.get('town') or a.get('city_district') or "Unbekannt"
        except: pass
        
        return {"gdf": gdf, "ort": ortsteil, "name": s_clean, "success": True}
    except:
        return {"success": False, "original": strasse}

# --- 4. UI HAUPTFENSTER ---
st.title("INTEGRAL PRO — V5.6")
st.caption("Präzisions-Tool für die Straßen-Analyse")

col1, col2 = st.columns(2)
with col1:
    files = st.file_uploader("TXT Dateien", type=["txt"], accept_multiple_files=True)
with col2:
    manual = st.text_area("Manuelle Eingabe", placeholder="Eine Straße pro Zeile...")

if st.button("🚀 Analyse starten", type="primary", use_container_width=True):
    strassen = []
    if files:
        for f in files: strassen.extend([s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()])
    if manual:
        strassen.extend([s.strip() for s in manual.splitlines() if s.strip()])
    
    strassen = list(dict.fromkeys(strassen)) # Dubletten weg
    
    if strassen:
        st.session_state.run_processing = True
        temp_ort = defaultdict(list)
        temp_err = []
        
        pb = st.progress(0)
        st_text = st.empty()
        
        with ThreadPoolExecutor(max_workers=4) as exe:
            results = list(exe.map(verarbeite_strasse, strassen))
            for i, res in enumerate(results):
                if res["success"]:
                    temp_ort[res["ort"]].append(res)
                else:
                    temp_err.append(res["original"])
                pb.progress((i+1)/len(strassen))
                st_text.text(f"Gelesen: {res.get('name', 'Fehler')}")
        
        st.session_state.ort_sammlung = dict(temp_ort)
        st.session_state.fehler_liste = temp_err
        st.session_state.run_processing = False
        st.balloons()
        st.rerun()

# --- 5. DARSTELLUNG ---
if st.session_state.ort_sammlung:
    if st.session_state.fehler_liste:
        with st.expander("⚠️ Nicht gefundene Einträge"):
            st.warning(", ".join(st.session_state.fehler_liste))

    # Karte Bauen
    m = folium.Map(location=[50.8, 8.8], zoom_start=11)
    all_gdfs = []

    for ort, items in st.session_state.ort_sammlung.items():
        color = selected_colors.get(ort, "#FF0000")
        fg = folium.FeatureGroup(name=f"{ort} ({len(items)})")
        
        for item in items:
            g = item["gdf"]
            all_gdfs.append(g)
            folium.GeoJson(
                g.__geo_interface__,
                style_function=lambda x, c=color: {'color': c, 'weight': 6, 'opacity': 0.8},
                tooltip=f"Straße: {item['name']}"
            ).add_to(fg)
        fg.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    # Zoom-Anpassung
    if all_gdfs:
        combined = pd.concat(all_gdfs)
        b = combined.total_bounds
        m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])

    # Anzeige
    html = m._repr_html_()
    components.html(html, height=700)
    
    st.download_button("📥 Karte als HTML speichern", html, file_name="Ergebnis.html", mime="text/html")
