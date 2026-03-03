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
ST_TITLE = "INTEGRAL Pro eMarker"
st.set_page_config(page_title=ST_TITLE, layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
# User-Agent Rotation für API-Stabilität
geolocator = Nominatim(user_agent=f"integral_pro_core_{random.randint(1000,9999)}", timeout=10)

# --- 2. GESTÄRKTE HILFSFUNKTIONEN ---
def parse_line(line):
    """Trennt Straße und Hausnummer mit erweitertem Regex für Sonderformate."""
    line = line.strip()
    if not line: return None, None
    if "|" in line:
        parts = line.split("|")
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
    
    # Erkennt "Hauptstr. 12", "Bachweg 1-3", "Testallee 4b"
    match = re.match(r"^(.*?)\s+([\d\s\-/]+[a-zA-Z]?)$", line)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return line, ""

def get_internet_verified(street, hnr=""):
    """Prüft Straße online und extrahiert exakten Namen aus den Adressdetails."""
    try:
        query = f"{street} {hnr}, Marburg-Biedenkopf".strip()
        results = geolocator.geocode(query, exactly_one=False, limit=1, addressdetails=True)
        if results:
            details = results[0].raw.get("address", {})
            # Bevorzugte Felder für Straßennamen in der OpenStreetMap-Struktur
            road = details.get("road") or details.get("pedestrian") or details.get("suburb")
            return road if road else results[0].address.split(',')[0].strip()
    except Exception:
        pass
    return None

# --- 3. PERSISTENZ (SESSION STATE) ---
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
st.markdown(f"<h1>{ST_TITLE}</h1>", unsafe_allow_html=True)
st.divider()

# --- 5. DATEI-IMPORT (OPTIMIERT) ---
uploaded_files = st.file_uploader("*.txt Dateien importieren", type=["txt"], accept_multiple_files=True)
if uploaded_files:
    new_entries = []
    all_lines = []
    for f in uploaded_files:
        lines = f.getvalue().decode("utf-8").splitlines()
        all_lines.extend([l.strip() for l in lines if l.strip()])
    
    total = len(all_lines)
    if total > 0:
        with st.status(f"Importiere {total} Datensätze...", expanded=True) as status:
            prog = st.progress(0)
            for i, line in enumerate(all_lines):
                s_name, h_num = parse_line(line)
                clean_entry = f"{s_name} | {h_num}".strip(" |")
                
                # Schneller Abgleich gegen Duplikate
                if not any(clean_entry.lower() == s.lower() for s in st.session_state.saved_manual_streets):
                    with st.spinner(f"Validierung: {s_name}"):
                        v_name = get_internet_verified(s_name, h_num)
                        final_name = v_name if v_name else s_name
                        new_entries.append(f"{final_name} | {h_num}".strip(" |"))
                        time.sleep(0.9) # API Safety Delay
                
                prog.progress((i + 1) / total)
                status.write(f"Verarbeitet: {i+1}/{total} - `{clean_entry}`")
            
            if new_entries:
                st.session_state.saved_manual_streets = sorted(list(set(st.session_state.saved_manual_streets + new_entries)))
                with open(STREETS_FILE, "w", encoding="utf-8") as f:
                    f.write("\n".join(st.session_state.saved_manual_streets))
            status.update(label="✅ Import & Validierung abgeschlossen!", state="complete")
        st.rerun()

# --- 6. UI: EINGABE & CACHE ---
with st.container(border=True):
    col_in, col_list = st.columns([1, 1])
    with col_in:
        st.subheader("📥 Einzelprüfung")
        m_s = st.text_input("Straßenname")
        m_h = st.text_input("Hausnummer")
        if st.button("Zur Liste hinzufügen", use_container_width=True):
            if m_s:
                with st.spinner("Prüfe Geodaten..."):
                    v_name = get_internet_verified(m_s, m_h) or m_s
                    entry = f"{v_name} | {m_h}".strip(" |")
                    if entry not in st.session_state.saved_manual_streets:
                        st.session_state.saved_manual_streets.append(entry)
                        with open(STREETS_FILE, "w", encoding="utf-8") as f:
                            f.write("\n".join(st.session_state.saved_manual_streets))
                        st.rerun()

    with col_list:
        st.subheader("📝 Aktuelle Liste")
        df = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Eintrag"])
        st.data_editor(df, use_container_width=True, height=200)
        if st.button("🗑️ Alle Einträge löschen", use_container_width=True):
            st.session_state.saved_manual_streets = []
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.rerun()

# --- 7. ANALYSE-ENGINE ---
st.divider()
c_go, c_st = st.columns(2)
if c_go.button("🚀 ANALYSE STARTEN", type="primary", use_container_width=True):
    st.session_state.run_processing = True
    st.rerun()
if c_st.button("🛑 STOPP", type="secondary", use_container_width=True):
    st.session_state.run_processing = False
    st.rerun()

if st.session_state.run_processing:
    results = defaultdict(list)
    s_list = st.session_state.saved_manual_streets
    if not s_list:
        st.warning("Die Liste ist leer.")
        st.session_state.run_processing = False
    else:
        with st.status("Geometrie-Analyse läuft...", expanded=True) as status:
            p_bar = st.progress(0)
            for i, s in enumerate(s_list):
                status.write(f"Bearbeite {i+1}/{len(s_list)}: **{s}**")
                try:
                    s_name, hnr = parse_line(s)
                    # OSMnx braucht oft "Straße" statt "Str."
                    s_cl = re.sub(r'(?i)\bstr\b\.?', 'Straße', s_name).strip()
                    
                    gdf = ox.features_from_address(f"{s_cl}, Marburg-Biedenkopf", tags={"highway": True}, dist=80)
                    if not gdf.empty:
                        gdf = gdf[gdf['name'].str.contains(s_cl, case=False, na=False)].to_crs(epsg=4326)
                        if not gdf.empty:
                            m_pos = None
                            if hnr:
                                loc = geolocator.geocode(f"{s_cl} {hnr}, Marburg-Biedenkopf")
                                if loc: m_pos = (loc.latitude, loc.longitude)
                            
                            # Ortsteil bestimmen via Reverse-Geocode
                            cent = gdf.geometry.unary_union.centroid
                            rv = geolocator.reverse((cent.y, cent.x), language='de')
                            details = rv.raw.get('address', {})
                            ort = details.get('village') or details.get('suburb') or details.get('town') or "Marburg"
                            results[ort].append({"gdf": gdf, "name": s_cl, "marker": m_pos})
                except: pass
                p_bar.progress((i + 1) / len(s_list))
                time.sleep(1.0)
            
            st.session_state.ort_sammlung = dict(results)
            st.session_state.run_processing = False
            status.update(label="✅ Analyse erfolgreich beendet!", state="complete")
            st.rerun()

# --- 8. KARTEN-AUSGABE ---
if st.session_state.ort_sammlung:
    with st.spinner("Visualisierung wird vorbereitet..."):
        m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
        for ort, items in st.session_state.ort_sammlung.items():
            fg = folium.FeatureGroup(name=ort)
            # Zufällige Farbe pro Ortsteil für bessere Übersicht
            color = "#%06x" % random.randint(0, 0xFFFFFF)
            for itm in items:
                folium.GeoJson(
                    itm["gdf"].__geo_interface__,
                    style_function=lambda x, c=color: {'color': c, 'weight': 6, 'opacity': 0.7},
                    highlight_function=lambda x: {'weight': 10, 'color': 'black'},
                    tooltip=folium.Tooltip(f"<b>{itm['name']}</b><br>Ortsteil: {ort}")
                ).add_to(fg)
                if itm["marker"]:
                    folium.Marker(itm["marker"], icon=folium.Icon(color="red", icon="home")).add_to(fg)
            fg.add_to(m)
        folium.LayerControl().add_to(m)
        components.html(m._repr_html_(), height=600)
