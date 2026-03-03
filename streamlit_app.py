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
SERIAL_NUMBER = "SN-022" 

# --- 1. SETUP & THEME ---
st.set_page_config(page_title=f"INTEGRAL PRO {SERIAL_NUMBER}", layout="wide", page_icon="📈")

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
geolocator = Nominatim(user_agent=f"integral_pro_{SERIAL_NUMBER}", timeout=5)

# --- HILFSFUNKTIONEN FÜR DATEI-ZUGRIFF ---
def save_streets(streets_list):
    with open(STREETS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(streets_list))

def load_streets():
    if os.path.exists(STREETS_FILE):
        with open(STREETS_FILE, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    return []

# --- HILFSFUNKTION FÜR EXCEL-EXPORT ---
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

# Session State - Initialisierung
if 'ort_sammlung' not in st.session_state: st.session_state.ort_sammlung = None
if 'fehler_liste' not in st.session_state: st.session_state.fehler_liste = []
if 'run_processing' not in st.session_state: st.session_state.run_processing = False
if 'stop_requested' not in st.session_state: st.session_state.stop_requested = False
# Lade gespeicherte Straßen beim Start
if 'saved_manual_streets' not in st.session_state: st.session_state.saved_manual_streets = load_streets()
# Für Vorschläge aus dem Internet
if 'online_suggestions' not in st.session_state: st.session_state.online_suggestions = []

# --- SIDEBAR ---
with st.sidebar:
    st.title("Einstellungen")
    st.markdown(f"**Version:** `{SERIAL_NUMBER}`")
    st.divider()
    selected_colors = {}
    if st.session_state.ort_sammlung:
        st.subheader("🎨 Ebenen-Farben")
        for ort in sorted(st.session_state.ort_sammlung.keys()):
            selected_colors[ort] = st.color_picker(f"{ort}", "#FF0000", key=f"cp_{ort}")
    st.divider()
    
    # --- CLEAR BUTTON ---
    if st.button("📋 Liste leeren", use_container_width=True):
        if os.path.exists(STREETS_FILE):
            os.remove(STREETS_FILE)
        st.session_state.saved_manual_streets = []
        st.success("Liste geleert.")
        st.rerun()

    if st.button("🗑️ Geocache leeren", use_container_width=True):
        shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR, exist_ok=True)
        st.success("Geocache gelöscht.")
        st.rerun()

# Hintergrundfarbe
st.markdown("<style>.stApp {background-color: #0E1117;}</style>", unsafe_allow_html=True)

# --- FUNKTION (MIT HAUSNUMMERN-SUPPORT) ---
def verarbeite_strasse(strasse_input):
    if not strasse_input: return {"success": False}
    
    # --- OPTIMIERUNG: Längere Pause ---
    time.sleep(random.uniform(0.5, 1.0))
    
    if " | " in strasse_input:
        parts = strasse_input.split(" | ")
        strasse_name = parts[0]
        hnr = parts[1]
    else:
        strasse_name = strasse_input
        hnr = None

    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse_name).strip()
    query = f"{s_clean}, Marburg-Biedenkopf"
    
    try:
        # Finde Straße
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=100)
        
        # --- MARKER-LOGIK ---
        marker_coords = None
        if hnr and not gdf.empty:
            loc = geolocator.geocode(f"{s_clean} {hnr}, Marburg-Biedenkopf", timeout=5)
            if loc:
                marker_coords = (loc.latitude, loc.longitude)
        
        if not marker_coords and not gdf.empty:
            gdf_proj = gdf.to_crs(epsg=3857)
            centroid = gdf_proj.geometry.unary_union.centroid
            point_gdf = gpd.GeoDataFrame(geometry=[centroid], crs="EPSG:3857").to_crs("EPSG:4326")
            marker_coords = (point_gdf.geometry.y[0], point_gdf.geometry.x[0])

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
                "original": strasse_input, 
                "marker": marker_coords, 
                "success": True
            }
    except:
        pass
    return {"success": False, "original": strasse_input}

# --- 3. UI ---
col_logo, col_title = st.columns([1, 10])
with col_logo: st.image(LOGO_URL, width=120)
with col_title:
    st.title("INTEGRAL PRO")
    st.markdown(f"Automatisierte Sortierung — **V9.13 (Optimization {SERIAL_NUMBER})**")

st.divider()

