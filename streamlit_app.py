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

# --- 2. THE "ULTIMATE" DESIGN ENGINE ---
def apply_ultra_style(dark_mode, show_bg):
    bg_img = ""
    if show_bg and os.path.exists('hintergrund.png'):
        with open('hintergrund.png', 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        bg_img = f'background-image: url("data:image/png;base64,{data}");'
    
    accent_color = "#00d4ff" if dark_mode else "#1976d2"
    panel_bg = "rgba(10, 10, 10, 0.6)" if dark_mode else "rgba(255, 255, 255, 0.6)"
    
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&display=swap');
        
        .stApp {{
            {bg_img}
            background-size: cover;
            background-attachment: fixed;
            background-position: center;
        }}
        
        .block-container {{
            background: {panel_bg};
            backdrop-filter: blur(20px) saturate(180%);
            -webkit-backdrop-filter: blur(20px) saturate(180%);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 30px;
            padding: 3rem !important;
            margin-top: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 25px 50px rgba(0,0,0,0.6);
        }}
        
        .ort-container {{
            background: rgba(0, 212, 255, 0.03);
            border-left: 5px solid {accent_color};
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 30px;
            transition: 0.3s;
        }}
        
        .ort-container:hover {{
            background: rgba(0, 212, 255, 0.07);
            transform: translateX(5px);
        }}

        h1, h2, h3 {{
            font-family: 'Orbitron', sans-serif;
            letter-spacing: 2px;
            color: {accent_color} !important;
            text-shadow: 0 0 10px rgba(0, 212, 255, 0.5);
        }}
        
        .stButton>button {{
            background: linear-gradient(90deg, {accent_color}, #0055ff);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 0.75rem;
            font-weight: bold;
            transition: 0.3s;
            text-transform: uppercase;
        }}
        
        .stButton>button:hover {{
            box-shadow: 0 0 20px {accent_color};
            transform: scale(1.02);
        }}
        </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="MAPMARKER 3000 ULTIMATE", layout="wide")

# Sidebar - Command Center
st.sidebar.markdown(f"<h2 style='text-align:center;'>🚀 COMMAND</h2>", unsafe_allow_html=True)
is_dark = st.sidebar.toggle("Cyber Mode", value=True)
show_bg = st.sidebar.toggle("Visualizer", value=True)
apply_ultra_style(is_dark, show_bg)

st.sidebar.divider()
st.sidebar.metric("Database", f"{cache_count} Streets", help="Anzahl der lokal gespeicherten Straßendaten.")

# Main UI
st.title("MAPMARKER 3000")
st.caption("Ultimate Gold Edition // Automated Mapping System")

# Clipboard Magic
cb_col1, cb_col2 = st.columns([2, 1])
with cb_col1:
    input_text = st.text_area("TARGET INPUT", height=150, placeholder="Eingabe hier oder Button nutzen...")
with cb_col2:
    st.markdown("<br>", unsafe_allow_html=True)
    clipboard_js = """<script>async function p(){const t=await navigator.clipboard.readText();const a=window.parent.document.querySelector('textarea');if(a){a.value=t;a.dispatchEvent(new Event('input',{{bubbles:true}}));}}</script><button onclick="p()" style="background:rgba(0,212,255,0.1); color:#00d4ff; border:1px solid #00d4ff; padding:15px; border-radius:12px; cursor:pointer; width:100%; font-family:'Orbitron'; font-weight:bold;">📋 SYNC CLIPBOARD</button>"""
    st.components.v1.html(clipboard_js, height=80)
    if st.button("CLEAR ALL"):
        st.session_state.clear()
        st.rerun()

if st.button("⚡ EXECUTE PROCESS"):
    if input_text:
        start_time = time.time()
        eintraege = [s.strip() for s in input_text.split('\n') if s.strip()]
        res_dict = defaultdict(list)
        
        with st.status("INITIALIZING SYSTEM...", expanded=True) as status:
            for entry in eintraege:
                try:
                    match = re.match(r"(.+?)\s+(\d+[a-zA-Z]?)", entry)
                    street = match.group(1).strip() if match else entry
                    num = match.group(2).strip() if match else None

                    q = f"{entry}, Landkreis Marburg-Biedenkopf, Germany"
                    gdf = ox.features_from_address(q, tags={"highway": True}, dist=800)
                    
                    if not gdf.empty:
                        # Find Suburb/Ortsteil
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
                                folium.Marker([lat, lon], icon=folium.Icon(color='blue', icon='flag', prefix='fa')).add_to(m)
                                m.location = [lat, lon]

                        res_dict[location].append((entry, m._repr_html_()))
                except Exception as e:
                    continue
            
            total_time = round(time.time() - start_time, 2)
            status.update(label=f"PROCESS COMPLETE IN {total_time}S", state="complete")

        if res_dict:
            st.toast(f"Mapping von {len(eintraege)} Zielen abgeschlossen!", icon="🚀")
            for area, maps in res_dict.items():
                st.markdown(f'<div class="ort-container"><h3>📡 AREA: {area}</h3>', unsafe_allow_html=True)
                grid = st.columns(2)
                for idx, (name, html) in enumerate(maps):
                    with grid[idx % 2]:
                        st.markdown(f"**Target:** `{name}`")
                        b64 = base64.b64encode(html.encode()).decode()
                        st.markdown(f'<a href="data:text/html;base64,{b64}" target="_blank"><button style="width:100%; background:rgba(0,212,255,0.2); color:#00d4ff; border:1px solid #00d4ff; padding:5px; border-radius:8px; cursor:pointer; font-size:12px;">VIEW FULLSCREEN</button></a>', unsafe_allow_html=True)
                        st.components.v1.html(html, height=400)
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.warning("SYSTEM IDLE: NO INPUT DETECTED")

st.markdown("<br><hr><center style='color:rgba(255,255,255,0.3);'>MM3000 // SERIES GOLD // 2026</center>", unsafe_allow_html=True)
