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
# Dynamische ID für jede Sitzung
SERIAL_NUMBER = f"GOLD-{datetime.now().strftime('%Y%m%d-%H%M')}"

st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

# CSS für stabiles UI
st.markdown("""
<style>
    .stApp {background-color: #0E1117;}
    div.stButton > button {width: 100%; border-radius: 5px; font-weight: bold;}
    div[data-testid="stExpander"] {border: 1px solid #30363d; border-radius: 8px;}
    .stDataFrame {border: 1px solid #30363d; border-radius: 8px;}
</style>
""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=10)

# --- 2. HILFSFUNKTIONEN (PERSISTENZ) ---
def get_cache_info():
    if os.path.exists(CACHE_DIR):
        files = os.listdir(CACHE_DIR)
        size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files) / (1024 * 1024)
        return len(files), round(size, 2)
    return 0, 0

def load_streets_from_disk():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return sorted(list(set([l.strip() for l in f.readlines() if l.strip()])))
    return []

def save_streets_to_disk(streets):
    clean_list = sorted(list(set([s.strip() for s in streets if s.strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(clean_list))
    return clean_list

# Session State Initialisierung
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets_from_disk()
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'run_processing' not in st.session_state: st.session_state.run_processing = False
if 'stop_requested' not in st.session_state: st.session_state.stop_requested = False
if 'colors' not in st.session_state: st.session_state.colors = {}

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("🛠️ System-Steuerung")
    st.caption(f"ID: {SERIAL_NUMBER}")
    st.divider()
    
    # Cache Info
    count, size = get_cache_info()
    st.metric("Cache Menge", f"{count} Files")
    st.metric("Cache Größe", f"{size} MB")
    
    if st.button("🗑️ System bereinigen"):
        if os.path.exists(CACHE_DIR): shutil.rmtree(CACHE_DIR)
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("🎨 Ortsteil-Farben")
    if st.session_state.ort_sammlung:
        for ort in sorted(st.session_state.ort_sammlung.keys()):
            default_color = st.session_state.colors.get(ort, "#FF0000")
            st.session_state.colors[ort] = st.color_picker(f"{ort}", default_color, key=f"cp_{ort}")
    else:
        st.info("Farben nach Analyse.")

# --- 4. HAUPTBEREICH: INPUT & LISTE ---
st.title("🚀 INTEGRAL PRO")

col_in1, col_in2 = st.columns(2)

with col_in1:
    with st.container(border=True):
        st.subheader("📥 Daten-Import")
        
        # DATEI-UPLOAD (SOFORTIGE AKTUALISIERUNG)
        uploaded_files = st.file_uploader("TXT Dateien wählen", type=["txt"], accept_multiple_files=True)
        if uploaded_files:
            new_entries = []
            for f in uploaded_files:
                lines = [s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()]
                new_entries.extend(lines)
            
            if new_entries:
                # Kombinieren, Speichern und State aktualisieren
                st.session_state.saved_manual_streets = save_streets_to_disk(st.session_state.saved_manual_streets + new_entries)
                # Wichtig: Rerun erzwingen, damit die Liste rechts sofort erscheint!
                st.rerun()
        
        st.divider()
        c_str, c_hnr = st.columns([3, 1])
        q_s = c_str.text_input("Straße:")
        q_h = c_hnr.text_input("Hnr:")
        
        if st.button("➕ Hinzufügen"):
            if q_s:
                entry = f"{q_s} | {q_h}" if q_h else q_s
                st.session_state.saved_manual_streets = save_streets_to_disk(st.session_state.saved_manual_streets + [entry])
                st.rerun()

with col_in2:
    with st.container(border=True):
        st.subheader("📝 Aktuelle Liste")
        # Zeigt die Liste direkt aus dem Session State
        st.dataframe(st.session_state.saved_manual_streets, use_container_width=True, height=250)
        
        if st.button("🗑️ Liste leeren"):
            st.session_state.saved_manual_streets = []
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.rerun()

# --- 5. ANALYSE-LOGIK ---
def verarbeite_strasse(strasse_input):
    if st.session_state.stop_requested: return {"success": False}
    time.sleep(1.1)
    parts = strasse_input.split(" | ") if " | " in strasse_input else [strasse_input, None]
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', parts[0].strip()).strip()
    try:
        gdf = ox.features_from_address(f"{s_clean}, Marburg-Biedenkopf", tags={"highway": True}, dist=50)
        if gdf.empty: return {"success": False}
        gdf = gdf[gdf['name'].apply(lambda x: str(x).strip().lower() == s_clean.lower())]
        if gdf.empty: return {"success": False}
        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
        centroid = gdf.geometry.unary_union.centroid
        loc_rev = geolocator.reverse((centroid.y, centroid.x), language='de')
        ort = loc_rev.raw.get('address', {}).get('village') or loc_rev.raw.get('address', {}).get('suburb', "Marburg")
        marker_coords = None
        if parts[1]:
            l = geolocator.geocode(f"{s_clean} {parts[1].strip()}, Marburg-Biedenkopf")
            if l: marker_coords = (l.latitude, l.longitude)
        return {"gdf": gdf, "ort": ort, "name": s_clean, "original": strasse_input, "marker": marker_coords, "success": True}
    except: return {"success": False}

st.divider()
c_act1, c_act2 = st.columns([1, 1])
if c_act1.button("🔥 ANALYSE STARTEN", type="primary"):
    st.session_state.run_processing, st.session_state.stop_requested = True, False

if c_act2.button("🛑 ABBRUCH"):
    st.session_state.stop_requested = True

if st.session_state.run_processing:
    temp_ort = defaultdict(list)
    total = len(st.session_state.saved_manual_streets)
    pb = st.progress(0)
    msg = st.empty()
    
    with ThreadPoolExecutor(max_workers=1) as exe:
        futs = {exe.submit(verarbeite_strasse, s): s for s in st.session_state.saved_manual_streets}
        for i, f in enumerate(futs):
            if st.session_state.stop_requested: break
            res = f.result()
            msg.markdown(f"🔍 **Verarbeite {i+1}/{total}:** `{res.get('original', '...')}`")
            pb.progress((i + 1) / total)
            if res.get("success"): temp_ort[res["ort"]].append(res)
    
    st.session_state.ort_sammlung = dict(temp_ort)
    st.session_state.run_processing = False
    st.rerun()

# --- 6. KARTE ---
if st.session_state.ort_sammlung:
    m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
    for ort, items in st.session_state.ort_sammlung.items():
        fg = folium.FeatureGroup(name=ort)
        color = st.session_state.colors.get(ort, "#FF0000")
        for itm in items:
            folium.GeoJson(itm["gdf"].__geo_interface__, style_function=lambda x, c=color: {'color': c, 'weight': 6, 'opacity': 0.7}).add_to(fg)
            if itm["marker"]: folium.Marker(itm["marker"], popup=itm["original"]).add_to(fg)
        fg.add_to(m)
    folium.LayerControl().add_to(m)
    components.html(m._repr_html_(), height=600)
