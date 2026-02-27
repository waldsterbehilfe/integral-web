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

# --- 2. INTELLIGENTE TEXT-KORREKTUR ---
def bereinige_adresse(text):
    t = text.strip()
    t = re.sub(r'(?i)\bstr\b\.?', 'Straße', t)
    t = re.sub(r'(?i)strase\b', 'Straße', t)
    t = re.sub(r'(?i)strasse\b', 'Straße', t)
    t = re.sub(r'(?i)(\w+)str\b\.?', r'\1straße', t)
    t = re.sub(r'\s+', ' ', t)
    return t

# --- 3. DESIGN & ANIMATIONEN ---
def apply_titan_style(dark, bg_active):
    bg_css = ""
    if bg_active and os.path.exists('hintergrund.png'):
        with open('hintergrund.png', 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        bg_css = f'background-image: url("data:image/png;base64,{data}");'
    
    akzent = "#00d4ff"
    panel_bg = "rgba(10, 10, 15, 0.75)" if dark else "rgba(235, 238, 245, 0.85)"
    text_col = "#ffffff" if dark else "#2c3e50"

    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@500;700&display=swap');
        .stApp {{ {bg_css} background-size: cover; background-attachment: fixed; background-position: center; }}
        .block-container {{ background: {panel_bg}; backdrop-filter: blur(30px); border-radius: 40px; padding: 3rem !important; color: {text_col}; }}
        
        /* ROTIERENDES SCAN-ICON ANIMATION */
        @keyframes rotate-vortex {{
            from {{ transform: rotate(0deg); }}
            to {{ transform: rotate(360deg); }}
        }}
        @keyframes pulse-glow {{
            0% {{ opacity: 0.4; transform: scale(0.9); }}
            50% {{ opacity: 1; transform: scale(1.1); }}
            100% {{ opacity: 0.4; transform: scale(0.9); }}
        }}
        .vortex-loader {{
            width: 50px; height: 50px;
            border: 3px solid transparent;
            border-top: 3px solid {akzent};
            border-radius: 50%;
            display: inline-block;
            animation: rotate-vortex 1s linear infinite;
            margin-right: 20px;
            vertical-align: middle;
            box-shadow: 0 0 15px {akzent};
        }}
        .status-container {{
            background: rgba(0, 212, 255, 0.1);
            padding: 20px; border-radius: 20px;
            border: 1px solid {akzent};
            margin-bottom: 20px;
        }}

        .ort-box-titan {{ background: rgba(0, 212, 255, 0.05); border-radius: 25px; padding: 30px; margin-bottom: 50px; border-top: 3px solid {akzent}; }}
        .titan-header {{ font-family: 'Orbitron', sans-serif; color: {akzent}; font-size: 1.8rem; }}
        .stButton button {{ width: 100%; height: 4rem; border-radius: 20px; background: linear-gradient(90deg, #0055ff, #00d4ff) !important; font-family: 'Orbitron'; font-size: 1.2rem; }}
        </style>
    """, unsafe_allow_html=True)

def spiele_audio(typ="erfolg"):
    sounds = {"erfolg": "https://codeskulptor-demos.commondatastorage.googleapis.com/descent/gotitem.mp3",
              "fehler": "https://www.myinstants.com/media/sounds/nelson-haha.mp3"}
    st.components.v1.html(f'<audio autoplay><source src="{sounds[typ]}" type="audio/mpeg"></audio>', height=0)

def erzeuge_link(html_code, name):
    b64 = base64.b64encode(html_code.encode()).decode()
    return f'''<a href="data:text/html;base64,{b64}" target="_blank" style="text-decoration:none;">
                <div style="background: linear-gradient(135deg, #00d4ff 0%, #0055ff 100%); 
                color: white; padding: 12px; border-radius: 12px; text-align: center; font-weight: bold; font-family: 'Orbitron';">
                🖥️ VOLLBILD: {name.upper()}
                </div></a>'''

# --- APP START ---
st.set_page_config(page_title="TITAN V10.4", layout="wide")
ist_dunkel = st.sidebar.toggle("Cyber-Modus (Dunkel)", True)
bg_an = st.sidebar.toggle("Hintergrund-Sättigung", True)
apply_titan_style(ist_dunkel, bg_an)

st.title("MAPMARKER 3000 — TITAN")
st.caption("Version 10.4 // Dynamischer Sektor-Scanner")

input_text = st.text_area("ZIEL-EINGABE:", height=180, placeholder="Eingabe hier...")

if st.button("SYSTEM-ANALYSE STARTEN"):
    if input_text:
        rohe_eintraege = [s.strip() for s in input_text.split('\n') if s.strip()]
        gesamt = len(rohe_eintraege)
        ergebnisse = defaultdict(list)
        fehler = []
        
        # --- ANIMIERTER STATUS BEREICH ---
        status_box = st.empty()
        prog_bar = st.progress(0)
        
        for i, roh_eintrag in enumerate(rohe_eintraege):
            aktuelle_nr = i + 1
            eintrag = bereinige_adresse(roh_eintrag)
            
            # Das drehende "Ding" (CSS Vortex)
            status_box.markdown(f"""
                <div class="status-container">
                    <div class="vortex-loader"></div>
                    <span style="font-family:'Orbitron'; font-size:1.2rem; color:#00d4ff;">
                        SCANE SEKTOR {aktuelle_nr} VON {gesamt}: <b>{eintrag}</b>
                    </span>
                </div>
            """, unsafe_allow_html=True)
            
            prog_bar.progress(aktuelle_nr / gesamt)
            
            try:
                q = f"{eintrag}, Landkreis Marburg-Biedenkopf, Germany"
                gdf = ox.features_from_address(q, tags={"highway": True}, dist=1000)
                
                if not gdf.empty:
                    ortsteil = "Landkreis"
                    for key in ['addr:suburb', 'suburb', 'addr:city', 'municipality']:
                        if key in gdf.columns and gdf[key].dropna().any():
                            ortsteil = gdf[key].dropna().iloc[0]
                            break
                    
                    m = folium.Map(location=[50.81, 8.77], zoom_start=16, 
                                   tiles='cartodbdark_matter' if ist_dunkel else 'cartodbpositron')
                    
                    str_clean = re.sub(r'\s+\d+.*', '', eintrag)
                    target = gdf[gdf['name'].str.contains(str_clean, case=False, na=False)] if 'name' in gdf.columns else gdf
                    folium.GeoJson(target, style_function=lambda x: {'color':'#ff0055','weight':10}).add_to(m)
                    
                    if any(c.isdigit() for c in eintrag):
                        p_gdf = ox.geocode_to_gdf(q)
                        if not p_gdf.empty:
                            loc = p_gdf.iloc[0].geometry.centroid
                            folium.Marker([loc.y, loc.x], icon=folium.Icon(color='blue', icon='flag')).add_to(m)
                            m.location = [loc.y, loc.x]
                    
                    ergebnisse[ortsteil].append((eintrag, m._repr_html_()))
                else: fehler.append(roh_eintrag)
            except:
                fehler.append(roh_eintrag)
                continue
        
        status_box.empty()
        prog_bar.empty()

        if ergebnisse:
            spiele_audio("erfolg")
            for ortsteil in sorted(ergebnisse.keys()):
                st.markdown(f'<div class="ort-box-titan"><h2 class="titan-header">📍 SEKTOR: {ortsteil}</h2>', unsafe_allow_html=True)
                cols = st.columns(2)
                for idx, (name, html) in enumerate(ergebnisse[ortsteil]):
                    with cols[idx % 2]:
                        st.markdown(f"**Ziel:** `{name}`")
                        st.markdown(erzeuge_link(html, name), unsafe_allow_html=True)
                        st.components.v1.html(html, height=450)
                st.markdown('</div>', unsafe_allow_html=True)
        
        if fehler:
            spiele_audio("fehler")
            st.error(f"Nicht gefunden: {', '.join(fehler)}")
