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

# --- 1. SETUP & THEME ---
st.set_page_config(page_title="INTEGRAL PRO", layout="wide", page_icon="📈")

LOGO_URL = "https://integral-online.de/images/integral-gmbh-logo.png"

# Cache & Verzeichnisse
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "persistent_geocache")
os.makedirs(CACHE_DIR, exist_ok=True)
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR

geolocator = Nominatim(user_agent="integral_pro_v66_form")

# Session State
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'fehler_liste' not in st.session_state: st.session_state.fehler_liste = []
if 'run_processing' not in st.session_state: st.session_state.run_processing = False
if 'stop_requested' not in st.session_state: st.session_state.stop_requested = False
if 'manual_text' not in st.session_state: st.session_state.manual_text = ""

# --- SIDEBAR ---
with st.sidebar:
    st.title("Einstellungen")
    st.divider()
    selected_colors = {}
    if st.session_state.ort_sammlung:
        st.subheader("🎨 Ebenen-Farben")
        for ort in sorted(st.session_state.ort_sammlung.keys()):
            selected_colors[ort] = st.color_picker(f"{ort}", "#FF0000", key=f"cp_{ort}")
    st.divider()
    if st.button("🗑️ Geocache leeren", use_container_width=True):
        shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR, exist_ok=True)
        st.rerun()

# Hintergrundfarbe
st.markdown("<style>.stApp {background-color: #0E1117;}</style>", unsafe_allow_html=True)

# --- FUNKTION (MIT HAUSNUMMERN-SUPPORT) ---
def verarbeite_strasse(strasse):
    if not strasse: return {"success": False}
    
    # Hausnummer-Erkennung
    hnr = None
    hnr_match = re.search(r'\s(\d+[a-zA-Z]?)', strasse)
    if hnr_match:
        hnr = hnr_match.group(1)
        strasse_name = strasse.replace(hnr_match.group(0), '').strip()
    else:
        strasse_name = strasse.strip()

    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse_name).strip()
    query = f"{s_clean}, Marburg-Biedenkopf"
    
    try:
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=100)
        if not gdf.empty and 'name' in gdf.columns:
            gdf = gdf[gdf['name'].str.contains(s_clean.split()[0], case=False, na=False)]

        marker_coords = None
        if hnr and not gdf.empty:
            loc = geolocator.geocode(f"{s_clean} {hnr}, Marburg-Biedenkopf", timeout=5)
            if loc:
                marker_coords = (loc.latitude, loc.longitude)

        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
            osm_name = gdf['name'].iloc[0] if 'name' in gdf.columns else s_clean
            
            ortsteil = "Unbekannt"
            if 'is_in:suburb' in gdf.columns: ortsteil = gdf['is_in:suburb'].iloc[0]
            elif 'is_in:village' in gdf.columns: ortsteil = gdf['is_in:village'].iloc[0]
            
            if ortsteil == "Unbekannt":
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
                "original": strasse, 
                "marker": marker_coords, 
                "success": True
            }
    except:
        pass
    return {"success": False, "original": strasse}

# --- 3. UI ---
col_logo, col_title = st.columns([1, 10])
with col_logo: st.image(LOGO_URL, width=120)
with col_title:
    st.title("INTEGRAL PRO")
    st.markdown("Automatisierte Sortierung — **V6.6 (Form Input Fix)**")

st.divider()

# --- NEUE EINGABE-LOGIK MIT FORM ---
col_in1, col_in2 = st.columns(2)
with col_in1: 
    files = st.file_uploader("TXT Dateien", type=["txt"], accept_multiple_files=True)
    
    st.subheader("🔍 Straßensuche")
    # Formular zur sicheren Eingabe
    with st.form("search_form"):
        query_input = st.text_input("Straße", placeholder="Name eingeben...", label_visibility="collapsed")
        submit_button = st.form_submit_button("➕ Hinzufügen")
        
        if submit_button and query_input:
            with st.spinner("Suche..."):
                try:
                    results = geolocator.geocode(f"{query_input}, Marburg-Biedenkopf", exactly_one=True, timeout=5)
                    if results:
                        st.session_state.manual_text += f"{results.address.split(',')[0]}\n"
                        st.success(f"Gefunden: {results.address.split(',')[0]}")
                    else:
                        st.warning("Nicht gefunden.")
                except:
                    st.error("Fehler bei der Suche.")

