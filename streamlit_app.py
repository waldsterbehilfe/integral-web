import streamlit as st
import osmnx as ox
import folium
from streamlit_folium import st_folium # Nutzung deiner requirements.txt
import io, zipfile, os, re
import pandas as pd
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor

# --- 1. SETUP ---
st.set_page_config(page_title="INTEGRAL PRO", layout="wide", page_icon="📈")

# Cache für OSMNX (Persistent für Performance)
CACHE_DIR = "geocache"
if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
ox.settings.use_cache = True
ox.settings.cache_folder = f"./{CACHE_DIR}"

if 'run_processing' not in st.session_state: st.session_state.run_processing = False

# --- 2. LOGIK ---
def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def verarbeite_strasse(strasse):
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    query = f"{s_clean}, Landkreis Marburg-Biedenkopf, Germany"
    
    try:
        # Direkte Suche
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=1000)
        
        if gdf.empty:
            # Auto-Korrektur (Fuzzy)
            search_area = f"Landkreis Marburg-Biedenkopf, Germany"
            temp_gdf = ox.features_from_place(search_area, tags={"highway": True})
            if 'name' in temp_gdf.columns:
                alle_namen = temp_gdf['name'].dropna().unique()
                best_match = None
                highest_score = 0
                for name in alle_namen:
                    score = similarity(s_clean, name)
                    if score > highest_score:
                        highest_score = score
                        best_match = name
                if highest_score > 0.8:
                    s_clean = best_match
                    query = f"{s_clean}, Landkreis Marburg-Biedenkopf, Germany"
                    gdf = ox.features_from_address(query, tags={"highway": True}, dist=1000)

        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            ortsteil = "Unbekannter_Ort"
            cols = ['addr:suburb', 'suburb', 'village', 'hamlet', 'addr:city', 'city']
            for col in cols:
                if col in gdf.columns and gdf[col].dropna().any():
                    val = str(gdf[col].dropna().iloc[0])
                    if "Marburg-Biedenkopf" not in val:
                        ortsteil = val
                        break
            return {"gdf": gdf, "ort": ortsteil, "name": s_clean, "success": True, "corrected": s_clean != strasse}
    except: pass
    return {"success": False, "original": strasse}

# --- 3. UI ---
col_logo, col_title = st.columns([1, 10])
with col_logo:
    st.image("https://integral-online.de/images/integral-gmbh-logo.png", width=120)
with col_title:
    st.title("INTEGRAL PRO")
    st.markdown("Automatisierte Sortierung — **Parallelisiert & Zentralisiert**")

st.divider()

# Eingabe
col_in1, col_in2 = st.columns(2)
with col_in1:
    uploaded_files = st.file_uploader("Dateien laden (.txt)", type=["txt"], accept_multiple_files=True)
with col_in2:
    manual_input = st.text_area("Manuelle Eingabe", placeholder="z.B. Schweinsberger Str (Tippfehler werden korrigiert)", height=126)

strassen_liste = []
if uploaded_files:
    for f in uploaded_files:
        strassen_liste.extend([s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()])
if manual_input:
    strassen_liste.extend([s.strip() for s in manual_input.splitlines() if s.strip()])
strassen_liste = list(dict.fromkeys(strassen_liste))

if st.button("🚀 Turbo-Analyse starten", type="primary"):
    st.session_state.run_processing = True

# --- VERARBEITUNG ---
if st.session_state.run_processing and strassen_liste:
    ort_sammlung = defaultdict(list)
    fehler_liste = []
    korrekturen_log = []
    
    status = st.empty()
    status.text(f"🚀 Starte parallele Suche für {len(strassen_liste)} Straßen...")
    
    # NEU: Multi-Threading
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(verarbeite_strasse, strassen_liste))
        
    for res in results:
        if res["success"]:
            ort_sammlung[res["ort"]].append(res)
            if res.get("corrected"):
                korrekturen_log.append(f"'{res['original']}' -> korrigiert zu '{res['name']}'")
        else:
            fehler_liste.append(res["original"])

    # --- AUSGABE & MASTER-KARTE ---
    if ort_sammlung:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            
            # Master-Karte erstellen
            master_map = folium.Map(location=[50.8, 8.8], zoom_start=11)
            
            for ort in sorted(ort_sammlung.keys()):
                # Für die Master-Karte: Jedes Dorf bekommt eine eigene FeatureGroup (Layer)
                feature_group = folium.FeatureGroup(name=ort)
                
                geoms = [it["gdf"] for it in ort_sammlung[ort]]
                for it in ort_sammlung[ort]:
                    folium.GeoJson(it["gdf"], style_function=lambda x: {'color':'red', 'weight':6}).add_to(feature_group)
                
                feature_group.add_to(master_map)
                
                # Einzelkarten für die ZIP
                m = folium.Map()
                for it in ort_sammlung[ort]:
                    folium.GeoJson(it["gdf"], style_function=lambda x: {'color':'red', 'weight':6}).add_to(m)
                combined = pd.concat(geoms)
                bounds = combined.total_bounds
                m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], padding=(0.1, 0.1))
                zip_file.writestr(f"Karte_{ort}.html", m._repr_html_())
            
            # Master-Karte Layer Control hinzufügen & in ZIP packen
            folium.LayerControl().add_to(master_map)
            zip_file.writestr(f"00_MASTER_UEBERSICHT.html", master_map._repr_html_())
        
        st.success(f"Turbo-Analyse fertig! {len(ort_sammlung)} Ortsteile erkannt.")
        if korrekturen_log:
            with st.expander("🛠️ Durchgeführte Auto-Korrekturen"):
                for log in korrekturen_log: st.write(log)
        
        st.divider()
        st.download_button("📥 ZIP: Alle Karten & Master-Übersicht", zip_buffer.getvalue(), f"INTEGRAL_Turbo.zip")
    
    if fehler_liste:
        st.error(f"Konnte {len(fehler_liste)} Straßen nicht finden.")
        st.download_button("⚠️ Unlösbare Fälle", "\n".join(fehler_liste), "fehler.txt")

    st.session_state.run_processing = False
