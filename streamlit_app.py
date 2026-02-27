import streamlit as st
import osmnx as ox
import folium
import io, zipfile, base64, os, re
from collections import defaultdict

# --- 1. SYSTEM & CACHE ---
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

# --- 2. EXKLUSIVES ORT-DESIGN ---
def apply_custom_style(dark_mode, show_bg):
    bg_css = ""
    if show_bg and os.path.exists('hintergrund.png'):
        with open('hintergrund.png', 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        bg_css = f'background-image: url("data:image/png;base64,{data}"); background-size: cover; background-attachment: fixed;'
    
    bg_color = "rgba(20, 20, 20, 0.98)" if dark_mode else "rgba(245, 245, 245, 0.98)"
    text_color = "#FFFFFF" if dark_mode else "#1A1A1A"
    accent = "#1976d2"
    
    st.markdown(f"""
        <style>
        .stApp {{ {bg_css} }} 
        .block-container {{ background: {bg_color}; color: {text_color}; border-radius: 20px; padding: 2rem; }}
        
        /* Design für die Ort-Fenster */
        .ort-container {{
            border: 2px solid {accent};
            background: rgba(40, 40, 40, 0.5);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 40px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }}
        .ort-header {{
            color: {accent};
            text-transform: uppercase;
            letter-spacing: 2px;
            border-bottom: 1px solid {accent};
            margin-bottom: 15px;
            padding-bottom: 5px;
        }}
        </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="INTERGAL MAPMARKER 3000", layout="wide")

# Sidebar
st.sidebar.title("🚀 MM3000 PRO")
is_dark = st.sidebar.toggle("Dark Mode", value=True)
show_background = st.sidebar.toggle("Hintergrundbild", value=True)
apply_custom_style(is_dark, show_background)
st.sidebar.info(f"📦 Cache: {cache_count} Objekte")

st.title("🗺️ INTERGAL MAPMARKER 3000")

# Clipboard Import Button
clipboard_js = """<script>async function paste() { const text = await navigator.clipboard.readText(); const ta = window.parent.document.querySelector('textarea'); if(ta){ta.value=text; ta.dispatchEvent(new Event('input', {bubbles:true}));}}</script><button onclick="paste()" style="background:#FF4B4B; color:white; border:none; padding:10px; border-radius:10px; cursor:pointer; width:100%; font-weight:bold;">📋 AUS ZWISCHENABLAGE IMPORTIEREN</button>"""
st.components.v1.html(clipboard_js, height=50)

input_text = st.text_area("Straßenliste:", height=150)

if st.button("KARTEN NACH ORTEN SORTIEREN"):
    if input_text:
        eintraege = [s.strip() for s in input_text.split('\n') if s.strip()]
        res_dict = defaultdict(list) # Hier wird nach Ort sortiert
        
        with st.status("Sortiere Straßen nach Ortsteilen...", expanded=True):
            for eintrag in eintraege:
                try:
                    match = re.match(r"(.+?)\s+(\d+[a-zA-Z]?)", eintrag)
                    strasse_rein = match.group(1).strip() if match else eintrag
                    hausnummer = match.group(2).strip() if match else None

                    q = f"{eintrag}, Landkreis Marburg-Biedenkopf, Germany"
                    gdf = ox.features_from_address(q, tags={"highway": True}, dist=800)
                    
                    if not gdf.empty:
                        # Ortsteil/Ort finden
                        stadt = "Unbekannter Ortsteil"
                        for col in ['addr:suburb', 'addr:city', 'municipality', 'name:de']:
                            if col in gdf.columns and gdf[col].dropna().any():
                                stadt = gdf[col].dropna().iloc[0]
                                break

                        # Karte erstellen
                        m = folium.Map(location=[50.81, 8.77], zoom_start=16)
                        target_strasse = gdf[gdf['name'].str.contains(strasse_rein, case=False, na=False)] if 'name' in gdf.columns else gdf
                        folium.GeoJson(target_strasse, style_function=lambda x: {'color':'red','weight':8, 'opacity':0.7}).add_to(m)

                        if hausnummer:
                            p_gdf = ox.geocode_to_gdf(q)
                            if not p_gdf.empty:
                                lat, lon = p_gdf.iloc[0].geometry.centroid.y, p_gdf.iloc[0].geometry.centroid.x
                                folium.Marker([lat, lon], icon=folium.Icon(color='blue', icon='flag')).add_to(m)
                                m.location = [lat, lon]

                        res_dict[stadt].append((eintrag, m._repr_html_()))
                except: continue

        # --- AUSGABE IN EIGENEN FENSTERN (CONTAINER) ---
        if res_dict:
            st.divider()
            for ort, karten in res_dict.items():
                # Eigenes Ergebnisfenster pro Ort
                st.markdown(f'<div class="ort-container"><h2 class="ort-header">📍 Ortsteil: {ort}</h2>', unsafe_allow_html=True)
                
                cols = st.columns(2)
                for idx, (name, html_code) in enumerate(karten):
                    with cols[idx % 2]:
                        st.markdown(f"**Straße: {name}**")
                        b64 = base64.b64encode(html_code.encode()).decode()
                        st.markdown(f'<a href="data:text/html;base64,{b64}" target="_blank"><button style="width:100%; background:#1976d2; color:white; border:none; padding:5px; border-radius:5px; cursor:pointer;">VOLLBILD</button></a>', unsafe_allow_html=True)
                        st.components.v1.html(html_code, height=400)
                
                st.markdown('</div>', unsafe_allow_html=True) # Ende des Ort-Containers
    else:
        st.warning("Bitte Liste aus Zwischenablage einfügen!")
