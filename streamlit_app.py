import streamlit as st
import osmnx as ox
import folium
import io, re, os, random, shutil
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from geopy.geocoders import Nominatim
from datetime import datetime
import streamlit.components.v1 as components
import time

# --- 1. SETUP & DYNAMISCHE SERIENNUMMER ---
CURRENT_ID = datetime.now().strftime("%Y%m%d-%H%M")
SERIAL_NUMBER = f"GOLD-{CURRENT_ID}"

st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

st.markdown(f"""
<style>
    .stApp {{background-color: #0E1117;}}
    div[data-testid="stExpander"] {{border: 1px solid #30363d; border-radius: 8px;}}
    .stDataFrame {{border: 1px solid #30363d; border-radius: 8px;}}
    .stButton > button {{width: 100%; border-radius: 5px; font-weight: bold;}}
</style>
""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=10)

# --- 2. HILFSFUNKTIONEN FÜR DIE LISTE ---
def save_streets_to_disk(streets):
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(list(set(streets)))))

def load_streets_from_disk():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return sorted([l.strip() for l in f.readlines() if l.strip()])
    return []

# Session State Initialisierung
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets_from_disk()
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'run_processing' not in st.session_state: st.session_state.run_processing = False

# --- 3. LOGIK (PRÄZISION) ---
def verarbeite_strasse(strasse_input):
    if not strasse_input: return {"success": False}
    time.sleep(1.1) 
    parts = strasse_input.split(" | ") if " | " in strasse_input else [strasse_input, None]
    s_name, hnr = parts[0].strip(), parts[1].strip() if parts[1] else None
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', s_name).strip()
    try:
        gdf = ox.features_from_address(f"{s_clean}, Marburg-Biedenkopf", tags={"highway": True}, dist=50)
        if gdf.empty: return {"success": False, "original": strasse_input, "name": s_clean}
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
st.caption(f"Sitzung: **{SERIAL_NUMBER}**")

c1, c2 = st.columns(2)
with c1:
    with st.container(border=True):
        st.subheader("📥 Input")
        u_file = st.file_uploader("TXT Datei laden", type=["txt"])
        if u_file:
            lines = [l.strip() for l in u_file.getvalue().decode("utf-8").splitlines() if l.strip()]
            st.session_state.saved_manual_streets = sorted(list(set(st.session_state.saved_manual_streets + lines)))
            save_streets_to_disk(st.session_state.saved_manual_streets)
            st.rerun()
        
        st.divider()
        q_str = st.text_input("Straße hinzufügen:", placeholder="z.B. Bachweg")
        q_hnr = st.text_input("Hausnummer (optional):", placeholder="z.B. 12")
        
        if st.button("➕ Hinzufügen"):
            if q_str:
                neuer_eintrag = f"{q_str} | {q_hnr}" if q_hnr else q_str
                if neuer_eintrag not in st.session_state.saved_manual_streets:
                    st.session_state.saved_manual_streets.append(neuer_eintrag)
                    st.session_state.saved_manual_streets.sort()
                    save_streets_to_disk(st.session_state.saved_manual_streets)
                    st.rerun() # Aktualisiert die Liste sofort

with c2:
    with st.container(border=True):
        st.subheader("📝 Liste")
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
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    with ThreadPoolExecutor(max_workers=1) as exe:
        futs = {exe.submit(verarbeite_strasse, s): s for s in st.session_state.saved_manual_streets}
        for i, f in enumerate(futs):
            res = f.result()
            status_text.markdown(f"🔍 **Verarbeite {i+1} von {total}:** `{res.get('original')}`")
            progress_bar.progress((i + 1) / total)
            if res.get("success"):
                temp_ort[res["ort"]].append(res)
    
    st.session_state.ort_sammlung = dict(temp_ort)
    st.session_state.run_processing = False
    st.rerun()

# --- 6. AUSGABE ---
if st.session_state.ort_sammlung:
    m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
    colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'cadetblue', 'darkgreen']
    for idx, (ort, items) in enumerate(st.session_state.ort_sammlung.items()):
        fg = folium.FeatureGroup(name=f"{ort} ({len(items)})")
        color = colors[idx % len(colors)]
        for item in items:
            folium.GeoJson(item["gdf"].__geo_interface__,
                           style_function=lambda x, c=color: {'color': c, 'weight': 5, 'opacity': 0.7}).add_to(fg)
            if item["marker"]:
                folium.Marker(item["marker"], popup=item["original"], icon=folium.Icon(color=color)).add_to(fg)
        fg.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    components.html(m._repr_html_(), height=600)
