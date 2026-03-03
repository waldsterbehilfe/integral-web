import streamlit as st
import osmnx as ox
import folium
import io, re, os, random
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components
import time

# --- 1. SETUP & CONFIG ---
SERIAL_NUMBER = "SN-029-GOLD3002"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
# User-Agent leicht variiert für bessere API-Akzeptanz
geolocator = Nominatim(user_agent=f"integral_pro_v3_{random.randint(100,999)}", timeout=10)

# --- 2. PERSISTENZ ---
def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    return []

def save_streets(streets_list):
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(streets_list))

# --- 3. SESSION STATE ---
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets()
if 'run_processing' not in st.session_state:
    st.session_state.run_processing = False
if 'stop_requested' not in st.session_state:
    st.session_state.stop_requested = False
if 'ort_sammlung' not in st.session_state:
    st.session_state.ort_sammlung = None

# --- 4. IMPORT-TRIGGER ---
uploaded_files = st.file_uploader("*.txt Datei für Sofort-Import", type=["txt"], accept_multiple_files=True)
if uploaded_files:
    new_data = []
    for f in uploaded_files:
        lines = f.getvalue().decode("utf-8").splitlines()
        new_data.extend([l.strip() for l in lines if l.strip()])
    updated = sorted(list(set(st.session_state.saved_manual_streets + new_data)))
    if len(updated) > len(st.session_state.saved_manual_streets):
        st.session_state.saved_manual_streets = updated
        save_streets(updated)
        st.rerun()

# --- 5. UI: INPUT MIT ANTI-CRASH PRÜFUNG ---
st.title("🚀 INTEGRAL PRO")
st.info(f"**Lokaler Cache:** {len(st.session_state.saved_manual_streets)} bekannte Einträge.")

with st.container(border=True):
    col_in, col_list = st.columns([1, 1])
    with col_in:
        st.subheader("📥 Dateneingabe")
        c1, c2 = st.columns([3, 1])
        m_s = c1.text_input("Straße", key="m_s", placeholder="z.B. Frankfurter Str.")
        m_h = c2.text_input("Hnr", key="m_h", placeholder="1")
        
        if st.button("✅ Hinzufügen / Prüfen", use_container_width=True):
            if m_s:
                full_entry = f"{m_s} | {m_h}".strip(" |")
                if full_entry in st.session_state.saved_manual_streets:
                    st.success("Bereits im Cache.")
                else:
                    try:
                        with st.spinner("Prüfe Straße..."):
                            test_loc = geolocator.geocode(f"{m_s}, Marburg-Biedenkopf")
                            if test_loc:
                                st.session_state.saved_manual_streets.append(full_entry)
                                save_streets(st.session_state.saved_manual_streets)
                                st.rerun()
                            else:
                                st.error("Straße nicht gefunden.")
                    except Exception:
                        st.warning("Dienst antwortet nicht. Speichere trotzdem...")
                        st.session_state.saved_manual_streets.append(full_entry)
                        save_streets(st.session_state.saved_manual_streets)
                        st.rerun()

    with col_list:
        st.subheader("📝 Lokale Liste")
        df = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Eintrag"])
        edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic", height=200)
        c_sv, c_cl = st.columns(2)
        if c_sv.button("💾 Speichern", use_container_width=True):
            st.session_state.saved_manual_streets = edited_df["Eintrag"].tolist()
            save_streets(st.session_state.saved_manual_streets)
            st.rerun()
        if c_cl.button("🗑️ Leeren", use_container_width=True):
            st.session_state.saved_manual_streets = []
            save_streets([])
            st.rerun()

# --- 6. STEUERUNG ---
st.divider()
c_go, c_st = st.columns(2)
if c_go.button("🔥 ANALYSE STARTEN", type="primary", use_container_width=True):
    st.session_state.run_processing = True
    st.session_state.stop_requested = False
    st.rerun()
if c_st.button("🛑 ABBRUCH", type="secondary", use_container_width=True):
    st.session_state.stop_requested = True
    st.session_state.run_processing = False
    st.rerun()

# --- 7. ANALYSE-ENGINE (ROBUST) ---
if st.session_state.run_processing:
    results = defaultdict(list)
    s_list = st.session_state.saved_manual_streets
    with st.status("Analysiere Geodaten...", expanded=True) as status:
        p_bar = st.progress(0)
        for i, s in enumerate(s_list):
            if st.session_state.stop_requested: break
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
                        try:
                            rv = geolocator.reverse((cent.y, cent.x), language='de')
                            ort = rv.raw.get('address', {}).get('village') or \
                                  rv.raw.get('address', {}).get('suburb') or "Marburg-Land"
                        except: ort = "Unbekannt"
                        
                        results[ort].append({"gdf": gdf, "name": s_cl, "marker": m_pos, "orig": s})
            except Exception: pass # Fehler bei einzelner Straße ignorieren
            p_bar.progress((i + 1) / len(s_list))
            time.sleep(1.1)
        
        st.session_state.ort_sammlung = dict(results)
        st.session_state.run_processing = False
        status.update(label="Analyse abgeschlossen!", state="complete")
        st.rerun()

# --- 8. KARTE ---
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