# --- EINGABE-LOGIK ---
col_in1, col_in2 = st.columns(2)
with col_in1: 
    files = st.file_uploader("TXT Dateien", type=["txt"], accept_multiple_files=True)
    
    # --- AUTOMATISCHER TRANSFER ---
    if files:
        new_streets = []
        for f in files: 
            file_streets = [s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()]
            new_streets.extend(file_streets)
        
        # Merge mit bestehenden und Duplikate entfernen
        merged_streets = list(set(st.session_state.saved_manual_streets + new_streets))
        if len(merged_streets) > len(st.session_state.saved_manual_streets):
            st.session_state.saved_manual_streets = merged_streets
            save_streets(st.session_state.saved_manual_streets)
            st.success(f"{len(new_streets)} Straßen aus Dateien hinzugefügt.")
            st.rerun()
    
    st.subheader("🔍 Straßensuche (Live-Prüfung)")
    
    col_str, col_hnr = st.columns([3, 1])
    with col_str:
        query_street = st.text_input("Name der Straße:", placeholder="z.B. Am Markt")
    with col_hnr:
        query_hnr = st.text_input("Nr.:", placeholder="12a")
    
    combined_query = f"{query_street} {query_hnr}".strip()
    
    # --- ONLINE-VALIDIERUNG ---
    selected_suggestion = None
    if len(query_street) > 2:
        with st.spinner("Prüfe Schreibweise..."):
            try:
                # Mehr Zeit für die Anfrage
                results = geolocator.geocode(f"{combined_query}, Marburg-Biedenkopf", exactly_one=False, limit=10, timeout=10)
                if results:
                    st.session_state.online_suggestions = [r.address for r in results]
                    selected_suggestion = st.selectbox("Ähnliche Straßen gefunden:", st.session_state.online_suggestions)
                else:
                    st.write("Keine Übereinstimmung gefunden.")
            except Exception as e:
                if "429" in str(e):
                    st.error("Too Many Requests: Der Server ist überlastet. Bitte warten Sie 10 Sekunden und versuchen es erneut.")
                else:
                    st.error(f"Fehler bei der Online-Prüfung: {e}")

    with st.form("manual_add_form", clear_on_submit=False):
        submit_btn = st.form_submit_button("➕ Straße hinzufügen")
        
        if submit_btn and selected_suggestion:
            # --- PARSING FIX ---
            full_street_address = selected_suggestion.split(',')[0].strip()
            if query_hnr and query_hnr in full_street_address:
                final_street_name = full_street_address.replace(query_hnr, "").strip()
            else:
                final_street_name = full_street_address
            
            # 3. Zusammenbauen
            street_to_save = f"{final_street_name} | {query_hnr}".strip(" |")
            
            if street_to_save not in st.session_state.saved_manual_streets:
                st.session_state.saved_manual_streets.append(street_to_save)
                save_streets(st.session_state.saved_manual_streets)
                st.success(f"Hinzugefügt: {street_to_save}")
                st.rerun()

with col_in2: 
    st.subheader("📝 Eingabeliste (Gespeichert)")
    
    if st.button("🔄 Liste aktualisieren"):
        shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR, exist_ok=True)
        st.session_state.saved_manual_streets = load_streets()
        st.success("Daten wurden frisch aus dem Netz geladen.")
        st.rerun()
        
    # --- VERBESSERTE LISTE ---
    st.write(f"Anzahl: {len(st.session_state.saved_manual_streets)}")
    # Tabelle anzeigen
    df_list = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Straße | Hausnummer"])
    st.dataframe(df_list, use_container_width=True, height=200)

# Finale Liste für die Analyse
strassen_liste = st.session_state.saved_manual_streets
strassen_liste = [s for s in strassen_liste if s]

col_btn1, col_btn2, col_excel = st.columns([1, 1, 2])

if col_btn1.button("🚀 Analyse starten", type="primary"):
    st.session_state.run_processing, st.session_state.stop_requested = True, False
    st.session_state.ort_sammlung, st.session_state.fehler_liste = None, []

if col_btn2.button("🛑 Abbruch", type="secondary"):
    st.session_state.stop_requested, st.session_state.run_processing = False, False
    st.rerun()

# --- 4. VERARBEITUNG ---
if st.session_state.run_processing and strassen_liste:
    temp_ort, temp_err = defaultdict(list), []
    
    # --- LOADINGSPINNER ---
    with st.spinner("Analyse läuft... Das kann einen Moment dauern."):
        pb = st.progress(0)
        st_text = st.empty()
        total = len(strassen_liste)
        
        # --- OPTIMIERUNG: Nur 1 Worker, um 429er zu vermeiden ---
        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = {executor.submit(verarbeite_strasse, s): s for s in strassen_liste}
            for i, future in enumerate(futures):
                if st.session_state.stop_requested: break
                res = future.result()
                if res.get("success"):
                    temp_ort[res["ort"]].append(res)
                else:
                    temp_err.append(res.get("original", "Unbekannt"))
                
                # --- FORTSCHRITTANZEIGE ---
                current_progress = (i + 1) / total
                pb.progress(current_progress)
                st_text.text(f"🔍 Fortschritt: {i+1} von {total} — Verarbeite: {res.get('name', '...')}")

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
                    popup=f"Adresse: {item['original']}",
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
    
    excel_data = create_excel_download(st.session_state.ort_sammlung)
    col_excel.download_button(
        "📥 Analyse als Excel exportieren",
        excel_data,
        file_name=f"Analyse_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    
    st.download_button("📥 Karte speichern (HTML)", m._repr_html_(), file_name="Ergebnis.html", mime="text/html")
