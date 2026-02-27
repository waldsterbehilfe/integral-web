import streamlit as st
import osmnx as ox
import folium
import io, zipfile, base64, os, re, time
from collections import defaultdict

# --- 1. ENGINE & ROBUSTER CACHE ---
CACHE_ZIP = "geocache.zip"
CACHE_DIR = "geocache"

@st.cache_resource
def power_up_engine():
    """Initialisiert den Cache und entpackt Zips."""
    vorher = 0
    if os.path.exists(CACHE_DIR):
        vorher = len(os.listdir(CACHE_DIR))
        
    if os.path.exists(CACHE_ZIP):
        try:
            with zipfile.ZipFile(CACHE_ZIP, 'r') as zip_ref:
                zip_ref.extractall(".")
        except:
            pass
            
    if os.path.exists(CACHE_DIR):
        ox.settings.use_cache = True
        ox.settings.cache_folder = f"./{CACHE_DIR}"
        nachher = len(os.listdir(CACHE_DIR))
        diff = nachher - vorher
        return nachher, diff
    return 0, 0

cache_total, cache_neu = power_up_engine()

# --- 2. INTELLIGENTE TEXT-KORREKTUR ---
def bereinige_adresse(text):
    t = text.strip()
    t = re.sub(r'(?i)\bstr\b\.?', 'Straße', t)
    t = re.sub(r'(?i)strase\b', 'Straße', t)
    t = re.sub(r'(?i)strasse\b', 'Straße', t)
    t = re.sub(r'(?i)(\w+)str\b\.?', r'\1straße', t)
    t = re.sub(r'\s+', ' ', t)
    return t

# --- 3. MULTIMEDIA & DYNAMIC UI ---
def spiele_audio(typ="erfolg"):
    sounds = {
        "erfolg": "https://codeskulptor-demos.commondatastorage.googleapis.com/descent/gotitem.mp3",
        "fehler": "https://www.myinstants.com/media/sounds/nelson-haha.mp3"
    }
    st.components.v1.html(f'<audio autoplay><source src="{sounds[typ]}" type="audio/mpeg"></audio>', height=0)

def erzeuge_link(html_code, ortsteil):
    b64 = base64.b64encode(html_code.encode()).decode()
    return f'''<a href="data:text/html;base64,{b64}" target="_blank" style="text-decoration:none;">
                <div style="background: linear-gradient(135deg, #00d4ff 0%, #0055ff 100%); 
                color: white; padding: 15px; border-radius: 15px; text-align: center; 
                font-weight: bold; font-family: 'Orbitron'; margin-top: 10px;
                box-shadow: 0 5px 20px rgba(0, 212, 255, 0.5);">
                🖥️ VOLLBILD: {ortsteil.upper()}
                </div></a>'''

