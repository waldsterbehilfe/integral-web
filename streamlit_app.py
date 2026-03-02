import streamlit as st
import osmnx as ox
import folium
import io, zipfile, os, re
import pandas as pd
from collections import defaultdict
from datetime import datetime

# --- 1. SETUP ---
st.set_page_config(page_title="INTEGRAL PRO", layout="wide", page_icon="📈")

CACHE_DIR = "geocache"
if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
ox.settings.use_cache = True
ox.settings.cache_folder = f"./{CACHE_DIR}"

if 'run_processing' not in st.session_state: st.session_state.run_processing = False
if 'stop_requested' not in st.session_state: st.session_state.stop_requested = False

# --- 2. LOGIK: STRASSEN- & ORTSTEIL-SUCHE ---
def verarbeite_strasse(strasse):
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    # Suche im gesamten Landkreis
    query = f"{s_clean}, Landkreis Marburg-Biedenkopf, Germany"
    
    try:
        # Erhöhter Radius (1500m), um Stadtteilgrenzen besser zu erfassen
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=1500)
        
        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            # Filtern auf exakten Namen (Case-Insensitive)
            if 'name' in gdf.columns:
                gdf_f = gdf[gdf['name'].str.contains(s_clean, case=False, na=False)]
            else:
                gdf_f = gdf

            if not gdf_f.empty:
                # --- INTELLIGENTE STADTTEIL-TRENNUNG ---
                # Wir priorisieren 'suburb' (Stadtteil), dann 'city' (Stadt)
                ortsteil = "Unbekannt"
                
                # Liste der Felder, die OSM für Stadtteile nutzt
                priority_cols = ['addr:suburb', 'suburb', 'neighbourhood', 'addr:city', 'municipality', 'city']
                
                for col in priority_cols:
                    if col in gdf_f.columns and gdf_f[col].dropna().any():
                        val = gdf_f[col].dropna().iloc[0]
                        # Ignoriere den Landkreis-Namen als Ortsteil
                        if "Marburg-Biedenkopf" not in str(val):
                            ortsteil = val
                            break
                
                return {"gdf": gdf_f, "ort": ortsteil, "name": s_clean, "success": True}
    except:
        pass
    return {"success": False, "original": strasse}

# --- 3. UI ---
col_logo, col_title = st.columns([1, 10])
with col_logo:
    st.image("https://integral-online.de/images/integral-gmbh-logo.png", width=120)
with col_title:
    st.title("INTEGRAL PRO")
    st.markdown("Automatisierte Sortierung nach **Stadt- und Ortsteilen** (Marburg-Biedenkopf)")

st.divider()

# Eingabe
col_in1, col_in2 = st.columns(2)
with col_in1:
    uploaded_file = st.file_uploader("Datei laden (.txt)", type=["txt"])
with col_in2:
    manual_input = st.text_area("Manuelle Eingabe", placeholder="z.B. Marbachweg\nKetzerbach", height=126)

strassen_liste = []
if uploaded_file:
    strassen_liste.extend([s.strip() for s in uploaded_file.getvalue().decode("utf-8").splitlines() if s.strip()])
if manual_input:
    strassen_liste.extend([s.strip() for s in manual_input.splitlines() if s.strip()])
strassen_liste = list(dict.fromkeys(strassen_liste))

# Steuerung
c_btn1, c_btn2, _ = st.columns([1, 1, 2])
if c_btn1.button("🚀 Suche & Sortierung starten", type="primary", use_container_width=True):
    st.session_state.run_processing = True
    st.session_state.stop_requested = False
if c_btn2.button("🛑 Abbruch", use_container_width=True):
    st.session_state.stop_requested = True

# --- VERARBEITUNG ---
if st.session_state.run_processing and strassen_liste:
    ort_sammlung = defaultdict(list)
    fehler_liste = []
    
    prog = st.progress(0)
    status = st.empty()
    
    for i, s in enumerate(strassen_liste):
        if st.session_state.stop_requested: break
        status.text(f"🔍 Analysiere: {s} ({i+1}/{len(strassen_liste)})")
        
        res = verarbeite_strasse(s)
        if res["success"]:
            ort_sammlung[res["ort"]].append(res)
        else:
            fehler_liste.append(s)
        prog.progress((i + 1) / len(strassen_liste))

    # --- ERGEBNISSE ---
    if ort_sammlung:
        st.success(f"Analyse abgeschlossen: {len(ort_sammlung)} verschiedene Stadt-/Ortsteile identifiziert.")
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            # Sortierung der Ortsteile nach Name
            for ort in sorted(ort_sammlung.keys()):
                items = ort_sammlung[ort]
                with st.expander(f"📍 {ort} ({len(items)} Straßen)"):
                    m = folium.Map()
                    geoms = [it["gdf"] for it in items]
                    for it in items:
                        folium.GeoJson(it["gdf"], 
                                       style_function=lambda x: {'color':'red', 'weight':6},
                                       tooltip=it["name"]).add_to(m)
                    
                    # Auto-Zoom auf den Ortsteil
                    combined = pd.concat(geoms)
                    bounds = combined.total_bounds
                    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], padding=(0.1, 0.1))
                    
                    st.components.v1.html(m._repr_html_(), height=450)
                    
                    # HTML in ZIP speichern
                    zip_file.writestr(f"Karte_{ort}.html", m._repr_html_())
        
        st.divider()
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button("📥 ZIP: Alle Ortsteil-Karten", zip_buffer.getvalue(), f"INTEGRAL_Sortiert_{datetime.now().strftime('%H%M')}.zip")
        if fehler_liste:
            with col_dl2:
                st.download_button("⚠️ Fehlerliste downloaden", "\n".join(fehler_liste), "korrektur_noetig.txt")

    st.session_state.run_processing = False
