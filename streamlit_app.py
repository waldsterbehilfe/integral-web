import streamlit as st
import osmnx as ox
import folium
import re, os, random, time
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from geopy.geocoders import Nominatim
from difflib import SequenceMatcher
import streamlit.components.v1 as components

# --- 1. SETUP & CONFIG ---
SERIAL_NUMBER = "SN-029-GOLD3002"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
geolocator = Nominatim(user_agent=f"integral_pro_v6_{random.randint(100,999)}", timeout=10)

# --- 2. HILFSFUNKTIONEN ---
def get_internet_verified(query):
    """Schnelle Validierung mit Error-Handling."""
    try:
        results = geolocator.geocode(f"{query}, Marburg-Biedenkopf", exactly_one=False, limit=1)
        if results:
            return results[0].address.split(',')[0].strip()
    except Exception:
        pass
    return None

# --- 3. PERSISTENZ ---
if 'saved_manual_streets' not in st.session_state:
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            st.session_state.saved_manual_streets = [l.strip() for l in f.readlines() if l.strip()]
    else:
        st.session_state.saved_manual_streets = []
if 'ort_sammlung' not in st.session_state:
    st.session_state.ort_sammlung = None
if 'run_processing' not in st.session_state:
    st.session_state.run_processing = False

# --- 4. HEADER ---
h_col1, h_col2 = st.columns([1, 15])
with h_col1:
    st.markdown("<h3>∫</h3>", unsafe_allow_html=True)
with h_col2:
    st.markdown("**INTEGRAL PRO**")
st.divider()

# --- 5. DATEI-IMPORT MIT FORTSCHRITT & SPEED-LOGIK ---
uploaded_files = st.file_uploader("*.txt Dateien importieren", type=["txt"], accept_multiple_files=True)
if uploaded_files:
    new_verified = []
    raw_lines = []
    for f in uploaded_files:
        raw_lines.extend([l.strip() for l in f.getvalue().decode("utf-8").splitlines() if l.strip()])
    
    total_lines = len(raw_lines)
    if total_lines > 0:
        with st.status(f"Importiere {total_lines} Einträge...", expanded=True) as status:
            prog_bar = st.progress(0)
            for i, line in enumerate(raw_lines):
                # Anzeige: X von Y
                status.write(f"Prüfe Datensatz {i+1} von {total_lines}: `{line}`")
                
                # Speed-Check: Wenn exakt im Cache, überspringen
                if line in st.session_state.saved_manual_streets:
                    new_verified.append(line)
                else:
                    # Nur bei unbekannten Daten Internet-Check (mit Spinner)
                    s_name = line.split("|")[0].strip()
                    verified_name = get_internet_verified(s_name)
                    if verified_name:
                        hnr = line.split("|")[1].strip() if "|" in line else ""
                        new_verified.append(f"{verified_name} | {hnr}".strip(" |"))
                        time.sleep(0.8) # Schutz für API
                
                prog_bar.progress((i + 1) / total_lines)
            
            # Speichern & Sync
            st.session_state.saved_manual_streets = sorted(list(set(st.session_state.saved_manual_streets + new_verified)))
            with open(STREETS_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(st.session_state.saved_manual_streets))
            status.update(label="✅ Import abgeschlossen!", state="complete")
        st.rerun()

# --- 6. MANUELLE EINGABE & CACHE ---
with st.container(border=True):
    col_in, col_list = st.columns([1, 1])
    with col_in:
        st.subheader("📥 Manuelle Prüfung")
        m_s = st.text_input("Straße")
        m_h = st.text_input("Hnr")
        if st.button("Hinzufügen"):
            with st.spinner("Validiere..."):
                v_name = get_internet_verified(m_s) or m_s
                entry = f"{v_name} | {m_h}".strip(" |")
                if entry not in st.session_state.saved_manual_streets:
                    st.session_state.saved_manual_streets.append(entry)
                    with open(STREETS_FILE, "w", encoding="utf-8") as f:
                        f.write("\n".join(st.session_state.saved_manual_streets))
                st.rerun()

    with col_list:
        st.subheader("📝 Lokale Liste")
        df = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Eintrag"])
        st.data_editor(df, use_container_width=True, height=200)
        if st.button("🗑️ Liste leeren"):
            st.session_state.saved_manual_streets = []
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.rerun()

# --- 7. ANALYSE-ENGINE MIT FORTSCHRITT ---
st.divider()
c_go, c_st = st.columns(2)
if c_go.button("🔥 ANALYSE STARTEN", type="primary", use_container_width=True):
    st.session_state.run_processing = True
    st.rerun()
if c_st.button("🛑 STOPP", type="secondary", use_container_width=True):
    st.session_state.run_processing = False
    st.rerun()

if st.session_state.run_processing:
    results = defaultdict(list)
    total_analysis = len(st.session_state.saved_manual_streets)
    with st.status(f"Berechne Geometrien (0 von {total_analysis})...", expanded=True) as status:
        p_bar = st.progress(0)
        for i, s in enumerate(st.session_state.saved_manual_streets):
            status.write(f"Analysiere {i+1}/{total_analysis}: **{s}**")
            try:
                s_name = s.split("|")[0].strip()
                hnr = s.split("|")[1].strip() if "|" in s else None
                s_cl = re.sub(r'(?i)\bstr\b\.?', 'Straße', s_name).strip()
                gdf = ox.features_from_address(f"{s_cl}, Marburg-Biedenkopf", tags={"highway": True}, dist=50)
                if not gdf.empty:
                    gdf = gdf[gdf['name'].str.contains(s_cl, case=False, na=False)].to_crs(epsg=4326)
                    if not gdf.empty:
                        m_pos = None
                        if hnr:
                            l = geolocator.geocode(f"{s_cl} {hnr}, Marburg-Biedenkopf")
                            if l: m_pos = (l.latitude, l.longitude)
                        cent = gdf.geometry.unary_union.centroid
                        rv = geolocator.reverse((cent.y, cent.x), language='de')
                        ort = rv.raw.get('address', {}).get('village') or \
                              rv.raw.get('address', {}).get('suburb') or "Marburg"
                        results[ort].append({"gdf": gdf, "name": s_cl, "marker": m_pos})
            except: pass
            p_bar.progress((i + 1) / total_analysis)
            time.sleep(1.1)
        st.session_state.ort_sammlung = dict(results)
        st.session_state.run_processing = False
        status.update(label="Analyse fertig!", state="complete")
        st.rerun()

# --- 8. KARTE ---
if st.session_state.ort_sammlung:
    with st.spinner("Karte wird gerendert..."):
        m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
        for ort, items in st.session_state.ort_sammlung.items():
            fg = folium.FeatureGroup(name=ort)
            color = "#%06x" % random.randint(0, 0xFFFFFF)
            for itm in items:
                folium.GeoJson(
                    itm["gdf"].__geo_interface__,
                    style_function=lambda x, c=color: {'color': c, 'weight': 6, 'opacity': 0.7},
                    highlight_function=lambda x: {'weight': 10, 'color': 'black'},
                    tooltip=folium.Tooltip(f"<b>{itm['name']}</b> ({ort})")
                ).add_to(fg)
                if itm["marker"]:
                    folium.Marker(itm["marker"], icon=folium.Icon(color="red")).add_to(fg)
            fg.add_to(m)
        folium.LayerControl().add_to(m)
        components.html(m._repr_html_(), height=600)
