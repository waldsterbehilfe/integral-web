import streamlit as st
import osmnx as ox
import folium
from streamlit_folium import st_folium
import io, zipfile, os, re
import pandas as pd
import geopandas as gpd # Hinzugefügt für bessere Performance
from collections import defaultdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# --- 1. SETUP ---
st.set_page_config(page_title="INTEGRAL PRO", layout="wide", page_icon="📈")

# Cache für OSMNX
CACHE_DIR = "geocache"
if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
ox.settings.use_cache = True
ox.settings.cache_folder = f"./{CACHE_DIR}"

if 'run_processing' not in st.session_state: st.session_state.run_processing = False

# --- 2. LOGIK (HOCHPERFORMANT) ---
def verarbeite_strasse(strasse):
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    query = f"{s_clean}, Landkreis Marburg-Biedenkopf, Germany"
    
    try:
        # Erhöhter Radius, um Grenzen besser zu finden
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=1000)
        
        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            
            # Robuste Filterung
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
    st.markdown("Automatisierte Sortierung — **Profi Edition**")

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

if st.button("🚀 Analyse starten", type="primary"):
    st.session_state.run_processing = True

# --- VERARBEITUNG ---
if st.session_state.run_processing and strassen_liste:
    ort_sammlung = defaultdict(list)
    fehler_liste = []
    
    prog_bar = st.progress(0)
    status_text = st.empty()
    
    results = []
    total = len(strassen_liste)
    
    # Threads erhöht für schnellere Verarbeitung (Cache nutzt lokale Platte!)
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_street = {executor.submit(verarbeite_strasse, strasse): strasse for strasse in strassen_liste}
        
        for i, future in enumerate(future_to_street):
            res = future.result()
            results.append(res)
            
            # Update Fortschritt
            prog_bar.progress((i + 1) / total)
            status_text.text(f"🔍 {res['name'] if res['success'] else res['original']} ({i+1}/{total})")

    # --- AUSGABE ---
    for res in results:
        if res["success"]:
            ort_sammlung[res["ort"]].append(res)
        else:
            fehler_liste.append(res["original"])

    if ort_sammlung:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            master_map = folium.Map(location=[50.8, 8.8], zoom_start=11)
            
            for ort in sorted(ort_sammlung.keys()):
                feature_group = folium.FeatureGroup(name=ort)
                geoms_list = []
                
                for it in ort_sammlung[ort]:
                    folium.GeoJson(it["gdf"], style_function=lambda x: {'color':'red', 'weight':6}).add_to(feature_group)
                    geoms_list.append(it["gdf"])
                
                feature_group.add_to(master_map)
                
                # --- PROFISCHNITT: Einzelkarte mit GeoPandas Bounds ---
                m = folium.Map()
                combined_gdf = gpd.GeoDataFrame(pd.concat(geoms_list), crs=geoms_list[0].crs)
                for it in ort_sammlung[ort]:
                    folium.GeoJson(it["gdf"], style_function=lambda x: {'color':'red', 'weight':6}).add_to(m)
                
                # Bounds effizient berechnen
                bounds = combined_gdf.total_bounds
                m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], padding=(0.05, 0.05))
                zip_file.writestr(f"Karte_{ort}.html", m._repr_html_())
            
            folium.LayerControl().add_to(master_map)
            zip_file.writestr(f"00_MASTER_UEBERSICHT.html", master_map._repr_html_())
        
        st.success(f"Analyse fertig! {len(ort_sammlung)} Ortsteile erkannt.")
        st.divider()
        st.download_button("📥 ZIP: Alle Karten", zip_buffer.getvalue(), f"INTEGRAL_Pro.zip")
    
    if fehler_liste:
        st.error(f"Konnte {len(fehler_liste)} Straßen nicht finden.")
        st.download_button("⚠️ Unlösbare Fälle", "\n".join(fehler_liste), "fehler.txt")

    st.session_state.run_processing = False
