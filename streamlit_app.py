import streamlit as st
import osmnx as ox
import folium
import re, os, random, time
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components

# --- 1. SETUP & KONFIGURATION ---
SERIAL_NUMBER = "SN-029-GOLD3002"
st.set_page_config(page_title="INTEGRAL Pro eMarker", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
# Dynamischer User-Agent zur Vermeidung von Sperren
geolocator = Nominatim(user_agent=f"integral_pro_v9_{random.randint(1000,9999)}", timeout=10)

# --- 2. VERBESSERTE HILFSFUNKTIONEN ---
def parse_line(line):
    """Trennt Straße und Hausnummer intelligent."""
    line = line.strip()
    if not line: return None, None
    if "|" in line:
        parts = line.split("|")
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
    
    # Erkennt z.B. "Hauptstraße 12a"
    match = re.match(r"^(.*?)\s+(\d+[a-zA-Z]?(-?\d+[a-zA-Z]?)?)$", line)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return line, ""

def get_internet_verified(street, hnr=""):
    """Validiert Straße via API und extrahiert NUR den Straßennamen."""
    try:
        query = f"{street} {hnr}, Marburg-Biedenkopf".strip()
        # addressdetails=True ist wichtig, um 'road' separat zu erhalten
        results = geolocator.geocode(query, exactly_one=False, limit=1, addressdetails=True)
        if results:
            details = results[0].raw.get("address", {})
            # Wir nehmen priorisiert das Feld 'road'
            road_name = details.get("road") or details.get("pedestrian") or details.get("cycleway")
            if road_name:
                return road_name
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
st.markdown("<h1>INTEGRAL Pro eMarker</h1>", unsafe_allow_html=True)
st.divider()

# --- 5. DATEI-IMPORT (VERBESSERT) ---
uploaded_files = st.file_uploader("*.txt Dateien importieren", type=["txt"], accept_multiple_files=True)
if uploaded_files:
    new_verified = []
    raw_lines = []
    for f in uploaded_files:
        content = f.getvalue().decode("utf-8").splitlines()
        raw_lines.extend([l.strip() for l in content if l.strip()])
    
    total = len(raw_lines)
    if total > 0:
        with st.status(f"Verarbeite {total} Einträge...", expanded=True) as status:
            prog = st.progress(0)
            for i, line in enumerate(raw_lines):
                status.write(f"Datensatz {i+1}/{total}: `{line}`")
                s_name, h_num = parse_line(line)
                
                # Check ob bereits im Cache
                check_entry = f"{s_name} | {h_num}".strip(" |")
                if any(check_entry in saved for saved in st.session_state.saved_manual_streets):
                    new_verified.append(check_entry)
                else:
                    # Validierung mit Spinner
                    with st.spinner(f"Prüfe {s_name}..."):
                        v_name = get_internet_verified(s_name, h_num)
                        if v_name:
                            new_verified.append(f"{v_name} | {h_num}".strip(" |"))
                            time.sleep(0.8) # API Schutz
                prog.progress((i + 1) / total)
            
            # Speichern
            st.session_state.saved_manual_streets = sorted(list(set(st.session_state.saved_manual_streets + new_verified)))
            with open(STREETS_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(st.session_state.saved_manual_streets))
            status.update(label="✅ Import erfolgreich!", state="complete")
        st.rerun()

# --- 6. MANUELLE EINGABE & LISTE ---
with st.container(border=True):
    col_in, col_list = st.columns([1, 1])
    with col_in:
        st.subheader("📥 Einzelprüfung")
        m_s = st.text_input("Straße")
        m_h = st.text_input("Hnr")
        if st.button("Hinzufügen", use_container_width=True):
            if m_s:
                with st.spinner("Validiere..."):
                    v_name = get_internet_verified(m_s, m_h) or m_s
                    entry = f"{v_name} | {m_h}".strip(" |")
                    if entry not in st.session_state.saved_manual_streets:
                        st.session_state.saved_manual_streets.append(entry)
                        with open(STREETS_FILE, "w", encoding="utf-8") as f:
                            f.write("\n".join(st.session_state.saved_manual_streets))
                    st.rerun()

    with col_list:
        st.subheader("📝 Liste")
        df = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Eintrag"])
        st.data_editor(df, use_container_width=True, height=200)
        if st.button("🗑️ Liste leeren", use_container_width=True):
            st.session_state.saved_manual_streets = []
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.rerun()

# --- 7. ANALYSE-ENGINE ---
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
    total_a = len(st.session_state.saved_manual_streets)
    
    if total_a == 0:
        st.warning("Keine Daten vorhanden.")
        st.session_state.run_processing = False
    else:
        with st.status(f"Analyse läuft...", expanded=True) as status:
            p_bar = st.progress(0)
            for i, s in enumerate(st.session_state.saved_manual_streets):
                status.write(f"Analysiere {i+1}/{total_a}: **{s}**")
                try:
                    s_name, hnr = parse_line(s)
                    s_cl = re.sub(r'(?i)\bstr\b\.?', 'Straße', s_name).strip()
                    
                    with st.spinner("Lade Geometrie..."):
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
                                      rv.raw.get('address', {}).get('suburb') or "Marburg-Land"
                                results[ort].append({"gdf": gdf, "name": s_cl, "marker": m_pos})
                except Exception: pass
                p_bar.progress((i + 1) / total_a)
                time.sleep(1.1)
                
            st.session_state.ort_sammlung = dict(results)
            st.session_state.run_processing = False
            status.update(label="✅ Analyse fertig!", state="complete")
            st.rerun()

# --- 8. KARTE ---
if st.session_state.ort_sammlung:
    with st.spinner("Erstelle Karte..."):
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
