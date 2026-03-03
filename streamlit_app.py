import streamlit as st
import osmnx as ox
import folium
import io, re, os, random, shutil
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components
import time

# --- 1. SETUP ---
SERIAL_NUMBER = "SN-029-FIX"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

# Optik-Korrektur (Ruhe & Klarheit)
st.markdown("""
<style>
    .stApp {background-color: #0E1117;}
    div[data-testid="stExpander"] {border: 1px solid #30363d; border-radius: 8px;}
    .stDataFrame {border: 1px solid #30363d; border-radius: 8px;}
    .stButton > button {width: 100%; border-radius: 5px;}
</style>
""", unsafe_allow_html=True)

# Pfade & Geocoder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=10)

# --- 2. SESSION STATE ---
if 'saved_manual_streets' not in st.session_state:
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            st.session_state.saved_manual_streets = [l.strip() for l in f.readlines() if l.strip()]
    else:
        st.session_state.saved_manual_streets = []

if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'run_processing' not in st.session_state: st.session_state.run_processing = False

# --- 3. LOGIK ---
def verarbeite_strasse(strasse_input):
    if not strasse_input: return {"success": False}
    time.sleep(1.2) # Nominatim Schutz
    
    # Parsing
    parts = strasse_input.split(" | ") if " | " in strasse_input else [strasse_input, None]
    s_name = parts[0].strip()
    hnr = parts[1].strip() if parts[1] else None
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', s_name).strip()

    try:
        # STRASSE HOLEN
        gdf = ox.features_from_address(f"{s_clean}, Marburg-Biedenkopf", tags={"highway": True}, dist=50)
        if gdf.empty: return {"success": False, "original": strasse_input}

        # PRÄZISIONS-FILTER (Markiert NUR die exakte Straße)
        gdf = gdf[gdf['name'].apply(lambda x: str(x).strip().lower() == s_clean.lower())]
        if gdf.empty: return {"success": False, "original": strasse_input}

        # MARKER (Optional für Hausnummer)
        marker_coords = None
        if hnr:
            loc = geolocator.geocode(f"{s_clean} {hnr}, Marburg-Biedenkopf")
            if loc: marker_coords = (loc.latitude, loc.longitude)

        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
        
        # ORTSTEIL via REVERSE GEOCODING
        centroid = gdf.geometry.unary_union.centroid
        loc_rev = geolocator.reverse((centroid.y, centroid.x), language='de')
        a = loc_rev.raw.get('address', {})
        ort = a.get('village') or a.get('suburb') or a.get('hamlet') or a.get('town') or "Marburg"
        
        return {"gdf": gdf, "ort": ort, "name": s_clean, "original": strasse_input, "marker": marker_coords, "success": True}
    except: return {"success": False, "original": strasse_input}

# --- 4. UI ANZEIGE ---
st.title("🚀 INTEGRAL PRO")
st.caption(f"Revision: {SERIAL_NUMBER} | Status: Bereit")

col_in1, col_in2 = st.columns(2)

with col_in1:
    with st.container(border=True):
        st.subheader("📥 Input")
        u_file = st.file_uploader("TXT Datei laden", type=["txt"])
        if u_file:
            lines = [l.strip() for l in u_file.getvalue().decode("utf-8").splitlines() if l.strip()]
            st.session_state.saved_manual_streets = list(set(st.session_state.saved_manual_streets + lines))
            with open(STREETS_FILE, "w", encoding="utf-8") as f: f.write("\n".join(st.session_state.saved_manual_streets))
            st.success("Geladen!")

with col_in2:
    with st.container(border=True):
        st.subheader("📝 Liste")
        st.dataframe(st.session_state.saved_manual_streets, use_container_width=True, height=150)
        if st.button("🗑️ Liste leeren"):
            st.session_state.saved_manual_streets = []
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.rerun()

if st.button("🔥 ANALYSE STARTEN", type="primary"):
    st.session_state.run_processing = True

# VERARBEITUNG-LOOP
if st.session_state.run_processing and st.session_state.saved_manual_streets:
    temp_ort = defaultdict(list)
    pb = st.progress(0)
    with ThreadPoolExecutor(max_workers=1) as exe:
        futs = {exe.submit(verarbeite_strasse, s): s for s in st.session_state.saved_manual_streets}
        for i, f in enumerate(futs):
            res = f.result()
            if res.get("success"): temp_ort[res["ort"]].append(res)
            pb.progress((i + 1) / len(futs))
    st.session_state.ort_sammlung = dict(temp_ort)
    st.session_state.run_processing = False
    st.rerun()

# --- 5. KARTE ANZEIGEN ---
if st.session_state.ort_sammlung:
    st.subheader("🗺️ Ergebnis-Karte")
    m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
    
    for ort, items in st.session_state.ort_sammlung.items():
        fg = folium.FeatureGroup(name=ort)
        color = "#%06x" % random.randint(0, 0xFFFFFF) # Zufallsfarbe pro Ortsteil
        for item in items:
            folium.GeoJson(item["gdf"].__geo_interface__,
                           style_function=lambda x, c=color: {'color': c, 'weight': 5, 'opacity': 0.7}).add_to(fg)
            if item["marker"]:
                folium.Marker(item["marker"], popup=item["original"]).add_to(fg)
        fg.add_to(m)
    
    folium.LayerControl().add_to(m)
    components.html(m._repr_html_(), height=600)
