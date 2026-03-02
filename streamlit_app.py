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

# --- 2. LOGIK & CACHE ---
geolocator = Nominatim(user_agent="integral_pro_app")
reverse = RateLimiter(geolocator.reverse, min_delay_seconds=1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "persistent_geocache")
os.makedirs(CACHE_DIR, exist_ok=True)
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR

# Session State Initialisierung
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'fehler_liste' not in st.session_state: st.session_state.fehler_liste = []
if 'run_processing' not in st.session_state: st.session_state.run_processing = False
if 'stop_requested' not in st.session_state: st.session_state.stop_requested = False

# --- SIDEBAR ---
with st.sidebar:
    st.title("Einstellungen")
    bg_toggle = st.checkbox("Hintergrundbild", value=True)
    st.divider()
    
    st.subheader("Ebenen-Farben")
    selected_colors = {}
    if st.session_state.ort_sammlung:
        for ort in sorted(st.session_state.ort_sammlung.keys()):
            selected_colors[ort] = st.color_picker(f"Farbe für {ort}", "#FF0000", key=f"cp_{ort}")
    else:
        st.info("Farben erscheinen nach der Analyse.")
    
    st.divider()
    st.subheader("Wartung")
    if st.button("🗑️ Geocache leeren"):
        try:
            shutil.rmtree(CACHE_DIR)
            os.makedirs(CACHE_DIR, exist_ok=True)
            st.success("Cache geleert!")
            st.rerun()
        except Exception as e:
            st.error(f"Fehler: {e}")

# Styling
if bg_toggle:
    st.markdown(f"<style>.stApp {{background-image: url('{GITHUB_BG_URL}'); background-size: cover; background-attachment: fixed; background-color: #0E1117;}}</style>", unsafe_allow_html=True)
else:
    st.markdown("<style>.stApp {background-image: none; background-color: #0E1117;}</style>", unsafe_allow_html=True)

# --- FUNKTIONEN ---
def verarbeite_strasse(strasse):
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    query = f"{s_clean}, Marburg-Biedenkopf"
    try:
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=500)
        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            if 'name' in gdf.columns:
                gdf_f = gdf[gdf['name'].str.contains(s_clean, case=False, na=False)]
            else:
                gdf_f = gdf
            if not gdf_f.empty:
                ortsteil = "Unbekannt"
                centroid = gdf_f.geometry.centroid.iloc[0]
                location = reverse((centroid.y, centroid.x), language='de')
                if location and 'address' in location.raw:
                    addr = location.raw['address']
                    for key in ['village', 'hamlet', 'suburb', 'city_district', 'town']:
                        if key in addr:
                            ortsteil = addr[key]
                            break
                return {"gdf": gdf_f, "ort": ortsteil, "name": s_clean, "success": True}
    except:
        return {"success": False, "original": strasse}
    return {"success": False, "original": strasse}

# --- 3. UI HAUPTFENSTER ---
col_logo, col_title = st.columns([1, 10])
with col_logo:
    st.image("https://integral-online.de/images/integral-gmbh-logo.png", width=120)
with col_title:
    st.title("INTEGRAL PRO")
    st.markdown("Automatisierte Sortierung — **V5.5 (Fix Edition)**")

st.divider()

col_in1, col_in2 = st.columns(2)
with col_in1:
    uploaded_files = st.file_uploader("Dateien laden (.txt)", type=["txt"], accept_multiple_files=True)
with col_in2:
    manual_input = st.text_area("Manuelle Eingabe", placeholder="Straßen untereinander...", height=126)

strassen_liste = []
if uploaded_files:
    for f in uploaded_files:
        strassen_liste.extend([s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()])
if manual_input:
    strassen_liste.extend([s.strip() for s in manual_input.splitlines() if s.strip()])
strassen_liste = list(dict.fromkeys(strassen_liste))

col_btn1, col_btn2, _ = st.columns([1, 1, 3])
if col_btn1.button("🚀 Analyse starten", type="primary"):
    st.session_state.run_processing = True
    st.session_state.stop_requested = False
    st.session_state.ort_sammlung = None # Reset für neuen Durchlauf
    st.session_state.fehler_liste = []

if col_btn2.button("🛑 Abbruch", type="secondary"):
    st.session_state.stop_requested = True

# --- 4. VERARBEITUNG ---
if st.session_state.run_processing and strassen_liste:
    temp_ort_sammlung = defaultdict(list)
    temp_fehler_liste = []
    
    prog_bar = st.progress(0)
    status_text = st.empty()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(verarbeite_strasse, s): s for s in strassen_liste}
        for i, future in enumerate(futures):
            if st.session_state.stop_requested:
                break
            res = future.result()
            if res["success"]:
                temp_ort_sammlung[res["ort"]].append(res)
            else:
                temp_fehler_liste.append(res["original"])
            
            prog_bar.progress((i + 1) / len(strassen_liste))
            status_text.text(f"🔍 Verarbeite: {res.get('name', res.get('original'))}")

    # Speichern in Session State
    st.session_state.ort_sammlung = dict(temp_ort_sammlung)
    st.session_state.fehler_liste = temp_fehler_liste
    st.session_state.run_processing = False
    
    if not st.session_state.stop_requested:
        st.balloons()
    st.rerun()

# --- 5. ERGEBNIS-ANZEIGE ---
if st.session_state.ort_sammlung:
    st.success(f"✅ Analyse abgeschlossen. {len(st.session_state.ort_sammlung)} Ortsteile gefunden.")
    
    # Fehleranzeige
    if st.session_state.fehler_liste:
        with st.expander("⚠️ Nicht gefundene Straßen"):
            st.write(", ".join(st.session_state.fehler_liste))

    # Karte rendern
    m = folium.Map(location=[50.8, 8.8], zoom_start=11, control_scale=True)
    all_geoms = []

    for ort, items in st.session_state.ort_sammlung.items():
        color = selected_colors.get(ort, "#FF0000")
        fg = folium.FeatureGroup(name=f"📍 {ort} ({len(items)} Str.)")
        
        for item in items:
            gdf = item["gdf"]
            all_geoms.append(gdf)
            folium.GeoJson(
                gdf.__geo_interface__,
                style_function=lambda x, c=color: {'color': c, 'weight': 6, 'opacity': 0.8},
                tooltip=folium.GeoJsonTooltip(fields=['name'], aliases=['Straße:'])
            ).add_to(fg)
        fg.add_to(m)
    
    folium.LayerControl(collapsed=False).add_to(m)
    
    if all_geoms:
        combined = gpd.GeoDataFrame(pd.concat(all_geoms))
        b = combined.total_bounds 
        m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])

    st.subheader("Interaktive Karte")
    html_string = m._repr_html_()
    components.html(html_string, height=600)
    st.download_button(label="📥 Karte speichern", data=html_string, file_name="Karte.html", mime="text/html")
