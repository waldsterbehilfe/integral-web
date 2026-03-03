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
SERIAL_NUMBER = "SN-058" 

# --- 1. SETUP & THEME ---
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide", page_icon="🌐")

LOGO_URL = "https://integral-online.de/images/integral-gmbh-logo.png"

# Fixes Dunkel Design
bg_color, text_color, box_bg, border_color, accent_color = "#0E1117", "#FAFAFA", "#1E232B", "#31333F", "#1E88E5"

st.markdown(f"""
<style>
    .stApp {{background-color: {bg_color}; color: {text_color};}}
    .block-container {{padding-top: 1rem;}}
    h1, h2, h3 {{color: {accent_color} !important;}}
    .step-box {{background-color: {box_bg}; padding: 15px; border-radius: 5px; border: 1px solid {border_color}; margin-bottom: 15px;}}
    .stButton>button {{background-color: {accent_color}; color: white; border-radius: 5px; width: 100%;}}
    .stSpinner > div > div {{border-top-color: {accent_color} !important;}}
    .metric-box {{background-color: {box_bg}; padding: 10px; border-radius: 5px; border-left: 5px solid {accent_color};}}
</style>
""", unsafe_allow_html=True)

# Verzeichnisse & OsmNx Cache
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "persistent_geocache")
os.makedirs(CACHE_DIR, exist_ok=True)
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR

STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=5)
COLORS = ['#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4', '#46f0f0', '#f032e6', '#bcf60c', '#fabebe', '#008080', '#e6beff', '#9a6324', '#fffac8', '#800000', '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080']

# --- LOGIK-FUNKTIONEN ---
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
        edits = st.session_state["streets_editor"]
        df_current = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])
        if edits.get("deleted_rows"):
            df_current = df_current.drop(edits["deleted_rows"])
        for idx, val in edits.get("edited_rows", {}).items():
            df_current.at[int(idx), "Adresse (Strasse | Nr)"] = val.get("Adresse (Strasse | Nr)", df_current.at[int(idx), "Adresse (Strasse | Nr)"])
        for row in edits.get("added_rows", []):
            if "Adresse (Strasse | Nr)" in row:
                df_current = pd.concat([df_current, pd.DataFrame([row])], ignore_index=True)
        save_streets(df_current["Adresse (Strasse | Nr)"].tolist())

def verarbeite_strasse_erweitert(strasse_input):
    if not strasse_input: return {"success": False}
    time.sleep(random.uniform(0.1, 0.2))
    
    parts = strasse_input.split(" | ")
    strasse_name = parts[0].strip()
    hnr = parts[1].strip() if len(parts) > 1 else None

    query = f"{strasse_name}, Marburg-Biedenkopf"
    try:
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=150)
        if gdf.empty: return {"success": False, "original": strasse_input}
        
        gdf = gdf[gdf['name'].str.contains(re.escape(strasse_name), case=False, na=False)].to_crs(epsg=32632) # Projektion für Meter
        if gdf.empty: return {"success": False, "original": strasse_input}

        # NEU: Distanz berechnen (Länge in Metern)
        laenge_m = gdf.geometry.length.sum()
        
        gdf = gdf.to_crs(epsg=4326) # Zurück für Karte
        
        # NEU: PLZ & Ortsteil Extraktion
        plz = "00000"
        ortsteil = "Unbekannt"
        
        # Geocoding für Metadaten
        loc = geolocator.geocode(f"{strasse_name} {hnr if hnr else ''}, Marburg-Biedenkopf", addressdetails=True, timeout=5)
        if loc and 'address' in loc.raw:
            addr = loc.raw['address']
            plz = addr.get('postcode', '00000')
            ortsteil = addr.get('village') or addr.get('suburb') or addr.get('town') or "Unbekannt"

        return {
            "gdf": gdf, "ort": ortsteil, "plz": plz, "laenge": laenge_m,
            "name": strasse_name, "original": strasse_input, 
            "marker": (loc.latitude, loc.longitude) if loc else None, "success": True
        }
    except: return {"success": False, "original": strasse_input}

