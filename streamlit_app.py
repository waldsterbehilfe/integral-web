import streamlit as st
import osmnx as ox
import folium
import io, re, os, random
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# --- 1. SETUP & PERSISTENTER CACHE ---
st.set_page_config(page_title="INTEGRAL PRO", layout="wide", page_icon="📈")

# Pfade für Cloud-Kompatibilität
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "persistent_geocache")

try:
    os.makedirs(CACHE_DIR, exist_ok=True)
except OSError as e:
    st.error(f"Cache-Fehler: {e}")

ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR

# Session States
if 'run_processing' not in st.session_state: st.session_state.run_processing = False
if 'stop_requested' not in st.session_state: st.session_state.stop_requested = False

def get_random_color():
    return f"#{random.randint(0, 0xFFFFFF):06x}"

# --- 2. LOGIK ---
def verarbeite_strasse(strasse):
    # Reinigung: 'str.' oder 'str' am Ende zu 'Straße'
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    query = f"{s_clean}, Landkreis Marburg-Biedenkopf, Germany"
    
    try:
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=800)
        
        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            # Filter auf den Namen (enthält den Suchstring)
            if 'name' in gdf.columns:
                gdf_f = gdf[gdf['name'].str.contains(s_clean, case=False, na=False)]
            else:
                gdf_f = gdf

            if not gdf_f.empty:
                # Stadtteil finden
                ortsteil = "Unbekannter_Ort"
                for col in ['addr:suburb', 'suburb', 'village', 'hamlet', 'addr:city']:
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
    st.markdown("Automatisierte Sortierung — **HTML Layer Edition (Gold)**")

st.divider()

col_in1, col_in2 = st.columns(2)
with col_in1:
    uploaded_files = st.file_uploader("Dateien laden (.txt)", type=["txt"], accept_multiple_files=True)
with col_in2:
    manual_input = st.text_area("Manuelle Eingabe", placeholder="z.B. Schweinsberger Str", height=126)

# Liste zusammenstellen
strassen_liste = []
if uploaded_files:
    for f in uploaded_files:
        strassen_liste.extend([s.strip() for s in f.getvalue().decode("utf-8").splitlines() if s.strip()])
if manual_input:
    strassen_liste.extend([s.strip() for s in manual_input.splitlines() if s.strip()])
strassen_liste = list(dict.fromkeys(strassen_liste))

# Buttons
col_btn1, col_btn2, _ = st.columns([1, 1, 3])
if col_btn1.button("🚀 Analyse starten", type="primary"):
    st.session_state.run_processing = True
    st.session_state.stop_requested = False
if col_btn2.button("🛑 Abbruch", type="secondary"):
    st.session_state.stop_requested = True

# --- 4. VERARBEITUNG ---
if st.session_state.run_processing and strassen_liste:
    ort_sammlung = defaultdict(list)
    fehler_liste = []
    all_geoms = [] # Für den finalen Zoom
    
    prog_bar = st.progress(0)
    status_text = st.empty()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(verarbeite_strasse, s): s for s in strassen_liste}
        for i, future in enumerate(futures):
            if st.session_state.stop_requested:
                status_text.warning("⏹️ Verarbeitung gestoppt.")
                break
            
            res = future.result()
            if res["success"]:
                ort_sammlung[res["ort"]].append(res)
                all_geoms.append(res["gdf"])
            else:
                fehler_liste.append(res["original"])
            
            prog_bar.progress((i + 1) / len(strassen_liste))
            status_text.text(f"🔍 {res.get('name', res.get('original'))} ({i+1}/{len(strassen_liste)})")

    # --- 5. HTML GENERIERUNG ---
    if ort_sammlung and not st.session_state.stop_requested:
        # Basis-Karte (Mittelpunkt wird später angepasst)
        m = folium.Map(location=[50.8, 8.8], zoom_start=11, control_scale=True)
        
        for ort in sorted(ort_sammlung.keys()):
            color = get_random_color()
            # FeatureGroup ist die "Ebene"
            fg = folium.FeatureGroup(name=f"📍 {ort} ({len(ort_sammlung[ort])} Str.)")
            
            for item in ort_sammlung[ort]:
                folium.GeoJson(
                    item["gdf"],
                    style_function=lambda x, c=color: {'color': c, 'weight': 6, 'opacity': 0.8},
                    tooltip=folium.GeoJsonTooltip(fields=['name'], aliases=['Straße:']),
                    popup=folium.GeoJsonPopup(fields=['name'], aliases=['Name:'])
                ).add_to(fg)
            fg.add_to(m)
        
        folium.LayerControl(collapsed=False).add_to(m)
        
        # Automatischer Zoom auf alle Straßen
        if all_geoms:
            combined = gpd.GeoDataFrame(pd.concat(all_geoms))
            b = combined.total_bounds # [minx, miny, maxx, maxy]
            m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])

        st.success(f"✅ Fertig! {len(ort_sammlung)} Ortsteile/Ebenen erstellt.")
        
        # Download
        html_string = m._repr_html_()
        st.download_button(
            label="📥 Interaktive Karte herunterladen",
            data=html_string,
            file_name=f"INTEGRAL_Master_{datetime.now().strftime('%H%M')}.html",
            mime="text/html"
        )

    if fehler_liste and not st.session_state.stop_requested:
        with st.expander("⚠️ Nicht gefundene Straßen"):
            st.write(", ".join(fehler_liste))

    # Reset
    st.session_state.run_processing = False
    st.session_state.stop_requested = False