with col_in2: 
    st.subheader("📝 Eingabeliste")
    # Das Textfeld wird nun über eine Variable befüllt
    st.text_area("Straßenliste", 
                 value=st.session_state.manual_text,
                 height=200,
                 disabled=True,
                 key="display_text_area")

strassen_liste = []
if files:
    for f in files: strassen_liste.extend([s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()])
if st.session_state.manual_text: 
    strassen_liste.extend([s.strip() for s in st.session_state.manual_text.splitlines() if s.strip()])
strassen_liste = list(dict.fromkeys(strassen_liste))

col_btn1, col_btn2, _ = st.columns([1, 1, 3])

if col_btn1.button("🚀 Analyse starten", type="primary"):
    st.session_state.run_processing, st.session_state.stop_requested = True, False
    st.session_state.ort_sammlung, st.session_state.fehler_liste = None, []

if col_btn2.button("🛑 Abbruch", type="secondary"):
    st.session_state.stop_requested, st.session_state.run_processing = True, False
    st.session_state.manual_text = "" 
    st.rerun()

# --- 4. VERARBEITUNG ---
if st.session_state.run_processing and strassen_liste:
    temp_ort, temp_err = defaultdict(list), []
    pb = st.progress(0)
    st_text = st.empty()
    total = len(strassen_liste)
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(verarbeite_strasse, s): s for s in strassen_liste}
        for i, future in enumerate(futures):
            if st.session_state.stop_requested: break
            res = future.result()
            if res.get("success"):
                temp_ort[res["ort"]].append(res)
            else:
                temp_err.append(res.get("original", "Unbekannt"))
            
            pb.progress((i + 1) / total)
            st_text.text(f"🔍 Prüfe: {i+1} von {total} — {res.get('name', 'Suche...')}")

    if not st.session_state.stop_requested:
        st.session_state.ort_sammlung, st.session_state.fehler_liste = dict(temp_ort), temp_err
        st.balloons()
    st.session_state.run_processing = False
    st.rerun()

# --- 5. ANZEIGE ---
if st.session_state.ort_sammlung:
    if st.session_state.fehler_liste:
        with st.expander("⚠️ Nicht gefunden"):
            st.write(", ".join(st.session_state.fehler_liste))

    m = folium.Map(location=[50.8, 8.8], zoom_start=11)
    all_geoms = []
    
    marker_fg = folium.FeatureGroup(name="📍 Hausnummern-Marker")

    for ort, items in st.session_state.ort_sammlung.items():
        color = selected_colors.get(ort, "#FF0000")
        fg = folium.FeatureGroup(name=f"📍 {ort} ({len(items)} Str.)")
        for item in items:
            all_geoms.append(item["gdf"])
            folium.GeoJson(item["gdf"].__geo_interface__,
                           style_function=lambda x, c=color: {'color': c, 'weight': 6, 'opacity': 0.8},
                           tooltip=f"Gefunden: {item['name']}").add_to(fg)
            
            if item.get("marker"):
                folium.Marker(
                    location=item["marker"],
                    popup=f"Hausnummer: {item['original']}",
                    icon=folium.Icon(color="blue", icon="info-sign")
                ).add_to(marker_fg)
                
        fg.add_to(m)
    
    marker_fg.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    
    if all_geoms:
        combined = gpd.GeoDataFrame(pd.concat(all_geoms))
        b = combined.total_bounds
        m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])

    components.html(m._repr_html_(), height=700)
    st.download_button("📥 Karte speichern", m._repr_html_(), file_name="Ergebnis.html", mime="text/html")
