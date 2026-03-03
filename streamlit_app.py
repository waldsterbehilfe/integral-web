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
SERIAL_NUMBER = "SN-029-GOLD"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

st.markdown("""
<style>
    .stApp {background-color: #0E1117;}
    div[data-testid="stExpander"] {border: 1px solid #30363d; border-radius: 8px;}
    .stDataFrame {border: 1px solid #30363d; border-radius: 8px;}
    .stButton > button {width: 100%; border-radius: 5px; font-weight: bold;}
    .status-text {font-size: 0.9rem; color: #888888; margin-bottom: 5px;}
</style>
""", unsafe_allow_html=True)

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

# --- 3. LOGIK (STRIKT & PRÄZISE) ---
def verarbeite_strasse(strasse_input):
    if not strasse_input: return {"success": False}
    time.sleep(1.1) 
    
    parts = strasse_input.split(" | ") if " | " in strasse_input else [strasse_input, None]
    s_name, hnr = parts[0].strip(), parts[1].strip() if parts[1] else None
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', s_name).strip()

    try:
        # Abfrage mit kleinem Radius für Präzision
        gdf = ox.features_from_address(f"{s_clean}, Marburg-Biedenkopf", tags={"highway": True}, dist=50)
        if gdf.empty: return {"success": False, "original": strasse_input, "name": s_clean}

        # FEHLER-FIX: Nur exakte Übereinstimmung markieren
        gdf = gdf[gdf['name'].apply(lambda x: str(x).strip().lower() == s_clean.lower())]
        if gdf.empty: return {"success": False, "original": strasse_input, "name": s_clean}

        marker_coords = None
        if hnr:
            loc = geolocator.geocode(f"{s_clean} {hnr}, Marburg-Biedenkopf")
            if loc: marker_coords = (loc.latitude, loc.longitude)

        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
        
        centroid = gdf.geometry.unary_union.centroid
        loc_rev = geolocator.reverse((centroid.y, centroid.x), language='de')
        a = loc_rev.raw.get('address', {})
        ort = a.get('village') or a.get('suburb') or a.get('hamlet') or a.get('town') or "Marburg"
        
        return {"gdf": gdf, "ort": ort, "name": s_clean, "original": strasse_input, "marker": marker_coords, "success": True}
    except: return {"success": False, "original": strasse_input, "name": s_clean}

# --- 4. UI ---
st.title("🚀 INTEGRAL PRO")
st.caption(f"Revision: {SERIAL_NUMBER} | Präzisions-Modus aktiv")

c1, c2 = st.columns(2)
with c1:
    with st.container(border=True):
        st.subheader("📥 Input")
        u_file = st.file_uploader("Datei wählen", type=["txt"], label_visibility="collapsed")
        if u_file:
            lines = [l.strip() for l in u_file.getvalue().decode("utf-8").splitlines() if l.strip()]
            st.session_state.saved_manual_streets = sorted(list(set(st.session_state.saved_manual_streets + lines)))
            with open(STREETS_FILE, "w", encoding="utf-8") as f: f.write("\n".join(st.session_state.saved_manual_streets))
            st.rerun()

with c2:
    with st.container(border=True):
        st.subheader("📝 Liste")
        st.dataframe(st.session_state.saved_manual_streets, use_container_width=True, height=150)
        if st.button("🗑️ Liste leeren"):
            st.session_state.saved_manual_streets = []
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.rerun()

st.divider()

if st.button("🔥 ANALYSE STARTEN", type="primary"):
    st.session_state.run_processing = True

# --- 5. VERARBEITUNG MIT STATUS-ANZEIGE ---
if st.session_state.run_processing and st.session_state.saved_manual_streets:
    temp_ort = defaultdict(list)
    total = len(st.session_state.saved_manual_streets)
    
    # Fortschritts-Container
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    with ThreadPoolExecutor(max_workers=1) as exe:
        futs = {exe.submit(verarbeite_strasse, s): s for s in st.session_state.saved_manual_streets}
        for i, f in enumerate(futs):
            res = f.result()
            # HIER: Anzeige "X von Y"
            status_text.markdown(f"🔍 **Suche {i+1} von {total}:** `{res.get('original')}`")
            progress_bar.progress((i + 1) / total)
            
            if res.get("success"):
                temp_ort[res["ort"]].append(res)
    
    st.session_state.ort_sammlung = dict(temp_ort)
    st.session_state.run_processing = False
    st.success("Analyse abgeschlossen!")
    time.sleep(1)
    st.rerun()

# --- 6. AUSGABE ---
if st.session_state.ort_sammlung:
    st.subheader("🗺️ Ergebnis-Karte")
    m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
    
    # Farben-Generator
    colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'cadetblue', 'darkgreen']
    
    for idx, (ort, items) in enumerate(st.session_state.ort_sammlung.items()):
        fg = folium.FeatureGroup(name=f"{ort} ({len(items)})")
        color = colors[idx % len(colors)]
        for item in items:
            folium.GeoJson(item["gdf"].__geo_interface__,
                           style_function=lambda x, c=color: {'color': c, 'weight': 5, 'opacity': 0.7},
                           tooltip=item['name']).add_to(fg)
            if item["marker"]:
                folium.Marker(item["marker"], popup=item["original"], icon=folium.Icon(color=color)).add_to(fg)
        fg.add_to(m)
    
    folium.LayerControl(collapsed=False).add_to(m)
    components.html(m._repr_html_(), height=600)
