import streamlit as st
import osmnx as ox
import folium
import io, re, os, random, shutil
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from datetime import datetime
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components
import time

# --- 1. KONFIGURATION ---
SERIAL_NUMBER = "SN-029-GOLD"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# OSMnx & Geocoder Setup
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=10)

# --- 2. PERSISTENZ-LAYER (STABILER DATEIZUGRIFF) ---
def load_streets():
    """Lädt die Liste und entfernt Duplikate sowie Leerzeilen."""
    if os.path.exists(STREETS_FILE):
        try:
            with open(STREETS_FILE, "r", encoding="utf-8") as f:
                return sorted(list(set(line.strip() for line in f if line.strip())))
        except Exception:
            return []
    return []

def save_streets(streets_list):
    """Speichert die Liste sortiert und ohne Dubletten."""
    try:
        clean_list = sorted(list(set(s.strip() for s in streets_list if s.strip())))
        with open(STREETS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(clean_list))
        return True
    except Exception as e:
        st.error(f"Speicherfehler: {e}")
        return False

# --- 3. SESSION STATE ---
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets()
if 'ort_sammlung' not in st.session_state:
    st.session_state.ort_sammlung = None
if 'run_processing' not in st.session_state:
    st.session_state.run_processing = False
if 'stop_requested' not in st.session_state:
    st.session_state.stop_requested = False

# --- 4. ANALYSE-LOGIK ---
def verarbeite_strasse(strasse_input):
    if not strasse_input or st.session_state.stop_requested:
        return {"success": False}
    
    time.sleep(1.1) # Höflichkeits-Delay für API
    
    # Trennung Straße | Hausnummer
    if " | " in strasse_input:
        s_name, hnr = strasse_input.split(" | ", 1)
    else:
        s_name, hnr = strasse_input, None
    
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', s_name.strip()).strip()
    
    try:
        # Geometrie-Abfrage
        gdf = ox.features_from_address(f"{s_clean}, Marburg-Biedenkopf", tags={"highway": True}, dist=50)
        if gdf.empty: return {"success": False, "original": strasse_input}
        
        gdf = gdf[gdf['name'].str.contains(s_clean, case=False, na=False)]
        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
        
        if gdf.empty: return {"success": False, "original": strasse_input}

        # Marker-Position (Hausnummer)
        marker_coords = None
        if hnr:
            loc = geolocator.geocode(f"{s_clean} {hnr}, Marburg-Biedenkopf")
            if loc: marker_coords = (loc.latitude, loc.longitude)

        # Ortsteil-Identifikation
        centroid = gdf.geometry.unary_union.centroid
        loc_rev = geolocator.reverse((centroid.y, centroid.x), language='de')
        addr = loc_rev.raw.get('address', {})
        ort = addr.get('village') or addr.get('suburb') or addr.get('town') or "Marburg"
        
        return {"gdf": gdf, "ort": ort, "name": s_clean, "original": strasse_input, "marker": marker_coords, "success": True}
    except:
        return {"success": False, "original": strasse_input}

# --- 5. UI ---
st.title("🚀 INTEGRAL PRO")

# Eingabe-Bereich
with st.container(border=True):
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("📥 TXT-Import (Additiv)")
        uploaded_files = st.file_uploader("Dateien wählen", type=["txt"], accept_multiple_files=True)
        if uploaded_files:
            new_data = []
            for f in uploaded_files:
                content = f.getvalue().decode("utf-8").splitlines()
                new_data.extend([line.strip() for line in content if line.strip()])
            
            # Mergen mit bestehender Liste & Speichern
            st.session_state.saved_manual_streets = list(set(st.session_state.saved_manual_streets + new_data))
            save_streets(st.session_state.saved_manual_streets)
            st.success(f"{len(new_data)} Einträge geladen.")
            st.rerun()

    with c2:
        st.subheader("📝 Aktuelle Liste")
        if st.session_state.saved_manual_streets:
            df = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Eintrag"])
            st.dataframe(df, use_container_width=True, height=180)
            if st.button("🗑️ Gesamte Liste löschen"):
                st.session_state.saved_manual_streets = []
                save_streets([])
                st.rerun()
        else:
            st.info("Liste ist leer.")

# Analyse-Steuerung
st.divider()
if not st.session_state.run_processing:
    if st.button("🔥 ANALYSE STARTEN", type="primary", use_container_width=True):
        st.session_state.run_processing = True
        st.rerun()
else:
    if st.button("🛑 STOPP", type="secondary", use_container_width=True):
        st.session_state.stop_requested = True

# Verarbeitung
if st.session_state.run_processing:
    results = defaultdict(list)
    s_list = st.session_state.saved_manual_streets
    
    with st.status("Verarbeite Straßen...", expanded=True) as status:
        p_bar = st.progress(0)
        for i, s in enumerate(s_list):
            if st.session_state.stop_requested: break
            res = verarbeite_strasse(s)
            if res.get("success"):
                results[res["ort"]].append(res)
            p_bar.progress((i + 1) / len(s_list))
        status.update(label="Analyse beendet!", state="complete")
    
    st.session_state.ort_sammlung = dict(results)
    st.session_state.run_processing = False
    st.session_state.stop_requested = False
    st.rerun()

# Karten-Ausgabe
if st.session_state.ort_sammlung:
    st.subheader("🗺️ Ergebnis-Karte")
    m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
    
    for ort, items in st.session_state.ort_sammlung.items():
        fg = folium.FeatureGroup(name=ort)
        color = "#%06x" % random.randint(0, 0xFFFFFF) # Zufallsfarbe pro Ortsteil
        for itm in items:
            folium.GeoJson(
                itm["gdf"].__geo_interface__,
                style_function=lambda x, c=color: {'color': c, 'weight': 5},
                tooltip=folium.Tooltip(f"<b>{itm['name']}</b> ({ort})")
            ).add_to(fg)
            if itm["marker"]:
                folium.Marker(itm["marker"], popup=itm["original"]).add_to(fg)
        fg.add_to(m)
    
    folium.LayerControl().add_to(m)
    components.html(m._repr_html_(), height=600)
