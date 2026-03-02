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

# --- 1. SETUP & THEME ---
st.set_page_config(page_title="INTEGRAL PRO", layout="wide", page_icon="📈")

GITHUB_BG_URL = 'https://raw.githubusercontent.com/waldsterbehilfe/integral-web/main/hintergrund.png'
LOGO_URL = "https://integral-online.de/images/integral-gmbh-logo.png"

# --- 2. LOGIK & CACHE ---
geolocator = Nominatim(user_agent="integral_pro_v58")
reverse = RateLimiter(geolocator.reverse, min_delay_seconds=1.1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "persistent_geocache")
os.makedirs(CACHE_DIR, exist_ok=True)
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR

if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'fehler_liste' not in st.session_state: st.session_state.fehler_liste = []
if 'run_processing' not in st.session_state: st.session_state.run_processing = False
if 'stop_requested' not in st.session_state: st.session_state.stop_requested = False

# --- SIDEBAR ---
with st.sidebar:
    st.title("Einstellungen")
    bg_toggle = st.checkbox("Hintergrundbild", value=True)
    st.divider()
    selected_colors = {}
    if st.session_state.ort_sammlung:
        st.subheader("🎨 Ebenen-Farben")
        for ort in sorted(st.session_state.ort_sammlung.keys()):
            selected_colors[ort] = st.color_picker(f"Farbe für {ort}", "#FF0000", key=f"cp_{ort}")
    st.divider()
    if st.button("🗑️ Geocache leeren", use_container_width=True):
        shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR, exist_ok=True)
        st.rerun()

if bg_toggle:
    st.markdown(f"<style>.stApp {{background-image: url('{GITHUB_BG_URL}'); background-size: cover; background-attachment: fixed; background-color: #0E1117;}}</style>", unsafe_allow_html=True)

# --- FUNKTIONEN (MIT AUTO-KORREKTUR) ---
def verarbeite_strasse(strasse):
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    # Suche im Landkreis Marburg-Biedenkopf einschränken
    query = f"{s_clean}, Marburg-Biedenkopf"
    
    try:
        # Erster Versuch: Exakte Suche
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=500)
        
        # Zweiter Versuch: Wenn leer, probiere "unscharfe" Suche über Geocoder
        if gdf.empty:
            possible_loc = geolocator.geocode(query, exactly_one=True, timeout=10)
            if possible_loc:
                # Nutze die gefundenen Koordinaten für eine Umkreissuche
                gdf = ox.features_from_point((possible_loc.latitude, possible_loc.longitude), tags={"highway": True}, dist=200)

        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            gdf = gdf.to_crs(epsg=4326)
            
            # Den wahrscheinlichsten Namen aus den OSM Daten extrahieren
            osm_name = gdf['name'].iloc[0] if 'name' in gdf.columns else s_clean
            
            ortsteil = "Unbekannt"
            centroid = gdf.geometry.unary_union.centroid
            location = reverse((centroid.y, centroid.x), language='de')
            if location and 'address' in location.raw:
                addr = location.raw['address']
                for key in ['village', 'hamlet', 'suburb', 'city_district', 'town']:
                    if key in addr:
                        ortsteil = addr[key]
                        break
            return {"gdf": gdf, "ort": ortsteil, "name": osm_name, "original": strasse, "success": True}
    except:
        return {"success": False, "original": strasse}
    return {"success": False, "original": strasse}

# --- 3. UI ---
col_logo, col_title = st.columns([1, 10])
with col_logo: st.image(LOGO_URL, width=120)
with col_title:
    st.title("INTEGRAL PRO")
    st.markdown("Automatisierte Sortierung — **V5.8 (Auto-Correct)**")

st.divider()
col_in1, col_in2 = st.columns(2)
with col_in1: files = st.file_uploader("TXT Dateien", type=["txt"], accept_multiple_files=True)
with col_in2: manual = st.text_area("Manuelle Eingabe", height=126)

strassen_liste = []
if files:
    for f in files: strassen_liste.extend([s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()])
if manual: strassen_liste.extend([s.strip() for s in manual.splitlines() if s.strip()])
strassen_liste = list(dict.fromkeys(strassen_liste))

col_btn1, col_btn2, _ = st.columns([1, 1, 3])
if col_btn1.button("🚀 Analyse starten", type="primary"):
    st.session_state.run_processing, st.session_state.stop_requested = True, False
    st.session_state.ort_sammlung, st.session_state.fehler_liste = None, []

if col_btn2.button("🛑 Abbruch", type="secondary"):
    st.session_state.stop_requested, st.session_state.run_processing = True, False

# --- 4. VERARBEITUNG ---
if st.session_state.run_processing and strassen_liste:
    temp_ort, temp_err = defaultdict(list), []
    pb = st.progress(0)
    st_text = st.empty()
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(verarbeite_strasse, s): s for s in strassen_liste}
        for i, future in enumerate(futures):
            if st.session_state.stop_requested: break
            res = future.result()
            if res["success"]:
                temp_ort[res["ort"]].append(res)
            else:
                temp_err.append(res["original"])
            pb.progress((i + 1) / len(strassen_liste))
            st_text.text(f"🔍 Gefunden: {res.get('name', 'Suche...')}")

    if not st.session_state.stop_requested:
        st.session_state.ort_sammlung, st.session_state.fehler_liste = dict(temp_ort), temp_err
        st.balloons()
    st.session_state.run_processing = False
    st.rerun()

# --- 5. ANZEIGE ---
if st.session_state.ort_sammlung:
    if st.session_state.fehler_liste:
        with st.expander("⚠️ Nicht gefunden (auch nicht via Korrektur)"):
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
                           tooltip=f"Gefunden als: {item['name']} (Input: {item['original']})").add_to(fg)
        fg.add_to(m)
    
    folium.LayerControl(collapsed=False).add_to(m)
    if all_geoms:
        combined = gpd.GeoDataFrame(pd.concat(all_geoms))
        b = combined.total_bounds 
        m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])

    st.subheader("Interaktive Karte")
    components.html(m._repr_html_(), height=700)
    st.download_button("📥 Karte speichern", m._repr_html_(), file_name="Ergebnis.html", mime="text/html")
