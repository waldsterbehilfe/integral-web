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
SERIAL_NUMBER = "SN-029" 

# --- 1. SETUP & THEME ---
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide", page_icon="📈")

# OPTISCHE BERUHIGUNG VIA CSS
st.markdown("""
<style>
    .stApp {background-color: #0E1117;}
    [data-testid="stHeader"] {background: rgba(0,0,0,0);}
    .stTabs [data-baseweb="tab-list"] {gap: 24px;}
    .stTabs [data-baseweb="tab"] {height: 50px; white-space: pre-wrap; background-color: #161B22; border-radius: 5px 5px 0 0; padding: 10px;}
    div.stButton > button {width: 100%; border-radius: 5px; height: 3em; transition: all 0.3s;}
    div[data-testid="stExpander"] {border: 1px solid #30363d; border-radius: 8px;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    .stDataFrame {border: 1px solid #30363d; border-radius: 8px;}
</style>
""", unsafe_allow_html=True)

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
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=10)

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
if 'online_suggestions' not in st.session_state: st.session_state.online_suggestions = []

# --- FUNKTION (MIT STRIKTER FILTERUNG) ---
def verarbeite_strasse(strasse_input):
    if not strasse_input: return {"success": False}
    time.sleep(random.uniform(1.0, 1.8))
    if " | " in strasse_input:
        parts = strasse_input.split(" | ")
        strasse_name = parts[0].strip()
        hnr = parts[1].strip()
    else:
        strasse_name = strasse_input.strip()
        hnr = None
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse_name).strip()
    query = f"{s_clean}, Marburg-Biedenkopf"
    try:
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=30)
        if gdf.empty: return {"success": False, "original": strasse_input}
        gdf = gdf[gdf['name'].str.contains(s_clean, case=False, na=False)]
        if gdf.empty: return {"success": False, "original": strasse_input}
        marker_coords = None
        if hnr:
            loc = geolocator.geocode(f"{s_clean} {hnr}, Marburg-Biedenkopf", timeout=10)
            if loc: marker_coords = (loc.latitude, loc.longitude)
        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
        osm_name = gdf['name'].iloc[0] if 'name' in gdf.columns else s_clean
        ortsteil = "Unbekannt"
        if 'is_in:suburb' in gdf.columns: ortsteil = gdf['is_in:suburb'].iloc[0]
        elif 'is_in:village' in gdf.columns: ortsteil = gdf['is_in:village'].iloc[0]
        if ortsteil == "Unbekannt" or pd.isna(ortsteil):
            try:
                centroid = gdf.geometry.unary_union.centroid
                loc_rev = geolocator.reverse((centroid.y, centroid.x), language='de', timeout=3)
                if loc_rev and 'address' in loc_rev.raw:
                    a = loc_rev.raw['address']
                    ortsteil = a.get('village') or a.get('suburb') or a.get('hamlet') or a.get('town') or "Unbekannt"
            except: pass
        return {"gdf": gdf, "ort": ortsteil, "name": osm_name, "original": strasse_input, "marker": marker_coords, "success": True}
    except: pass
    return {"success": False, "original": strasse_input}

# --- 3. UI ---
col_logo, col_title = st.columns([1, 10])
with col_logo: st.image(LOGO_URL, width=100)
with col_title:
    st.title("INTEGRAL PRO")
    st.caption(f"Status: Confirmed {SERIAL_NUMBER} | System: Marburg-Biedenkopf")

st.divider()

# --- EINSTELLUNGEN ---
with st.expander("⚙️ System-Steuerung & Farben", expanded=False):
    col_set1, col_set2 = st.columns([2, 1])
    with col_set1:
        st.write("**Ebenen-Farben**")
        selected_colors = {}
        if st.session_state.ort_sammlung:
            c_cols = st.columns(3)
            for i, ort in enumerate(sorted(st.session_state.ort_sammlung.keys())):
                with c_cols[i % 3]:
                    selected_colors[ort] = st.color_picker(f"{ort}", "#FF0000", key=f"cp_{ort}")
        else:
            st.info("Nach der ersten Analyse erscheinen hier die Ortsteile.")
    with col_set2:
        st.write("**Wartung**")
        if st.button("📋 Liste leeren"):
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.session_state.saved_manual_streets = []
            st.rerun()
        if st.button("🗑️ Cache leeren"):
            clear_all_caches()
            st.rerun()

