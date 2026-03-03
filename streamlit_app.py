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
SERIAL_NUMBER = "SN-055" 

# --- 1. SETUP & THEME ---
st.set_page_config(page_title=f"INTEGRAL DASHBOARD {SERIAL_NUMBER}", layout="wide", page_icon="🌐")

LOGO_URL = "https://integral-online.de/images/integral-gmbh-logo.png"

# --- FIXES DUNKEL DESIGN ---
bg_color = "#0E1117"
text_color = "#FAFAFA"
box_bg = "#1E232B"
border_color = "#31333F"
accent_color = "#1E88E5" # Integral Blau für Dark

st.markdown(f"""
<style>
    .stApp {{background-color: {bg_color}; color: {text_color};}}
    .block-container {{padding-top: 1rem;}}
    h1, h2, h3 {{color: {accent_color} !important;}}
    .step-box {{background-color: {box_bg}; padding: 15px; border-radius: 5px; border: 1px solid {border_color}; margin-bottom: 15px;}}
    .stButton>button {{background-color: {accent_color}; color: white; border-radius: 5px;}}
    /* Spinner Farbe */
    .stSpinner > div > div {{border-top-color: {accent_color} !important;}}
</style>
""", unsafe_allow_html=True)

# Cache & Verzeichnisse
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "persistent_geocache")
os.makedirs(CACHE_DIR, exist_ok=True)
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR

STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=5)

COLORS = ['#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4', '#46f0f0', '#f032e6', '#bcf60c', '#fabebe', '#008080', '#e6beff', '#9a6324', '#fffac8', '#800000', '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080']