# Initialisierung
if 'saved_manual_streets' not in st.session_state: st.session_state.saved_manual_streets = load_streets()
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'run_processing' not in st.session_state: st.session_state.run_processing = False

# --- UI ---
col_logo, col_title = st.columns([1, 8])
with col_logo: st.image(LOGO_URL, width=100)
with col_title: st.title(f"Integral Dashboard {SERIAL_NUMBER}")

c1, c2, c3, c4 = st.columns(4)
with c1:
    search = st.text_input("📍 Straße schnell hinzufügen:", placeholder="z.B. Ringstraße 10")
    if search and st.button("Hinzufügen"):
        save_streets(st.session_state.saved_manual_streets + [search])
        st.rerun()
with c2:
    if st.button("🚀 ANALYSE STARTEN", type="primary"):
        st.session_state.run_processing = True
        st.rerun()
with c3:
    if st.button("🔄 RESET LISTE"):
        if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
        st.session_state.saved_manual_streets = []
        st.session_state.ort_sammlung = None
        st.rerun()
with c4:
    if st.button("🗑️ CACHE LEEREN"):
        if os.path.exists(CACHE_DIR): shutil.rmtree(CACHE_DIR)
        st.rerun()

st.markdown("---")

if st.session_state.run_processing:
    temp_ort = defaultdict(list)
    with st.spinner("Integral KI berechnet Distanzen und PLZ..."):
        pb = st.progress(0)
        streets = st.session_state.saved_manual_streets
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(verarbeite_strasse_erweitert, s): s for s in streets}
            for i, future in enumerate(futures):
                res = future.result()
                if res.get("success"): temp_ort[res["ort"]].append(res)
                pb.progress((i + 1) / len(streets))
        st.session_state.ort_sammlung = dict(temp_ort)
        st.balloons()
    st.session_state.run_processing = False
    st.rerun()

if st.session_state.ort_sammlung:
    # --- DASHBOARD ANSICHT ---
    total_km = sum(item["laenge"] for items in st.session_state.ort_sammlung.values() for item in items) / 1000
    
    m1, m2, m3 = st.columns(3)
    m1.markdown(f"<div class='metric-box'><b>Gesamtstrecke:</b><br><h2>{total_km:.2f} km</h2></div>", unsafe_allow_html=True)
    m2.markdown(f"<div class='metric-box'><b>Ortsteile:</b><br><h2>{len(st.session_state.ort_sammlung)}</h2></div>", unsafe_allow_html=True)
    m3.markdown(f"<div class='metric-box'><b>Analysierte Punkte:</b><br><h2>{len(st.session_state.saved_manual_streets)}</h2></div>", unsafe_allow_html=True)

    col_res1, col_res2 = st.columns([1, 2])
    with col_res1:
        st.subheader("📊 Ortsteil-Statistik")
        stats = []
        for ort, items in st.session_state.ort_sammlung.items():
            dist = sum(i["laenge"] for i in items) / 1000
            stats.append({"Ortsteil": ort, "PLZ": items[0]["plz"], "Straßen": len(items), "Kilometer": f"{dist:.2f} km"})
        st.dataframe(pd.DataFrame(stats), use_container_width=True, hide_index=True)
        
    with col_res2:
        m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron" if not any([True]) else "CartoDB dark_matter")
        all_geoms = []
        for ort, items in st.session_state.ort_sammlung.items():
            for item in items:
                all_geoms.append(item["gdf"])
                folium.GeoJson(item["gdf"].__geo_interface__, style_function=lambda x: {'color': '#1E88E5', 'weight': 4}).add_to(m)
        if all_geoms:
            b = gpd.GeoDataFrame(pd.concat(all_geoms)).total_bounds
            m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])
        components.html(m._repr_html_(), height=500)
else:
    st.subheader("📝 Straßenliste")
    df_display = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])
    st.data_editor(df_display, num_rows="dynamic", use_container_width=True, key="streets_editor", on_change=sync_editor)
