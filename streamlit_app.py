import streamlit as st
import osmnx as ox
import folium
import io, re, os, random, shutil
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components

# --- 1. SETUP & THEME ---
st.set_page_config(page_title="INTEGRAL PRO GOLD", layout="wide", page_icon="📈")

LOGO_URL = "https://integral-online.de/images/integral-gmbh-logo.png"

# Cache & Verzeichnisse
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "persistent_geocache")
os.makedirs(CACHE_DIR, exist_ok=True)
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR

# --- DATEI FÜR MANUELLE LISTEN ---
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
geolocator = Nominatim(user_agent="integral_pro_v89_local")

# --- HILFSFUNKTIONEN ---
def save_streets(streets_list):
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(streets_list))

def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return sorted(list(set([line.strip() for line in f.readlines() if line.strip()])))
    return []

# Session State Initialisierung
if 'saved_manual_streets' not in st.session_state: 
    st.session_state.saved_manual_streets = load_streets()
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'fehler_liste' not in st.session_state: st.session_state.fehler_liste = []
if 'run_processing' not in st.session_state: st.session_state.run_processing = False

# --- SIDEBAR ---
with st.sidebar:
    st.image(LOGO_URL, width=150)
    st.title("Einstellungen")
    selected_colors = {}
    if st.session_state.ort_sammlung:
        st.subheader("🎨 Farben pro Ortsteil")
        for ort in sorted(st.session_state.ort_sammlung.keys()):
            selected_colors[ort] = st.color_picker(f"{ort}", "#FF0000", key=f"cp_{ort}")
    
    st.divider()
    if st.button("🗑️ Liste & Cache leeren", use_container_width=True):
        if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
        st.session_state.saved_manual_streets = []
        st.rerun()

# --- FUNKTION VERARBEITUNG ---
def verarbeite_strasse(strasse):
    if not strasse: return {"success": False}
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
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=150)
        marker_coords = None
        if hnr and not gdf.empty:
            loc = geolocator.geocode(f"{s_clean} {hnr}, Marburg-Biedenkopf", timeout=5)
            if loc: marker_coords = (loc.latitude, loc.longitude)

        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
            ortsteil = "Unbekannt"
            try:
                centroid = gdf.geometry.unary_union.centroid
                loc_rev = geolocator.reverse((centroid.y, centroid.x), language='de', timeout=3)
                if loc_rev and 'address' in loc_rev.raw:
                    a = loc_rev.raw['address']
                    ortsteil = a.get('village') or a.get('suburb') or a.get('hamlet') or a.get('town') or "Unbekannt"
            except: pass
            
            return {"gdf": gdf, "ort": ortsteil, "name": s_clean, "original": strasse, "marker": marker_coords, "success": True}
    except: pass
    return {"success": False, "original": strasse}

# --- UI HAUPTBEREICH ---
st.title("🚀 INTEGRAL PRO — Lokale Analyse")

c1, c2 = st.columns([1, 1])

with c2:
    st.subheader("📝 Zentrale Eingabeliste")
    input_text = st.text_area("Straßen hier einpflegen (Eine pro Zeile):", 
                              value="\n".join(st.session_state.saved_manual_streets), 
                              height=300,
                              help="Änderungen werden sofort für die Suche und Analyse übernommen.")
    
    # Live-Synchronisierung
    current_list = [s.strip() for s in input_text.splitlines() if s.strip()]
    if current_list != st.session_state.saved_manual_streets:
        st.session_state.saved_manual_streets = current_list
        save_streets(current_list)

with c1:
    st.subheader("🔍 Lokale Suche")
    search_q = st.text_input("In der Liste oben suchen:", placeholder="Tippe Straßennamen...")
    
    if search_q:
        results = [s for s in st.session_state.saved_manual_streets if search_q.lower() in s.lower()]
        if results:
            st.success(f"{len(results)} Treffer gefunden:")
            for r in results[:8]: 
                st.markdown(f"📍 **{r}**")
        else:
            st.error("Kein Treffer in der aktuellen Liste.")
    else:
        st.info(f"Die Liste enthält aktuell {len(st.session_state.saved_manual_streets)} Adressen.")

st.divider()

# --- ANALYSE STARTEN ---
if st.button("🔥 ANALYSE STARTEN", type="primary", use_container_width=True):
    if not st.session_state.saved_manual_streets:
        st.warning("Liste ist leer!")
    else:
        st.session_state.run_processing = True

if st.session_state.run_processing:
    temp_ort, temp_err = defaultdict(list), []
    pb = st.progress(0)
    st_status = st.empty()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(verarbeite_strasse, s): s for s in st.session_state.saved_manual_streets}
        for i, future in enumerate(futures):
            res = future.result()
            if res.get("success"):
                temp_ort[res["ort"]].append(res)
            else:
                temp_err.append(res.get("original", "Unbekannt"))
            pb.progress((i + 1) / len(futures))
            st_status.text(f"Verarbeite: {res.get('original')}")

    st.session_state.ort_sammlung = dict(temp_ort)
    st.session_state.fehler_liste = temp_err
    st.session_state.run_processing = False
    st.rerun()

# --- KARTE ---
if st.session_state.ort_sammlung:
    st.subheader("🗺️ Interaktive Karte")
    m = folium.Map(location=[50.8, 8.8], zoom_start=12)
    
    all_geoms = []
    for ort, items in st.session_state.ort_sammlung.items():
        color = selected_colors.get(ort, "#3178C6")
        fg = folium.FeatureGroup(name=f"{ort} ({len(items)})")
        for item in items:
            all_geoms.append(item["gdf"])
            folium.GeoJson(item["gdf"].__geo_interface__,
                           style_function=lambda x, c=color: {'color': c, 'weight': 5, 'opacity': 0.7},
                           tooltip=item['name']).add_to(fg)
            if item.get("marker"):
                folium.CircleMarker(location=item["marker"], radius=5, color="red", fill=True, popup=item["original"]).add_to(fg)
        fg.add_to(m)
    
    folium.LayerControl().add_to(m)
    if all_geoms:
        combined = gpd.GeoDataFrame(pd.concat(all_geoms))
        b = combined.total_bounds
        m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])
    
    components.html(m._repr_html_(), height=600)