# --- EINGABE ---
st.subheader("📥 Daten-Management")
col_in1, col_in2 = st.columns(2)

with col_in1:
    with st.container(border=True):
        st.markdown("**Datei-Upload & Suche**")
        files = st.file_uploader("TXT Dateien importieren", type=["txt"], accept_multiple_files=True, label_visibility="collapsed")
        if files:
            new_streets = []
            for f in files: 
                file_streets = [s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()]
                new_streets.extend(file_streets)
            merged = list(set(st.session_state.saved_manual_streets + new_streets))
            if len(merged) > len(st.session_state.saved_manual_streets):
                st.session_state.saved_manual_streets = merged
                save_streets(st.session_state.saved_manual_streets)
                st.rerun()
        
        st.divider()
        c_str, c_hnr = st.columns([3, 1])
        with c_str: q_street = st.text_input("Straße suchen:", placeholder="Am Markt")
        with c_hnr: q_hnr = st.text_input("Haus-Nr:", placeholder="1")
        
        c_query = f"{q_street} {q_hnr}".strip()
        selected_suggestion = None
        if len(q_street) > 2:
            try:
                results = geolocator.geocode(f"{c_query}, Marburg-Biedenkopf", exactly_one=False, limit=8)
                if results:
                    st.session_state.online_suggestions = [r.address for r in results]
                    selected_suggestion = st.selectbox("Ergebnisse:", st.session_state.online_suggestions)
                else: st.caption("Keine Treffer.")
            except: pass

        if st.button("➕ Hinzufügen") and selected_suggestion:
            addr_part = selected_suggestion.split(',')[0].strip()
            final_name = addr_part.replace(q_hnr, "").strip() if q_hnr in addr_part else addr_part
            entry = f"{final_name} | {q_hnr}".strip(" |")
            if entry not in st.session_state.saved_manual_streets:
                st.session_state.saved_manual_streets.append(entry)
                save_streets(st.session_state.saved_manual_streets)
                st.rerun()

with col_in2:
    with st.container(border=True):
        st.markdown(f"**Aktuelle Liste ({len(st.session_state.saved_manual_streets)})**")
        df_list = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Straße | Hausnummer"])
        st.dataframe(df_list, use_container_width=True, height=235)
        if st.button("🔄 Liste aktualisieren"):
            st.session_state.saved_manual_streets = load_streets()
            st.rerun()

# --- AKTIONEN ---
st.divider()
c_btn1, c_btn2, c_excel = st.columns([1, 1, 2])
with c_btn1:
    if st.button("🚀 ANALYSE STARTEN", type="primary"):
        st.session_state.run_processing, st.session_state.stop_requested = True, False
        st.session_state.ort_sammlung, st.session_state.fehler_liste = None, []
with c_btn2:
    if st.button("🛑 ABBRUCH"):
        st.session_state.stop_requested, st.session_state.run_processing = False, False
        st.rerun()

# --- VERARBEITUNG ---
if st.session_state.run_processing:
    t_ort, t_err = defaultdict(list), []
    with st.status("Verarbeite Daten...", expanded=True) as status:
        pb = st.progress(0)
        txt = st.empty()
        s_list = [s for s in st.session_state.saved_manual_streets if s]
        total = len(s_list)
        with ThreadPoolExecutor(max_workers=1) as exe:
            futs = {exe.submit(verarbeite_strasse, s): s for s in s_list}
            for i, f in enumerate(futs):
                if st.session_state.stop_requested: break
                r = f.result()
                if r.get("success"): t_ort[r["ort"]].append(r)
                else: t_err.append(r.get("original", "Unbekannt"))
                pb.progress((i + 1) / total)
                txt.caption(f"Prüfe: {r.get('name', '...')}")
        status.update(label="Analyse abgeschlossen!", state="complete")
    
    if not st.session_state.stop_requested:
        st.session_state.ort_sammlung, st.session_state.fehler_liste = dict(t_ort), t_err
        st.balloons()
    st.session_state.run_processing = False
    st.rerun()

