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

# --- 0. SERIENNUMMER ---
SERIAL_NUMBER = "SN-060" 

# --- 1. SETUP & THEME ---
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide", page_icon="🌐")

LOGO_URL = "https://integral-online.de/images/integral-gmbh-logo.png"

# Integral Dark Design
bg_color, text_color, box_bg, border_color, accent_color = "#0E1117", "#FAFAFA", "#1E232B", "#31333F", "#1E88E5"

st.markdown(f"""
<style>
    .stApp {{background-color: {bg_color}; color: {text_color};}}
    .block-container {{padding-top: 1rem;}}
    h1, h2, h3 {{color: {accent_color} !important;}}
    .step-box {{background-color: {box_bg}; padding: 15px; border-radius: 5px; border: 1px solid {border_color}; margin-bottom: 15px;}}
    .stButton>button {{background-color: {accent_color}; color: white; border-radius: 5px; width: 100%;}}
    .metric-box {{background-color: {box_bg}; padding: 15px; border-radius: 10px; border-left: 5px solid {accent_color}; margin-bottom: 10px;}}
</style>
""", unsafe_allow_html=True)

# Verzeichnisse
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "persistent_geocache")
os.makedirs(CACHE_DIR, exist_ok=True)
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=5)

# --- FUNKTIONEN ---
def save_streets(streets_list):
    cleaned = sorted(list(set([str(s).strip() for s in streets_list if str(s).strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned))
    st.session_state.saved_manual_streets = cleaned

def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return sorted(list(set([l.strip() for l in f.readlines() if l.strip()])))
    return []

def sync_editor():
    if "streets_editor" in st.session_state:
        # Erzwungener Sync der Tabelle
        new_data = st.session_state["streets_editor"]["data"]["Adresse (Strasse | Nr)"].tolist()
        save_streets(new_data)

def verarbeite_strasse_erweitert(strasse_input):
    if not strasse_input: return {"success": False}
    time.sleep(random.uniform(0.05, 0.15))
    parts = strasse_input.split(" | ")
    s_name = parts[0].strip()
    hnr = parts[1].strip() if len(parts) > 1 else ""
    query = f"{s_name}, Marburg-Biedenkopf"
    try:
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=150)
        if gdf.empty: return {"success": False, "original": strasse_input}
        gdf = gdf[gdf['name'].str.contains(re.escape(s_name), case=False, na=False)].to_crs(epsg=32632)
        laenge = gdf.geometry.length.sum()
        gdf = gdf.to_crs(epsg=4326)
        loc = geolocator.geocode(f"{s_name} {hnr}, Marburg-Biedenkopf", addressdetails=True, timeout=5)
        plz, ort = "00000", "Unbekannt"
        if loc and 'address' in loc.raw:
            a = loc.raw['address']
            plz = a.get('postcode', '00000')
            ort = a.get('village') or a.get('suburb') or a.get('town') or "Unbekannt"
        return {"gdf": gdf, "ort": ort, "plz": plz, "laenge": laenge, "original": strasse_input, "marker": (loc.latitude, loc.longitude) if loc else None, "success": True}
    except: return {"success": False, "original": strasse_input}

# Init
if 'saved_manual_streets' not in st.session_state: st.session_state.saved_manual_streets = load_streets()
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'run_processing' not in st.session_state: st.session_state.run_processing = False

# --- UI ---
c_l, c_t = st.columns([1, 7])
with c_l: st.image(LOGO_URL, width=100)
with c_t: st.title(f"Integral Dashboard {SERIAL_NUMBER}")

# 1. Zeile: Import & Steuerung
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    up = st.file_uploader("📂 Liste importieren (*.txt)", type=["txt"])
    if up:
        imported = [s.strip() for s in up.getvalue().decode("utf-8").splitlines() if s.strip()]
        save_streets(st.session_state.saved_manual_streets + imported)
        st.rerun()
with col2:
    st.write("##")
    if st.button("🚀 ANALYSE STARTEN", type="primary"):
        st.session_state.run_processing = True
        st.rerun()
with col3:
    st.write("##")
    if st.button("🔄 KOMPLETT-RESET"):
        if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
        st.session_state.saved_manual_streets, st.session_state.ort_sammlung = [], None
        st.rerun()

# 2. Zeile: Suche & Tabelle
st.markdown("---")
if not st.session_state.ort_sammlung:
    s_col1, s_col2 = st.columns([1, 2])
    with s_col1:
        st.subheader("📍 Einzelsuche")
        new_s = st.text_input("Straße & Nr:", placeholder="Hauptstr 1")
        if st.button("➕ Hinzufügen") and new_s:
            save_streets(st.session_state.saved_manual_streets + [new_s])
            st.rerun()
    with s_col2:
        st.subheader(f"📝 Liste ({len(st.session_state.saved_manual_streets)})")
        df = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])
        st.data_editor(df, num_rows="dynamic", use_container_width=True, key="streets_editor", on_change=sync_editor)

# Analyse & Ergebnisse
if st.session_state.run_processing:
    res_dict = defaultdict(list)
    with st.spinner("🔄 Integral KI berechnet Distanzen..."):
        prog = st.progress(0)
        streets = st.session_state.saved_manual_streets
        with ThreadPoolExecutor(max_workers=3) as ex:
            futs = {ex.submit(verarbeite_strasse_erweitert, s): s for s in streets}
            for i, f in enumerate(futs):
                r = f.result()
                if r.get("success"): res_dict[r["ort"]].append(r)
                prog.progress((i + 1) / len(streets))
        st.session_state.ort_sammlung = dict(res_dict)
        st.balloons()
    st.session_state.run_processing = False
    st.rerun()

if st.session_state.ort_sammlung:
    tot_km = sum(i["laenge"] for o in st.session_state.ort_sammlung.values() for i in o) / 1000
    m1, m2, m3 = st.columns(3)
    m1.markdown(f"<div class='metric-box'><b>Gesamtstrecke</b><br><h2>{tot_km:.2f} km</h2></div>", unsafe_allow_html=True)
    m2.markdown(f"<div class='metric-box'><b>Ortsteile</b><br><h2>{len(st.session_state.ort_sammlung)}</h2></div>", unsafe_allow_html=True)
    m3.markdown(f"<div class='metric-box'><b>Straßen</b><br><h2>{len(st.session_state.saved_manual_streets)}</h2></div>", unsafe_allow_html=True)
    
    c_res1, c_res2 = st.columns([1, 2])
    with c_res1:
        st.subheader("📊 Statistik")
        stats = [{"Ortsteil": o, "PLZ": it[0]["plz"], "km": f"{sum(i['laenge'] for i in it)/1000:.2f}"} for o, it in st.session_state.ort_sammlung.items()]
        st.dataframe(pd.DataFrame(stats), use_container_width=True, hide_index=True)
    with c_res2:
        m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="CartoDB dark_matter")
        for o, it in st.session_state.ort_sammlung.items():
            for i in it:
                folium.GeoJson(i["gdf"].__geo_interface__, style_function=lambda x: {'color': '#1E88E5', 'weight': 4}).add_to(m)
        components.html(m._repr_html_(), height=500)
