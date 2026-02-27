import streamlit as st
import osmnx as ox
import folium
import io, zipfile, base64, os, re, time
from collections import defaultdict

# --- 1. ENGINE & CACHE ---
CACHE_ZIP = "geocache.zip"
CACHE_DIR = "geocache"

@st.cache_resource
def power_up_engine():
    if os.path.exists(CACHE_ZIP) and not os.path.exists(CACHE_DIR):
        with zipfile.ZipFile(CACHE_ZIP, 'r') as zip_ref:
            zip_ref.extractall(".")
    if os.path.exists(CACHE_DIR):
        ox.settings.use_cache = True
        ox.settings.cache_folder = f"./{CACHE_DIR}"
        return len(os.listdir(CACHE_DIR))
    return 0

cache_count = power_up_engine()

# --- 2. MULTIMEDIA & VOLLBILD ---
def spiele_audio(typ="erfolg"):
    sounds = {"erfolg": "https://codeskulptor-demos.commondatastorage.googleapis.com/descent/gotitem.mp3",
              "fehler": "https://www.myinstants.com/media/sounds/nelson-haha.mp3"}
    st.components.v1.html(f'<audio autoplay><source src="{sounds[typ]}" type="audio/mpeg"></audio>', height=0)

def erzeuge_link(html_code, name):
    b64 = base64.b64encode(html_code.encode()).decode()
    return f'''<a href="data:text/html;base64,{b64}" target="_blank" style="text-decoration:none;">
                <div style="background: linear-gradient(135deg, #00d4ff 0%, #0055ff 100%); 
                color: white; padding: 12px; border-radius: 12px; text-align: center; 
                font-weight: bold; font-family: 'Orbitron', sans-serif; letter-spacing: 1px;
                box-shadow: 0 4px 15px rgba(0, 212, 255, 0.4); margin-bottom: 15px; cursor: pointer;">
                🖥️ VOLLBILD: {name.upper()}
                </div></a>'''

