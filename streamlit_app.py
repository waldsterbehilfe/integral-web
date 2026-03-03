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
import time

# --- 1. SETUP ---
SERIAL_NUMBER = f"GOLD-{datetime.now().strftime('%Y%m%d-%H%M')}"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=10)

# Session State Initialisierung
if 'saved_manual_streets' not in st.session_state: st.session_state.saved_manual_streets = []
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'run_processing' not in st.session_state: st.session_state.run_processing = False
if 'stop_requested' not in st.session_state: st.session_state.stop_requested = False
if 'colors' not in st.session_state: st.session_state.colors = {}

# --- 2. SIDEBAR (ERWEITERT) ---
with st.sidebar:
    st.header("🛠️ Einstellungen")
    
    # NEU: Linienstärke für bessere Hover-Erfahrung
    line_weight = st.slider("Linienstärke (Karte)", 1, 15, 6)
    
    st.divider()
    if st.session_state.ort_sammlung:
        st.subheader("🎨 Ortsteil-Farben")
        for ort in sorted(st.session_state.ort_sammlung.keys()):
            st.session_state.colors[ort] = st.color_picker(f"{ort}", st.session_state.colors.get(ort, "#FF0000"), key=f"cp_{ort}")
    
    st.divider()
    if st.button("🗑️ Cache leeren"):
        if os.path.exists(CACHE_DIR): shutil.rmtree(CACHE_DIR)
        st.rerun()

# --- 3. LOGIK ---
def verarbeite_strasse(strasse_input):
    if st.session_state.stop_requested: return {"success": False}
    time.sleep(1.1)
    parts = strasse_input.split(" | ") if " | " in strasse_input else [strasse_input, None]
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', parts[0].strip()).strip()
    try:
        gdf = ox.features_from_address(f"{s_clean}, Marburg-Biedenkopf", tags={"highway": True}, dist=60)
        if gdf.empty: return {"success": False}
        gdf = gdf[gdf['name'].apply(lambda x: str(x).strip().lower() == s_clean.lower())]
        if gdf.empty: return {"success": False}
        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
        
        centroid = gdf.geometry.unary_union.centroid
        loc_rev = geolocator.reverse((centroid.y, centroid.x), language='de')
        ort = loc_rev.raw.get('address', {}).get('village') or loc_rev.raw.get('address', {}).get('suburb', "Marburg")
        
        return {"gdf": gdf, "ort": ort, "name": s_clean, "original": strasse_input, "marker": None, "success": True}
    except: return {"success": False}

# --- 4. UI HAUPTBEREICH ---
st.title("🚀 INTEGRAL PRO")
col_in1, col_in2 = st.columns(2)

with col_in1:
    with st.container(border=True):
        files = st.file_uploader("TXT Dateien importieren", type=["txt"], accept_multiple_files=True)
        if files:
            new = []
            for f in files: new.extend([s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()])
            st.session_state.saved_manual_streets = sorted(list(set(st.session_state.saved_manual_streets + new)))
            st.rerun()
        
        q_s = st.text_input("Straße:")
        if st.button("➕ Hinzufügen"):
            if q_s and q_s not in st.session_state.saved_manual_streets:
                st.session_state.saved_manual_streets.append(q_s)
                st.session_state.saved_manual_streets.sort()
                st.rerun()

with col_in2:
    st.dataframe(st.session_state.saved_manual_streets, use_container_width=True, height=220)
    if st.button("🗑️ Liste leeren"):
        st.session_state.saved_manual_streets = []
        st.rerun()

if st.button("🔥 ANALYSE STARTEN", type="primary"):
    st.session_state.run_processing, st.session_state.stop_requested = True, False

# --- 5. LOOP ---
if st.session_state.run_processing:
    temp_ort = defaultdict(list)
    total = len(st.session_state.saved_manual_streets)
    pb = st.progress(0)
    with ThreadPoolExecutor(max_workers=1) as exe:
        futs = {exe.submit(verarbeite_strasse, s): s for s in st.session_state.saved_manual_streets}
        for i, f in enumerate(futs):
            if st.session_state.stop_requested: break
            res = f.result()
            pb.progress((i + 1) / total)
            if res.get("success"): temp_ort[res["ort"]].append(res)
    st.session_state.ort_sammlung = dict(temp_ort)
    st.session_state.run_processing = False
    st.rerun()

# --- 6. KARTE MIT MOUSE-OVER (TOOLTIP) ---
if st.session_state.ort_sammlung:
    m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
    for ort, items in st.session_state.ort_sammlung.items():
        color = st.session_state.colors.get(ort, "#FF0000")
        fg = folium.FeatureGroup(name=ort)
        for itm in items:
            # Das Tooltip-Feature für Mouse-Over:
            folium.GeoJson(
                itm["gdf"].__geo_interface__,
                style_function=lambda x, c=color: {
                    'color': c, 
                    'weight': line_weight, 
                    'opacity': 0.7
                },
                highlight_function=lambda x: {'weight': line_weight + 3, 'opacity': 1}, # Effekt bei Mouse-Over
                tooltip=folium.Tooltip(f"<b>{itm['name']}</b><br>Ortsteil: {ort}") # Das eigentliche Mouse-Over
            ).add_to(fg)
        fg.add_to(m)
    
    folium.LayerControl().add_to(m)
    components.html(m._repr_html_(), height=600)
