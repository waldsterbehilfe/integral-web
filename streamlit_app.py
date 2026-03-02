import streamlit as st
import osmnx as ox
import folium
import io, re, os, random, shutil
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components
import time

# --- 0. SERIENNUMMER ---
SERIAL_NUMBER = "SN-030" 

# --- 1. SETUP & THEME ---
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide", page_icon="📈")

LOGO_URL = "https://integral-online.de/images/integral-gmbh-logo.png"

# Cache & Verzeichnisse
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "persistent_geocache")
os.makedirs(CACHE_DIR, exist_ok=True)
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR

# --- DATEI FÜR MANUELLE LISTEN ---
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")

# --- OPTIMIERUNG: Timeout für geolocator ---
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=10)

# --- HILFSFUNKTIONEN FÜR DATEI-ZUGRIFF ---
def save_streets(streets_list):
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(streets_list))

def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    return []

def clear_all_caches():
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR, exist_ok=True)
    ox.settings.use_cache = False
    ox.settings.use_cache = True
    st.cache_data.clear()
    st.cache_resource.clear()

# --- HILFSFUNKTION FÜR EXCEL-EXPORT ---
def create_excel_download(ort_sammlung):
    data = []
    for ort, items in ort_sammlung.items():
        for item in items:
            data.append({
                "Ortsteil": ort,
                "Originaleingabe": item["original"],
                "Gefundener Straßenname": item["name"],
                "Zentrum Lat": item["gdf"].geometry.unary_union.centroid.y,
                "Zentrum Lon": item["gdf"].geometry.unary_union.centroid.x,
                "Marker Lat": item["marker"][0] if item["marker"] else None,
                "Marker Lon": item["marker"][1] if item["marker"] else None
            })
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Analyseergebnisse')
    return output.getvalue()

# Session State - Initialisierung
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'fehler_liste' not in st.session_state: st.session_state.fehler_liste = []
if 'run_processing' not in st.session_state: st.session_state.run_processing = False
if 'stop_requested' not in st.session_state: st.session_state.stop_requested = False
if 'saved_manual_streets' not in st.session_state: st.session_state.saved_manual_streets = load_streets()
if 'online_suggestions' not in st.session_state: st.session_state.online_suggestions = []

# Hintergrundfarbe
st.markdown("<style>.stApp {background-color: #0E1117;}</style>", unsafe_allow_html=True)

# --- FUNKTION (MIT STRIKTER FILTERUNG) ---
def verarbeite_strasse(strasse_input):
    if not strasse_input: return {"success": False}
    
    # --- PAUSE ---
    time.sleep(random.uniform(0.5, 1.0))
    
    if " | " in strasse_input:
        parts = strasse_input.split(" | ")
        strasse_name = parts[0].strip()
        hnr = parts[1].strip()
    else:
        strasse_name = strasse_input.strip()
        hnr = None

    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse_name).strip()
    query = f"{s_clean}, Marburg-Biedenkopf"
    
    try:
        # 1. Finde die Geometrie der Straße
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=30)
        
        if gdf.empty:
            return {"success": False, "original": strasse_input}

        # 2. Filtere auf den exakten Namen
        gdf = gdf[gdf['name'].str.contains(s_clean, case=False, na=False)]
        
        if gdf.empty:
            return {"success": False, "original": strasse_input}

        # --- PRÄZISERE MARKER-LOGIK (NUR BEI HNR) ---
        marker_coords = None
        if hnr:
            loc = geolocator.geocode(f"{s_clean} {hnr}, Marburg-Biedenkopf", timeout=10)
            if loc:
                marker_coords = (loc.latitude, loc.longitude)

        # 3. Ortsteil bestimmen
        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
        osm_name = gdf['name'].iloc[0] if 'name' in gdf.columns else s_clean
        
        ortsteil = "Unbekannt"
        if 'is_in:suburb' in gdf.columns: ortsteil = gdf['is_in:suburb'].iloc[0]
        elif 'is_in:village' in gdf.columns: ortsteil = gdf['is_in:village'].iloc[0]
        
        if ortsteil == "Unbekannt" or pd.isna(ortsteil):
            try:
                centroid = gdf.geometry.unary_union.centroid
                loc_rev = geolocator.reverse((centroid.y, centroid.x), language='de', timeout=3)
                if loc_rev and 'address' in loc_rev.raw:
                    a = loc_rev.raw['address']
                    ortsteil = a.get('village') or a.get('suburb') or a.get('hamlet') or a.get('town') or "Unbekannt"
            except: pass
        
        return {
            "gdf": gdf, 
            "ort": ortsteil, 
            "name": osm_name, 
            "original": strasse_input, 
            "marker": marker_coords, 
            "success": True
        }
    except:
        pass
    return {"success": False, "original": strasse_input}

