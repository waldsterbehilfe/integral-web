import streamlit as st
import osmnx as ox
import folium
import io, re, os, random, time
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components

# --- 1. SETUP & CONFIG ---
SERIAL_NUMBER = "SN-029-GOLD3002-VAL"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
geolocator = Nominatim(user_agent=f"integral_pro_v5_{random.randint(100,999)}", timeout=10)

# --- 2. HILFSFUNKTIONEN (ERWEITERT) ---
def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return sorted(list(set([line.strip() for line in f.readlines() if line.strip()])))
    return []

def save_streets(streets_list):
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(list(set(streets_list)))))

def intelligent_parse(line):
    line = line.strip()
    if " | " in line:
        parts = line.split(" | ")
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
    match = re.search(r"^(.*?)\s+(\d+[a-zA-Z]?)$", line)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return line, ""

# --- NEU: VALIDIERUNGS-LOGIK ---
def validate_street_smart(input_street, cache_list):
    # 1. Direkter Cache-Match (Groß/Kleinschreibung ignorieren)
    input_clean = input_street.lower().replace("str.", "straße").strip()
    for entry in cache_list:
        cached_name = entry.split(" | ")[0]
        if input_clean == cached_name.lower().replace("str.", "straße").strip():
            return cached_name
    
    # 2. Internet-Validierung falls nicht im Cache
    try:
        query = f"{input_street}, Marburg-Biedenkopf"
        location = geolocator.geocode(query, addressdetails=True)
        if location:
            # Extrahiere den exakten Straßennamen aus den Adressdetails
            address = location.raw.get('address', {})
            verified_name = address.get('road') or address.get('pedestrian') or input_street
            return verified_name
    except:
        pass
    return input_street

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
    st.session_state.saved_manual_streets = updated
    save_streets(updated)
    st.rerun()

# --- 5. UI: INPUT ---
st.title("🚀 INTEGRAL PRO")
st.info(f"**Datenstand:** {len(st.session_state.saved_manual_streets)} verifizierte/bekannte Einträge.")

with st.container(border=True):
    col_in, col_list = st.columns([1, 1])
    with col_in:
        st.subheader("📥 Dateneingabe")
        c1, c2 = st.columns([3, 1])
        m_s = c1.text_input("Straße", key="m_s")
        m_h = c2.text_input("Hnr", key="m_h")
        
        if st.button("✅ Hinzufügen", use_container_width=True):
            if m_s:
                full_entry = f"{m_s} | {m_h}".strip(" |")
                if full_entry not in st.session_state.saved_manual_streets:
                    st.session_state.saved_manual_streets.append(full_entry)
                    save_streets(st.session_state.saved_manual_streets)
                st.rerun()

    with col_list:
        st.subheader("📝 Lokale Liste")
        df_list = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Eintrag"])
        edited_df = st.data_editor(df_list, use_container_width=True, num_rows="dynamic", height=200)
        c_sv, c_cl = st.columns(2)
        if c_sv.button("💾 Liste Speichern", use_container_width=True):
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
if c_go.button("🔥 ANALYSE & VALIDIERUNG STARTEN", type="primary", use_container_width=True):
    st.session_state.run_processing = True
    st.session_state.stop_requested = False
    st.rerun()
if c_st.button("🛑 ABBRUCH", type="secondary", use_container_width=True):
    st.session_state.stop_requested = True
    st.session_state.run_processing = False
    st.rerun()

# --- 7. ANALYSE-ENGINE (MIT SMART-VALIDIERUNG) ---
if st.session_state.run_processing:
    results = defaultdict(list)
    ort_cache = {}
    s_list = st.session_state.saved_manual_streets
    updated_cache = False
    
    with st.status("Validierung und Analyse...", expanded=True) as status:
        p_bar = st.progress(0)
        for i, s in enumerate(s_list):
            if st.session_state.stop_requested: break
            
            raw_s, hnr = intelligent_parse(s)
            
            # --- SCHRITT 1: SMARTE VALIDIERUNG ---
            # Sucht im Cache oder Internet und korrigiert Namen
            v_name = validate_street_smart(raw_s, st.session_state.saved_manual_streets)
            
            # Wenn korrigiert wurde, Cache-Eintrag aktualisieren
            if v_name != raw_s:
                st.session_state.saved_manual_streets[i] = f"{v_name} | {hnr}".strip(" |")
                updated_cache = True
            
            s_cl = re.sub(r'(?i)\bstr\b\.?', 'Straße', v_name).strip()
            
            # --- SCHRITT 2: GEOMETRIE & KARTIERUNG ---
            try:
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
                        coord_key = f"{round(cent.y, 3)},{round(cent.x, 3)}"
                        if coord_key in ort_cache:
                            ort = ort_cache[coord_key]
                        else:
                            try:
                                rv = geolocator.reverse((cent.y, cent.x), language='de')
                                addr = rv.raw.get('address', {})
                                ort = addr.get('village') or addr.get('suburb') or addr.get('town') or "Marburg-Land"
                                ort_cache[coord_key] = ort
                            except: ort = "Unbekannt"
                        
                        results[ort].append({"gdf": gdf, "name": s_cl, "marker": m_pos, "orig": s})
            except: pass
            
            p_bar.progress((i + 1) / len(s_list))
            time.sleep(1.0) # API-Richtlinie
        
        if updated_cache:
            save_streets(st.session_state.saved_manual_streets)
            
        st.session_state.ort_sammlung = dict(results)
        st.session_state.run_processing = False
        status.update(label="Fertig!", state="complete")
        st.rerun()

# --- 8. KARTE & EXPORT ---
if st.session_state.ort_sammlung:
    df_export = pd.DataFrame([{"Ortsteil": k, "Straße": i["name"], "Eintrag": i["orig"]} 
                             for k, v in st.session_state.ort_sammlung.items() for i in v])
    st.download_button("📥 Ergebnisse als CSV speichern", df_export.to_csv(index=False).encode('utf-8'), "ergebnisse.csv", use_container_width=True)

    m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
    all_bounds = []
    for ort, items in st.session_state.ort_sammlung.items():
        fg = folium.FeatureGroup(name=ort)
        color = "#%06x" % random.randint(0, 0xFFFFFF)
        for itm in items:
            folium.GeoJson(itm["gdf"].__geo_interface__, 
                           style_function=lambda x, c=color: {'color': c, 'weight': 6, 'opacity': 0.7},
                           tooltip=f"{itm['name']} ({ort})").add_to(fg)
            for coord in itm["gdf"].geometry.unary_union.envelope.exterior.coords:
                all_bounds.append([coord[1], coord[0]])
            if itm["marker"]:
                folium.Marker(itm["marker"], icon=folium.Icon(color="red")).add_to(fg)
                all_bounds.append(itm["marker"])
        fg.add_to(m)
    
    if all_bounds: m.fit_bounds(all_bounds)
    folium.LayerControl().add_to(m)
    components.html(m._repr_html_(), height=600)
