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

# --- 2. AUDIO & VOLLBILD-FIX ---
def spiele_audio(typ="erfolg"):
    sounds = {"erfolg": "https://codeskulptor-demos.commondatastorage.googleapis.com/descent/gotitem.mp3",
              "fehler": "https://www.myinstants.com/media/sounds/nelson-haha.mp3"}
    st.components.v1.html(f'<audio autoplay><source src="{sounds[typ]}" type="audio/mpeg"></audio>', height=0)

def erzeuge_vollbild_link(html_content, label):
    # Stabilere Methode via Blob-Simulation
    b64 = base64.b64encode(html_content.encode()).decode()
    href = f'data:text/html;base64,{b64}'
    return f'''<a href="{href}" target="_blank" style="text-decoration:none;">
                <button style="width:100%; background:linear-gradient(90deg, #00d4ff, #0055ff); 
                color:white; border:none; padding:10px; border-radius:10px; cursor:pointer; 
                font-family:sans-serif; font-weight:bold; margin-bottom:10px;">
                🖥️ {label} IM VOLLBILD
                </button></a>'''

# --- 3. DESIGN ---
def apply_style(dark, bg):
    bg_img = ""
    if bg and os.path.exists('hintergrund.png'):
        with open('hintergrund.png', 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        bg_img = f'background-image: url("data:image/png;base64,{data}");'
    
    panel = "rgba(10,10,10,0.7)" if dark else "rgba(255,255,255,0.75)"
    st.markdown(f"""
        <style>
        .stApp {{ {bg_img} background-size: cover; background-attachment: fixed; }}
        .block-container {{ background: {panel}; backdrop-filter: blur(20px); border-radius: 30px; padding: 2rem !important; }}
        .ort-box {{ border: 2px solid #00d4ff; background: rgba(0,212,255,0.05); border-radius: 20px; padding: 20px; margin-bottom: 30px; }}
        h2 {{ color: #00d4ff !important; border-bottom: 1px solid #00d4ff; padding-bottom: 10px; }}
        </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="MM3000 V9.5", layout="wide")
ist_dunkel = st.sidebar.toggle("Cyber Modus", True)
anwenden_bg = st.sidebar.toggle("Hintergrund", True)
apply_style(ist_dunkel, anwenden_bg)

st.title("MAPMARKER 3000 — V9.5")

input_text = st.text_area("ZIEL-EINGABE:", height=150)

if st.button("🚀 ANALYSIEREN & SORTIEREN"):
    if input_text:
        eintraege = [s.strip() for s in input_text.split('\n') if s.strip()]
        ergebnisse = defaultdict(list)
        fehler = []
        
        prog = st.progress(0)
        status = st.empty()
        
        for i, eintrag in enumerate(eintraege):
            status.write(f"Verarbeite: {eintrag}...")
            prog.progress((i+1)/len(eintraege))
            
            try:
                q = f"{eintrag}, Landkreis Marburg-Biedenkopf, Germany"
                gdf = ox.features_from_address(q, tags={"highway": True}, dist=1000)
                
                if not gdf.empty:
                    # Hierarchie: Ortsteil > Stadt > Gemeinde
                    ort = "Unbekannt"
                    for schluessel in ['addr:suburb', 'suburb', 'addr:city', 'municipality']:
                        if schluessel in gdf.columns and gdf[schluessel].dropna().any():
                            ort = gdf[schluessel].dropna().iloc[0]
                            break
                    
                    m = folium.Map(location=[50.81, 8.77], zoom_start=16, tiles='cartodbdark_matter' if ist_dunkel else 'cartodbpositron')
                    
                    # Straße finden (Regex-Bereinigung für Hausnummern)
                    str_name = re.sub(r'\s+\d+.*', '', eintrag)
                    target = gdf[gdf['name'].str.contains(str_name, case=False, na=False)] if 'name' in gdf.columns else gdf
                    folium.GeoJson(target, style_function=lambda x: {'color':'#ff0055','weight':8}).add_to(m)
                    
                    # Hausnummer-Fahne
                    if any(char.isdigit() for char in eintrag):
                        p_gdf = ox.geocode_to_gdf(q)
                        if not p_gdf.empty:
                            loc = p_gdf.iloc[0].geometry.centroid
                            folium.Marker([loc.y, loc.x], icon=folium.Icon(color='blue', icon='flag')).add_to(m)
                            m.location = [loc.y, loc.x]
                    
                    ergebnisse[ort].append((eintrag, m._repr_html_()))
                else: fehler.append(eintrag)
            except: 
                fehler.append(eintrag)
                continue
        
        status.empty()
        prog.empty()

        if ergebnisse:
            spiele_audio("erfolg")
            for ortsteil, karten in ergebnisse.items():
                st.markdown(f'<div class="ort-box"><h2>📍 {ortsteil}</h2>', unsafe_allow_html=True)
                cols = st.columns(2)
                for idx, (name, html) in enumerate(karten):
                    with cols[idx % 2]:
                        st.write(f"**{name}**")
                        # Der gefixte Vollbild-Button
                        st.markdown(erzeuge_vollbild_link(html, name), unsafe_allow_html=True)
                        st.components.v1.html(html, height=400)
                st.markdown('</div>', unsafe_allow_html=True)
        
        if fehler:
            spiele_audio("fehler")
            st.error(f"Nicht gefunden: {', '.join(fehler)}")
