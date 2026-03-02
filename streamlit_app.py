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
SERIAL_NUMBER = "SN-043" 

# --- 1. SETUP & THEME ---
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide", page_icon="🌐")

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
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=5) # Strengerer Timeout

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
if 'suggestion_map' not in st.session_state: st.session_state.suggestion_map = {}
if 'show_markers' not in st.session_state: st.session_state.show_markers = False

# Hintergrundfarbe & Style
st.markdown("""
<style>
    .stApp {background-color: #0E1117;}
</style>
""", unsafe_allow_html=True)

# --- FUNKTION (MIT STRIKTER FILTERUNG) ---
def verarbeite_strasse(strasse_input):
    if not strasse_input: return {"success": False}
    
    # --- PAUSE VERRINGERT, DAFÜR MEHR THREADS ---
    time.sleep(random.uniform(0.1, 0.3))
    
    if " | " in strasse_input:
        parts = strasse_input.split(" | ")
        strasse_name = parts[0].strip()
        hnr = parts[1].strip()
    else:
        strasse_name = strasse_input.strip()
        hnr = None

    query = f"{strasse_name}, Marburg-Biedenkopf"
    
    try:
        # Finde die Geometrie der Straße
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=100)
        
        if gdf.empty:
            return {"success": False, "original": strasse_input}

        gdf = gdf[gdf['name'].str.contains(re.escape(strasse_name), case=False, na=False)]
        
        if gdf.empty:
            return {"success": False, "original": strasse_input}

        marker_coords = None
        if hnr:
            loc = geolocator.geocode(f"{strasse_name} {hnr}, Marburg-Biedenkopf", timeout=5)
            if loc:
                marker_coords = (loc.latitude, loc.longitude)

        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
        
        osm_name = gdf['name'].iloc[0] if 'name' in gdf.columns else strasse_name
        
        ortsteil = "Unbekannt"
        if 'is_in:suburb' in gdf.columns: ortsteil = gdf['is_in:suburb'].iloc[0]
        elif 'is_in:village' in gdf.columns: ortsteil = gdf['is_in:village'].iloc[0]
        
        if ortsteil == "Unbekannt" or pd.isna(ortsteil):
            try:
                centroid = gdf.geometry.unary_union.centroid
                loc_rev = geolocator.reverse((centroid.y, centroid.x), language='de', timeout=2)
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
    except Exception as e:
        # --- ROBUSTE FEHLERBEHANDLUNG ---
        print(f"Fehler bei {strasse_name}: {e}")
        pass
        
    return {"success": False, "original": strasse_input}

# --- 3. UI LAYOUT ---

# Top Header
col_h1, col_h2 = st.columns([1, 4])
with col_h1: st.image(LOGO_URL, width=150)
with col_h2: 
    st.title("Integral Pro")
    st.markdown(f"**Version:** {SERIAL_NUMBER} | GIS Dashboard")

st.markdown("---")

# --- CONTROL PANEL ---
with st.container():
    st.subheader("⚙️ Steuerung")
    c_col1, c_col2, c_col3, c_col4 = st.columns(4)
    
    with c_col1:
        query_input = st.text_input("Adresse eingeben (Strasse + Nr):", placeholder="Ringstr 10")
        if len(query_input) > 3:
            with st.spinner("Suche..."):
                try:
                    results = geolocator.geocode(f"{query_input}, Marburg-Biedenkopf", exactly_one=False, limit=5, timeout=5)
                    if results:
                        st.session_state.suggestion_map = {r.address: r for r in results}
                        selected_address = st.selectbox("Vorschläge:", list(st.session_state.suggestion_map.keys()))
                    else:
                        st.write("Keine Übereinstimmung.")
                        st.session_state.suggestion_map = {}
                        selected_address = None
                except Exception as e:
                    st.error(f"Fehler: {e}")
                    selected_address = None
        else:
            selected_address = None
        
        if st.button("➕ Straße hinzufügen", use_container_width=True):
            if selected_address and selected_address in st.session_state.suggestion_map:
                res = st.session_state.suggestion_map[selected_address]
                raw = res.raw.get('address', {})
                street_found = raw.get('road') or raw.get('pedestrian') or raw.get('cycleway') or selected_address.split(',')[0]
                hnr_found = raw.get('house_number', "")
                street_to_save = f"{street_found} | {hnr_found}".strip(" |")
                
                if street_to_save not in st.session_state.saved_manual_streets:
                    st.session_state.saved_manual_streets.append(street_to_save)
                    save_streets(st.session_state.saved_manual_streets)
                    st.success(f"Hinzugefügt: {street_to_save}")
                    st.rerun()

    with c_col2:
        st.write("**Dateneingabe**")
        files = st.file_uploader("Upload TXT Dateien", type=["txt"], accept_multiple_files=True, label_visibility="collapsed")
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

    with c_col3:
        st.write("**Aktionen**")
        col_c_a1, col_c_a2 = st.columns(2)
        if col_c_a1.button("📋 Liste leeren", use_container_width=True):
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.session_state.saved_manual_streets = []
            st.rerun()
        if col_c_a2.button("🗑️ Cache leeren", use_container_width=True):
            clear_all_caches()
            st.rerun()

    with c_col4:
        st.write("**Analyse**")
        if st.button("🚀 Analyse starten", type="primary", use_container_width=True):
            st.session_state.run_processing, st.session_state.stop_requested = True, False
            st.session_state.ort_sammlung, st.session_state.fehler_liste = None, []
            st.rerun()
        if st.button("🛑 Abbruch", type="secondary", use_container_width=True):
            st.session_state.stop_requested, st.session_state.run_processing = False, False
            st.rerun()

