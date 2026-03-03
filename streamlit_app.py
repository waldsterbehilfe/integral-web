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
SERIAL_NUMBER = "SN-049" 

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
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=5)

# --- FESTER FARB-POOL FÜR ORTSTEILE ---
COLORS = ['#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4', '#46f0f0', '#f032e6', '#bcf60c', '#fabebe', '#008080', '#e6beff', '#9a6324', '#fffac8', '#800000', '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080']

# --- HILFSFUNKTIONEN FÜR DATEI-ZUGRIFF ---
def save_streets(streets_list):
    # Liste bereinigen: Leerzeichen trimmen, Dubletten entfernen
    cleaned_list = sorted(list(set([s.strip() for s in streets_list if s.strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned_list))
    return cleaned_list

def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return sorted(list(set([line.strip() for line in f.readlines() if line.strip()])))
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
if 'ort_colors' not in st.session_state: st.session_state.ort_colors = {}

# Hintergrundfarbe & Style
st.markdown("""
<style>
    .stApp {background-color: #0E1117;}
    .block-container {padding-top: 1rem;}
    h1 {font-size: 1.5rem !important;}
    h3 {font-size: 1.1rem !important; margin-bottom: 0.5rem;}
    .step-box {background-color: #1E232B; padding: 10px; border-radius: 5px; border: 1px solid #31333F; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# --- FUNKTION (MIT STRIKTER FILTERUNG) ---
def verarbeite_strasse(strasse_input):
    if not strasse_input: return {"success": False}
    
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
        pass
        
    return {"success": False, "original": strasse_input}

# --- 3. UI LAYOUT ---

# Top Header
col_h1, col_h2 = st.columns([1, 10])
with col_h1: st.image(LOGO_URL, width=80)
with col_h2: 
    st.title("Integral GIS Dashboard")
    st.markdown(f"Version: {SERIAL_NUMBER} | <span style='color:grey'>Marburg-Biedenkopf</span>", unsafe_allow_html=True)

st.markdown("---")

# --- SCHRITT-FÜR-SCHRITT ANLEITUNG ---
if not st.session_state.ort_sammlung:
    with st.container():
        st.markdown("<div class='step-box'>", unsafe_allow_html=True)
        st.subheader("💡 Anleitung")
        st.markdown("1. Fülle die Liste mit Straßen (Suchen oder TXT-Import).<br>2. Klicke auf '💾 Speichern & Bereinigen'.<br>3. Starte die Analyse.", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# --- TOP CONTROL PANEL ---
with st.container():
    c_col1, c_col2, c_col3, c_col4 = st.columns([2,2,1,1])
    
    with c_col1:
        query_input = st.text_input("📍 1. Straße suchen:", placeholder="Ringstr 10")
        if len(query_input) > 3:
            try:
                results = geolocator.geocode(f"{query_input}, Marburg-Biedenkopf", exactly_one=False, limit=5, timeout=5)
                if results:
                    st.session_state.suggestion_map = {r.address: r for r in results}
                    selected_address = st.selectbox("Auswahl:", list(st.session_state.suggestion_map.keys()), label_visibility="collapsed")
                else:
                    st.write("Keine Übereinstimmung.")
                    st.session_state.suggestion_map = {}
                    selected_address = None
            except: selected_address = None
        else: selected_address = None
        
        if st.button("➕ Hinzufügen", use_container_width=True):
            if selected_address and selected_address in st.session_state.suggestion_map:
                res = st.session_state.suggestion_map[selected_address]
                raw = res.raw.get('address', {})
                street_found = raw.get('road') or raw.get('pedestrian') or raw.get('cycleway') or selected_address.split(',')[0]
                hnr_found = raw.get('house_number', "")
                street_to_save = f"{street_found} | {hnr_found}".strip(" |")
                
                new_list = st.session_state.saved_manual_streets + [street_to_save]
                st.session_state.saved_manual_streets = save_streets(new_list)
                st.rerun()

    with c_col2:
        st.write("**📥 2. TXT-Import**")
        files = st.file_uploader("Datei hochladen", type=["txt"], accept_multiple_files=True, label_visibility="collapsed")
        if files:
            new_streets = []
            for f in files: 
                file_streets = [s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()]
                new_streets.extend(file_streets)
            
            new_list = st.session_state.saved_manual_streets + new_streets
            st.session_state.saved_manual_streets = save_streets(new_list)
            st.rerun()

    with c_col3:
        st.write("**🗑️ Cache**")
        if st.button("🗑️ Cache leeren", use_container_width=True):
            clear_all_caches()
            st.rerun()
        if st.button("📋 Leeren", use_container_width=True):
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.session_state.saved_manual_streets = []
            st.rerun()

    with c_col4:
        st.write("**🚀 Analyse**")
        if st.button("🚀 Start", type="primary", use_container_width=True):
            st.session_state.run_processing, st.session_state.stop_requested = True, False
            st.session_state.ort_sammlung, st.session_state.fehler_liste = None, []
            st.rerun()
        if st.button("🛑 Stop", type="secondary", use_container_width=True):
            st.session_state.stop_requested, st.session_state.run_processing = False, False
            st.rerun()

st.markdown("---")

# 4. VERARBEITUNG
if st.session_state.run_processing:
    strassen_liste = [s for s in st.session_state.saved_manual_streets if s]
    temp_ort, temp_err = defaultdict(list), []
    with st.spinner("🔍 Analysiere..."):
        pb = st.progress(0)
        total = len(strassen_liste)
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
            
            # Farbzuordnung nach der Verarbeitung (sortiert nach Name für Konsistenz)
            sorted_orts = sorted(st.session_state.ort_sammlung.keys())
            st.session_state.ort_colors = {ort: COLORS[i % len(COLORS)] for i, ort in enumerate(sorted_orts)}
            
            st.balloons()
        st.session_state.run_processing = False
        st.rerun()

# 5. ANZEIGE (ZWEISPALTIG)
if st.session_state.ort_sammlung:
    col_res1, col_res2 = st.columns([1, 2])
    
    with col_res1:
        st.subheader("📊 Ergebnisse")
        st.session_state.show_markers = st.checkbox("📍 Marker", value=st.session_state.show_markers)
        
        # Ortsteil Tabelle mit Farben
        res_data = []
        for ort, items in st.session_state.ort_sammlung.items():
            res_data.append({"Ortsteil": ort, "Anzahl": len(items), "Farbe": st.session_state.ort_colors.get(ort, "#FFFFFF")})
        
        # Einfache Anzeige der Farbe
        st.dataframe(pd.DataFrame(res_data), use_container_width=True, hide_index=True)

        # Downloads
        st.markdown("---")
        col_d1, col_d2 = st.columns(2)
        try:
            excel_data = create_excel_download(st.session_state.ort_sammlung)
            col_d1.download_button("📥 Excel", excel_data, file_name=f"Analyse.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        except: pass
        
        # HIER IST DER DOWNLOAD-BUTTON JETZT KORREKT PLATZIERT
        # m = folium.Map(...)  # <--- Das war der Fehler, 'm' existierte hier noch nicht

    with col_res2:
        # Karte
        m = folium.Map(location=[50.8, 8.8], zoom_start=11)
        all_geoms = []
        marker_fg = folium.FeatureGroup(name="📍 Marker")

        for ort, items in st.session_state.ort_sammlung.items():
            color = st.session_state.ort_colors.get(ort, "#FF0000")
            fg = folium.FeatureGroup(name=f"📍 {ort}")
            for item in items:
                all_geoms.append(item["gdf"])
                folium.GeoJson(item["gdf"].__geo_interface__,
                               style_function=lambda x, c=color: {'color': c, 'weight': 4, 'opacity': 0.8},
                               tooltip=f"{item['name']} ({ort})").add_to(fg)
                
                if item.get("marker") and st.session_state.show_markers:
                    folium.Marker(location=item["marker"], popup=f"{item['original']}", icon=folium.Icon(color="blue", icon="info-sign")).add_to(marker_fg)
            fg.add_to(m)
        
        if st.session_state.show_markers: marker_fg.add_to(m)
        folium.LayerControl(collapsed=False).add_to(m)
        
        if all_geoms:
            combined = gpd.GeoDataFrame(pd.concat(all_geoms))
            b = combined.total_bounds
            m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])
        
        components.html(m._repr_html_(), height=600)
        
        # Download-Button für HTML Karte hier platziert
        col_d2.download_button("📥 Map HTML", m._repr_html_(), file_name="Ergebnis.html", mime="text/html", use_container_width=True)

else:
    # --- INTERAKTIVE LISTE ---
    st.write(f"📝 **3. Liste ({len(st.session_state.saved_manual_streets)})**")
    
    df_streets = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])
    edited_df = st.data_editor(df_streets, num_rows="dynamic", use_container_width=True)
    
    col_l1, col_l2, col_l3 = st.columns(3)
    if col_l1.button("💾 Speichern & Bereinigen", use_container_width=True):
        st.session_state.saved_manual_streets = save_streets(edited_df["Adresse (Strasse | Nr)"].tolist())
        st.success("Gespeichert und sortiert!")
        st.rerun()
