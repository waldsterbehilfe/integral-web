import streamlit as st
import osmnx as ox
import folium
from streamlit_folium import st_folium
import io, zipfile, base64, os
from collections import defaultdict

# --- TURBO-CACHE & SYSTEM ---
CACHE_DIR = "geocache"
if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
ox.settings.use_cache = True
ox.settings.cache_folder = f"./{CACHE_DIR}"

# --- DESIGN ---
def apply_gold_design():
    if os.path.exists('hintergrund.png'):
        with open('hintergrund.png', 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        st.markdown(f"""
            <style>
            .stApp {{ background-image: url("data:image/png;base64,{data}"); background-size: cover; background-attachment: fixed; }}
            .block-container {{ background: rgba(25, 25, 25, 0.95); color: white; border-radius: 20px; padding: 2rem; }}
            </style>
        """, unsafe_allow_html=True)

st.set_page_config(page_title="INTEGRAL PRO", layout="wide")
apply_gold_design()

# --- SESSION STATE (Speicher) ---
if 'html_maps' not in st.session_state:
    st.session_state.html_maps = {}

st.title("🗺️ INTEGRAL GOLD v7.0")

input_text = st.text_area("Straßenliste:", height=150)

if st.button("KARTEN GENERIEREN"):
    strassen = [s.strip() for s in input_text.split('\n') if s.strip()]
    if strassen:
        with st.status("Erstelle hochauflösende Karten...", expanded=True):
            res_dict = defaultdict(list)
            for s in strassen:
                try:
                    q = f"{s}, Landkreis Marburg-Biedenkopf, Germany"
                    gdf = ox.features_from_address(q, tags={"highway": True}, dist=800)
                    if not gdf.empty:
                        target = gdf[gdf['name'].str.contains(s, case=False, na=False)] if 'name' in gdf.columns else gdf
                        stadt = "Unbekannt"
                        for col in ['addr:suburb', 'addr:city', 'municipality']:
                            if col in target.columns and target[col].dropna().any():
                                stadt = target[col].dropna().iloc[0]
                                break
                        geo = folium.GeoJson(target, style_function=lambda x: {'color':'red','weight':8})
                        res_dict[stadt].append(geo)
                except: continue
            
            # Karten im Speicher für "neue Seite" ablegen
            for ort, elemente in res_dict.items():
                m = folium.Map(location=[50.81, 8.77], zoom_start=14)
                for e in elemente: e.add_to(m)
                st.session_state.html_maps[ort] = m._repr_html_()

# --- AUSGABE ALS "NEUE SEITE" ---
if st.session_state.html_maps:
    st.divider()
    st.subheader("📍 Generierte Ergebnisse")
    
    tabs = st.tabs(list(st.session_state.html_maps.keys()))
    
    for i, (ort, html_code) in enumerate(st.session_state.html_maps.items()):
        with tabs[i]:
            # Button zum Öffnen in echtem neuen Tab (HTML-Trick)
            b64 = base64.b64encode(html_code.encode()).decode()
            href = f'<a href="data:text/html;base64,{b64}" target="_blank" style="text-decoration: none;"><button style="background-color: #1976d2; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin-bottom: 10px;">➔ In neuem Tab öffnen (Vollbild)</button></a>'
            st.markdown(href, unsafe_allow_html=True)
            
            # Anzeige direkt in der App (als Backup)
            st.components.v1.html(html_code, height=600, scrolling=True)

    if st.button("Alle Ergebnisse löschen"):
        st.session_state.html_maps = {}
        st.rerun()
