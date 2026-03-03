import streamlit as st
import osmnx as ox
import folium
import io, re, os, random, time, tempfile
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components

# --- 1. SETUP & CONFIG ---
SERIAL_NUMBER = "SN-029-GOLD3002-LIVE"
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREETS_FILE = os.path.join(BASE_DIR, ".manual_streets.txt")
CACHE_DIR = os.path.join(BASE_DIR, "osmnx_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR
geolocator = Nominatim(user_agent=f"integral_pro_live_{random.randint(1000,9999)}", timeout=12)

# --- 2. ROBUSTE PERSISTENZ ---
def load_streets():
    if not os.path.exists(STREETS_FILE):
        return []
    try:
        with open(STREETS_FILE, "r", encoding="utf-8-sig") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            return sorted(list(set(lines)))
    except Exception as e:
        st.error(f"Fehler beim Laden: {e}")
        return []

def save_streets_safely(streets_list):
    unique_streets = sorted(list(set([s.strip() for s in streets_list if s.strip()])))
    try:
        with tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8-sig', dir=BASE_DIR) as tf:
            tf.write("\n".join(unique_streets))
            temp_name = tf.name
        if os.path.exists(STREETS_FILE):
            os.replace(temp_name, STREETS_FILE)
        else:
            os.rename(temp_name, STREETS_FILE)
    except Exception as e:
        st.error(f"Kritischer Fehler beim Speichern: {e}")

# --- 3. LOGIK-FUNKTIONEN ---
def intelligent_parse(line):
    line = line.strip()
    if " | " in line:
        parts = line.split(" | ")
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
    match = re.search(r"^(.*?)\s+(\d+[a-zA-Z]?)$", line)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return line, ""

def validate_street_smart(input_street, cache_list):
    input_norm = input_street.lower().replace("str.", "straße").strip()
    for entry in cache_list:
        cached_name = entry.split(" | ")[0]
        if input_norm == cached_name.lower().replace("str.", "straße").strip():
            return cached_name
    try:
        query = f"{input_street}, Marburg-Biedenkopf"
        location = geolocator.geocode(query, addressdetails=True)
        if location:
            addr = location.raw.get('address', {})
            return addr.get('road') or addr.get('pedestrian') or input_street
    except:
        time.sleep(1)
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

# --- 5. UI: IMPORT & INPUT ---
st.title("🚀 INTEGRAL PRO")
st.caption(f"Status: {SERIAL_NUMBER} | Geladen: {len(st.session_state.saved_manual_streets)} Einträge")

# Der Uploader wurde nach oben geschoben für sofortige Reaktion
with st.expander("📥 Daten importieren / hinzufügen", expanded=True):
    up = st.file_uploader("*.txt Dateien auswählen", type=["txt"], accept_multiple_files=True, key="file_up")
    
    # Sofortige Verarbeitung bei Upload
    if up:
        new_entries = []
        for f in up:
            # Buffer auslesen und decodieren
            content = f.getvalue().decode("utf-8-sig", errors="ignore").splitlines()
            for l in content:
                if l.strip():
                    s_name, h_num = intelligent_parse(l)
                    new_entries.append(f"{s_name} | {h_num}".strip(" |"))
        
        if new_entries:
            # Dubletten vermeiden und mit bestehender Liste mischen
            current_list = st.session_state.saved_manual_streets
            combined = list(set(current_list + new_entries))
            st.session_state.saved_manual_streets = sorted(combined)
            save_streets_safely(st.session_state.saved_manual_streets)
            # WICHTIG: Sofortiger Rerun für die Anzeige
            st.rerun()

    c1, c2, c3 = st.columns([3, 1, 1])
    m_s = c1.text_input("Straße", key="manual_s")
    m_h = c2.text_input("Hnr", key="manual_h")
    if c3.button("Hinzufügen", use_container_width=True):
        if m_s:
            entry = f"{m_s} | {m_h}".strip(" |")
            if entry not in st.session_state.saved_manual_streets:
                st.session_state.saved_manual_streets.append(entry)
                save_streets_safely(st.session_state.saved_manual_streets)
                st.rerun()

# --- 6. LISTE & STEUERUNG ---
with st.container(border=True):
    # Tabelle greift direkt auf den aktuellen session_state zu
    df_list = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Eintrag"])
    ed_df = st.data_editor(df_list, use_container_width=True, num_rows="dynamic", height=250, key="editor")
    
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    if col_btn1.button("💾 Liste sichern", use_container_width=True):
        st.session_state.saved_manual_streets = ed_df["Eintrag"].tolist()
        save_streets_safely(st.session_state.saved_manual_streets)
        st.rerun()
    if col_btn2.button("🗑️ Liste leeren", use_container_width=True):
        st.session_state.saved_manual_streets = []
        save_streets_safely([])
        st.rerun()
    if col_btn3.button("🔥 ANALYSE STARTEN", type="primary", use_container_width=True):
        st.session_state.run_processing = True
        st.session_state.stop_requested = False
        st.rerun()

# --- 7. ANALYSE-ENGINE ---
if st.session_state.run_processing:
    results = defaultdict(list)
    ort_cache = {}
    s_list = st.session_state.saved_manual_streets
    updated_any = False
    
    if st.button("🛑 ANALYSE ABBRECHEN", use_container_width=True):
        st.session_state.stop_requested = True

    with st.status("Verarbeitung läuft...", expanded=True) as status:
        p_bar = st.progress(0)
        for i, s in enumerate(s_list):
            if st.session_state.stop_requested: break
            
            raw_s, hnr = intelligent_parse(s)
            v_name = validate_street_smart(raw_s, st.session_state.saved_manual_streets)
            
            if v_name != raw_s:
                st.session_state.saved_manual_streets[i] = f"{v_name} | {hnr}".strip(" |")
                updated_any = True
            
            s_cl = re.sub(r'(?i)\bstr\b\.?', 'Straße', v_name).strip()
            
            try:
                gdf = ox.features_from_address(f"{s_cl}, Marburg-Biedenkopf", tags={"highway": True}, dist=60)
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
                        ckey = f"{round(cent.y, 3)},{round(cent.x, 3)}"
                        if ckey in ort_cache:
                            ort = ort_cache[ckey]
                        else:
                            rv = geolocator.reverse((cent.y, cent.x), language='de')
                            addr = rv.raw.get('address', {})
                            ort = addr.get('village') or addr.get('suburb') or addr.get('town') or "Landkreis"
                            ort_cache[ckey] = ort
                        
                        results[ort].append({"gdf": gdf, "name": s_cl, "marker": m_pos, "orig": s})
            except: pass
            
            p_bar.progress((i + 1) / len(s_list))
            time.sleep(1.1)
        
        if updated_any:
            save_streets_safely(st.session_state.saved_manual_streets)
        
        st.session_state.ort_sammlung = dict(results)
        st.session_state.run_processing = False
        status.update(label="Analyse beendet!", state="complete")
        st.rerun()

# --- 8. AUSGABE ---
if st.session_state.ort_sammlung:
    st.divider()
    exp_df = pd.DataFrame([{"Ortsteil": k, "Straße": i["name"], "Quelle": i["orig"]} 
                          for k, v in st.session_state.ort_sammlung.items() for i in v])
    st.download_button("📥 Ergebnisse (CSV) exportieren", exp_df.to_csv(index=False).encode('utf-8-sig'), "marker_export.csv", use_container_width=True)

    m = folium.Map(location=[50.8, 8.8], zoom_start=11, tiles="cartodbpositron")
    all_pts = []
    for ort, items in st.session_state.ort_sammlung.items():
        fg = folium.FeatureGroup(name=ort)
        clr = "#%06x" % random.randint(0, 0xFFFFFF)
        for itm in items:
            folium.GeoJson(itm["gdf"].__geo_interface__, style_function=lambda x, c=clr: {'color': c, 'weight': 6, 'opacity': 0.8}, tooltip=f"{itm['name']}").add_to(fg)
            for c in itm["gdf"].geometry.unary_union.envelope.exterior.coords: all_pts.append([c[1], c[0]])
            if itm["marker"]:
                folium.Marker(itm["marker"], icon=folium.Icon(color="red", icon="info-sign")).add_to(fg)
                all_pts.append(itm["marker"])
        fg.add_to(m)
    
    if all_pts: m.fit_bounds(all_pts)
    folium.LayerControl().add_to(m)
    components.html(m._repr_html_(), height=600)
