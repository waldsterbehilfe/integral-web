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
SERIAL_NUMBER = "SN-029-GOLD3002-ULTIMATE"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
VERIFIED_CACHE_FILE = os.path.join(BASE_DIR, ".verified_streets.json")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
geolocator = Nominatim(user_agent=f"integral_ultimate_{random.randint(1000,9999)}", timeout=12)

# --- 2. PERSISTENZ & CACHE LOGIK ---
def load_streets():
    if not os.path.exists(STREETS_FILE): return []
    try:
        with open(STREETS_FILE, "r", encoding="utf-8-sig") as f:
            return sorted(list(set([l.strip() for l in f.readlines() if l.strip()])))
    except: return []

def save_streets_safely(streets_list):
    try:
        with tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8-sig', dir=BASE_DIR) as tf:
            tf.write("\n".join(sorted(list(set(streets_list)))))
            temp_name = tf.name
        os.replace(temp_name, STREETS_FILE)
    except Exception as e: st.error(f"Fehler: {e}")

def load_verified_cache():
    if os.path.exists(VERIFIED_CACHE_FILE):
        with open(VERIFIED_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_to_verified_cache(raw_name, verified_name):
    cache = load_verified_cache()
    cache[raw_name.lower()] = verified_name
    with open(VERIFIED_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=4)

# --- 3. LOGIK-FUNKTIONEN ---
def intelligent_parse(line):
    line = line.strip()
    if " | " in line:
        parts = line.split(" | ")
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
    match = re.search(r"^(.*?)\s+(\d+[a-zA-Z]?)$", line)
    if match: return match.group(1).strip(), match.group(2).strip()
    return line, ""

def validate_at_start(input_street, street_cache):
    """Prüft beim Start erst im Cache, dann im Netz."""
    low_name = input_street.lower().strip()
    
    # 1. Direkter Cache Match
    if low_name in street_cache:
        return street_cache[low_name]
    
    # 2. Fuzzy Match (Ähnlichkeit im Cache suchen)
    matches = get_close_matches(low_name, street_cache.keys(), n=1, cutoff=0.85)
    if matches:
        return street_cache[matches[0]]
    
    # 3. Internet Validierung
    try:
        query = f"{input_street}, Marburg-Biedenkopf"
        loc = geolocator.geocode(query, addressdetails=True)
        if loc:
            v_name = loc.raw.get('address', {}).get('road') or input_street
            save_to_verified_cache(input_street, v_name)
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

# --- 5. UI: IMPORT & INPUT (WIE GEWÜNSCHT) ---
st.title("🚀 INTEGRAL PRO")
st.caption(f"Status: {SERIAL_NUMBER} | Lokaler Datenstamm: {len(st.session_state.saved_manual_streets)}")

with st.expander("📥 Daten importieren / hinzufügen", expanded=True):
    up = st.file_uploader("*.txt Dateien", type=["txt"], accept_multiple_files=True)
    if up:
        new_raw = []
        for f in up:
            lines = f.getvalue().decode("utf-8-sig", errors="ignore").splitlines()
            new_raw.extend([l.strip() for l in lines if l.strip()])
        if new_raw:
            st.session_state.saved_manual_streets = sorted(list(set(st.session_state.saved_manual_streets + new_raw)))
            save_streets_safely(st.session_state.saved_manual_streets)
            st.rerun()

    c1, c2, c3 = st.columns([3, 1, 1])
    m_s = c1.text_input("Straße")
    m_h = c2.text_input("Hnr")
    if c3.button("Hinzufügen", use_container_width=True):
        if m_s:
            st.session_state.saved_manual_streets.append(f"{m_s} | {m_h}".strip(" |"))
            save_streets_safely(st.session_state.saved_manual_streets)
            st.rerun()

# --- 6. LISTE & STEUERUNG ---
with st.container(border=True):
    df_disp = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Eintrag"])
    ed_key = f"ed_{len(st.session_state.saved_manual_streets)}"
    ed_df = st.data_editor(df_disp, use_container_width=True, num_rows="dynamic", height=250, key=ed_key)
    
    col_b1, col_b2, col_b3 = st.columns(3)
    if col_b1.button("💾 Liste sichern", use_container_width=True):
        st.session_state.saved_manual_streets = sorted(list(set(ed_df["Eintrag"].tolist())))
        save_streets_safely(st.session_state.saved_manual_streets)
        st.rerun()
    if col_b2.button("🗑️ Liste leeren", use_container_width=True):
        st.session_state.saved_manual_streets = []
        save_streets_safely([])
        st.rerun()
    if col_b3.button("🔥 ANALYSE STARTEN", type="primary", use_container_width=True):
        st.session_state.run_processing = True
        st.session_state.stop_requested = False
        st.rerun()

# --- 7. ANALYSE-ENGINE (MIT OPTION 1) ---
if st.session_state.run_processing:
    results = defaultdict(list)
    v_cache = load_verified_cache()
    ort_cache = {}
    s_list = st.session_state.saved_manual_streets
    
    if st.button("🛑 STOP"): st.session_state.stop_requested = True

    with st.status("Validierung & Analyse läuft...", expanded=True) as status:
        p_bar = st.progress(0)
        for i, s in enumerate(s_list):
            if st.session_state.stop_requested: break
            
            # --- OPTION 1: Validierung erst hier beim Start ---
            raw_s, hnr = intelligent_parse(s)
            v_name = validate_at_start(raw_s, v_cache)
            s_cl = re.sub(r'(?i)\bstr\b\.?', 'Straße', v_name).strip()
            
            try:
                gdf = ox.features_from_address(f"{s_cl}, Marburg-Biedenkopf", tags={"highway": True}, dist=60)
                if not gdf.empty:
                    gdf = gdf[gdf['name'].str.contains(s_cl, case=False, na=False)].to_crs(epsg=4326)
                    if not gdf.empty:
                        m_pos = None
                        if hnr:
                            l = geolocator.geocode(f"{s_cl} {hnr}, Marburg-Biedenkopf")
                            if l: m_pos = (l.latitude, l.longitude)
                        
                        cent = gdf.geometry.unary_union.centroid
                        ckey = f"{round(cent.y, 3)},{round(cent.x, 3)}"
                        if ckey in ort_cache:
                            ort = ort_cache[ckey]
                        else:
                            rv = geolocator.reverse((cent.y, cent.x), language='de')
                            addr = rv.raw.get('address', {})
                            ort = addr.get('village') or addr.get('suburb') or addr.get('town') or "Marburg"
                            ort_cache[ckey] = ort
                        
                        results[ort].append({"gdf": gdf, "name": s_cl, "marker": m_pos, "orig": s})
            except: pass
            p_bar.progress((i + 1) / len(s_list))
            time.sleep(1.1)
        
        st.session_state.ort_sammlung = dict(results)
        st.session_state.run_processing = False
        status.update(label="Analyse beendet!", state="complete")
        st.rerun()

# --- 8. AUSGABE & STATISTIK (OPTION 2) ---
if st.session_state.ort_sammlung:
    st.divider()
    
    # Option 2: Statistik-Bereich
    st.subheader("📊 Ortsteil-Verteilung")
    stat_data = []
    for ort, items in st.session_state.ort_sammlung.items():
        stat_data.append({"Ortsteil": ort, "Anzahl Straßen": len(items)})
    st.dataframe(pd.DataFrame(stat_data), use_container_width=True)

    exp_df = pd.DataFrame([{"Ortsteil": k, "Straße": i["name"], "Marker": "Ja" if i["marker"] else "Nein"} 
                          for k, v in st.session_state.ort_sammlung.items() for i in v])
    st.download_button("📥 CSV Export", exp_df.to_csv(index=False).encode('utf-8-sig'), "ergebnisse.csv", use_container_width=True)

    m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
    all_pts = []
    for ort, items in st.session_state.ort_sammlung.items():
        fg = folium.FeatureGroup(name=ort)
        clr = "#%06x" % random.randint(0, 0xFFFFFF)
        for itm in items:
            folium.GeoJson(itm["gdf"].__geo_interface__, style_function=lambda x, c=clr: {'color': c, 'weight': 6, 'opacity': 0.8}, tooltip=itm["name"]).add_to(fg)
            for c in itm["gdf"].geometry.unary_union.envelope.exterior.coords: all_pts.append([c[1], c[0]])
            if itm["marker"]:
                folium.Marker(itm["marker"], icon=folium.Icon(color="red")).add_to(fg)
                all_pts.append(itm["marker"])
        fg.add_to(m)
    
    if all_pts: m.fit_bounds(all_pts)
    folium.LayerControl().add_to(m)
    components.html(m._repr_html_(), height=600)
