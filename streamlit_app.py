import streamlit as st
import osmnx as ox
import folium
from streamlit_folium import st_folium
from collections import defaultdict
import io
import zipfile
from datetime import datetime

# --- 1. DESIGN & STYLING ---
st.set_page_config(page_title="INTEGRAL - Kartengenerator", page_icon="🗺️", layout="centered")

# CSS für den Gold-Look
st.markdown("""
    <style>
    .stApp { background-color: #f5f7f9; }
    .stButton>button {
        background-color: #1976d2;
        color: white;
        border-radius: 5px;
        height: 3em;
        width: 100%;
        font-weight: bold;
        border: none;
    }
    .footer { font-size: 12px; color: #95a5a6; text-align: right; font-style: italic; margin-top: 50px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. INHALT ---
st.title("🗺️ INTEGRAL")
st.subheader("Automatischer Kartengenerator (Marburg-Biedenkopf)")

# Eingabefeld
input_text = st.text_area("Straßenliste hier einfügen (eine pro Zeile):", height=180, placeholder="Hauptstraße\nSchulgasse...")

if st.button("VERARBEITEN & KARTEN ERSTELLEN"):
    strassen = [s.strip() for s in input_text.split('\n') if s.strip()]
    
    if not strassen:
        st.error("Bitte gib zuerst Straßen ein.")
    else:
        # Cache-Verzeichnis sicherstellen
        ox.settings.use_cache = True
        ox.settings.cache_folder = "./geocache"
        
        with st.status("⚙️ Arbeite für dich... bitte warten", expanded=True) as status:
            ort_sammlung = defaultdict(list)
            
            for i, strasse in enumerate(strassen):
                try:
                    # Suche im Landkreis Marburg-Biedenkopf
                    query = f"{strasse}, Landkreis Marburg-Biedenkopf, Germany"
                    gdf = ox.features_from_address(query, tags={"highway": True}, dist=800)
                    
                    if not gdf.empty:
                        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
                        
                        # Ortsteilerkennung
                        stadt = "Unbekannt"
                        for col in ['addr:suburb', 'addr:city', 'municipality']:
                            if col in gdf.columns and gdf[col].dropna().any():
                                stadt = gdf[col].dropna().iloc[0]
                                break
                        
                        geo_json = folium.GeoJson(gdf, style_function=lambda x: {'color':'red','weight':6})
                        ort_sammlung[stadt].append(geo_json)
                except:
                    continue
            
            status.update(label="✅ Fertig!", state="complete", expanded=False)

        # Download-Bereich
        if ort_sammlung:
            st.balloons()
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for ort, elemente in ort_sammlung.items():
                    m = folium.Map(location=[50.81, 8.77], zoom_start=13)
                    for el in elemente:
                        el.add_to(m)
                    
                    # HTML der Karte in die ZIP
                    zf.writestr(f"Karte_{ort}.html", m._repr_html_())
            
            st.download_button(
                label="📥 KARTEN-PAKET (ZIP) HERUNTERLADEN",
                data=zip_buffer.getvalue(),
                file_name=f"Karten_{datetime.now().strftime('%H%M')}.zip",
                mime="application/zip"
            )
        else:
            st.error("Keine Ergebnisse für diese Straßen gefunden.")

st.markdown("<div class='footer'>© Maus | INTEGRAL Engine v3.0</div>", unsafe_allow_html=True)
