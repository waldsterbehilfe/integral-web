import streamlit as st
import osmnx as ox
import folium
import re, os, random, time
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from geopy.geocoders import Nominatim
from difflib import SequenceMatcher
import streamlit.components.v1 as components

# --- 1. SETUP & CONFIG ---
SERIAL_NUMBER = "SN-029-GOLD3002"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
geolocator = Nominatim(user_agent=f"integral_pro_final_{random.randint(100,999)}", timeout=10)

# --- 2. HILFSFUNKTIONEN (VALIDIERUNG) ---
def check_similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def get_internet_verified(query):
    try:
        results = geolocator.geocode(f"{query}, Marburg-Biedenkopf", exactly_one=False, limit=3, addressdetails=True)
        if results:
            return [r.address.split(',')[0].strip() for r in results]
    except:
        pass
    return []

# --- 3. PERSISTENZ (TXT CACHE) ---
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

# --- 4. HEADER: H1 & LOGO (OHNE RAKETE) ---
header_col1, header_col2 = st.columns([1, 10])
with header_col1:
    # Platzhalter für das Integral-Logo
    st.markdown("<h3>∫</h3>", unsafe_allow_html=True) 
with header_col2:
    st.markdown("<h1>INTEGRAL PRO</h1>", unsafe_allow_html=True)
st.divider()

# --- 5. UI: INPUT MIT HYBRID-LOGIK (CACHE FIRST) ---
with st.container(border=True):
    col_in, col_list = st.columns([1, 1])
    with col_in:
        st.subheader("📥 Verifizierte Eingabe")
        m_s = st.text_input("Straßenname", key="m_s", placeholder="z.B. Hauptstr.")
        m_h = st.text_input("Hnr", key="m_h")
        
        if m_s:
            full_raw = f"{m_s} | {m_h}".strip(" |")
            if full_raw in st.session_state.saved_manual_streets:
                st.success("⚡ Treffer im lokalen Cache.")
            else:
                suggestions = get_internet_verified(m_s)
                if suggestions:
                    best = suggestions[0]
                    if check_similarity(m_s, best) >= 0.8:
                        st.info(f"💡 Vorschlag: **{best}**")
                        if st.button(f"'{best}' verifiziert speichern"):
                            full_v = f"{best} | {m_h}".strip(" |")
                            st.session_state.saved_manual_streets.append(full_v)
                            with open(STREETS_FILE, "w", encoding="utf-8") as f:
                                f.write("\n".join(st.session_state.saved_manual_streets))
                            st.rerun()
                    else:
                        st.warning("Unklar. Bitte wählen:")
                        for s in suggestions:
                            if st.button(f"Nutze: {s}", key=s):
                                full_v = f"{s} | {m_h}".strip(" |")
                                st.session_state.saved_manual_streets.append(full_v)
                                with open(STREETS_FILE, "w", encoding="utf-8") as f:
                                    f.write("\n".join(st.session_state.saved_manual_streets))
                                st.rerun()
                else:
                    st.error("❌ Straße im Internet unbekannt.")

    with col_list:
        st.subheader("📝 Verifizierter Cache")
        df = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Eintrag"])
        edited_df = st.data_editor(df, use_container_width=True, height=200)
        c_sv, c_cl = st.columns(2)
        if c_sv.button("💾 Liste korrigieren", use_container_width=True):
            st.session_state.saved_manual_streets = edited_df["Eintrag"].tolist()
            with open(STREETS_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(st.session_state.saved_manual_streets))
            st.rerun()
        if c_cl.button("🗑️ Cache leeren", use_container_width=True):
            st.session_state.saved_manual_streets = []
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.rerun()

# --- 6. STEUERUNG ---
st.divider()
c_go, c_st = st.columns(2)
if c_go.button("🔥 ANALYSE STARTEN", type="primary", use_container_width=True):
    st.session_state.run_processing = True
    st.rerun()
if c_st.button("🛑 ABBRUCH", type="secondary", use_container_width=True):
    st.session_state.run_processing = False
    st.rerun()

# --- 7. ANALYSE-ENGINE ---
if st.session_state.run_processing:
    results = defaultdict(list)
    s_list = st.session_state.saved_manual_streets
    with st.status("Suche Geometrien...", expanded=True) as status:
        p_bar = st.progress(0)
        for i, s in enumerate(s_list):
            try:
                s_name = s.split(" | ")[0]
                hnr = s.split(" | ")[1] if " | " in s else None
                s_cl = re.sub(r'(?i)\bstr\b\.?', 'Straße', s_name).strip()
                
                gdf = ox.features_from_address(f"{s_cl}, Marburg-Biedenkopf", tags={"highway": True}, dist=50)
                if not gdf.empty:
                    gdf = gdf[gdf['name'].str.contains(s_cl, case=False, na=False)].to_crs(epsg=4326)
                    if not gdf.empty:
                        m_pos = None
                        if hnr:
                            try:
                                l = geolocator.geocode(f"{s_cl} {hnr}, Marburg-Biedenkopf")
                                if l: m_pos = (l.latitude, l.longitude)
                            except: pass
                        cent = gdf.geometry.unary_union.centroid
                        rv = geolocator.reverse((cent.y, cent.x), language='de')
                        ort = rv.raw.get('address', {}).get('village') or \
                              rv.raw.get('address', {}).get('suburb') or "Marburg-Land"
                        results[ort].append({"gdf": gdf, "name": s_cl, "marker": m_pos})
            except: pass
            p_bar.progress((i + 1) / len(s_list))
            time.sleep(1.1)
        
        st.session_state.ort_sammlung = dict(results)
        st.session_state.run_processing = False
        status.update(label="Fertig!", state="complete")
        st.rerun()

# --- 8. KARTE (MOUSEOVER) ---
if st.session_state.ort_sammlung:
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