# --- AUSGABE ---
if st.session_state.ort_sammlung:
    if st.session_state.fehler_liste:
        with st.expander("⚠️ Nicht gefundene Einträge"):
            st.write(", ".join(st.session_state.fehler_liste))

    m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
    all_geoms = []
    marker_fg = folium.FeatureGroup(name="📍 Details")

    for ort, items in st.session_state.ort_sammlung.items():
        color = selected_colors.get(ort, "#FF0000")
        fg = folium.FeatureGroup(name=f"📍 {ort}")
        for item in items:
            all_geoms.append(item["gdf"])
            folium.GeoJson(item["gdf"].__geo_interface__,
                           style_function=lambda x, c=color: {'color': c, 'weight': 6, 'opacity': 0.7},
                           tooltip=f"{item['name']}").add_to(fg)
            if item.get("marker"):
                folium.Marker(location=item["marker"], popup=f"{item['original']}", icon=folium.Icon(color="blue", icon="info-sign")).add_to(marker_fg)
        fg.add_to(m)
    
    marker_fg.add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    
    if all_geoms:
        combined = gpd.GeoDataFrame(pd.concat(all_geoms))
        b = combined.total_bounds
        m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])

    st.subheader("🗺️ Ergebnis-Karte")
    components.html(m._repr_html_(), height=600)
    
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        try:
            excel_data = create_excel_download(st.session_state.ort_sammlung)
            st.download_button("📥 Excel-Liste", excel_data, file_name=f"Analyse.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except: st.error("Fehler beim Excel-Export.")
    with col_dl2:
        st.download_button("📥 Karte (HTML)", m._repr_html_(), file_name="Ergebnis.html", mime="text/html")import streamlit as st
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

# --- 1. SETUP & DYNAMISCHE SERIENNUMMER ---
# Jeder Start erhält eine eigene ID basierend auf Datum/Uhrzeit
SERIAL_NUMBER = f"GOLD-{datetime.now().strftime('%Y%m%d-%H%M')}"

st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

# Optische Anpassung
st.markdown("""
<style>
    .stApp {background-color: #0E1117;}
    div.stButton > button {width: 100%; border-radius: 5px; font-weight: bold;}
    div[data-testid="stExpander"] {border: 1px solid #30363d; border-radius: 8px;}
    .stDataFrame {border: 1px solid #30363d; border-radius: 8px;}
</style>
""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=10)

# --- 2. HILFSFUNKTIONEN ---
def save_streets(streets_list):
    clean = sorted(list(set([s.strip() for s in streets_list if s.strip()])))
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(clean))
    return clean

def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return sorted([line.strip() for line in f.readlines() if line.strip()])
    return []

# Session State Initialisierung
if 'saved_manual_streets' not in st.session_state:
    st.session_state.saved_manual_streets = load_streets()
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'run_processing' not in st.session_state: st.session_state.run_processing = False

# --- 3. VERARBEITUNG (STRIKTES MATCHING) ---
def verarbeite_strasse(strasse_input):
    if not strasse_input: return {"success": False}
    time.sleep(1.1)
    parts = strasse_input.split(" | ") if " | " in strasse_input else [strasse_input, None]
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', parts[0].strip()).strip()
    
    try:
        # Suche im 50m Umkreis für Präzision
        gdf = ox.features_from_address(f"{s_clean}, Marburg-Biedenkopf", tags={"highway": True}, dist=50)
        if gdf.empty: return {"success": False, "original": strasse_input}
        
        # FIX: Nur exakte Übereinstimmung (verhindert "zu viel markieren")
        gdf = gdf[gdf['name'].apply(lambda x: str(x).strip().lower() == s_clean.lower())]
        if gdf.empty: return {"success": False, "original": strasse_input}
        
        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
        centroid = gdf.geometry.unary_union.centroid
        loc_rev = geolocator.reverse((centroid.y, centroid.x), language='de')
        ort = loc_rev.raw.get('address', {}).get('village', "Marburg")
        
        marker_coords = None
        if parts[1]:
            l = geolocator.geocode(f"{s_clean} {parts[1].strip()}, Marburg-Biedenkopf")
            if l: marker_coords = (l.latitude, l.longitude)
            
        return {"gdf": gdf, "ort": ort, "name": s_clean, "original": strasse_input, "marker": marker_coords, "success": True}
    except: return {"success": False, "original": strasse_input}

# --- 4. UI ---
st.title("🚀 INTEGRAL PRO")
st.caption(f"Sitzung: **{SERIAL_NUMBER}** | System bereit.")

col_in1, col_in2 = st.columns(2)

with col_in1:
    with st.container(border=True):
        st.subheader("📥 Daten-Import")
        
        # UPLOAD LOGIK (FUNKTIONIEREND)
        files = st.file_uploader("TXT Dateien importieren", type=["txt"], accept_multiple_files=True)
        if files:
            new_streets = []
            for f in files:
                lines = [s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()]
                new_streets.extend(lines)
            
            # Update & Sofort-Rerun
            st.session_state.saved_manual_streets = save_streets(st.session_state.saved_manual_streets + new_streets)
            st.rerun()
            
        st.divider()
        c_str, c_hnr = st.columns([3, 1])
        q_s = c_str.text_input("Straße:")
        q_h = c_hnr.text_input("Hnr:")
        if st.button("➕ Hinzufügen"):
            if q_s:
                entry = f"{q_s} | {q_h}" if q_h else q_s
                st.session_state.saved_manual_streets = save_streets(st.session_state.saved_manual_streets + [entry])
                st.rerun()

with col_in2:
    with st.container(border=True):
        st.subheader("📝 Aktuelle Liste")
        st.dataframe(st.session_state.saved_manual_streets, use_container_width=True, height=250)
        if st.button("🗑️ Liste leeren"):
            st.session_state.saved_manual_streets = []
            if os.path.exists(STREETS_FILE): os.remove(STREETS_FILE)
            st.rerun()

st.divider()

if st.button("🔥 ANALYSE STARTEN", type="primary"):
    st.session_state.run_processing = True

# --- 5. VERARBEITUNG ---
if st.session_state.run_processing and st.session_state.saved_manual_streets:
    temp_ort = defaultdict(list)
    total = len(st.session_state.saved_manual_streets)
    pb = st.progress(0)
    msg = st.empty()
    
    with ThreadPoolExecutor(max_workers=1) as exe:
        futs = {exe.submit(verarbeite_strasse, s): s for s in st.session_state.saved_manual_streets}
        for i, f in enumerate(futs):
            res = f.result()
            msg.markdown(f"🔍 **Suche {i+1} von {total}:** `{res.get('original')}`")
            pb.progress((i + 1) / total)
            if res.get("success"):
                temp_ort[res["ort"]].append(res)
    
    st.session_state.ort_sammlung = dict(temp_ort)
    st.session_state.run_processing = False
    st.rerun()

# --- 6. KARTE ---
if st.session_state.ort_sammlung:
    m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
    for ort, items in st.session_state.ort_sammlung.items():
        fg = folium.FeatureGroup(name=ort)
        color = "#%06x" % random.randint(0, 0xFFFFFF)
        for itm in items:
            folium.GeoJson(itm["gdf"].__geo_interface__, 
                           style_function=lambda x, c=color: {'color': c, 'weight': 5, 'opacity': 0.7}).add_to(fg)
            if itm["marker"]:
                folium.Marker(itm["marker"], popup=itm["original"]).add_to(fg)
        fg.add_to(m)
    folium.LayerControl().add_to(m)
    components.html(m._repr_html_(), height=600)

