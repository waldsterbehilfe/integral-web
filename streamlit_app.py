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
geolocator = Nominatim(user_agent=f"integral_pro_final_{random.randint(1000,9999)}", timeout=10)

# --- 2. HILFSFUNKTIONEN ---
def parse_line(line):
    """Trennt Straße und Hausnummer."""
    line = line.strip()
    if not line: return None, None
    if "|" in line:
        parts = line.split("|")
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
    match = re.match(r"^(.*?)\s+([\d\s\-/]+[a-zA-Z]?)$", line)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return line, ""

def get_internet_verified(street, hnr=""):
    """Validiert Straße online."""
    try:
        query = f"{street} {hnr}, Marburg-Biedenkopf".strip()
        results = geolocator.geocode(query, exactly_one=False, limit=1, addressdetails=True)
        if results:
            details = results[0].raw.get("address", {})
            road = details.get("road") or details.get("pedestrian") or details.get("suburb")
            return road if road else results[0].address.split(',')[0].strip()
    except: pass
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
st.markdown(f"<h2>{ST_TITLE}</h2>", unsafe_allow_html=True)
st.divider()

# --- 5. DATEI-IMPORT (JETZT OHNE SOFORT-VALIDIERUNG) ---
uploaded_files = st.file_uploader("*.txt Dateien importieren (Schnell-Import aktiv)", type=["txt"], accept_multiple_files=True)
if uploaded_files:
    new_raw_entries = []
    for f in uploaded_files:
        lines = f.getvalue().decode("utf-8").splitlines()
        for line in lines:
            s_name, h_num = parse_line(line)
            if s_name:
                new_raw_entries.append(f"{s_name} | {h_num}".strip(" |"))
    
    if new_raw_entries:
        # Nur neue Einträge hinzufügen (Duplikate vermeiden)
        existing = set(st.session_state.saved_manual_streets)
        to_add = [e for e in new_raw_entries if e not in existing]
        st.session_state.saved_manual_streets.extend(to_add)
        with open(STREETS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(st.session_state.saved_manual_streets))
        st.success(f"{len(to_add)} neue Einträge geladen.")
        st.rerun()

# --- 6. UI: EINGABE & LISTE ---
with st.container(border=True):
    col_in, col_list = st.columns([1, 1])
    with col_in:
        st.subheader("📥 Manuelle Eingabe")
        m_s = st.text_input("Straße")
        m_h = st.text_input("Hnr")
        if st.button("Hinzufügen", use_container_width=True):
            if m_s:
                entry = f"{m_s} | {m_h}".strip(" |")
                if entry not in st.session_state.saved_manual_streets:
                    st.session_state.saved_manual_streets.append(entry)
                    with open(STREETS_FILE, "w", encoding="utf-8") as f:
                        f.write("\n".join(st.session_state.saved_manual_streets))
                    st.rerun()

    with col_list:
        st.subheader("📝 Liste")
        df = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Eintrag"])
        edited_df = st.data_editor(df, use_container_width=True, height=200)
        c1, c2 = st.columns(2)
        if c1.button("💾 Liste speichern", use_container_width=True):
            st.session_state.saved_manual_streets = edited_df["Eintrag"].tolist()
            with open(STREETS_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(st.session_state.saved_manual_streets))
            st.rerun()
        if c2.button("🗑️ Liste leeren", use_container_width=True):
            st.session_state.saved_manual_streets = []
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.rerun()

# --- 7. ANALYSE-ENGINE (JETZT MIT INTEGRIERTER VALIDIERUNG) ---
st.divider()
c_go, c_st = st.columns(2)
if c_go.button("🔥 ANALYSE & VALIDIERUNG STARTEN", type="primary", use_container_width=True):
    st.session_state.run_processing = True
    st.rerun()
if c_st.button("🛑 STOPP", type="secondary", use_container_width=True):
    st.session_state.run_processing = False
    st.rerun()

if st.session_state.run_processing:
    results = defaultdict(list)
    s_list = st.session_state.saved_manual_streets
    total = len(s_list)
    
    if total == 0:
        st.warning("Keine Daten vorhanden.")
        st.session_state.run_processing = False
    else:
        with st.status("Verarbeite Daten...", expanded=True) as status:
            p_bar = st.progress(0)
            for i, s in enumerate(s_list):
                status.write(f"Datensatz {i+1}/{total}: **{s}**")
                try:
                    # 1. Schritt: Straße und Hnr parsen
                    raw_s, hnr = parse_line(s)
                    
                    # 2. Schritt: Validierung (Internet-Check erst jetzt!)
                    v_name = get_internet_verified(raw_s, hnr) or raw_s
                    s_cl = re.sub(r'(?i)\bstr\b\.?', 'Straße', v_name).strip()
                    
                    # 3. Schritt: Geometrie holen
                    gdf = ox.features_from_address(f"{s_cl}, Marburg-Biedenkopf", tags={"highway": True}, dist=80)
                    if not gdf.empty:
                        gdf = gdf[gdf['name'].str.contains(s_cl, case=False, na=False)].to_crs(epsg=4326)
                        if not gdf.empty:
                            m_pos = None
                            if hnr:
                                loc = geolocator.geocode(f"{s_cl} {hnr}, Marburg-Biedenkopf")
                                if loc: m_pos = (loc.latitude, loc.longitude)
                            
                            cent = gdf.geometry.unary_union.centroid
                            rv = geolocator.reverse((cent.y, cent.x), language='de')
                            ort = rv.raw.get('address', {}).get('village') or \
                                  rv.raw.get('address', {}).get('suburb') or "Unbekannt"
                            results[ort].append({"gdf": gdf, "name": s_cl, "marker": m_pos})
                    
                    time.sleep(1.0) # Schutz für die API
                except: pass
                p_bar.progress((i + 1) / total)
            
            st.session_state.ort_sammlung = dict(results)
            st.session_state.run_processing = False
            status.update(label="✅ Analyse und Validierung abgeschlossen!", state="complete")
            st.rerun()

# --- 8. KARTEN-AUSGABE ---
if st.session_state.ort_sammlung:
    m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
    for ort, items in st.session_state.ort_sammlung.items():
        fg = folium.FeatureGroup(name=ort)
        color = "#%06x" % random.randint(0, 0xFFFFFF)
        for itm in items:
            folium.GeoJson(
                itm["gdf"].__geo_interface__,
                style_function=lambda x, c=color: {'color': c, 'weight': 6, 'opacity': 0.7},
                tooltip=folium.Tooltip(f"<b>{itm['name']}</b> ({ort})")
            ).add_to(fg)
            if itm["marker"]:
                folium.Marker(itm["marker"], icon=folium.Icon(color="red", icon="home")).add_to(fg)
        fg.add_to(m)
    folium.LayerControl().add_to(m)
    components.html(m._repr_html_(), height=600)