# --- 3. DAS TITAN DESIGN ---
def apply_titan_style(dark, bg_active):
    bg_css = ""
    if bg_active and os.path.exists('hintergrund.png'):
        with open('hintergrund.png', 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        bg_css = f'background-image: url("data:image/png;base64,{data}");'

    akzent = "#00d4ff"
    panel_bg = "rgba(10, 10, 15, 0.75)" if dark else "rgba(255, 255, 255, 0.8)"
    text_col = "#ffffff" if dark else "#111111"

    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@500;700&display=swap');
        
        .stApp {{ 
            {bg_css} 
            background-size: cover; 
            background-attachment: fixed; 
            background-position: center;
        }}
        
        .block-container {{
            background: {panel_bg};
            backdrop-filter: blur(30px) saturate(160%);
            border-radius: 40px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 3rem !important;
            box-shadow: 0 40px 100px rgba(0,0,0,0.9);
            color: {text_col};
        }}

        .ort-box-titan {{
            background: rgba(0, 212, 255, 0.05);
            border-radius: 25px;
            padding: 30px;
            margin-bottom: 50px;
            border-top: 2px solid {akzent};
            box-shadow: inset 0 0 20px rgba(0, 212, 255, 0.05);
        }}

        .titan-header {{
            font-family: 'Orbitron', sans-serif;
            color: {akzent};
            font-size: 1.8rem;
            text-shadow: 0 0 20px rgba(0, 212, 255, 0.6);
            margin-bottom: 25px;
            text-transform: uppercase;
        }}

        .stTextArea textarea {{
            background: rgba(0, 0, 0, 0.3) !important;
            border: 1px solid rgba(0, 212, 255, 0.3) !important;
            border-radius: 15px !important;
            color: {akzent} !important;
            font-family: 'Rajdhani', sans-serif;
            font-size: 1.2rem;
        }}

        .stButton button {{
            width: 100%;
            height: 4rem;
            border-radius: 20px !important;
            background: linear-gradient(90deg, #0055ff, #00d4ff) !important;
            font-family: 'Orbitron', sans-serif !important;
            font-size: 1.2rem !important;
            transition: 0.4s !important;
        }}
        
        .stButton button:hover {{
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(0, 212, 255, 0.5) !important;
        }}
        </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="MAPMARKER TITAN", layout="wide")
ist_dunkel = st.sidebar.toggle("Cyber-Modus Aktiv", True)
bg_an = st.sidebar.toggle("Hintergrund-Sättigung", True)
apply_titan_style(ist_dunkel, bg_an)

st.sidebar.markdown(f"---")
st.sidebar.metric("SYSTEM-CACHE", f"{cache_count} OBJEKTE")

# Hauptseite
st.title("MAPMARKER 3000 — TITAN")
st.markdown("---")

input_text = st.text_area("ZIEL-EINGABE (Eine Adresse pro Zeile):", height=180)

if st.button("PROZESS STARTEN"):
    if input_text:
        eintraege = [s.strip() for s in input_text.split('\n') if s.strip()]
        ergebnisse = defaultdict(list)
        fehler = []
        
        prog = st.progress(0)
        status_bar = st.empty()
        
        for i, eintrag in enumerate(eintraege):
            status_bar.markdown(f"📡 **Scanne Sektor:** `{eintrag}`")
            prog.progress((i+1)/len(eintraege))
            
            try:
                q = f"{eintrag}, Landkreis Marburg-Biedenkopf, Germany"
                gdf = ox.features_from_address(q, tags={"highway": True}, dist=1000)
                
                if not gdf.empty:
                    # Ortsteil-Logik
                    ortsteil = "Landkreis"
                    for key in ['addr:suburb', 'suburb', 'addr:city', 'municipality']:
                        if key in gdf.columns and gdf[key].dropna().any():
                            ortsteil = gdf[key].dropna().iloc[0]
                            break
                    
                    # Karten-Stil
                    m = folium.Map(location=[50.81, 8.77], zoom_start=16, 
                                   tiles='cartodbdark_matter' if ist_dunkel else 'cartodbpositron')
                    
                    street_clean = re.sub(r'\s+\d+.*', '', eintrag)
                    target = gdf[gdf['name'].str.contains(street_clean, case=False, na=False)] if 'name' in gdf.columns else gdf
                    folium.GeoJson(target, style_function=lambda x: {'color':'#ff0055','weight':10, 'opacity':0.8}).add_to(m)
                    
                    if any(c.isdigit() for c in eintrag):
                        p_gdf = ox.geocode_to_gdf(q)
                        if not p_gdf.empty:
                            loc = p_gdf.iloc[0].geometry.centroid
                            folium.Marker([loc.y, loc.x], icon=folium.Icon(color='blue', icon='flag')).add_to(m)
                            m.location = [loc.y, loc.x]
                    
                    ergebnisse[ortsteil].append((eintrag, m._repr_html_()))
                else: fehler.append(eintrag)
            except:
                fehler.append(eintrag)
                continue
        
        status_bar.empty()
        prog.empty()

        if ergebnisse:
            spiele_audio("erfolg")
            # Alphabetisch sortierte Ortsteile für bessere Übersicht
            for ortsteil in sorted(ergebnisse.keys()):
                karten = ergebnisse[ortsteil]
                st.markdown(f'<div class="ort-box-titan"><h2 class="titan-header">📍 SEKTOR: {ortsteil}</h2>', unsafe_allow_html=True)
                
                cols = st.columns(2)
                for idx, (name, html) in enumerate(karten):
                    with cols[idx % 2]:
                        st.markdown(f"<span style='font-family:Rajdhani; font-size:1.3rem; color:#00d4ff;'>◆ {name}</span>", unsafe_allow_html=True)
                        st.markdown(erzeuge_link(html, name), unsafe_allow_html=True)
                        st.components.v1.html(html, height=450)
                st.markdown('</div>', unsafe_allow_html=True)
        
        if fehler:
            spiele_audio("fehler")
            st.error(f"Folgende Sektoren konnten nicht geladen werden: {', '.join(fehler)}")
    else:
        st.warning("BITTE DATEN EINGEBEN.")
