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
from geopy.extra.rate_limiter import RateLimiter
import streamlit.components.v1 as components

# --- 1. SETUP & THEME (Fix auf Dunkel) ---
st.set_page_config(page_title="INTEGRAL PRO", layout="wide", page_icon="📈")

# Hintergrundbild Link (Raw)
GITHUB_BG_URL = 'https://raw.githubusercontent.com/waldsterbehilfe/integral-web/main/hintergrund.png'

# --- 2. LOGIK & CACHE ---
geolocator = Nominatim(user_agent="integral_pro_app")
reverse = RateLimiter(geolocator.reverse, min_delay_seconds=1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "persistent_geocache")
os.makedirs(CACHE_DIR, exist_ok=True)
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR

# --- THEME SWITCHER UI & CACHE BUTTON (Sidebar) ---
with st.sidebar:
    st.title("Einstellungen")
    bg_toggle = st.checkbox("Hintergrundbild", value=True)
    st.divider()
    st.subheader("Wartung")
    # NEU: Cache leeren Button
    if st.button("🗑️ Geocache leeren"):
        try:
            shutil.rmtree(CACHE_DIR)
            os.makedirs(CACHE_DIR, exist_ok=True)
            st.success("Cache wurde geleert!")
            st.rerun()
        except Exception as e:
            st.error(f"Fehler beim Leeren: {e}")
    st.divider()

# Hintergrundbild Logik via CSS
if bg_toggle:
    st.markdown(f"""
        <style>
            .stApp {{
                background-image: url('{GITHUB_BG_URL}');
                background-size: cover;
                background-attachment: fixed;
                background-color: #0E1117;
            }}
        </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <style>
            .stApp {
                background-image: none;
                background-color: #0E1117;
            }
        </style>
    """, unsafe_allow_html=True)

if 'run_processing' not in st.session_state: st.session_state.run_processing = False
if 'stop_requested' not in st.session_state: st.session_state.stop_requested = False

def get_random_color():
    return f"#{random.randint(0, 0xFFFFFF):06x}"

def verarbeite_strasse(strasse):
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    query = f"{s_clean}, Marburg-Biedenkopf"
    
    try:
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=500)
        
        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            if 'name' in gdf.columns:
                gdf_f = gdf[gdf['name'].str.contains(s_clean, case=False, na=False)]
            else:
                gdf_f = gdf

            if not gdf_f.empty:
                ortsteil = "Unbekannter_Ort"
                centroid = gdf_f.geometry.centroid.iloc[0]
                location = reverse((centroid.y, centroid.x), language='de')
                
                if location and 'address' in location.raw:
                    addr = location.raw['address']
                    for key in ['village', 'hamlet', 'suburb', 'city_district', 'town']:
                        if key in addr:
                            ortsteil = addr[key]
                            break
                
                return {"gdf": gdf_f, "ort": ortsteil, "name": s_clean, "success": True}
    except Exception as e:
        return {"success": False, "original": strasse, "error": str(e)}
        
    return {"success": False, "original": strasse}

# --- 3. UI ---
col_logo, col_title = st.columns([1, 10])
with col_logo:
    st.image("https://integral-online.de/images/integral-gmbh-logo.png", width=120)
with col_title:
    st.title("INTEGRAL PRO")
    st.markdown("Automatisierte Sortierung — **V5.0 (mit Cache-Button)**")

st.divider()

col_in1, col_in2 = st.columns(2)
with col_in1:
    uploaded_files = st.file_uploader("Dateien laden (.txt)", type=["txt"], accept_multiple_files=True)
with col_in2:
    manual_input = st.text_area("Manuelle Eingabe", placeholder="z.B. Schweinsberger Str", height=126)

strassen_liste = []
if uploaded_files:
    for f in uploaded_files:
        strassen_liste.extend([s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()])
if manual_input:
    strassen_liste.extend([s.strip() for s in manual_input.splitlines() if s.strip()])
strassen_liste = list(dict.fromkeys(strassen_liste))

# Buttons
col_btn1, col_btn2, _ = st.columns([1, 1, 3])
if col_btn1.button("🚀 Analyse starten", type="primary"):
    st.session_state.run_processing = True
    st.session_state.stop_requested = False
if col_btn2.button("🛑 Abbruch", type="secondary"):
    st.session_state.stop_requested = True

# --- 4. VERARBEITUNG ---
if st.session_state.run_processing and strassen_liste:
    ort_sammlung = defaultdict(list)
    fehler_liste = []
    all_geoms = [] 
    
    prog_bar = st.progress(0)
    status_text = st.empty()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(verarbeite_strasse, s): s for s in strassen_liste}
        for i, future in enumerate(futures):
            if st.session_state.stop_requested:
                status_text.warning("⏹️ Verarbeitung gestoppt.")
                break
            
            res = future.result()
            if res["success"]:
                ort_sammlung[res["ort"]].append(res)
                all_geoms.append(res["gdf"])
            else:
                fehler_liste.append(res["original"])
            
            prog_bar.progress((i + 1) / len(strassen_liste))
            status_text.text(f"🔍 {res.get('name', res.get('original'))} ({i+1}/{len(strassen_liste)})")

    # --- 5. ERGEBNIS-GENERIERUNG & ANZEIGE ---
    if ort_sammlung and not st.session_state.stop_requested:
        m = folium.Map(location=[50.8, 8.8], zoom_start=11, control_scale=True)
        
        for ort in sorted(ort_sammlung.keys()):
            color = get_random_color()
            fg = folium.FeatureGroup(name=f"📍 {ort} ({len(ort_sammlung[ort])} Str.)")
            
            for item in ort_sammlung[ort]:
                # Robustes GeoJSON Rendering
                gdf = item["gdf"]
                if not gdf.empty:
                    # Umwandlung für Folium Kompatibilität
                    geojson_data = gdf.__geo_interface__
                    
                    folium.GeoJson(
                        geojson_data,
                        style_function=lambda x, c=color: {'color': c, 'weight': 6, 'opacity': 0.8},
                        tooltip=folium.GeoJsonTooltip(fields=['name'], aliases=['Straße:']),
                        popup=folium.GeoJsonPopup(fields=['name'], aliases=['Name:'])
                    ).add_to(fg)
            fg.add_to(m)
        
        folium.LayerControl(collapsed=False).add_to(m)
        
        if all_geoms:
            combined = gpd.GeoDataFrame(pd.concat(all_geoms))
            b = combined.total_bounds 
            m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])

        st.success(f"✅ Fertig! {len(ort_sammlung)} Ortsteile/Ebenen erkannt.")
        
        # --- DIREKTE ANZEIGE ---
        st.subheader("Interaktive Karte")
        try:
            html_string = m._repr_html_()
            components.html(html_string, height=600)
            
            # Optionaler Download
            st.download_button(
                label="📥 Karte als HTML Datei herunterladen",
                data=html_string,
                file_name=f"INTEGRAL_Master_{datetime.now().strftime('%H%M')}.html",
                mime="text/html"
            )
        except Exception as e:
            st.error(f"Fehler beim Rendern der Karte: {e}")

    if fehler_liste and not st.session_state.stop_requested:
        with st.expander("⚠️ Nicht gefundene Straßen"):
            st.write(", ".join(fehler_liste))

    st.session_state.run_processing = False
    st.session_state.stop_requested = False