# --- 3. UI LAYOUT ---
# Header
col_logo, col_title = st.columns([1, 10])
with col_logo: st.image(LOGO_URL, width=80)
with col_title:
    st.title("INTEGRAL PRO")
    st.markdown(f"Automatisierte Straßensortierung — **V9.21 (LayoutUpdate {SERIAL_NUMBER})**")

st.divider()

# Layout: 2 Spalten (Eingabe links, Karte rechts)
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("📥 Dateneingabe")
    
    with st.expander("🛠️ Einstellungen & Aktionen", expanded=False):
        st.write("🎨 **Farbeinstellungen**")
        if st.session_state.ort_sammlung:
            for ort in sorted(st.session_state.ort_sammlung.keys()):
                st.color_picker(f"{ort}", "#FF0000", key=f"cp_{ort}")
        else:
            st.write("Farben verfügbar nach Analyse.")
        
        st.write("⚡ **Cache & Liste**")
        col_c1, col_c2 = st.columns(2)
        if col_c1.button("📋 Liste leeren"):
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.session_state.saved_manual_streets = []
            st.rerun()
        if col_c2.button("🗑️ Cache leeren"):
            clear_all_caches()
            st.rerun()

    # File Uploader
    files = st.file_uploader("Upload TXT Dateien", type=["txt"], accept_multiple_files=True)
    if files:
        new_streets = []
        for f in files: 
            file_streets = [s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()]
            new_streets.extend(file_streets)
        
        merged_streets = list(set(st.session_state.saved_manual_streets + new_streets))
        if len(merged_streets) > len(st.session_state.saved_manual_streets):
            st.session_state.saved_manual_streets = merged_streets
            save_streets(st.session_state.saved_manual_streets)
            st.success(f"{len(new_streets)} Straßen hinzugefügt.")
            st.rerun()

    # Manuelle Suche
    st.markdown("---")
    st.write("🔍 **Einzelne Straße suchen**")
    col_s1, col_s2 = st.columns([3, 1])
    with col_s1: query_street = st.text_input("Name:", placeholder="z.B. Am Markt")
    with col_s2: query_hnr = st.text_input("Nr.:", placeholder="12a")
    
    combined_query = f"{query_street} {query_hnr}".strip()
    selected_suggestion = None
    if len(query_street) > 2:
        with st.spinner("Prüfe..."):
            try:
                results = geolocator.geocode(f"{combined_query}, Marburg-Biedenkopf", exactly_one=False, limit=5, timeout=5)
                if results:
                    st.session_state.online_suggestions = [r.address for r in results]
                    selected_suggestion = st.selectbox("Gefundene Adressen:", st.session_state.online_suggestions)
                else:
                    st.write("Keine Übereinstimmung.")
            except Exception as e:
                st.error(f"Fehler: {e}")

    if st.button("➕ Straße hinzufügen"):
        if selected_suggestion:
            full_street_address = selected_suggestion.split(',')[0].strip()
            if query_hnr and query_hnr in full_street_address:
                final_street_name = full_street_address.replace(query_hnr, "").strip()
            else:
                final_street_name = full_street_address
            street_to_save = f"{final_street_name} | {query_hnr}".strip(" |")
            if street_to_save not in st.session_state.saved_manual_streets:
                st.session_state.saved_manual_streets.append(street_to_save)
                save_streets(st.session_state.saved_manual_streets)
                st.rerun()

    # Eingabeliste Anzeige
    st.markdown("---")
    st.write(f"📝 **Liste ({len(st.session_state.saved_manual_streets)})**")
    st.dataframe(st.session_state.saved_manual_streets, use_container_width=True, height=200)
    
    # Analyse Buttons
    col_b1, col_b2 = st.columns(2)
    if col_b1.button("🚀 Analyse starten", type="primary"):
        st.session_state.run_processing, st.session_state.stop_requested = True, False
        st.session_state.ort_sammlung, st.session_state.fehler_liste = None, []
    if col_b2.button("🛑 Abbruch"):
        st.session_state.stop_requested, st.session_state.run_processing = False, False
        st.rerun()

