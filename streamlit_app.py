import streamlit as st
import osmnx as ox
import folium
import io, zipfile, os, re
import pandas as pd
from collections import defaultdict
from datetime import datetime

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="INTEGRAL Web", layout="wide")

# Cache für OSMNX (spart Zeit bei wiederholten Suchen)
CACHE_DIR = "geocache"
if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
ox.settings.use_cache = True
ox.settings.cache_folder = f"./{CACHE_DIR}"

# --- 2. LOGIK AUS DEM GOLD-CODE ---
def verarbeite_strasse(strasse):
    # Reinigung für bessere Treffer
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    query = f"{s_clean}, Landkreis Marburg-Biedenkopf, Germany"
    
    try:
        # Suche highway-Features (wie im Original)
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=800)
        
        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            if 'name' in gdf.columns:
                gdf = gdf[gdf['name'].str.contains(s_clean, case=False, na=False)]
            
            if not gdf.empty:
                # Orts-Erkennung (Suburb/City Logik)
                stadt_info = "Unbekannt"
                for col in ['addr:suburb', 'addr:city', 'municipality', 'city']:
                    if col in gdf.columns and gdf[col].dropna().any():
                        stadt_info = gdf[col].dropna().iloc[0]
                        break
                return {"gdf": gdf, "ort": stadt_info, "name": strasse}
    except:
        pass
    return None

# --- 3. UI LAYOUT ---
st.title("🛡️ INTEGRAL — Kartengenerator")
st.caption("Automatisierte Sortierung nach Ortsteilen im Landkreis Marburg-Biedenkopf")

# Sidebar für Status und Cache
st.sidebar.header("System-Status")
cache_count = sum([len(files) for r, d, files in os.walk(CACHE_DIR)])
st.sidebar.write(f"Cache: {cache_count} Einträge")

uploaded_file = st.file_uploader("📥 Lade deine Straßenliste (.txt) hoch", type=["txt"])

if uploaded_file:
    if st.button("🚀 Verarbeitung starten"):
        # Datei einlesen
        stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
        strassen = [s.strip() for s in stringio if s.strip()]
        
        ort_sammlung = defaultdict(list)
        fehler_liste = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, strasse in enumerate(strassen):
            status_text.text(f"Suche: {strasse} ({i+1}/{len(strassen)})")
            res = verarbeite_strasse(strasse)
            
            if res:
                ort_sammlung[res["ort"]].append(res)
            else:
                fehler_liste.append(strasse)
            
            progress_bar.progress((i + 1) / len(strassen))

        # --- ERGEBNISSE & DOWNLOADS ---
        st.divider()
        
        if ort_sammlung:
            st.success(f"Fertig! {len(ort_sammlung)} Orte identifiziert.")
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                
                # Pro Ort eine Karte erstellen
                for ort, items in ort_sammlung.items():
                    with st.expander(f"📍 {ort} ({len(items)} Straßen)"):
                        # Karte zentrieren (automatisch auf die erste Straße des Ortes)
                        first_geom = items[0]["gdf"].iloc[0].geometry.centroid
                        m = folium.Map(location=[first_geom.y, first_geom.x], zoom_start=14)
                        
                        all_geoms = []
                        for item in items:
                            folium.GeoJson(item["gdf"], 
                                           style_function=lambda x: {'color':'red', 'weight':6},
                                           tooltip=item["name"]).add_to(m)
                            all_geoms.append(item["gdf"])
                        
                        # Zoom auf alle Straßen des Ortes anpassen
                        combined_gdf = pd.concat(all_geoms)
                        bounds = combined_gdf.total_bounds
                        m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
                        
                        # In Streamlit anzeigen
                        st.components.v1.html(m._repr_html_(), height=400)
                        
                        # HTML für ZIP speichern
                        zip_file.writestr(f"Karte_{ort}.html", m._repr_html_())
            
            # Download Buttons
            col1, col2 = st.columns(2)
            with col1:
                st.download_button("📥 Alle Karten (ZIP) herunterladen", 
                                   data=zip_buffer.getvalue(), 
                                   file_name=f"INTEGRAL_Karten_{datetime.now().strftime('%H%M')}.zip", 
                                   mime="application/zip")
            
            if fehler_liste:
                with col2:
                    fehler_text = "\n".join(fehler_liste)
                    st.download_button("⚠️ Fehlerliste (.txt) herunterladen", 
                                       data=fehler_text, 
                                       file_name="nicht_gefunden.txt", 
                                       mime="text/plain")
        else:
            st.error("Keine der Straßen konnte im Landkreis gefunden werden.")

st.markdown("---")
st.caption("© 2026 Maus Industries | Minimaler Aufwand, maximales Ergebnis.")
