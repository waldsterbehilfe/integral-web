import streamlit as st
import osmnx as ox
import folium
from streamlit_folium import st_folium
from collections import defaultdict
import io
import zipfile
from datetime import datetime

# --- KONFIGURATION ---
st.set_page_config(page_title="INTEGRAL Web", page_icon="🗺️")

# Caching für OSMNX (Goldstandard)
ox.settings.use_cache = True
ox.settings.cache_folder = "./geocache"

# --- UI DESIGN ---
st.title("INTEGRAL - Kartengenerator")
st.sidebar.header("Einstellungen")
dark_mode = st.sidebar.toggle("Dark Mode (Vorschau)")

st.markdown("### Straßenliste verarbeiten")
input_text = st.text_area("Straßen hier einfügen (eine pro Zeile):", height=200, placeholder="Hauptstraße\nSchulweg")

if st.button("Karten generieren"):
    strassen = [s.strip() for s in input_text.split('\n') if s.strip()]
    
    if not strassen:
        st.warning("Bitte gib zuerst Straßen ein.")
    else:
        ort_sammlung = defaultdict(list)
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, strasse in enumerate(strassen):
            status_text.text(f"Suche: {strasse} ({i+1}/{len(strassen)})")
            try:
                query = f"{strasse}, Landkreis Marburg-Biedenkopf, Germany"
                gdf = ox.features_from_address(query, tags={"highway": True}, dist=800)
                
                if not gdf.empty:
                    gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
                    # Orts-Erkennung
                    stadt_info = "Unbekannter_Ort"
                    for col in ['addr:suburb', 'addr:city', 'municipality', 'city']:
                        if col in gdf.columns and gdf[col].dropna().any():
                            stadt_info = gdf[col].dropna().iloc[0]
                            break
                    
                    # Karten-Element erstellen
                    style = {'color':'red','weight':6,'opacity':0.8}
                    geo_json = folium.GeoJson(gdf, style_function=lambda x: style, tooltip=strasse)
                    ort_sammlung[stadt_info].append(geo_json)
            except:
                st.error(f"Fehler bei: {strasse}")
            
            progress_bar.progress((i + 1) / len(strassen))

        # --- DOWNLOAD BEREICH ---
        if ort_sammlung:
            st.success(f"Fertig! {len(ort_sammlung)} Orte gefunden.")
            
            # ZIP im Speicher erstellen
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for ort, elemente in ort_sammlung.items():
                    m = folium.Map(location=[50.81, 8.77], zoom_start=13)
                    for el in elemente:
                        el.add_to(m)
                    
                    safe_ort = "".join([c for c in ort if c.isalnum() or c in " _-"])
                    zf.writestr(f"Karte_{safe_ort}.html", m._repr_html_())
            
            st.download_button(
                label="📥 Alle Karten als ZIP herunterladen",
                data=zip_buffer.getvalue(),
                file_name=f"Karten_Export_{datetime.now().strftime('%H%M')}.zip",
                mime="application/zip"
            )
        else:
            st.error("Nichts gefunden.")

st.divider()
st.caption("© Maus | Marburg-Biedenkopf Modus")