st.markdown("---")

# 4. VERARBEITUNG
if st.session_state.run_processing:
    strassen_liste = [s for s in st.session_state.saved_manual_streets if s]
    temp_ort, temp_err = defaultdict(list), []
    with st.spinner("🔍 Analysiere Straßen... Das kann dauern."):
        pb = st.progress(0)
        total = len(strassen_liste)
        # --- MEHR THREADS FÜR STABILITÄT ---
        with ThreadPoolExecutor(max_workers=3) as executor:
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

# 5. ANZEIGE
if st.session_state.ort_sammlung:
    
    # Darstellung Optionen
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        st.session_state.show_markers = st.checkbox("📍 Marker anzeigen", value=st.session_state.show_markers)
    with col_opt2:
        st.write("🎨 Ortsteil Farben")
        for ort in sorted(st.session_state.ort_sammlung.keys()):
            st.color_picker(ort, "#FF0000", key=f"cp_{ort}")

    if st.session_state.fehler_liste:
        with st.expander("⚠️ Nicht gefundene Straßen"):
            st.write(", ".join(st.session_state.fehler_liste))

    # Karte
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
                           tooltip=f"{item['name']} ({ort})").add_to(fg)
            
            if item.get("marker") and st.session_state.show_markers:
                folium.Marker(location=item["marker"], popup=f"{item['original']}", icon=folium.Icon(color="blue", icon="info-sign")).add_to(marker_fg)
        fg.add_to(m)
    
    if st.session_state.show_markers:
        marker_fg.add_to(m)
        
    folium.LayerControl(collapsed=False).add_to(m)
    
    if all_geoms:
        combined = gpd.GeoDataFrame(pd.concat(all_geoms))
        b = combined.total_bounds
        m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])

    components.html(m._repr_html_(), height=700)
    
    # Downloads
    st.markdown("---")
    st.subheader("📥 Export & Downloads")
    col_d1, col_d2 = st.columns(2)
    try:
        excel_data = create_excel_download(st.session_state.ort_sammlung)
        col_d1.download_button("Excel Analyse herunterladen", excel_data, file_name=f"Analyse.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    except ImportError:
        col_d1.error("xlsxwriter fehlt.")
    col_d2.download_button("Karte als HTML speichern", m._repr_html_(), file_name="Ergebnis.html", mime="text/html", use_container_width=True)

else:
    # --- INTERAKTIVE LISTE ---
    st.write(f"📝 **Aktuelle Liste ({len(st.session_state.saved_manual_streets)})**")
    
    df_streets = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])
    
    edited_df = st.data_editor(df_streets, num_rows="dynamic", use_container_width=True)
    
    if st.button("💾 Liste speichern"):
        st.session_state.saved_manual_streets = edited_df["Adresse (Strasse | Nr)"].tolist()
        save_streets(st.session_state.saved_manual_streets)
        st.success("Liste gespeichert!")
        st.rerun()