def apply_titan_style(dark, bg_active):
    bg_css = ""
    if bg_active and os.path.exists('hintergrund.png'):
        with open('hintergrund.png', 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        bg_css = f'background-image: url("data:image/png;base64,{data}");'
    
    akzent = "#00d4ff"
    danger = "#ff4b4b"
    panel_bg = "rgba(10, 10, 15, 0.85)" if dark else "rgba(240, 242, 246, 0.9)"
    text_col = "#ffffff" if dark else "#2c3e50"
    sub_bg = "rgba(0, 212, 255, 0.05)" if dark else "rgba(0, 85, 255, 0.05)"

    # --- KONFIGURATION FÜR MAIL ---
    EMAIL_ADRESSE = "deine.email@beispiel.de" # <-- HIER ANPASSEN
    MAIL_LINK = f"mailto:{EMAIL_ADRESSE}?subject=Feedback%20zu%20Titan%20Mapmarker"

    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@500;700&display=swap');
        .stApp {{ {bg_css} background-size: cover; background-attachment: fixed; }}
        .block-container {{ background: {panel_bg}; backdrop-filter: blur(20px); border-radius: 40px; padding: 3rem !important; color: {text_col}; position: relative; padding-bottom: 60px !important; }}
        
        /* KLICKBARES BRANDING UNTEN RECHTS */
        .copyright-branding {{
            position: absolute;
            bottom: 20px;
            right: 30px;
            font-family: 'Rajdhani', sans-serif;
            font-size: 0.9rem;
            color: rgba(255, 255, 255, 0.5);
            letter-spacing: 2px;
            text-decoration: none;
            transition: color 0.3s ease;
        }}
        .copyright-branding:hover {{ color: {akzent}; }}
        .copyright-branding b {{ color: {akzent}; }}
        
        @keyframes rotate-vortex {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
        .vortex-loader {{ width: 50px; height: 50px; border: 3px solid transparent; border-top: 3px solid {akzent}; border-radius: 50%; display: inline-block; animation: rotate-vortex 1s linear infinite; margin-right: 20px; vertical-align: middle; box-shadow: 0 0 15px {akzent}; }}
        .status-container {{ background: rgba(0, 212, 255, 0.1); padding: 25px; border-radius: 25px; border: 1px solid {akzent}; margin-bottom: 30px; }}
        
        .ort-box-titan {{ background: {sub_bg}; border-radius: 30px; padding: 40px; margin-bottom: 50px; border: 1px solid rgba(0, 212, 255, 0.2); box-shadow: 0 10px 30px rgba(0,0,0,0.3); }}
        .titan-header {{ font-family: 'Orbitron'; color: {akzent}; font-size: 2.2rem; margin-bottom: 30px; text-shadow: 0 0 10px rgba(0,212,255,0.5); }}
        .stButton button {{ width: 100%; height: 4rem; border-radius: 20px; background: linear-gradient(90deg, #0055ff, #00d4ff) !important; font-family: 'Orbitron'; font-size: 1.2rem; border: none; }}
        div.stButton > button[kind="primary"] {{ background: linear-gradient(90deg, #550000, {danger}) !important; }}
        
        </style>
        <a href="{MAIL_LINK}" class="copyright-branding">Powered by <b>[DEIN NAME/FIRMA]</b> © 2026</a>
    """, unsafe_allow_html=True)

# --- APP LAYOUT ---
st.set_page_config(page_title="TITAN V12.4", layout="wide")
ist_dunkel = st.sidebar.toggle("Cyber-Modus (Dunkel)", True)
bg_an = st.sidebar.toggle("Hintergrund-Sättigung", True)
apply_titan_style(ist_dunkel, bg_an)

# --- SIDEBAR FEEDBACK ---
st.sidebar.markdown("---")
st.sidebar.markdown("### Gefällt dir TITAN?")
col_f1, col_f2 = st.sidebar.columns(2)
with col_f1:
    if st.button("👍 Like"):
        st.sidebar.success("Danke!")
with col_f2:
    if st.button("👎 Dislike"):
        st.sidebar.warning("Wir arbeiten dran!")
st.sidebar.markdown("---")

if cache_neu > 0:
    st.sidebar.success(f"⚡ {cache_neu} neue Sektoren geladen!")
st.sidebar.metric("GESAMT-DATENBANK", f"{cache_total} Objekte")

st.title("MAPMARKER 3000 — TITAN")
st.caption("Version 12.4 // Contact Edition")

input_text = st.text_area("ZIEL-EINGABE:", height=180, placeholder="Straßenliste...")

col1, col2 = st.columns([4, 1])
with col1:
    start_btn = st.button("🚀 SYSTEM-ANALYSE STARTEN")
with col2:
    abort_btn = st.button("🛑 ABBRECHEN", type="primary")

# --- PROZESS LOGIK ---
if start_btn:
    if input_text:
        rohe_eintraege = [s.strip() for s in input_text.split('\n') if s.strip()]
        gesamt = len(rohe_eintraege)
        ergebnisse = defaultdict(list)
        fehler = []
        
        status_box = st.empty()
        prog_bar = st.progress(0)
        
        for i, roh_eintrag in enumerate(rohe_eintraege):
            if abort_btn:
                st.warning("⚠️ PROZESS ABGEBROCHEN")
                break
                
            aktuelle_nr = i + 1
            eintrag = bereinige_adresse(roh_eintrag)
            
            status_box.markdown(f"""
                <div class="status-container">
                    <div class="vortex-loader"></div>
                    <span style="font-family:'Orbitron'; color:#00d4ff; font-size:1.2rem;">
                        ANALYSE: {aktuelle_nr} / {gesamt} — <b>{eintrag}</b>
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
                    
                    str_clean = re.sub(r'\s+\d+.*', '', eintrag)
                    target = gdf[gdf['name'].str.contains(str_clean, case=False, na=False)] if 'name' in gdf.columns else gdf
                    
                    ergebnisse[ortsteil].append({
                        "name": eintrag,
                        "gdf": target,
                        "query": q
                    })
                else: fehler.append(roh_eintrag)
            except:
                fehler.append(roh_eintrag)
                continue
        
        status_box.empty()
        prog_bar.empty()

        # Ergebnisse anzeigen
        if ergebnisse:
            spiele_audio("erfolg")
            for ortsteil in sorted(ergebnisse.keys()):
                st.markdown(f'<div class="ort-box-titan"><h2 class="titan-header">📍 SEKTOR: {ortsteil}</h2>', unsafe_allow_html=True)
                
                m = folium.Map(tiles='cartodbdark_matter' if ist_dunkel else 'cartodbpositron')
                alle_geoms = []
                
                for item in ergebnisse[ortsteil]:
                    folium.GeoJson(item["gdf"], style_function=lambda x: {'color':'#ff0055','weight':8}).add_to(m)
                    alle_geoms.append(item["gdf"])
                    
                    if any(c.isdigit() for c in item["name"]):
                        p_gdf = ox.geocode_to_gdf(item["query"])
                        if not p_gdf.empty:
                            loc = p_gdf.iloc[0].geometry.centroid
                            folium.Marker([loc.y, loc.x], icon=folium.Icon(color='blue', icon='flag')).add_to(m)
                
                if alle_geoms:
                    import pandas as pd
                    combined_gdf = pd.concat(alle_geoms)
                    m.fit_bounds(combined_gdf.total_bounds[[1, 0, 3, 2]].tolist())
                
                html_map = m._repr_html_()
                st.markdown(erzeuge_link(html_map, ortsteil), unsafe_allow_html=True)
                st.components.v1.html(html_map, height=600)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        if fehler:
            spiele_audio("fehler")
            st.error(f"Nicht gefunden: {', '.join(fehler)}")
