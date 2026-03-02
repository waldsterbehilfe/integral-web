import streamlit as st
import osmnx as ox
import folium
import io, re
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import random

# --- 1. SETUP ---
st.set_page_config(page_title="INTEGRAL PRO", layout="wide", page_icon="📈")

CACHE_DIR = "persistent_geocache"
if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
ox.settings.use_cache = True
ox.settings.cache_folder = f"./{CACHE_DIR}"

if 'run_processing' not in st.session_state: st.session_state.run_processing = False
if 'stop_requested' not in st.session_state: st.session_state.stop_requested = False

def get_random_color():
    return f"#{random.randint(0, 0xFFFFFF):06x}"

# --- 2. LOGIK ---
def verarbeite_strasse(strasse):
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    query = f"{s_clean}, Landkreis Marburg-Biedenkopf, Germany"
    
    try:
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=1000)
        
        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            if 'name' in gdf.columns:
                gdf_f = gdf[gdf['name'].str.contains(s_clean, case=False, na=False)]
            else:
                gdf_f = gdf

            if not gdf_f.empty:
                ortsteil = "Unbekannter_Ort"
                cols = ['addr:suburb', 'suburb', 'village', 'hamlet', 'addr:city', 'city']
                for col in cols:
                    if col in gdf_f.columns and gdf_f[col].dropna().any():
                        val = str(gdf_f[col].dropna().iloc[0])
                        if "Marburg-Biedenkopf" not in val:
                            ortsteil = val
                            break
                return {"gdf": gdf_f, "ort": ortsteil, "name": s_clean, "success": True}
    except: pass
    return {"success": False, "original": strasse}

# --- 3. UI ---
col_logo, col_title = st.columns([1, 10])
with col_logo:
    st.image("https://integral-online.de/images/integral-gmbh-logo.png", width=120)
with col_title:
    st.title("INTEGRAL PRO")
    st.markdown("Automatisierte Sortierung — **HTML Single Page Edition**")

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

# --- BUTTONS ---
col_btn1, col_btn2, _ = st.columns([1, 1, 3])

if col_btn1.button("🚀 Analyse starten", type="primary"):
    st.session_state.run_processing = True
    st.session_state.stop_requested = False

if col_btn2.button("🛑 Abbruch", type="secondary"):
    st.session_state.stop_requested = True
    st.session_state.run_processing = False

# --- VERARBEITUNG ---
if st.session_state.run_processing and strassen_liste:
    ort_sammlung = defaultdict(list)
    fehler_liste = []
    
    prog_bar = st.progress(0)
    status_text = st.empty()
    
    results = []
    total = len(strassen_liste)
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_street = {executor.submit(verarbeite_strasse, strasse): strasse for strasse in strassen_liste}
        
        for i, future in enumerate(future_to_street):
            if st.session_state.stop_requested:
                status_text.warning("Verarbeitung abgebrochen.")
                break
                
            res = future.result()
            results.append(res)
            prog_bar.progress((i + 1) / total)
            status_text.text(f"🔍 {res['name'] if res['success'] else res['original']} ({i+1}/{total})")

    # --- AUSGABE (HTML ERSTELLUNG) ---
    if not st.session_state.stop_requested:
        for res in results:
            if res["success"]:
                ort_sammlung[res["ort"]].append(res)
            else:
                fehler_liste.append(res["original"])

        if ort_sammlung:
            # Hauptkarte erstellen
            master_map = folium.Map(location=[50.8, 8.8], zoom_start=11)
            ort_colors = {ort: get_random_color() for ort in ort_sammlung.keys()}
            
            for ort in sorted(ort_sammlung.keys()):
                color = ort_colors[ort]
                
                # --- NEU: EIGENE EBENE (FeatureGroup) FÜR JEDEN ORT ---
                feature_group = folium.FeatureGroup(name=ort)
                
                for it in ort_sammlung[ort]:
                    folium.GeoJson(
                        it["gdf"],
                        style_function=lambda x, color=color: {'color': color, 'weight': 5, 'opacity': 0.8},
                        tooltip=folium.GeoJsonTooltip(fields=['name'], aliases=['Straße:']),
                        popup=folium.GeoJsonPopup(fields=['name'], aliases=['Gefunden:'])
                    ).add_to(feature_group)
                
                feature_group.add_to(master_map)
            
            # LayerControl für Ebenen hinzufügen
            folium.LayerControl().add_to(master_map)
            
            # HTML Daten generieren
            html_data = master_map._repr_html_()
            
            st.success(f"Analyse fertig! {len(ort_sammlung)} Ortsteile auf der Karte.")
            st.divider()
            
            # HTML DOWNLOAD BUTTON
            st.download_button(
                label="📥 Download Interaktive Karte (.html)",
                data=html_data,
                file_name=f"INTEGRAL_Map_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
                mime="text/html"
            )
        
        if fehler_liste:
            st.error(f"Konnte {len(fehler_liste)} Straßen nicht finden.")
            st.download_button("⚠️ Liste fehlender Straßen", "\n".join(fehler_liste), "fehler.txt")

    st.session_state.run_processing = False
