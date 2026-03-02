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
import streamlit.components.v1 as components

# --- 1. SETUP & THEME ---
st.set_page_config(page_title="INTEGRAL PRO", layout="wide", page_icon="📈")

GITHUB_BG_URL = 'https://raw.githubusercontent.com/waldsterbehilfe/integral-web/main/hintergrund.png'
LOGO_URL = "https://integral-online.de/images/integral-gmbh-logo.png"

# Cache & Verzeichnisse
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "persistent_geocache")
os.makedirs(CACHE_DIR, exist_ok=True)
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR

# Geocoder ohne künstliche Bremse (ThreadPool regelt das)
geolocator = Nominatim(user_agent="integral_pro_v59_fast")

# Session State
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'fehler_liste' not in st.session_state: st.session_state.fehler_liste = []
if 'run_processing' not in st.session_state: st.session_state.run_processing = False
if 'stop_requested' not in st.session_state: st.session_state.stop_requested = False
if 'manual_text' not in st.session_state: st.session_state.manual_text = ""

# --- SIDEBAR ---
with st.sidebar:
    st.title("Einstellungen")
    bg_toggle = st.checkbox("Hintergrundbild", value=True)
    st.divider()
    selected_colors = {}
    if st.session_state.ort_sammlung:
        st.subheader("🎨 Ebenen-Farben")
        for ort in sorted(st.session_state.ort_sammlung.keys()):
            selected_colors[ort] = st.color_picker(f"{ort}", "#FF0000", key=f"cp_{ort}")
    st.divider()
    if st.button("🗑️ Geocache leeren", use_container_width=True):
        shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR, exist_ok=True)
        st.rerun()

if bg_toggle:
    st.markdown(f"<style>.stApp {{background-image: url('{GITHUB_BG_URL}'); background-size: cover; background-attachment: fixed; background-color: #0E1117;}}</style>", unsafe_allow_html=True)

# --- SPEED-OPTIMIERTE FUNKTION ---
def verarbeite_strasse(strasse):
    if not strasse: return {"success": False}
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    query = f"{s_clean}, Marburg-Biedenkopf"
    
    try:
        # 1. Schnelle Suche via OSMnx Cache/API
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=500)
        
        # 2. Nur wenn nichts gefunden: Geocoder Fallback (langsam)
        if gdf.empty:
            loc = geolocator.geocode(query, timeout=5)
            if loc:
                gdf = ox.features_from_point((loc.latitude, loc.longitude), tags={"highway": True}, dist=250)

        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
            osm_name = gdf['name'].iloc[0] if 'name' in gdf.columns else s_clean
            
            # Ortsteil-Bestimmung (Schnell-Check)
            centroid = gdf.geometry.unary_union.centroid
            # Wir machen den Reverse-Check nur einmal pro Straße
            loc_rev = geolocator.reverse((centroid.y, centroid.x), language='de', timeout=5)
            ortsteil = "Unbekannt"
            if loc_rev and 'address' in loc_rev.raw:
                a = loc_rev.raw['address']
                ortsteil = a.get('village') or a.get('suburb') or a.get('hamlet') or a.get('town') or "Unbekannt"
            
            return {"gdf": gdf, "ort": ortsteil, "name": osm_name, "original": strasse, "success": True}
    except:
        pass
    return {"success": False, "original": strasse}

# --- 3. UI ---
col_logo, col_title = st.columns([1, 10])
with col_logo: st.image(LOGO_URL, width=120)
with col_title:
    st.title("INTEGRAL PRO")
    st.markdown("Automatisierte Sortierung — **V5.9 (High Speed)**")

st.divider()
col_in1, col_in2 = st.columns(2)
with col_in1: files = st.file_uploader("TXT Dateien", type=["txt"], accept_multiple_files=True)
with col_in2: 
    manual_input = st.text_area("Manuelle Eingabe", 
                                value=st.session_state.manual_text,
                                placeholder="Straßen untereinander...", 
                                height=126)

strassen_liste = []
if files:
    for f in files: strassen_liste.extend([s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()])
if manual_input: 
    strassen_liste.extend([s.strip() for s in manual_input.splitlines() if s.strip()])
strassen_liste = list(dict.fromkeys(strassen_liste))

col_btn1, col_btn2, _ = st.columns([1, 1, 3])

if col_btn1.button("🚀 Analyse starten", type="primary"):
    st.session_state.manual_text = manual_input # Speichern für Rerun-Sicherheit
    st.session_state.run_processing, st.session_state.stop_requested = True, False
    st.session_state.ort_sammlung, st.session_state.fehler_liste = None, []

if col_btn2.button("🛑 Abbruch", type="secondary"):
    st.session_state.stop_requested, st.session_state.run_processing = True, False
    st.session_state.manual_text = "" # LEEREN BEI ABBRUCH
    st.rerun()

# --- 4. PARALLELE VERARBEITUNG ---
if st.session_state.run_processing and strassen_liste:
    temp_ort, temp_err = defaultdict(list), []
    pb = st.progress(0)
    st_text = st.empty()
    
    # max_workers=2 um Nominatim nicht zu verärgern, aber parallel genug für OSMnx
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(verarbeite_strasse, s): s for s in strassen_liste}
        for i, future in enumerate(futures):
            if st.session_state.stop_requested: break
            res = future.result()
            if res.get("success"):
                temp_ort[res["ort"]].append(res)
            else:
                temp_err.append(res.get("original", "Unbekannt"))
            pb.progress((i + 1) / len(strassen_liste))
            st_text.text(f"🔍 Status: {res.get('name', 'Suche...')}")

    if not st.session_state.stop_requested:
        st.session_state.ort_sammlung, st.session_state.fehler_liste = dict(temp_ort), temp_err
        st.balloons()
    st.session_state.run_processing = False
    st.rerun()

# --- 5. ANZEIGE ---
if st.session_state.ort_sammlung:
    if st.session_state.fehler_liste:
        with st.expander("⚠️ Nicht gefunden"):
            st.write(", ".join(st.session_state.fehler_liste))

    m = folium.Map(location=[50.8, 8.8], zoom_start=11)
    all_geoms = []
    for ort, items in st.session_state.ort_sammlung.items():
        color = selected_colors.get(ort, "#FF0000")
        fg = folium.FeatureGroup(name=f"📍 {ort} ({len(items)} Str.)")
        for item in items:
            all_geoms.append(item["gdf"])
            folium.GeoJson(item["gdf"].__geo_interface__,
                           style_function=lambda x, c=color: {'color': c, 'weight': 6, 'opacity': 0.8},
                           tooltip=f"{item['name']}").add_to(fg)
        fg.add_to(m)
    
    folium.LayerControl(collapsed=False).add_to(m)
    if all_geoms:
        combined = gpd.GeoDataFrame(pd.concat(all_geoms))
        m.fit_bounds([[combined.total_bounds[1], combined.total_bounds[0]], [combined.total_bounds[3], combined.total_bounds[2]]])

    components.html(m._repr_html_(), height=700)
    st.download_button("📥 Karte speichern", m._repr_html_(), file_name="Ergebnis.html", mime="text/html")
