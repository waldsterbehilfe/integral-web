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

# --- 2. LOGIK: TIEFE ORTSTEIL-ANALYSE ---
def verarbeite_strasse(strasse):
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    query = f"{s_clean}, Landkreis Marburg-Biedenkopf, Germany"
    
    try:
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=1000)
        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            gdf_f = gdf[gdf['name'].str.contains(s_clean, case=False, na=False)] if 'name' in gdf.columns else gdf

            if not gdf_f.empty:
                ortsteil = "Unbekannter_Ort"
                cols_to_check = ['addr:suburb', 'suburb', 'village', 'hamlet', 'neighbourhood', 'addr:city', 'city']
                for col in cols_to_check:
                    if col in gdf_f.columns and gdf_f[col].dropna().any():
                        val = str(gdf_f[col].dropna().iloc[0])
                        if "Marburg-Biedenkopf" not in val:
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
    st.markdown("Automatisierte Straßensortierung — **Multi-File-Support**")

st.divider()

# --- EINGABE-SEKTION (Multi-Upload) ---
st.subheader("📝 Dateneingabe")
col_input1, col_input2 = st.columns(2)

with col_input1:
    # NEU: accept_multiple_files=True
    uploaded_files = st.file_uploader("Option A: Mehrere Dateien laden (.txt)", type=["txt"], accept_multiple_files=True)

with col_input2:
    manual_input = st.text_area("Option B: Manuelle Eingabe", placeholder="z.B. Schweinsberger Straße\nLahnstraße", height=126)

# Listen aus allen Quellen zusammenführen
strassen_liste = []

if uploaded_files:
    for f in uploaded_files:
        content = f.getvalue().decode("utf-8")
        strassen_liste.extend([s.strip() for s in content.splitlines() if s.strip()])

if manual_input:
    strassen_liste.extend([s.strip() for s in manual_input.splitlines() if s.strip()])

# Dubletten entfernen
strassen_liste = list(dict.fromkeys(strassen_liste))

# Anzeige der Anzahl der geladenen Daten
if strassen_liste:
    st.info(f"Gesamtanzahl zu prüfender Straßen: **{len(strassen_liste)}** (aus {len(uploaded_files) if uploaded_files else 0} Dateien + manueller Eingabe)")

# Steuerung
col_b1, col_b2, _ = st.columns([1, 1, 2])
if col_b1.button("🚀 Gesamtanalyse starten", type="primary", use_container_width=True):
    st.session_state.run_processing = True
    st.session_state.stop_requested = False
if col_b2.button("🛑 Abbruch", use_container_width=True):
    st.session_state.stop_requested = True

# --- VERARBEITUNG ---
if st.session_state.run_processing and strassen_liste:
    ort_sammlung = defaultdict(list)
    fehler_liste = []
    
    prog = st.progress(0)
    status = st.empty()
    
    for i, s in enumerate(strassen_liste):
        if st.session_state.stop_requested: 
            st.error("Verarbeitung abgebrochen.")
            break
        status.text(f"🔍 Analysiere: {s} ({i+1}/{len(strassen_liste)})")
        
        res = verarbeite_strasse(s)
        if res["success"]:
            ort_sammlung[res["ort"]].append(res)
        else:
            fehler_liste.append(s)
        prog.progress((i + 1) / len(strassen_liste))

    # --- AUSGABE ---
    if ort_sammlung:
        st.success(f"Analyse abgeschlossen: {len(ort_sammlung)} verschiedene Ortsteile/Dörfer erkannt.")
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for ort in sorted(ort_sammlung.keys()):
                with st.expander(f"🏘️ {ort.upper()} ({len(ort_sammlung[ort])} Straßen)"):
                    m = folium.Map()
                    geoms = []
                    for it in ort_sammlung[ort]:
                        folium.GeoJson(it["gdf"], style_function=lambda x: {'color':'red', 'weight':6}).add_to(m)
                        geoms.append(it["gdf"])
                    
                    combined = pd.concat(geoms)
                    bounds = combined.total_bounds
                    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], padding=(0.1, 0.1))
                    
                    st.components.v1.html(m._repr_html_(), height=450)
                    zip_file.writestr(f"Ortsteil_{ort}.html", m._repr_html_())
        
        st.divider()
        c_dl1, c_dl2 = st.columns(2)
        with c_dl1:
            st.download_button("📥 ZIP: Alle Karten laden", zip_buffer.getvalue(), f"INTEGRAL_Batch_{datetime.now().strftime('%H%M')}.zip")
        if fehler_liste:
            with c_dl2:
                st.download_button("⚠️ Fehlerliste", "\n".join(fehler_liste), "fehler_checken.txt")

    st.session_state.run_processing = False
