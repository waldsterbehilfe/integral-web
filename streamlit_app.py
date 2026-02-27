import streamlit as st
import osmnx as ox
import folium
import io, zipfile, os, re
import pandas as pd
from collections import defaultdict
from datetime import datetime

# --- 1. SETUP ---
st.set_page_config(page_title="Mapmarker Pro", layout="wide")

# Cache einrichten
CACHE_DIR = "geocache"
if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
ox.settings.use_cache = True
ox.settings.cache_folder = f"./{CACHE_DIR}"

# --- 2. LOGIK ---
def verarbeite_strasse(strasse):
    strasse_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    
    # Strikte Suche im Landkreis
    query = f"{strasse_clean}, Landkreis Marburg-Biedenkopf, Germany"
    
    try:
        # Daten laden
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=2000)
        
        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            if 'name' in gdf.columns:
                gdf = gdf[gdf['name'].str.contains(strasse_clean, case=False, na=False)]
            
            if not gdf.empty:
                # Ortsteil finden
                ort = "Unbekannt"
                for col in ['addr:suburb', 'addr:city', 'municipality', 'county']:
                    if col in gdf.columns and gdf[col].dropna().any():
                        ort = gdf[col].dropna().iloc[0]
                        break
                return {"gdf": gdf, "ort": ort, "name": strasse, "original": strasse}
    except:
        pass
    return None

# --- 3. UI ---
st.title("Mapmarker Pro")
uploaded_file = st.file_uploader("Textdatei hochladen", type=["txt"])

if uploaded_file:
    if st.button("Start"):
        stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
        strassen_liste = [s.strip() for s in stringio if s.strip()]
        
        results = defaultdict(list)
        errors = []
        
        prog = st.progress(0)
        for i, s in enumerate(strassen_liste):
            res = verarbeite_strasse(s)
            if res:
                results[res["ort"]].append(res)
            else:
                errors.append(s)
            prog.progress((i + 1) / len(strassen_liste))
            
        # Karten erstellen
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for ort, items in results.items():
                st.subheader(ort)
                
                m = folium.Map()
                geoms = []
                for item in items:
                    # Rote Linie
                    folium.GeoJson(item["gdf"], style_function=lambda x: {'color':'red'}).add_to(m)
                    geoms.append(item["gdf"])
                    
                    # 🔵 SCHNICKSCHNACK MIT SINN: Fähnchen bei Hausnummer
                    if any(c.isdigit() for c in item["original"]):
                        try:
                            # Geocode mit Ortsteil für höhere Präzision
                            p_gdf = ox.geocode_to_gdf(f"{item['original']}, {ort}, Landkreis Marburg-Biedenkopf, Germany")
                            if not p_gdf.empty:
                                loc = p_gdf.iloc[0].geometry.centroid
                                folium.Marker([loc.y, loc.x], icon=folium.Icon(color='blue', icon='info-sign')).add_to(m)
                        except: pass
                
                # Zoom
                if geoms:
                    combined = pd.concat(geoms)
                    bounds = combined.total_bounds
                    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
                
                st.components.v1.html(m._repr_html_(), height=400)
                zip_file.writestr(f"{ort}.html", m._repr_html_())
        
        # 🔵 SCHNICKSCHNACK MIT SINN: Download Button
        st.download_button("Download ZIP", zip_buffer.getvalue(), "karten.zip", "application/zip")
        
        # 🔵 SCHNICKSCHNACK MIT SINN: Fehler-Export
        if errors:
            st.error(f"{len(errors)} Straßen nicht gefunden.")
            error_text = "\n".join(errors)
            st.download_button("Download Fehler-Liste", error_text, "fehler.txt", "text/plain")