# --- HILFSFUNKTIONEN ---
def save_streets(streets_list):
    cleaned_list = sorted(list(set([s.strip() for s in streets_list if s.strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned_list))
    st.session_state.saved_manual_streets = cleaned_list
    return cleaned_list

def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return sorted(list(set([line.strip() for line in f.readlines() if line.strip()])))
    return []

def sync_editor():
    """Wird aufgerufen, wenn der Editor geändert wird"""
    if "streets_editor" in st.session_state:
        current_data = st.session_state["streets_editor"]["data"]["Adresse (Strasse | Nr)"].tolist()
        save_streets(current_data)

def clear_all_caches():
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR, exist_ok=True)
    ox.settings.use_cache = False
    ox.settings.use_cache = True
    st.cache_data.clear()
    st.cache_resource.clear()

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

# Session State
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'fehler_liste' not in st.session_state: st.session_state.fehler_liste = []
if 'run_processing' not in st.session_state: st.session_state.run_processing = False
if 'stop_requested' not in st.session_state: st.session_state.stop_requested = False
if 'saved_manual_streets' not in st.session_state: st.session_state.saved_manual_streets = load_streets()
if 'suggestion_map' not in st.session_state: st.session_state.suggestion_map = {}
if 'show_markers' not in st.session_state: st.session_state.show_markers = False
if 'ort_colors' not in st.session_state: st.session_state.ort_colors = {}

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
        if gdf.empty: return {"success": False, "original": strasse_input}
        gdf = gdf[gdf['name'].str.contains(re.escape(strasse_name), case=False, na=False)]
        if gdf.empty: return {"success": False, "original": strasse_input}

        marker_coords = None
        if hnr:
            loc = geolocator.geocode(f"{strasse_name} {hnr}, Marburg-Biedenkopf", timeout=5)
            if loc: marker_coords = (loc.latitude, loc.longitude)

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
        
        return {"gdf": gdf, "ort": ortsteil, "name": osm_name, "original": strasse_input, "marker": marker_coords, "success": True}
    except: return {"success": False, "original": strasse_input}

# --- UI LAYOUT ---
col_h1, col_h2 = st.columns([1, 10])
with col_h1: st.image(LOGO_URL, width=120)
with col_h2: 
    st.title("Integral GIS Dashboard")
    st.markdown(f"Version: {SERIAL_NUMBER} | <span style='color:grey'>Marburg-Biedenkopf</span>", unsafe_allow_html=True)

st.markdown("---")

if not st.session_state.ort_sammlung:
    with st.container():
        st.markdown("<div class='step-box'>", unsafe_allow_html=True)
        st.subheader("💡 Anleitung")
        st.markdown("1. Lade Liste hoch oder suche einzeln. <br> 2. Tabelle speichert Änderungen automatisch. <br> 3. Starte die Analyse.", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

with st.container():
    c_col1, c_col2, c_col3, c_col4 = st.columns([2,2,1,1])
    with c_col1:
        st.markdown("**📍 1. Suche**")
        query_input = st.text_input("Suche:", placeholder="Ringstr 10", label_visibility="collapsed")
        if len(query_input) > 3:
            try:
                results = geolocator.geocode(f"{query_input}, Marburg-Biedenkopf", exactly_one=False, limit=5, timeout=5)
                if results:
                    st.session_state.suggestion_map = {r.address: r for r in results}
                    selected_address = st.selectbox("Auswahl:", list(st.session_state.suggestion_map.keys()), label_visibility="collapsed")
                else: selected_address = None
            except: selected_address = None
        else: selected_address = None
        
        if st.button("➕ Hinzufügen", use_container_width=True):
            if selected_address:
                res = st.session_state.suggestion_map[selected_address]
                raw = res.raw.get('address', {})
                street_to_save = f"{raw.get('road', selected_address.split(',')[0])} | {raw.get('house_number', '')}".strip(" |")
                save_streets(st.session_state.saved_manual_streets + [street_to_save])
                st.rerun()

    with c_col2:
        st.write("**📥 2. TXT-Import**")
        uploaded_file = st.file_uploader("Datei hochladen", type=["txt"], label_visibility="collapsed")
        if uploaded_file:
            file_streets = [s.strip() for s in uploaded_file.getvalue().decode("utf-8").splitlines() if s.strip()]
            save_streets(st.session_state.saved_manual_streets + file_streets)
            st.rerun()

    with c_col3:
        st.write("**🗑️ Kontrolle**")
        if st.button("🗑️ Cache leeren", use_container_width=True): clear_all_caches(); st.rerun()
        if st.button("📋 Alles Löschen", use_container_width=True):
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.session_state.saved_manual_streets = []
            st.rerun()
        # --- NEU: ZURÜCKSETZEN ---
        if st.button("🔄 Zurücksetzen", use_container_width=True):
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.session_state.saved_manual_streets = []
            st.session_state.ort_sammlung = None
            st.rerun()

    with c_col4:
        st.write("**🚀 Analyse**")
        if st.button("🚀 Start", type="primary", use_container_width=True):
            st.session_state.run_processing, st.session_state.stop_requested = True, False
            st.rerun()
        if st.button("🛑 Stop", use_container_width=True):
            st.session_state.stop_requested = True; st.rerun()

st.markdown("---")

# Verarbeitung mit Spinner
if st.session_state.run_processing:
    temp_ort, temp_err = defaultdict(list), []
    
    # --- SPINNER UND FORTSCHRITT ---
    with st.spinner("🔍 Analysiere Daten... Bitte warten..."):
        pb = st.progress(0)
        total = len(st.session_state.saved_manual_streets)
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(verarbeite_strasse, s): s for s in st.session_state.saved_manual_streets}
            for i, future in enumerate(futures):
                if st.session_state.stop_requested: break
                res = future.result()
                if res.get("success"): temp_ort[res["ort"]].append(res)
                else: temp_err.append(res.get("original"))
                pb.progress((i + 1) / total)
        
        st.session_state.ort_sammlung = dict(temp_ort)
        sorted_orts = sorted(st.session_state.ort_sammlung.keys())
        st.session_state.ort_colors = {ort: COLORS[i % len(COLORS)] for i, ort in enumerate(sorted_orts)}
    
    st.session_state.run_processing = False
    
    # --- LUFTBALLONS ---
    st.balloons()
    st.rerun()

# Anzeige
if st.session_state.ort_sammlung:
    col_res1, col_res2 = st.columns([1, 2])
    with col_res1:
        st.subheader("📊 Ergebnisse")
        st.session_state.show_markers = st.checkbox("📍 Marker anzeigen", value=st.session_state.show_markers)
        res_data = [{"Ortsteil": o, "Anzahl": len(i), "Farbe": st.session_state.ort_colors.get(o)} for o, i in st.session_state.ort_sammlung.items()]
        st.dataframe(pd.DataFrame(res_data), use_container_width=True, hide_index=True)
        excel_data = create_excel_download(st.session_state.ort_sammlung)
        st.download_button("📥 Excel Export", excel_data, file_name="Analyse.xlsx", use_container_width=True)
        
    with col_res2:
        m = folium.Map(location=[50.8, 8.8], zoom_start=11)
        all_geoms = []
        for ort, items in st.session_state.ort_sammlung.items():
            color = st.session_state.ort_colors.get(ort, "#FF0000")
            for item in items:
                all_geoms.append(item["gdf"])
                folium.GeoJson(item["gdf"].__geo_interface__, style_function=lambda x, c=color: {'color': c, 'weight': 4}).add_to(m)
                if item.get("marker") and st.session_state.show_markers:
                    folium.Marker(location=item["marker"], popup=item["original"]).add_to(m)
        if all_geoms:
            b = gpd.GeoDataFrame(pd.concat(all_geoms)).total_bounds
            m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])
        components.html(m._repr_html_(), height=600)
        st.download_button("📥 Map HTML Export", m._repr_html_(), file_name="Karte.html", use_container_width=True)
else:
    st.write(f"📝 **3. Straßenliste ({len(st.session_state.saved_manual_streets)})**")
    df_streets = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])
    # Dateneditor mit korrekter Sync-Funktion
    st.data_editor(df_streets, num_rows="dynamic", use_container_width=True, key="streets_editor", on_change=sync_editor)