with col_right:
    # 4. VERARBEITUNG & 5. ANZEIGE
    if st.session_state.run_processing:
        strassen_liste = [s for s in st.session_state.saved_manual_streets if s]
        temp_ort, temp_err = defaultdict(list), []
        with st.spinner("🔍 Analysiere Straßen..."):
            pb = st.progress(0)
            total = len(strassen_liste)
            with ThreadPoolExecutor(max_workers=1) as executor:
                futures = {executor.submit(verarbeite_strasse, s): s for s in strassen_liste}
                for i, future in enumerate(futures):
                    if st.session_state.stop_requested: break
                    res = future.result()
                    if res.get("success"): temp_ort[res["ort"]].append(res)
                    else: temp_err.append(res.get("original", "Unbekannt"))
                    pb.progress((i + 1) / total)

        if not st.session_state.stop_requested:
            st.session_state.ort_sammlung, st.session_state.fehler_liste = dict(temp_ort), temp_err
            st.balloons()
        st.session_state.run_processing = False
        st.rerun()

    if st.session_state.ort_sammlung:
        st.subheader("🗺️ Karte")
        if st.session_state.fehler_liste:
            with st.expander("⚠️ Nicht gefunden"): st.write(", ".join(st.session_state.fehler_liste))

        m = folium.Map(location=[50.8, 8.8], zoom_start=11)
        all_geoms = []
        marker_fg = folium.FeatureGroup(name="📍 Marker")

        for ort, items in st.session_state.ort_sammlung.items():
            color = st.session_state.get(f"cp_{ort}", "#FF0000")
            fg = folium.FeatureGroup(name=f"📍 {ort}")
            for item in items:
                all_geoms.append(item["gdf"])
                folium.GeoJson(item["gdf"].__geo_interface__,
                               style_function=lambda x, c=color: {'color': c, 'weight': 5, 'opacity': 0.7},
                               tooltip=f"{item['name']}").add_to(fg)
                if item.get("marker"):
                    folium.Marker(location=item["marker"], popup=f"{item['original']}", icon=folium.Icon(color="blue", icon="info-sign")).add_to(marker_fg)
            fg.add_to(m)
        
        marker_fg.add_to(m)
        folium.LayerControl(collapsed=False).add_to(m)
        
        if all_geoms:
            combined = gpd.GeoDataFrame(pd.concat(all_geoms))
            b = combined.total_bounds
            m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])

        components.html(m._repr_html_(), height=600)
        
        # Downloads
        st.markdown("---")
        st.write("📥 **Downloads**")
        col_d1, col_d2 = st.columns(2)
        try:
            excel_data = create_excel_download(st.session_state.ort_sammlung)
            col_d1.download_button("Excel exportieren", excel_data, file_name=f"Analyse.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        except ImportError:
            col_d1.error("xlsxwriter fehlt.")
        col_d2.download_button("Karte speichern (HTML)", m._repr_html_(), file_name="Ergebnis.html", mime="text/html", use_container_width=True)
