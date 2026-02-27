import streamlit as st
import osmnx as ox
import folium
from streamlit_folium import st_folium
from collections import defaultdict
import io
import zipfile
from datetime import datetime

# --- DESIGN & STYLING (Dein Gold-Look) ---
st.set_page_config(page_title="INTEGRAL - Kartengenerator", page_icon="🗺️", layout="centered")

# CSS für den edlen Look (Dunkel/Blau)
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button {
        background-color: #1976d2;
        color: white;
        border-radius: 5px;
        height: 3em;
        width: 100%;
        font-weight: bold;
        border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stTextArea textarea {
        border-radius: 10px;
        border: 1px solid #1976d2;
    }
    .title-text { color: #2c3e50; font-family: 'Arial', sans-serif; font-weight: bold; }
    .footer { font-size: 12px; color: #95a5a6; text-align: right; font-style: italic; margin-top: 50px; }
    </style>
    """, unsafe_allow_html=True)

# --- INHALT ---
st.markdown("<h1 class='title-text'>🗺️ INTEGRAL</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #34495e;'>Kartengenerator | Modus: Marburg-Biedenkopf</p>", unsafe_allow_html=True)

# Eingabefeld
input_text = st.text_area("Straßenliste hier einfügen:", height=180, placeholder="Hauptstraße\nSchulgasse...")

if st.button("VERARBEITEN & KARTEN ERSTELLEN"):
    strassen = [s.strip() for s in input_text.split('\n') if s.strip()]
    
    if not strassen:
        st.error("Bitte gib zuerst Straßen ein.")
    else:
        with st.status("⚙️ Arbeite für dich... bitte warten", expanded=True) as status:
            ort_sammlung = defaultdict(list)
            
            # Gold-Logik
            for i, strasse in enumerate(strassen):
                try:
                    query = f"{strasse}, Landkreis Marburg-Biedenkopf, Germany"
                    gdf = ox.features_from_address(query, tags={"highway": True}, dist=800)
                    if not gdf.empty:
                        # Ortsteilerkennung
                        stadt = "Unbekannt"
                        for col in ['addr:suburb', 'addr:city', 'municipality']:
                            if col in gdf.columns and gdf[col].dropna().any():
                                stadt = gdf[col].dropna().iloc[0]
                                break
                        
                        geo_json = folium.GeoJson(gdf, style_function=lambda x: {'color':'red','weight':6})
                        ort_sammlung[stadt].append(geo_json)
                except: continue
            
            status.update(label="✅ Fertig!", state="complete", expanded=False)

        # Download-Sektion
        if ort_sammlung:
            st.balloons() # Kleiner Erfolgseffekt
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for ort, elemente in ort_sammlung.items():
                    m = folium.Map(location=[50.81, 8.77], zoom_start=13)
                    for el in elemente: el.add_to(m)
                    zf.writestr(f"Karte_{ort}.html", m._repr_html_())
            
            st.download_button(
                label="📥 KARTEN-PAKET (ZIP) HERUNTERLADEN",
                data=zip_buffer.getvalue(),
                file_name=f"Karten_{datetime.now().strftime('%H%M')}.zip",
                mime="application/zip"
            )

st.markdown("<div class='footer'>© Maus | INTEGRAL Engine v3.0</div>", unsafe_allow_html=True)import streamlit as st
import osmnx as ox
import folium
from streamlit_folium import st_folium
from collections import defaultdict
import io
import zipfile
from datetime import datetime

st.set_page_config(page_title="INTEGRAL Web", layout="wide")

# Gold-Standard Caching
ox.settings.use_cache = True
ox.settings.cache_folder = "./geocache"

st.title("🗺️ INTEGRAL - Automatik-Modus")
st.write("Füge unten deine Straßen ein. Den Rest erledige ich.")

input_text = st.text_area("Straßenliste:", height=150, placeholder="Hauptstraße 1\nBahnhofstraße 10...")

if st.button("Arbeit starten"):
    strassen = [s.strip() for s in input_text.split('\n') if s.strip()]
    if strassen:
        ort_sammlung = defaultdict(list)
        progress = st.progress(0)
        
        for i, strasse in enumerate(strassen):
            try:
                query = f"{strasse}, Landkreis Marburg-Biedenkopf, Germany"
                gdf = ox.features_from_address(query, tags={"highway": True}, dist=800)
                if not gdf.empty:
                    # Automatisches Sortieren nach Ortsteilen
                    stadt = "Unbekannt"
                    for col in ['addr:suburb', 'addr:city', 'municipality']:
                        if col in gdf.columns and gdf[col].dropna().any():
                            stadt = gdf[col].dropna().iloc[0]
                            break
                    
                    style = {'color':'red','weight':6}
                    geo_json = folium.GeoJson(gdf, style_function=lambda x: style, tooltip=strasse)
                    ort_sammlung[stadt].append(geo_json)
            except:
                continue
            progress.progress((i + 1) / len(strassen))

        # Automatischer ZIP-Download
        if ort_sammlung:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for ort, elemente in ort_sammlung.items():
                    m = folium.Map(location=[50.81, 8.77], zoom_start=13)
                    for el in elemente: el.add_to(m)
                    zf.writestr(f"Karte_{ort}.html", m._repr_html_())
            
            st.success("Alle Karten wurden erstellt!")
            st.download_button("📂 Klicke hier für dein fertiges Karten-Paket", zip_buffer.getvalue(), 
                               file_name=f"Karten_{datetime.now().strftime('%H%M')}.zip")



