import streamlit as st
import osmnx as ox
import folium
import io, re, os, random, time, tempfile, json
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components
from difflib import get_close_matches

# --- 1. SETUP & CONFIG ---
SERIAL_NUMBER = "SN-029-GOLD3001-CLEAN"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide", page_icon="🚀")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
VERIFIED_CACHE_FILE = os.path.join(BASE_DIR, ".verified_streets.json")
ORTSTEIL_CACHE_FILE = os.path.join(BASE_DIR, ".ortsteil_cache.json")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
geolocator = Nominatim(user_agent=f"integral_clean_v2_{random.randint(1000,9999)}", timeout=12)

# --- 2. PERSISTENZ-HELFER ---
def load_json_cache(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def save_json_cache(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def load_streets():
    if not os.path.exists(STREETS_FILE): return []
    try:
        with open(STREETS_FILE, "r", encoding="utf-8-sig") as f:
            return sorted(list(set([l.strip() for l in f.readlines() if l.strip()])))
    except: return []

def save_streets_safely(streets_list):
    try:
        unique_list = sorted(list(set([s.strip() for s in streets_list if s.strip()])))
        with tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8-sig', dir=BASE_DIR) as tf:
            tf.write("\n".join(unique_list))
            temp_name = tf.name
        os.replace(temp_name, STREETS_FILE)
    except Exception as e: st.error(f"Speicherfehler: {e}")

# --- 3. LOGIK-FUNKTIONEN ---
def intelligent_parse(line):
    line = line.strip()
    if " | " in line:
        parts = line.split(" | ")
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
    match = re.search(r"^(.*?)\s+(\d+[a-zA-Z]?)$", line)
    if match: return match.group(1).strip(), match.group(2).strip()
    return line, ""

def validate_with_cache(input_street, street_cache):
    low_name = input_street.lower().strip()
    if low_name in street_cache: return street_cache[low_name]
    matches = get_close_matches(low_name, street_cache.keys(), n=1, cutoff=0.9)
    if matches: return street_cache[matches[0]]
    try:
        query = f"{input_street}, Marburg-Biedenkopf"
        loc = geolocator.geocode(query, addressdetails=True)
        if loc:
            v_name = loc.raw.get('address', {}).get('road') or input_street
            street_cache[low_name] = v_name
            save_json_cache(VERIFIED_CACHE_FILE, street_cache)
            return v_name
    except: pass
    return input_street

# --- 4. SESSION STATE ---
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets()
if 'run_processing' not in st.session_state:
    st.session_state.run_processing = False
if 'stop_requested' not in st.session_state:
    st.session_state.stop_requested = False
if 'ort_sammlung' not in st.session_state:
    st.session_state.ort_sammlung = None

# --- 5. CALLBACKS (FÜR INSTANT START) ---
def start_analysis():
    if st.session_state.saved_manual_streets:
        st.session_state.run_processing = True
        st.session_state.stop_requested = False

def clear_list():
    st.session_state.saved_manual_streets = []
    save_streets_safely([])
    st.session_state.ort_sammlung = None
    st.session_state.run_processing = False

# --- 6. UI HEADER ---
st.title("🚀 INTEGRAL PRO")
st.markdown(f"**Status:** Marker entfernt | **Einträge:** {len(st.session_state.saved_manual_streets)}")

# --- 7. ANALYSE-ENGINE (VOR UI FÜR SCHNELLEN START) ---
if st.session_state.run_processing:
    st.divider()
    results = defaultdict(list)
    v_cache = load_json_cache(VERIFIED_CACHE_FILE)
    ort_cache = load_json_cache(ORTSTEIL_CACHE_FILE)
    s_list = st.session_state.saved_manual_streets
    total = len(s_list)
    
    col_stop, col_spin = st.columns([1, 4])
    with col_stop:
        if st.button("🛑 STOPP", type="primary", use_container_width=True): 
            st.session_state.run_processing = False
            st.session_state.stop_requested = True
            st.rerun()

    with col_spin:
        with st.spinner("🚀 Präzisions-Analyse..."):
            st_info = st.empty()
            for i, s in enumerate(s_list):
                if st.session_state.stop_requested: break
                start_t = time.time()
                st_info.markdown(f"#### 📍 `{s}` ({i+1}/{total})")
                
                raw_s, hnr = intelligent_parse(s)
                v_name = validate_with_cache(raw_s, v_cache)
                s_cl = re.sub(r'(?i)\bstr\b\.?', 'Straße', v_name).strip()
                
                try:
                    # Hoher Radius für komplette Straßenzüge
                    gdf = ox.features_from_address(f"{s_cl}, Marburg-Biedenkopf", tags={"highway": True}, dist=1600)
                    if not gdf.empty:
                        gdf = gdf[gdf['name'].str.contains(s_cl, case=False, na=False)].to_crs(epsg=4326)
                        if not gdf.empty:
                            cent = gdf.geometry.unary_union.centroid
                            ckey = f"{round(cent.y, 4)},{round(cent.x, 4)}"
                            
                            if ckey not in ort_cache:
                                try:
                                    rv = geolocator.reverse((cent.y, cent.x), language='de')
                                    addr = rv.raw.get('address', {})
                                    ort = addr.get('village') or addr.get('suburb') or addr.get('town') or "Unbekannt"
                                    ort_cache[ckey] = ort
                                    save_json_cache(ORTSTEIL_CACHE_FILE, ort_cache)
                                except: ort = "Marburg-Region"
                            else: ort = ort_cache[ckey]
                            
                            results[ort].append({"gdf": gdf, "name": s_cl, "orig": s})
                except: pass
                
                # Cache-Speed-Check
                if (time.time() - start_t) > 0.3: time.sleep(1.05)
            
            st.session_state.ort_sammlung = dict(results)
            st.session_state.run_processing = False
            if not st.session_state.stop_requested: st.balloons()
            st.rerun()

# --- 8. UI CONTROLS ---
with st.container(border=True):
    up = st.file_uploader("Texte importieren", type=["txt"], accept_multiple_files=True)
    if up:
        new_raw = []
        for f in up:
            new_raw.extend([l.strip() for l in f.getvalue().decode("utf-8-sig").splitlines() if l.strip()])
        if new_raw:
            st.session_state.saved_manual_streets = sorted(list(set(st.session_state.saved_manual_streets + new_raw)))
            save_streets_safely(st.session_state.saved_manual_streets)
            st.rerun()

    c_btn1, c_btn2 = st.columns(2)
    c_btn1.button("🗑️ Liste leeren", on_click=clear_list, use_container_width=True)
    c_btn2.button("🔥 ANALYSE STARTEN", type="primary", on_click=start_analysis, use_container_width=True)

# --- 9. OUTPUT (REINE STRASSENKARTE) ---
if st.session_state.ort_sammlung:
    st.divider()
    st.subheader("🗺️ Straßenkarte (Mouseover aktiv, ohne Marker)")
    
    # CartoDB Positron ist die sauberste Hintergrundkarte
    m = folium.Map(location=[50.81, 8.77], zoom_start=12, tiles="cartodbpositron")
    all_pts = []
    
    for ort, items in st.session_state.ort_sammlung.items():
        fg = folium.FeatureGroup(name=ort)
        color = "#%06x" % random.randint(0, 0xFFFFFF)
        for itm in items:
            # GEOMETRIE-MARKIERUNG
            folium.GeoJson(
                itm["gdf"].__geo_interface__,
                style_function=lambda x, c=color: {'color': c, 'weight': 7, 'opacity': 0.8},
                tooltip=f"Straße: {itm['name']} (Ortsteil: {ort})"
            ).add_to(fg)
            
            # Bounds berechnen
            for c in itm["gdf"].geometry.unary_union.envelope.exterior.coords:
                all_pts.append([c[1], c[0]])
                
        fg.add_to(m)
    
    if all_pts: m.fit_bounds(all_pts)
    folium.LayerControl().add_to(m)
    components.html(m._repr_html_(), height=700)
