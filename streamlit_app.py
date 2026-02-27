
import streamlit as st
import osmnx as ox
import folium
from collections import defaultdict
import io
import zipfile
from datetime import datetime

# --- SETUP ---
st.set_page_config(page_title="INTEGRAL", layout="centered")

# Design
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .stButton>button { background-color: #1976d2; color: white; width: 100%; font-weight: bold; border-radius: 5px; border: none; height: 3em; }
    .footer { font-size: 10px; color: gray; text-align: right; margin-top: 50px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🗺️ INTEGRAL")
st.caption("Professioneller Kartengenerator | v3.0")

# Eingabe
input_text = st.text_area("Straßenliste hier einfügen:", height=200, placeholder="Am Markt\nSchloßstraße 1\n...")

if st.button("KARTEN JETZT GENERIEREN"):
    strassen = [s.strip() for s in input_text.split('\n') if s.strip()]
    
    if strassen:
        # Cache Logik
        ox.settings.use_cache = True
        ox.settings.cache_folder = "./geocache"
        
        ort_sammlung = defaultdict(list)
        progress = st.progress(0)
        status_msg = st.empty()
        
        for i, strasse in enumerate(strassen):
            status_msg.text(f"Verarbeite: {strasse}...")
            try:
                # Suche im Landkreis
                query = f"{strasse}, Landkreis Marburg-Biedenkopf, Germany"
                gdf = ox.features_from_address(query, tags={"highway": True}, dist=800)
                
                if not gdf.empty:
                    # Ortsteilerkennung
                    stadt = "Unbekannt"
                    for col in ['addr:suburb', 'addr:city', 'municipality', 'city']:
                        if col in gdf.columns and gdf[col].dropna().any():
                            stadt = gdf[col].dropna().iloc[0]
                            break
                    
                    # Karten-Element
                    geo_json = folium.GeoJson(gdf, style_function=lambda x: {'color':'red','weight':6})
                    ort_sammlung[stadt].append(geo_json)
            except:
                continue
            progress.progress((i + 1) / len(strassen))

        if ort_sammlung:
            status_msg.success(f"Erfolg! {len(ort_sammlung)} Ortsteile gefunden.")
            st.balloons()
            
            # ZIP erstellen
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for ort, elemente in ort_sammlung.items():
                    # Karte zentrieren (Marburg Fokus)
                    m = folium.Map(location=[50.81, 8.77], zoom_start=13)
                    for el in elemente:
                        el.add_to(m)
                    
                    safe_ort = "".join([c for c in ort if c.isalnum() or c in " _-"])
                    zf.writestr(f"Karte_{safe_ort}.html", m._repr_html_())
            
            st.download_button(
                label="📥 FERTIGES PAKET HERUNTERLADEN (ZIP)", 
                data=zip_buffer.getvalue(), 
                file_name=f"Karten_{datetime.now().strftime('%H%M')}.zip",
                mime="application/zip"
            )
        else:
            status_msg.error("Keine Ergebnisse gefunden. Bitte Schreibweise prüfen.")
    else:
        st.warning("Bitte gib zuerst mindestens eine Straße ein.")

st.markdown("<div class='footer'>© Maus | INTEGRAL Engine</div>", unsafe_allow_html=True)
