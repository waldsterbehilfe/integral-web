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
SERIAL_NUMBER = "SN-029-test-1-2-3"
st.set_page_config(page_title=f"INTEGRAL Pro eMarker", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
geolocator = Nominatim(user_agent=f"integral_pro_v8_{random.randint(100,999)}", timeout=10)

# --- 2. HILFSFUNKTIONEN (NEU: ROBUSTE PARSER) ---
def parse_line(line):
    """Trennt Straße und Hausnummer intelligent, auch wenn kein '|' vorhanden ist."""
    line = line.strip()
    if "|" in line:
        parts = line.split("|")
        return parts[0].strip(), parts[1].strip()
    
    # Sucht nach dem Muster: Text (Straße) gefolgt von Zahlen (Hausnummer)
    match = re.match(r"^(.*?)\s+(\d+[a-zA-Z]?(-?\d+[a-zA-Z]?)?)$", line)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return line, ""

def get_internet_verified(street, hnr=""):
    """Validiert die Straße und extrahiert garantiert nur den Straßennamen."""
    try:
        query = f"{street} {hnr}, Marburg-Biedenkopf".strip()
        results = geolocator.geocode(query, exactly_one=False, limit=1, addressdetails=True)
        if results:
            # Hole explizit die 'road' (Straße) aus den Backend-Daten, nicht aus dem Anzeigetext!
            addr_details = results[0].raw.get("address", {})
            road = addr_details.get("road")
            if road:
                return road
            # Fallback, falls 'road' leer ist
            return results[0].address.split(',')[0].strip()
    except Exception:
        pass
    return None

# --- 3. PERSISTENZ (SPEICHERUNG) ---
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
st.markdown("<h2>INTEGRAL Pro eMarker</h2>", unsafe_allow_html=True)
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
                status.write(f"Prüfe Datensatz {i+1} von {total_lines}: `{line}`")
                
                # Straße und Hausnummer sauber trennen
                street, hnr = parse_line(line)
                normalized_entry = f"{street} | {hnr}".strip(" |")
                
                # Speed-Check
                if normalized_entry in st.session_state.saved_manual_streets:
                    new_verified.append(normalized_entry)
                else:
                    with st.spinner(f"Validierung für: {street}"):
                        verified_name = get_internet_verified(street, hnr)
                        if verified_name:
                            new_verified.append(f"{verified_name} | {hnr}".strip(" |"))
                            time.sleep(1.0) # API-Schutz
                
                prog_bar.progress((i + 1) / total_lines)
            
            # Speichern & Synchronisieren (Duplikate entfernen)
            st.session_state.saved_manual_streets = sorted(list(set(st.session_state.saved_manual_streets + new_verified)))
            with open(STREETS_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(st.session_state.saved_manual_streets))
            status.update(label="✅ Import erfolgreich abgeschlossen!", state="complete")
        st.rerun()

# --- 6. MANUELLE EINGABE & LISTE ---
with st.container(border=True):
    col_in, col_list = st.columns([1, 1])
    with col_in:
        st.subheader("📥 Manuelle Prüfung")
        m_s = st.text_input("Straße", placeholder="z.B. Hauptstr.")
        m_h = st.text_input("Hnr", placeholder="1")
        if st.button("Hinzufügen"):
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
    
    if total_analysis == 0:
        st.warning("Keine Daten zum Analysieren vorhanden.")
        st.session_state.run_processing = False
    else:
        with st.status(f"Berechne Geometrien (0 von {total_analysis})...", expanded=True) as status:
            p_bar = st.progress(0)
            for i, s in enumerate(st.session_state.saved_manual_streets):
                status.write(f"Analysiere {i+1} von {total_analysis}: **{s}**")
                
                try:
                    s_name, hnr = parse_line(s)
                    s_cl = re.sub(r'(?i)\bstr\b\.?', 'Straße', s_name).strip()
                    
                    with st.spinner(f"Kartendaten laden für {s_cl}..."):
                        gdf = ox.features_from_address(f"{s_cl}, Marburg-Biedenkopf", tags={"highway": True}, dist=50)
                        
                        if not gdf.empty:
                            gdf = gdf[gdf['name'].str.contains(s_cl, case=False, na=False)].to_crs(epsg=4326)
                            if not gdf.empty:
                                m_pos = None
                                if hnr:
                                    # Genauere Geokodierung für den Marker
                                    l = geolocator.geocode(f"{s_cl} {hnr}, Marburg-Biedenkopf")
                                    if l: m_pos = (l.latitude, l.longitude)
                                cent = gdf.geometry.unary_union.centroid
                                rv = geolocator.reverse((cent.y, cent.x), language='de')
                                ort = rv.raw.get('address', {}).get('village') or \
                                      rv.raw.get('address', {}).get('suburb') or "Marburg"
                                results[ort].append({"gdf": gdf, "name": s_cl, "marker": m_pos})
                except Exception:
                    pass
                    
                p_bar.progress((i + 1) / total_analysis)
                status.update(label=f"Berechne Geometrien ({i+1} von {total_analysis})...")
                time.sleep(1.0)
                
            st.session_state.ort_sammlung = dict(results)
            st.session_state.run_processing = False
            status.update(label="✅ Analyse abgeschlossen!", state="complete")
            st.rerun()

# --- 8. KARTE ---
if st.session_state.ort_sammlung:
    with st.spinner("Karte wird erstellt..."):
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
