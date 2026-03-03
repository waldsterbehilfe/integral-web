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

# --- 1. SETUP & KONFIGURATION ---
SERIAL_NUMBER = "SN-029-GOLD3001"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=10)

# --- 2. PERSISTENZ-FUNKTIONEN (CACHE) ---
def load_streets():
    if os.path.exists(STREETS_FILE):
        try:
            with open(STREETS_FILE, "r", encoding="utf-8") as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except: return []
    return []

def save_streets(streets_list):
    try:
        with open(STREETS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(streets_list))
    except Exception as e:
        st.error(f"Fehler beim Speichern: {e}")

# --- 3. SESSION STATE ---
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets()
if 'run_processing' not in st.session_state:
    st.session_state.run_processing = False
if 'stop_requested' not in st.session_state:
    st.session_state.stop_requested = False
if 'ort_sammlung' not in st.session_state:
    st.session_state.ort_sammlung = None

# --- 4. UI: HEADER & STATISTIK ---
st.title("🚀 INTEGRAL PRO")
cache_count = len(st.session_state.saved_manual_streets)
st.caption(f"Version: {SERIAL_NUMBER} | Straßen im Cache: **{cache_count}** | Fokus: Marburg-Biedenkopf")

# --- 5. INPUT-MANAGEMENT ---
with st.container(border=True):
    col_input, col_table = st.columns([1, 1])

    with col_input:
        st.subheader("📥 Dateneingabe")
        
        # Manueller Input
        with st.expander("Manuelle Eingabe", expanded=True):
            c_str, c_hnr = st.columns([3, 1])
            q_street = c_str.text_input("Straßenname", placeholder="z.B. Frankfurter Straße")
            q_hnr = c_hnr.text_input("Hnr (optional)", placeholder="1a")
            if st.button("➕ Zur Liste hinzufügen"):
                if q_street:
                    entry = f"{q_street} | {q_hnr}".strip(" |")
                    if entry not in st.session_state.saved_manual_streets:
                        st.session_state.saved_manual_streets.append(entry)
                        save_streets(st.session_state.saved_manual_streets)
                        st.rerun()

        # TXT-Upload
        uploaded_files = st.file_uploader("TXT-Dateien importieren", type=["txt"], accept_multiple_files=True)
        if uploaded_files:
            new_entries = []
            for f in uploaded_files:
                lines = f.getvalue().decode("utf-8").splitlines()
                new_entries.extend([l.strip() for l in lines if l.strip()])
            st.session_state.saved_manual_streets = sorted(list(set(st.session_state.saved_manual_streets + new_entries)))
            save_streets(st.session_state.saved_manual_streets)
            st.rerun()

    with col_table:
        st.subheader("📝 Liste & Korrektur")
        if st.session_state.saved_manual_streets:
            # Korrektur-Möglichkeit via Data Editor
            edited_df = st.data_editor(
                pd.DataFrame(st.session_state.saved_manual_streets, columns=["Eintrag"]),
                use_container_width=True,
                num_rows="dynamic",
                height=250,
                key="editor"
            )
            # Speichern der Änderungen aus dem Editor
            if st.button("💾 Änderungen übernehmen"):
                st.session_state.saved_manual_streets = edited_df["Eintrag"].tolist()
                save_streets(st.session_state.saved_manual_streets)
                st.rerun()
            
            if st.button("🗑️ Cache (Liste) leeren"):
                st.session_state.saved_manual_streets = []
                save_streets([])
                st.rerun()
        else:
            st.info("Keine Daten vorhanden.")

# --- 6. STEUERUNG & ABBRUCH ---
st.divider()
c_start, c_stop = st.columns(2)

if c_start.button("🔥 ANALYSE STARTEN", type="primary", use_container_width=True, disabled=st.session_state.run_processing):
    st.session_state.run_processing = True
    st.session_state.stop_requested = False
    st.rerun()

if c_stop.button("🛑 ABBRUCH / ANHALTEN", type="secondary", use_container_width=True):
    st.session_state.stop_requested = True
    st.session_state.run_processing = False
    st.warning("Abbruch wird verarbeitet...")

# --- 7. VERARBEITUNGS-LOGIK ---
if st.session_state.run_processing:
    results = defaultdict(list)
    s_list = st.session_state.saved_manual_streets
    
    with st.status("Verarbeite Straßen...", expanded=True) as status:
        p_bar = st.progress(0)
        for i, s in enumerate(s_list):
            if st.session_state.stop_requested:
                status.update(label="Analyse abgebrochen.", state="error")
                break
                
            # Hier findet die Geokodierung statt
            time.sleep(1.1) 
            try:
                # Normierung und Abfrage
                s_base = s.split(" | ")[0]
                s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', s_base).strip()
                
                gdf = ox.features_from_address(f"{s_clean}, Marburg-Biedenkopf", tags={"highway": True}, dist=50)
                if not gdf.empty:
                    gdf = gdf[gdf['name'].str.contains(s_clean, case=False, na=False)]
                    gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
                    
                    # Ort bestimmen
                    centroid = gdf.geometry.unary_union.centroid
                    loc_rev = geolocator.reverse((centroid.y, centroid.x), language='de')
                    ort = loc_rev.raw.get('address', {}).get('village', "Marburg")
                    
                    results[ort].append({"gdf": gdf, "name": s_clean, "original": s})
            except:
                pass
                
            p_bar.progress((i + 1) / len(s_list))
        
        if not st.session_state.stop_requested:
            status.update(label="Analyse erfolgreich!", state="complete")
            st.session_state.ort_sammlung = dict(results)
            st.session_state.run_processing = False
            st.balloons()
            st.rerun()

# --- 8. KARTEN-AUSGABE ---
if st.session_state.ort_sammlung:
    st.subheader("🗺️ Ergebnis-Karte")
    m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
    for ort, items in st.session_state.ort_sammlung.items():
        fg = folium.FeatureGroup(name=ort)
        color = "#%06x" % random.randint(0, 0xFFFFFF)
        for itm in items:
            folium.GeoJson(itm["gdf"].__geo_interface__, style_function=lambda x, c=color: {'color': c, 'weight': 5}).add_to(fg)
        fg.add_to(m)
    folium.LayerControl().add_to(m)
    components.html(m._repr_html_(), height=600)
