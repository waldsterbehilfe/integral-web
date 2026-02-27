import streamlit as st
import osmnx as ox
import folium
from streamlit_folium import st_folium
import io, zipfile, base64, os
from collections import defaultdict

# --- 1. TURBO-CACHE SYSTEM ---
# Wir definieren einen festen Ordner für die Straßendaten
CACHE_NAME = "geocache"
if not os.path.exists(CACHE_NAME):
    os.makedirs(CACHE_NAME)

# Hier wird der Speicher aktiviert
ox.settings.use_cache = True
ox.settings.cache_folder = f"./{CACHE_NAME}"
ox.settings.log_console = False # Macht das Programm schneller

# --- 2. DESIGN & MODUS ---
def apply_gold_design(dark):
    bg_img = ""
    if os.path.exists('hintergrund.png'):
        with open('hintergrund.png', 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        bg_img = f'background-image: url("data:image/png;base64,{data}"); background-size: cover; background-attachment: fixed;'
    
    panel_bg = "rgba(25, 25, 25, 0.95)" if dark else "rgba(255, 255, 255, 0.95)"
    text_col = "white" if dark else "#1a1a1a"
    
    st.markdown(f"""
        <style>
        .stApp {{ {bg_img} }}
        .block-container {{ background: {panel_bg}; color: {text_col}; border-radius: 20px; padding: 2.5rem; }}
        .stButton>button {{ background: #1976d2; color: white; border-radius: 10px; font-weight: bold; width: 100%; height: 3em; }}
        </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="INTEGRAL TURBO-CACHE", layout="wide")

# Sidebar
st.sidebar.title("Optionen")
choice = st.sidebar.radio("Design:", ["Dark Mode", "Light Mode"])
apply_design_status = apply_gold_design(dark=(choice == "Dark Mode"))

st.title("🗺️ INTEGRAL GOLD v6.0")
st.caption("Status: Turbo-Cache ist AKTIV (Wiederholte Suchen gehen blitzschnell)")

# --- 3. VERARBEITUNG MIT SPEICHER-PRÜFUNG ---
input_text = st.text_area("Straßenliste:", height=200, placeholder="Straße eingeben...")

if st.button("KARTEN MIT CACHE GENERIEREN"):
    strassen = [s.strip() for s in input_text.split('\n') if s.strip()]
    
    if strassen:
        with st.status("Verarbeite Straßen...", expanded=True) as status:
            res_dict = defaultdict(list)
            
            for s in strassen:
                # Das Programm prüft hier automatisch erst den Ordner 'geocache'
                try:
                    q = f"{s}, Landkreis Marburg-Biedenkopf, Germany"
                    
                    # Suche (greift auf den Cache zu, wenn vorhanden)
                    gdf = ox.features_from_address(q, tags={"highway": True}, dist=800)
                    
                    if not gdf.empty:
                        target = gdf[gdf['name'].str.contains(s, case=False, na=False)] if 'name' in gdf.columns else gdf
                        stadt = "Ort"
                        for col in ['addr:suburb', 'addr:city', 'municipality']:
                            if col in target.columns and target[col].dropna().any():
                                stadt = target[col].dropna().iloc[0]
                                break
                        geo = folium.GeoJson(target, style_function=lambda x: {'color':'red','weight':8})
                        res_dict[stadt].append(geo)
                except: continue
            
            if res_dict:
                status.update(label="✅ Fertig (aus Cache geladen)!", state="complete")
                # Anzeige Logik...
                for ort, elemente in res_dict.items():
                    st.write(f"**📍 {ort}**")
                    m = folium.Map(location=[50.81, 8.77], zoom_start=14)
                    for e in elemente: e.add_to(m)
                    st_folium(m, width=800, height=400, key=f"map_{ort}")
    else:
        st.warning("Keine Straßen eingegeben.")
