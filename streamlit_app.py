import streamlit as st
import osmnx as ox
import folium
from collections import defaultdict
import io
import zipfile
import base64
from datetime import datetime
import os

# --- HINTERGRUND-LOGIK ---
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def set_png_as_page_bg(bin_file):
    if os.path.exists(bin_file):
        bin_str = get_base64_of_bin_file(bin_file)
        page_bg_img = f'''
        <style>
        .stApp {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: cover;
            background-attachment: fixed;
        }}
        /* Kontrast-Box für den Inhalt */
        .block-container {{
            background: rgba(255, 255, 255, 0.9);
            padding: 3rem;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-top: 2rem;
        }}
        </style>
        '''
        st.markdown(page_bg_img, unsafe_allow_html=True)

# --- UI SETUP ---
st.set_page_config(page_title="INTEGRAL Gold", page_icon="🗺️")

# Hintergrund setzen (wenn Datei existiert)
set_png_as_page_bg('hintergrund.png')

# Button Design
st.markdown("""
    <style>
    .stButton>button {
        background: linear-gradient(to right, #1976d2, #004a99);
        color: white; border: none; border-radius: 10px;
        font-weight: bold; width: 100%; height: 3.5em;
    }
    .footer { text-align: right; font-size: 11px; color: #7f8c8d; margin-top: 30px; }
    </style>
    """, unsafe_allow_html=True)

# --- HAUPTTEIL ---
st.title("🗺️ INTEGRAL Gold")
st.markdown("Professioneller Kartengenerator | Modus: Marburg-Biedenkopf")

input_text = st.text_area("Straßenliste:", height=150, placeholder="Hauptstraße\nSchulstraße...")

if st.button("KARTEN ERSTELLEN"):
    strassen = [s.strip() for s in input_text.split('\n') if s.strip()]
    
    if strassen:
        ox.settings.use_cache = True
        ox.settings.cache_folder = "./geocache"
        
        ort_sammlung = defaultdict(list)
        bar = st.progress(0)
        status = st.empty()
        
        for i, strasse in enumerate(strassen):
            status.text(f"🔍 Suche: {strasse}...")
            try:
                query = f"{strasse}, Landkreis Marburg-Biedenkopf, Germany"
                gdf = ox.features_from_address(query, tags={"highway": True}, dist=800)
                if not gdf.empty:
                    stadt = "Unbekannt"
                    for col in ['addr:suburb', 'addr:city', 'municipality']:
                        if col in gdf.columns and gdf[col].dropna().any():
                            stadt = gdf[col].dropna().iloc[0]
                            break
                    geo_json = folium.GeoJson(gdf, style_function=lambda x: {'color':'#e74c3c','weight':6})
                    ort_sammlung[stadt].append(geo_json)
            except: continue
            bar.progress((i + 1) / len(strassen))

        if ort_sammlung:
            st.balloons()
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for ort, elemente in ort_sammlung.items():
                    m = folium.Map(location=[50.81, 8.77], zoom_start=13)
                    for el in elemente: el.add_to(m)
                    zf.writestr(f"Karte_{ort}.html", m._repr_html_())
            
            st.download_button("📥 KARTEN-PAKET (ZIP) LADEN", zip_buffer.getvalue(), file_name="INTEGRAL_Export.zip")

st.markdown("<div class='footer'>© Maus | v3.2 Gold</div>", unsafe_allow_html=True)
