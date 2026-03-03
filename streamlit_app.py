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

# --- 1. SETUP & DYNAMISCHE SERIENNUMMER ---
# Jeder Start erhält eine eigene ID basierend auf Datum/Uhrzeit
SERIAL_NUMBER = f"GOLD-{datetime.now().strftime('%Y%m%d-%H%M')}"

st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

# Optische Anpassung
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
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=10)

# --- 2. HILFSFUNKTIONEN ---
def save_streets(streets_list):
    clean = sorted(list(set([s.strip() for s in streets_list if s.strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(clean))
    return clean

def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return sorted([line.strip() for line in f.readlines() if line.strip()])
    return []

# Session State Initialisierung
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets()
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'run_processing' not in st.session_state: st.session_state.run_processing = False

# --- 3. VERARBEITUNG (STRIKTES MATCHING) ---
def verarbeite_strasse(strasse_input):
    if not strasse_input: return {"success": False}
    time.sleep(1.1)
    parts = strasse_input.split(" | ") if " | " in strasse_input else [strasse_input, None]
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', parts[0].strip()).strip()
    
    try:
        # Suche im 50m Umkreis für Präzision
        gdf = ox.features_from_address(f"{s_clean}, Marburg-Biedenkopf", tags={"highway": True}, dist=50)
        if gdf.empty: return {"success": False, "original": strasse_input}
        
        # FIX: Nur exakte Übereinstimmung (verhindert "zu viel markieren")
        gdf = gdf[gdf['name'].apply(lambda x: str(x).strip().lower() == s_clean.lower())]
        if gdf.empty: return {"success": False, "original": strasse_input}
        
        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
        centroid = gdf.geometry.unary_union.centroid
        loc_rev = geolocator.reverse((centroid.y, centroid.x), language='de')
        ort = loc_rev.raw.get('address', {}).get('village', "Marburg")
        
        marker_coords = None
        if parts[1]:
            l = geolocator.geocode(f"{s_clean} {parts[1].strip()}, Marburg-Biedenkopf")
            if l: marker_coords = (l.latitude, l.longitude)
            
        return {"gdf": gdf, "ort": ort, "name": s_clean, "original": strasse_input, "marker": marker_coords, "success": True}
    except: return {"success": False, "original": strasse_input}

# --- 4. UI ---
st.title("🚀 INTEGRAL PRO")
st.caption(f"Sitzung: **{SERIAL_NUMBER}** | System bereit.")

col_in1, col_in2 = st.columns(2)

with col_in1:
    with st.container(border=True):
        st.subheader("📥 Daten-Import")
        
        # UPLOAD LOGIK (FUNKTIONIEREND)
        files = st.file_uploader("TXT Dateien importieren", type=["txt"], accept_multiple_files=True)
        if files:
            new_streets = []
            for f in files:
                lines = [s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()]
                new_streets.extend(lines)
            
            # Update & Sofort-Rerun
            st.session_state.saved_manual_streets = save_streets(st.session_state.saved_manual_streets + new_streets)
            st.rerun()
            
        st.divider()
        c_str, c_hnr = st.columns([3, 1])
        q_s = c_str.text_input("Straße:")
        q_h = c_hnr.text_input("Hnr:")
        if st.button("➕ Hinzufügen"):
            if q_s:
                entry = f"{q_s} | {q_h}" if q_h else q_s
                st.session_state.saved_manual_streets = save_streets(st.session_state.saved_manual_streets + [entry])
                st.rerun()

with col_in2:
    with st.container(border=True):
        st.subheader("📝 Aktuelle Liste")
        st.dataframe(st.session_state.saved_manual_streets, use_container_width=True, height=250)
        if st.button("🗑️ Liste leeren"):
            st.session_state.saved_manual_streets = []
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.rerun()

st.divider()

if st.button("🔥 ANALYSE STARTEN", type="primary"):
    st.session_state.run_processing = True

# --- 5. VERARBEITUNG ---
if st.session_state.run_processing and st.session_state.saved_manual_streets:
    temp_ort = defaultdict(list)
    total = len(st.session_state.saved_manual_streets)
    pb = st.progress(0)
    msg = st.empty()
    
    with ThreadPoolExecutor(max_workers=1) as exe:
        futs = {exe.submit(verarbeite_strasse, s): s for s in st.session_state.saved_manual_streets}
        for i, f in enumerate(futs):
            res = f.result()
            msg.markdown(f"🔍 **Suche {i+1} von {total}:** `{res.get('original')}`")
            pb.progress((i + 1) / total)
            if res.get("success"):
                temp_ort[res["ort"]].append(res)
    
    st.session_state.ort_sammlung = dict(temp_ort)
    st.session_state.run_processing = False
    st.rerun()

# --- 6. KARTE ---
if st.session_state.ort_sammlung:
    m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
    for ort, items in st.session_state.ort_sammlung.items():
        fg = folium.FeatureGroup(name=ort)
        color = "#%06x" % random.randint(0, 0xFFFFFF)
        for itm in items:
            folium.GeoJson(itm["gdf"].__geo_interface__, 
                           style_function=lambda x, c=color: {'color': c, 'weight': 5, 'opacity': 0.7}).add_to(fg)
            if itm["marker"]:
                folium.Marker(itm["marker"], popup=itm["original"]).add_to(fg)
        fg.add_to(m)
    folium.LayerControl().add_to(m)
    components.html(m._repr_html_(), height=600)
