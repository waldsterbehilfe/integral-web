import streamlit as st
import osmnx as ox
import folium
import io, re, os, random
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from geopy.geocoders import Nominatim
from datetime import datetime
import streamlit.components.v1 as components
import time

# --- 1. SETUP ---
CURRENT_ID = datetime.now().strftime("%Y%m%d-%H%M")
SERIAL_NUMBER = f"GOLD-{CURRENT_ID}"

st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

# CSS für Stabilität
st.markdown("""
<style>
    .stApp {background-color: #0E1117;}
    .stButton > button {width: 100%; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=10)

# --- 2. PERSISTENZ-LOGIK ---
def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return sorted(list(set([l.strip() for l in f.readlines() if l.strip()])))
    return []

def save_streets(streets):
    clean_list = sorted(list(set([s.strip() for s in streets if s.strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(clean_list))
    return clean_list

# Session State Initialisierung
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets()
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'run_processing' not in st.session_state: st.session_state.run_processing = False

# --- 3. VERARBEITUNG (STRIKT) ---
def verarbeite_strasse(strasse_input):
    if not strasse_input: return {"success": False}
    time.sleep(1.1)
    parts = strasse_input.split(" | ") if " | " in strasse_input else [strasse_input, None]
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', parts[0].strip()).strip()
    try:
        gdf = ox.features_from_address(f"{s_clean}, Marburg-Biedenkopf", tags={"highway": True}, dist=50)
        if gdf.empty: return {"success": False, "original": strasse_input}
        # Striktes Matching
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
st.caption(f"Sitzung: {SERIAL_NUMBER}")

c1, c2 = st.columns(2)

with c1:
    with st.container(border=True):
        st.subheader("📥 Input")
        
        # FIX: Upload & Sofort-Update
        uploaded_file = st.file_uploader("TXT Datei wählen", type=["txt"])
        if uploaded_file is not None:
            content = uploaded_file.getvalue().decode("utf-8").splitlines()
            new_lines = [l.strip() for l in content if l.strip()]
            if new_lines:
                # Liste im State und auf Disk aktualisieren
                st.session_state.saved_manual_streets = save_streets(st.session_state.saved_manual_streets + new_lines)
                # Den Datei-Uploader "austricksen", indem wir die Seite neu laden
                st.rerun()

        st.divider()
        in_str = st.text_input("Straße:")
        in_hnr = st.text_input("Hausnummer (opt.):")
        if st.button("➕ Hinzufügen"):
            if in_str:
                entry = f"{in_str} | {in_hnr}" if in_hnr else in_str
                st.session_state.saved_manual_streets = save_streets(st.session_state.saved_manual_streets + [entry])
                st.rerun()

with c2:
    with st.container(border=True):
        st.subheader("📝 Liste")
        # WICHTIG: Die Liste wird hier direkt aus dem State gelesen
        st.dataframe(st.session_state.saved_manual_streets, use_container_width=True, height=250)
        
        if st.button("🗑️ Liste leeren"):
            st.session_state.saved_manual_streets = []
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.rerun()

st.divider()
if st.button("🔥 ANALYSE STARTEN", type="primary"):
    st.session_state.run_processing = True

# --- 5. LOOP ---
if st.session_state.run_processing and st.session_state.saved_manual_streets:
    temp_ort = defaultdict(list)
    total = len(st.session_state.saved_manual_streets)
    pb = st.progress(0)
    st_msg = st.empty()
    
    with ThreadPoolExecutor(max_workers=1) as exe:
        futs = {exe.submit(verarbeite_strasse, s): s for s in st.session_state.saved_manual_streets}
        for i, f in enumerate(futs):
            res = f.result()
            st_msg.markdown(f"🔍 **Suche {i+1} von {total}:** `{res.get('original')}`")
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
        for itm in items:
            folium.GeoJson(itm["gdf"].__geo_interface__, style_function=lambda x: {'color': 'red', 'weight': 5}).add_to(fg)
            if itm["marker"]: folium.Marker(itm["marker"], popup=itm["original"]).add_to(fg)
        fg.add_to(m)
    folium.LayerControl().add_to(m)
    components.html(m._repr_html_(), height=600)
