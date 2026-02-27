import streamlit as st
import osmnx as ox
import folium
from streamlit_folium import st_folium
from collections import defaultdict
import io
import zipfile
import base64
import os
from datetime import datetime

# --- 1. SESSION STATE (Das Gedächtnis der App) ---
if 'maps_ready' not in st.session_state:
    st.session_state.maps_ready = False
if 'ort_sammlung' not in st.session_state:
    st.session_state.ort_sammlung = None
if 'zip_data' not in st.session_state:
    st.session_state.zip_data = None

# --- 2. DESIGN-LOGIK ---
def set_design(dark_mode):
    bg_color = "rgba(30, 30, 30, 0.9)" if dark_mode else "rgba(255, 255, 255, 0.9)"
    text_color = "white" if dark_mode else "#2c3e50"
    
    bg_img_html = ""
    if os.path.exists('hintergrund.png'):
        with open('hintergrund.png', 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        bg_img_html = f'background-image: url("data:image/png;base64,{data}"); background-size: cover; background-attachment: fixed;'

    st.markdown(f"""
        <style>
        .stApp {{ {bg_img_html} }}
        .block-container {{
            background: {bg_color};
            padding: 2rem; border-radius: 15px; color: {text_color};
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        }}
        .stButton>button {{
            background: linear-gradient(to right, #1976d2, #004a99);
            color: white; font-weight: bold; width: 100%; border-radius: 8px; height: 3em;
        }}
        </style>
    """, unsafe_allow_html=True)

# --- 3. UI STRUKTUR ---
st.set_page_config(page_title="INTEGRAL Gold v5.0", layout="wide")

# Auswahl-Design in der Sidebar (bleibt immer sichtbar)
st.sidebar.title("🎨 Design & Optionen")
choice = st.sidebar.radio("Farbschema wählen:", ["Dark Mode", "Light Mode"])
set_design(dark_mode=(choice == "Dark Mode"))

st.title("🗺️ INTEGRAL Web Gold")
st.markdown("Karten bleiben nach der Suche dauerhaft sichtbar.")

# Eingabe
input_text = st.text_area("Straßenliste:", height=150, placeholder="Hauptstraße\nSchloßweg...")

# --- 4. VERARBEITUNG ---
if st.button("KARTEN GENERIEREN"):
    strassen_liste = [s.strip() for s in input_text.split('\n') if s.strip()]
    
    if strassen_liste:
        with st.status("Suche läuft...", expanded=True) as status:
            temp_ort_sammlung = defaultdict(list)
            
            for s_name in strassen_liste:
                try:
                    q = f"{s_name}, Landkreis Marburg-Biedenkopf, Germany"
                    gdf = ox.features_from_address(q, tags={"highway": True}, dist=800)
                    if not gdf.empty:
                        if 'name' in gdf.columns:
                            target_gdf = gdf[gdf['name'].str.contains(s_name, case=False, na=False)]
                        else:
                            target_gdf = gdf

                        if not target_gdf.empty:
                            stadt = "Unbekannt"
                            for col in ['addr:suburb', 'addr:city', 'municipality']:
                                if col in target_gdf.columns and target_gdf[col].dropna().any():
                                    stadt = target_gdf[col].dropna().iloc[0]
                                    break
                            
                            geo = folium.GeoJson(target_gdf, style_function=lambda x: {'color':'red','weight':8})
                            temp_ort_sammlung[stadt].append(geo)
                except: continue
            
            if temp_ort_sammlung:
                # Ergebnisse im Session State speichern
                st.session_state.ort_sammlung = temp_ort_sammlung
                st.session_state.maps_ready = True
                
                # ZIP im Hintergrund erstellen
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for ort, elemente in temp_ort_sammlung.items():
                        m_temp = folium.Map(location=[50.81, 8.77], zoom_start=14)
                        for e in elemente: e.add_to(m_temp)
                        zf.writestr(f"Karte_{ort}.html", m_temp._repr_html_())
                st.session_state.zip_data = zip_buffer.getvalue()
                status.update(label="✅ Berechnung abgeschlossen!", state="complete")
            else:
                st.error("Keine passenden Straßen gefunden.")

# --- 5. ANZEIGE DER ERGEBNISSE (Dauerhaft) ---
if st.session_state.maps_ready:
    st.divider()
    st.write("### 👁️ Deine generierten Karten:")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        for ort, elemente in st.session_state.ort_sammlung.items():
            st.write(f"**📍 Ort: {ort}**")
            # Neue Karte für die Anzeige
            m_display = folium.Map(location=[50.81, 8.77], zoom_start=14)
            for e in elemente:
                e.add_to(m_display)
            st_folium(m_display, width=700, height=400, key=f"perm_map_{ort}")
            st.divider()

    with col2:
        st.write("### 📥 Download")
        st.download_button(
            label="PAKET ALS ZIP LADEN",
            data=st.session_state.zip_data,
            file_name="INTEGRAL_Export.zip",
            mime="application/zip"
        )
        if st.button("Ergebnisse löschen"):
            st.session_state.maps_ready = False
            st.rerun()

st.markdown("<p style='text-align: right; color: gray; font-size: 10px;'>© Maus</p>", unsafe_allow_html=True)
