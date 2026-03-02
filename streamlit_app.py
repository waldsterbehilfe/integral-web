import streamlit as st
import osmnx as ox
import folium
import io, zipfile, os, re
import pandas as pd
from collections import defaultdict
from datetime import datetime

# --- 1. SETUP ---
st.set_page_config(page_title="INTEGRAL PRO", layout="wide", page_icon="🛡️")

CACHE_DIR = "geocache"
if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
ox.settings.use_cache = True
ox.settings.cache_folder = f"./{CACHE_DIR}"

# --- 2. LOGIK ---
def verarbeite_strasse(strasse):
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    query = f"{s_clean}, Landkreis Marburg-Biedenkopf, Germany"
    
    try:
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=800)
        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            gdf_f = gdf[gdf['name'].str.contains(s_clean, case=False, na=False)] if 'name' in gdf.columns else gdf
            
            if not gdf_f.empty:
                stadt_info = "Unbekannt"
                for col in ['addr:suburb', 'addr:city', 'municipality', 'city', 'county']:
                    if col in gdf_f.columns and gdf_f[col].dropna().any():
                        val = gdf_f[col].dropna().iloc[0]
                        if "Marburg-Biedenkopf" not in val:
                            stadt_info = val
                            break
                        stadt_info = val
                return {"gdf": gdf_f, "ort": stadt_info, "name": s_clean}
    except:
        pass
    return None

# --- 3. UI ---
st.title("🛡️ INTEGRAL PRO")
st.markdown("Automatisierte Straßensortierung — **Landkreis Marburg-Biedenkopf**")

# --- EINGABE-BEREICH ---
st.subheader("📝 Dateneingabe")
col_input1, col_input2 = st.columns(2)

with col_input1:
    uploaded_file = st.file_uploader("Option A: Datei laden (.txt)", type=["txt"])

with col_input2:
    manual_input = st.text_area("Option B: Manuelle Eingabe", placeholder="Beispiel:\nMarbachweg\nBahnhofstraße 5\nDaubringer Straße", height=126)

# Zusammenführen der Listen
strassen_liste = []
if uploaded_file:
    strassen_liste.extend([s.strip() for s in uploaded_file.getvalue().decode("utf-8").splitlines() if s.strip()])
if manual_input:
    strassen_liste.extend([s.strip() for s in manual_input.splitlines() if s.strip()])

# Dubletten entfernen, Reihenfolge beibehalten
strassen_liste = list(dict.fromkeys(strassen_liste))

if strassen_liste:
    if st.button("🚀 Verarbeitung von " + str(len(strassen_liste)) + " Straßen starten"):
        ort_sammlung = defaultdict(list)
        fehler_liste = []
        
        prog = st.progress(0)
        status = st.empty()
        
        for i, s in enumerate(strassen_liste):
            status.text(f"🔍 Suche: {s} ({i+1}/{len(strassen_liste)})")
            res = verarbeite_strasse(s)
            if res:
                ort_sammlung[res["ort"]].append(res)
            else:
                fehler_liste.append(s)
            prog.progress((i + 1) / len(strassen_liste))
            
        status.text("✅ Fertig.")

        if ort_sammlung:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for ort, items in ort_sammlung.items():
                    with st.expander(f"📍 {ort} ({len(items)} Treffer)"):
                        m = folium.Map()
                        all_geoms = []
                        for item in items:
                            folium.GeoJson(item["gdf"], style_function=lambda x: {'color':'red', 'weight':6}).add_to(m)
                            all_geoms.append(item["gdf"])
                        
                        if all_geoms:
                            combined = pd.concat(all_geoms)
                            bounds = combined.total_bounds
                            m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], padding=(0.05, 0.05))
                        
                        st.components.v1.html(m._repr_html_(), height=450)
                        zip_file.writestr(f"Karte_{ort}.html", m._repr_html_())
            
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("📥 ZIP: Alle Karten", zip_buffer.getvalue(), f"Export_{datetime.now().strftime('%H%M')}.zip", "application/zip")
            if fehler_liste:
                with c2:
                    st.download_button("⚠️ Fehlerliste (.txt)", "\n".join(fehler_liste), "fehler.txt", "text/plain")
