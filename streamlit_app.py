import streamlit as st
import osmnx as ox
import folium
import io, zipfile, base64, os, re
from collections import defaultdict

# --- TURBO-CACHE ---
CACHE_ZIP = "geocache.zip"
CACHE_DIR = "geocache"

def prepare_cache():
    if os.path.exists(CACHE_ZIP) and not os.path.exists(CACHE_DIR):
        with zipfile.ZipFile(CACHE_ZIP, 'r') as zip_ref:
            zip_ref.extractall(".")
    if os.path.exists(CACHE_DIR):
        ox.settings.use_cache = True
        ox.settings.cache_folder = f"./{CACHE_DIR}"
        return len(os.listdir(CACHE_DIR))
    return 0

cache_count = prepare_cache()

# --- DESIGN ---
def apply_custom_style(dark_mode, show_bg):
    bg_css = ""
    if show_bg and os.path.exists('hintergrund.png'):
        with open('hintergrund.png', 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        bg_css = f'background-image: url("data:image/png;base64,{data}"); background-size: cover; background-attachment: fixed;'
    
    bg_color = "rgba(25, 25, 25, 0.95)" if dark_mode else "rgba(255, 255, 255, 0.95)"
    text_color = "#FFFFFF" if dark_mode else "#1A1A1A"
    st.markdown(f"""
        <style>
        .stApp {{ {bg_css} }} 
        .block-container {{ background: {bg_color}; color: {text_color}; border-radius: 20px; padding: 2rem; }}
        .stButton>button {{ border-radius: 10px; height: 3em; font-weight: bold; }}
        </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="INTERGAL MAPMARKER 3000", layout="wide")

# Sidebar
st.sidebar.title("🚀 MM3000 CONTROL")
is_dark = st.sidebar.toggle("Dark Mode", value=True)
show_background = st.sidebar.toggle("Hintergrundbild", value=True)
apply_custom_style(is_dark, show_background)
st.sidebar.divider()
st.sidebar.info(f"📦 Cache: {cache_count} Objekte")

st.title("🗺️ INTERGAL MAPMARKER 3000")

# --- CLIPBOARD LOGIK ---
# HTML/JS Trick um die Zwischenablage mit einem Klick zu holen
clipboard_js = """
<script>
async function pasteFromClipboard() {
    const text = await navigator.clipboard.readText();
    const textArea = window.parent.document.querySelector('textarea');
    if (textArea) {
        textArea.value = text;
        textArea.dispatchEvent(new Event('input', { bubbles: true }));
    }
}
</script>
<button onclick="pasteFromClipboard()" style="
    background: #FF4B4B; color: white; border: none; padding: 10px 20px; 
    border-radius: 10px; cursor: pointer; font-weight: bold; width: 100%; margin-bottom: 20px;">
    📋 AUS ZWISCHENABLAGE EINFÜGEN
</button>
"""

st.components.v1.html(clipboard_js, height=70)

if 'input_val' not in st.session_state:
    st.session_state.input_val = ""

input_text = st.text_area("Straßenliste:", value=st.session_state.input_val, height=150)

# Check auf mehr als 3 Straßen
strassen_count = len([s for s in input_text.split('\n') if s.strip()])
if strassen_count > 3:
    st.info(f"💡 Info: Du hast {strassen_count} Straßen in der Liste. Soll ich den Prozess starten?")

# --- VERARBEITUNG ---
if st.button("PROZESS STARTEN"):
    if input_text:
        eintraege = [s.strip() for s in input_text.split('\n') if s.strip()]
        res_dict = defaultdict(list)
        
        with st.status("Analysiere Daten...", expanded=True):
            for eintrag in eintraege:
                try:
                    match = re.match(r"(.+?)\s+(\d+[a-zA-Z]?)", eintrag)
                    strasse_rein = match.group(1).strip() if match else eintrag
                    hausnummer = match.group(2).strip() if match else None

                    q = f"{eintrag}, Landkreis Marburg-Biedenkopf, Germany"
                    gdf_strasse = ox.features_from_address(q, tags={"highway": True}, dist=800)
                    
                    if not gdf_strasse.empty and 'name' in gdf_strasse.columns:
                        target_strasse = gdf_strasse[gdf_strasse['name'].str.contains(strasse_rein, case=False, na=False)]
                        stadt = "Ort"
                        for col in ['addr:city', 'municipality', 'addr:suburb']:
                            if col in target_strasse.columns and target_strasse[col].dropna().any():
                                stadt = target_strasse[col].dropna().iloc[0]
                                break

                        m = folium.Map(location=[50.81, 8.77], zoom_start=16)
                        folium.GeoJson(target_strasse, style_function=lambda x: {'color':'red','weight':8, 'opacity':0.7}).add_to(m)

                        if hausnummer:
                            try:
                                point_gdf = ox.geocode_to_gdf(q)
                                if not point_gdf.empty:
                                    lat, lon = point_gdf.iloc[0].geometry.centroid.y, point_gdf.iloc[0].geometry.centroid.x
                                    folium.Marker([lat, lon], popup=eintrag, icon=folium.Icon(color='blue', icon='flag')).add_to(m)
                                    m.location = [lat, lon]
                            except: pass

                        res_dict[stadt].append((eintrag, m._repr_html_()))
                except: continue

        if res_dict:
            for ort, karten in res_dict.items():
                st.subheader(f"📍 Bereich: {ort}")
                grid = st.columns(2)
                for idx, (name, html_code) in enumerate(karten):
                    with grid[idx % 2]:
                        st.info(f"Ziel: **{name}**")
                        b64 = base64.b64encode(html_code.encode()).decode()
                        st.markdown(f'<a href="data:text/html;base64,{b64}" target="_blank"><button style="width:100%; border-radius:5px; background:#1976d2; color:white; border:none; padding:5px; cursor:pointer;">➔ VOLLBILD</button></a>', unsafe_allow_html=True)
                        st.components.v1.html(html_code, height=400)
