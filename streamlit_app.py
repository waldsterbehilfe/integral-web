import streamlit as st
import osmnx as ox
import folium
import io, zipfile, base64, os, re, time
from collections import defaultdict

# --- 1. ENGINE & TURBO-CACHE ---
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

# --- 2. MULTI-AUDIO LOGIK ---
def play_audio(sound_type="success"):
    # Links zu den Sounds
    sounds = {
        "success": "https://codeskulptor-demos.commondatastorage.googleapis.com/descent/gotitem.mp3",
        "fail": "https://www.myinstants.com/media/sounds/nelson-haha.mp3" # Der "Nananaaa" / Ha-Ha Effekt
    }
    audio_html = f"""
    <audio autoplay>
      <source src="{sounds[sound_type]}" type="audio/mpeg">
    </audio>
    """
    st.components.v1.html(audio_html, height=0)

# --- 3. THE "ULTIMATE" DESIGN ENGINE ---
def apply_ultra_style(dark_mode, show_bg):
    bg_img = ""
    if show_bg and os.path.exists('hintergrund.png'):
        with open('hintergrund.png', 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        bg_img = f'background-image: url("data:image/png;base64,{data}");'
    
    accent_color = "#00d4ff" if dark_mode else "#1976d2"
    panel_bg = "rgba(10, 10, 10, 0.7)" if dark_mode else "rgba(255, 255, 255, 0.75)"
    
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&display=swap');
        .stApp {{ {bg_img} background-size: cover; background-attachment: fixed; background-position: center; }}
        .block-container {{ 
            background: {panel_bg}; backdrop-filter: blur(25px); border-radius: 30px; padding: 3rem !important;
            margin-top: 2rem; border: 1px solid rgba(255, 255, 255, 0.1); 
            box-shadow: 0 20px 60px rgba(0,0,0,0.7);
        }}
        .ort-container {{ border-left: 5px solid {accent_color}; background: rgba(0, 212, 255, 0.05); border-radius: 15px; padding: 25px; margin-bottom: 30px; }}
        h1, h2, h3 {{ font-family: 'Orbitron', sans-serif; color: {accent_color} !important; text-transform: uppercase; }}
        .stButton>button {{ background: linear-gradient(90deg, {accent_color}, #0055ff); color: white; border-radius: 15px; font-weight: bold; border: none; height: 3.5em; }}
        </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="MAPMARKER 3000 GOLD", layout="wide")

# Sidebar
st.sidebar.markdown(f"<h2 style='text-align:center;'>🚀 COMMAND</h2>", unsafe_allow_html=True)
is_dark = st.sidebar.toggle("Cyber Mode", value=True)
show_bg = st.sidebar.toggle("Visualizer", value=True)
apply_ultra_style(is_dark, show_bg)
st.sidebar.metric("Database", f"{cache_count} Streets")

st.title("MAPMARKER 3000")
st.caption("Ultimate Gold Edition // Intelligent Audio Feedback")

# Clipboard Input
input_text = st.text_area("TARGET INPUT", height=150, placeholder="Eingabe hier...")
clipboard_js = """<script>async function p(){const t=await navigator.clipboard.readText();const a=window.parent.document.querySelector('textarea');if(a){a.value=t;a.dispatchEvent(new Event('input',{{bubbles:true}}));}}</script><button onclick="p()" style="background:rgba(0,212,255,0.1); color:#00d4ff; border:1px solid #00d4ff; padding:10px; border-radius:12px; cursor:pointer; width:100%; font-family:'Orbitron';">📋 SYNC CLIPBOARD</button>"""
st.components.v1.html(clipboard_js, height=60)

if st.button("⚡ EXECUTE PROCESS"):
    if input_text:
        eintraege = [s.strip() for s in input_text.split('\n') if s.strip()]
        res_dict = defaultdict(list)
        errors = []
        
        with st.status("INITIALIZING SYSTEM...", expanded=True) as status:
            for entry in eintraege:
                try:
                    match = re.match(r"(.+?)\s+(\d+[a-zA-Z]?)", entry)
                    street = match.group(1).strip() if match else entry
                    num = match.group(2).strip() if match else None

                    q = f"{entry}, Landkreis Marburg-Biedenkopf, Germany"
                    gdf = ox.features_from_address(q, tags={"highway": True}, dist=800)
                    
                    if not gdf.empty:
                        location = "Landkreis"
                        for col in ['addr:suburb', 'addr:city', 'municipality']:
                            if col in gdf.columns and gdf[col].dropna().any():
                                location = gdf[col].dropna().iloc[0]
                                break

                        m = folium.Map(location=[50.81, 8.77], zoom_start=16, tiles='cartodbpositron' if not is_dark else 'cartodbdark_matter')
                        target = gdf[gdf['name'].str.contains(street, case=False, na=False)] if 'name' in gdf.columns else gdf
                        folium.GeoJson(target, style_function=lambda x: {'color':'#ff0055','weight':7, 'opacity':0.8}).add_to(m)

                        if num:
                            p_gdf = ox.geocode_to_gdf(q)
                            if not p_gdf.empty:
                                lat, lon = p_gdf.iloc[0].geometry.centroid.y, p_gdf.iloc[0].geometry.centroid.x
                                folium.Marker([lat, lon], icon=folium.Icon(color='blue', icon='flag')).add_to(m)
                                m.location = [lat, lon]

                        res_dict[location].append((entry, m._repr_html_()))
                    else:
                        errors.append(entry)
                except: 
                    errors.append(entry)
                    continue
            
            if res_dict:
                status.update(label="PROCESS COMPLETE", state="complete")
                play_audio("success")
            if errors:
                status.update(label=f"WARNING: {len(errors)} FAILED", state="error")
                play_audio("fail")
        
        # Ergebnisanzeige
        if res_dict:
            for area, maps in res_dict.items():
                st.markdown(f'<div class="ort-container"><h3>📡 AREA: {area}</h3>', unsafe_allow_html=True)
                grid = st.columns(2)
                for idx, (name, html) in enumerate(maps):
                    with grid[idx % 2]:
                        st.markdown(f"**Target:** `{name}`")
                        b64 = base64.b64encode(html.encode()).decode()
                        st.markdown(f'<a href="data:text/html;base64,{b64}" target="_blank"><button style="width:100%; background:rgba(0,212,255,0.2); color:#00d4ff; border:1px solid #00d4ff; padding:5px; border-radius:8px; cursor:pointer;">VIEW FULLSCREEN</button></a>', unsafe_allow_html=True)
                        st.components.v1.html(html, height=400)
                st.markdown('</div>', unsafe_allow_html=True)
        
        if errors:
            st.error(f"Folgende Einträge wurden nicht im Cache oder Online gefunden: {', '.join(errors)}")
