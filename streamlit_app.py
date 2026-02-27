import streamlit as st
import osmnx as ox
import folium
from collections import defaultdict
import io
import zipfile
from datetime import datetime

# --- UI SETUP ---
st.set_page_config(page_title="INTEGRAL v3.0", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .stButton>button { background-color: #1976d2; color: white; width: 100%; font-weight: bold; border-radius: 5px; height: 3em; border: none; }
    </style>
    """, unsafe_allow_html=True)

st.title("🗺️ INTEGRAL")
st.caption("Modus: Marburg-Biedenkopf | Stabilisierte Version")

# Straßen-Input
input_text = st.text_area("Straßenliste hier einfügen:", height=200, placeholder="Hauptstraße\nBahnhofstraße...")

if st.button("KARTEN GENERIEREN"):
    strassen = [s.strip() for s in input_text.split('\n') if s.strip()]
    
    if strassen:
        # Cache aktivieren für Speed
        ox.settings.use_cache = True
        ox.settings.cache_folder = "./geocache"
        
        ort_sammlung = defaultdict(list)
        bar = st.progress(0)
        status = st.empty()
        
        for i, strasse in enumerate(strassen):
            status.text(f"Suche: {strasse}...")
            try:
                # Suche mit Distanz-Puffer
                query = f"{strasse}, Landkreis Marburg-Biedenkopf, Germany"
                gdf = ox.features_from_address(query, tags={"highway": True}, dist=800)
                
                if not gdf.empty:
                    # Stadt/Ort erkennen
                    stadt = "Unbekannt"
                    for col in ['addr:suburb', 'addr:city', 'municipality', 'city']:
                        if col in gdf.columns and gdf[col].dropna().any():
                            stadt = gdf[col].dropna().iloc[0]
                            break
                    
                    geo_json = folium.GeoJson(gdf, style_function=lambda x: {'color':'red','weight':6})
                    ort_sammlung[stadt].append(geo_json)
            except:
                continue
            bar.progress((i + 1) / len(strassen))

        if ort_sammlung:
            st.success(f"Fertig! {len(ort_sammlung)} Orte verarbeitet.")
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for ort, elemente in ort_sammlung.items():
                    m = folium.Map(location=[50.81, 8.77], zoom_start=13)
                    for el in elemente: el.add_to(m)
                    
                    safe_name = "".join([c for c in ort if c.isalnum() or c in " _-"])
                    zf.writestr(f"Karte_{safe_name}.html", m._repr_html_())
            
            st.download_button("📥 ZIP-PAKET LADEN", zip_buffer.getvalue(), 
                               file_name=f"INTEGRAL_{datetime.now().strftime('%H%M')}.zip")
        else:
            st.error("Keine Straßen gefunden. Bitte prüfe die Namen.")
    else:
        st.warning("Eingabe fehlt!")

st.markdown("<p style='text-align: right; color: gray; font-size: 10px;'>© Maus</p>", unsafe_allow_html=True)
