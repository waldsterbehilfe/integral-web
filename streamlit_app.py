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

# --- 1. SETUP & SERIENNUMMER ---
# Fix: Alle unsichtbaren Zeichen entfernt
SERIAL_NUMBER = f"GOLD-{datetime.now().strftime('%Y%m%d-%H%M')}"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
EGG_IMAGE_PATH = os.path.join(BASE_DIR, "eegg.jpg")
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
if 'egg_counter' not in st.session_state: st.session_state.egg_counter = 0

# --- 2. SIDEBAR ---
with st.sidebar:
    st.header("🛠️ Einstellungen")
    line_weight = st.slider("Linienstärke Karte", 1, 15, 6)
    
    if st.session_state.ort_sammlung:
        st.subheader("🎨 Ortsteil-Farben")
        for ort in sorted(st.session_state.ort_sammlung.keys()):
            st.session_state.colors[ort] = st.color_picker(f"{ort}", st.session_state.colors.get(ort, "#FF0000"), key=f"cp_{ort}")
    
    st.divider()
    if st.button("🗑️ Cache & System leeren"):
        if os.path.exists(CACHE_DIR): shutil.rmtree(CACHE_DIR)
        st.cache_data.clear()
        st.rerun()

# --- 3. HAUPTBEREICH MIT VERSTECKTEM O (EASTER EGG) ---
# Das O ist jetzt ein nahtlos integrierter Button
c_title_text, c_title_o = st.columns([2.3, 10])

with c_title_text:
    st.markdown("<h1 style='text-align: right; margin-bottom: 0;'>🚀 INTEGRAL PR</h1>", unsafe_allow_html=True)

with c_title_o:
    if st.button("O", key="egg_trigger"):
        st.session_state.egg_counter += 1
    
    st.markdown("""
        <style>
            /* Macht den Button unsichtbar bzw. passt ihn an den Text an */
            div[data-testid="stColumn"]:nth-child(2) button {
                background: none !important;
                border: none !important;
                padding: 0 !important;
                font-size: 3rem !important;
                font-weight: 700 !important;
                color: white !important;
                margin-top: 0.45rem !important;
                line-height: 1 !important;
                box-shadow: none !important;
            }
            div[data-testid="stColumn"]:nth-child(2) button:hover {
                color: #00ff00 !important; /* Kleiner visueller Hinweis beim Hover */
            }
        </style>
    """, unsafe_allow_html=True)

if st.session_state.egg_counter >= 10:
    st.balloons()
    with st.container(border=True):
        st.success("🎉 Easter Egg aktiviert!")
        if os.path.exists(EGG_IMAGE_PATH):
            st.image(EGG_IMAGE_PATH, use_container_width=True)
        else:
            st.error(f"Bild 'eegg.jpg' nicht im Ordner {BASE_DIR} gefunden.")
        if st.button("Schließen"):
            st.session_state.egg_counter = 0
            st.rerun()

st.divider()

# --- 4. INPUT (DATEI & EINZELN) ---
col_in1, col_in2 = st.columns(2)
with col_in1:
    with st.container(border=True):
        files = st.file_uploader("TXT Dateien importieren", type=["txt"], accept_multiple_files=True)
        if files:
            new = []
            for f in files: 
                lines = [s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()]
                new.extend(lines)
            st.session_state.saved_manual_streets = sorted(list(set(st.session_state.saved_manual_streets + new)))
            st.rerun()
        
        st.divider()
        q_s = st.text_input("Straße hinzufügen:")
        if st.button("➕ Hinzufügen"):
            if q_s and q_s not in st.session_state.saved_manual_streets:
                st.session_state.saved_manual_streets.append(q_s)
                st.session_state.saved_manual_streets.sort()
                st.rerun()

with col_in2:
    st.subheader("📝 Aktuelle Liste")
    st.dataframe(st.session_state.saved_manual_streets, use_container_width=True, height=220)
    if st.button("🗑️ Liste leeren"):
        st.session_state.saved_manual_streets = []
        st.rerun()

# --- 5. ANALYSE-LOGIK ---
def verarbeite_strasse(strasse_input):
    if st.session_state.stop_requested: return {"success": False}
    time.sleep(1.1)
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse_input).strip()
    try:
        gdf = ox.features_from_address(f"{s_clean}, Marburg-Biedenkopf", tags={"highway": True}, dist=60)
        if gdf.empty: return {"success": False}
        gdf = gdf[gdf['name'].apply(lambda x: str(x).strip().lower() == s_clean.lower())]
        if gdf.empty: return {"success": False}
        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
        centroid = gdf.geometry.unary_union.centroid
        loc_rev = geolocator.reverse((centroid.y, centroid.x), language='de')
        ort = loc_rev.raw.get('address', {}).get('village') or loc_rev.raw.get('address', {}).get('suburb', "Marburg")
        return {"gdf": gdf, "ort": ort, "name": s_clean, "original": strasse_input, "success": True}
    except: return {"success": False}

if st.button("🔥 ANALYSE STARTEN", type="primary"):
    st.session_state.run_processing, st.session_state.stop_requested = True, False

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

# --- 6. KARTE MIT TOOLTIP ---
if st.session_state.ort_sammlung:
    m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
    for ort, items in st.session_state.ort_sammlung.items():
        color = st.session_state.colors.get(ort, "#FF0000")
        fg = folium.FeatureGroup(name=ort)
        for itm in items:
            folium.GeoJson(
                itm["gdf"].__geo_interface__,
                style_function=lambda x, c=color: {'color': c, 'weight': line_weight, 'opacity': 0.7},
                highlight_function=lambda x: {'weight': line_weight + 3, 'opacity': 1},
                tooltip=folium.Tooltip(f"<b>{itm['name']}</b><br>Ortsteil: {ort}")
            ).add_to(fg)
        fg.add_to(m)
    folium.LayerControl().add_to(m)
    components.html(m._repr_html_(), height=600)
