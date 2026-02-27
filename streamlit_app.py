import streamlit as st
import osmnx as ox
import folium
import io, zipfile, base64, os, re, time
import pandas as pd
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

# --- 3. UI HELPER ---
def erzeuge_link(html_code, ortsteil):
    b64 = base64.b64encode(html_code.encode()).decode()
    return f'''<a href="data:text/html;base64,{b64}" target="_blank" style="text-decoration:none;">
                <div style="background: linear-gradient(135deg, #00d4ff 0%, #0055ff 100%); 
                color: white; padding: 10px; border-radius: 10px; text-align: center; 
                font-weight: bold; font-family: 'Orbitron'; font-size: 0.9rem; margin-top: 10px;
                box-shadow: 0 3px 10px rgba(0, 212, 255, 0.4);">
                🖥️ VOLLBILD: {ortsteil.upper()}
                </div></a>'''

def apply_titan_style(dark, bg_active):
    bg_css = ""
    if bg_active and os.path.exists('hintergrund.png'):
        with open('hintergrund.png', 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        bg_css = f'background-image: url("data:image/png;base64, {data}");'
    
    akzent = "#00d4ff"
    danger = "#ff4b4b"
    panel_bg = "rgba(10, 10, 15, 0.85)" if dark else "rgba(240, 242, 246, 0.9)"
    text_col = "#ffffff" if dark else "#2c3e50"
    sub_bg = "rgba(0, 212, 255, 0.03)" if dark else "rgba(0, 85, 255, 0.03)"

    # --- KONFIGURATION FÜR MAIL ---
    EMAIL_ADRESSE = "deine.email@beispiel.de" # <-- HIER ANPASSEN
    MAIL_LINK = f"mailto:{EMAIL_ADRESSE}?subject=Feedback%20zu%20Titan%20Mapmarker"

    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@500;700&display=swap');
        .stApp {{ {bg_css} background-size: cover; background-attachment: fixed; }}
        .block-container {{ background: {panel_bg}; backdrop-filter: blur(20px); border-radius: 40px; padding: 3rem !important; color: {text_col}; position: relative; padding-bottom: 80px !important; }}
        
        /* BRANDING FIX */
        .copyright-branding {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            font-family: 'Orbitron', sans-serif;
            font-size: 0.9rem;
            color: {akzent};
            text-decoration: none;
            transition: all 0.3s ease;
            text-shadow: 0 0 10px rgba(0,212,255,0.5);
            letter-spacing: 2px;
            z-index: 1000;
        }}
        .copyright-branding:hover {{ color: #ffffff; text-shadow: 0 0 15px #ffffff; }}
        
        @keyframes rotate-vortex {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
        .vortex-loader {{ width: 40px; height: 40px; border: 3px solid transparent; border-top: 3px solid {akzent}; border-radius: 50%; display: inline-block; animation: rotate-vortex 1s linear infinite; margin-right: 15px; vertical-align: middle; box-shadow: 0 0 10px {akzent}; }}
        .status-container {{ background: rgba(0, 212, 255, 0.05); padding: 20px; border-radius: 20px; border: 1px solid rgba(0, 212, 255, 0.3); margin-bottom: 20px; }}
        
        .ort-box-titan {{ background: {sub_bg}; border-radius: 25px; padding: 30px; margin-bottom: 40px; border: 1px solid rgba(0, 212, 255, 0.1); box-shadow: 0 5px 15px rgba(0,0,0,0.2); }}
        .titan-header {{ font-family: 'Orbitron'; color: {akzent}; font-size: 1.6rem; margin-bottom: 20px; text-shadow: 0 0 5px rgba(0,212,255,0.3); }}
        
        .stButton button {{ width: 100%; height: 3.5rem; border-radius: 15px; background: linear-gradient(90deg, #0055ff, #00d4ff) !important; font-family: 'Orbitron'; font-size: 1rem; border: none; }}
        div.stButton > button[kind="primary"] {{ background: linear-gradient(90deg, #550000, {danger}) !important; }}
        
        /* SIDEBAR FEEDBACK */
        .feedback-sidebar-btn {{ font-size: 0.5rem !important; height: 1.5rem !important; opacity: 0.5; }}
        </style>
        <a href="{MAIL_LINK}" class="copyright-branding"><b>[DEIN NAME/FIRMA]</b> © 2026</a>
    """, unsafe_allow_html=True)

# --- APP LAYOUT ---
st.set_page_config(page_title="TITAN V15.1", layout="wide")
ist_dunkel = st.sidebar.toggle("Cyber-Modus (Dunkel)", True)
bg_an = st.sidebar.toggle("Hintergrund-Sättigung", True)
apply_titan_style(ist_dunkel, bg_an)

# --- SIDEBAR FEEDBACK (Ganz unten & klein) ---
st.sidebar.markdown("---")
st.sidebar.markdown("### Feedback")
col_f1, col_f2 = st.sidebar.columns(2)
with col_f1:
    if st.button("👍", key="like_sb"):
        st.sidebar.success("Danke!")
with col_f2:
    if st.button("👎", key="dislike_sb"):
        st.sidebar.warning("Verbesserung läuft!")
st.sidebar.markdown("---")

if cache_neu > 0:
    st.sidebar.success(f"⚡ {cache_neu} neue Sektoren geladen!")
st.sidebar.metric("GESAMT-DATENBANK", f"{cache_total} Objekte")

st.title("MAPMARKER 3000 — TITAN")
st.caption("Version 15.1 // Fix & Stability")

input_text = st.text_area("ZIEL-EINGABE:", height=150, placeholder="Bahnhofstr. 5\nAm Markt...")

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
        
        results_by_district = defaultdict(list)
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
                    <span style="font-family:'Orbitron'; color:#00d4ff; font-size:1rem;">
                        ANALYSE: {aktuelle_nr} / {gesamt} — <b>{eintrag}</b>
                    </span>
                </div>
            """, unsafe_allow_html=True)
            prog_bar.progress(aktuelle_nr / gesamt)
            
            try:
                q = f"{eintrag}, Landkreis Marburg-Biedenkopf, Germany"
                gdf = ox.features_from_address(q, tags={"highway": True}, dist=2000)
                
                if not gdf.empty:
                    # Bessere Ermittlung des Ortsteils
                    ortsteil = "Unbekannt"
                    for key in ['addr:suburb', 'suburb', 'addr:city', 'municipality', 'county']:
                        if key in gdf.columns:
                            val = gdf[key].dropna().unique()
                            if len(val) > 0:
                                ortsteil = val[0]
                                break
                    
                    str_clean = re.sub(r'\s+\d+.*', '', eintrag)
                    target = gdf[gdf['name'].str.contains(str_clean, case=False, na=False)] if 'name' in gdf.columns else gdf
                    
                    results_by_district[ortsteil].append({
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
        if results_by_district:
            for ortsteil, items in results_by_district.items():
                st.markdown(f'<div class="ort-box-titan"><h2 class="titan-header">📍 {ortsteil}</h2>', unsafe_allow_html=True)
                
                # --- MAP INITIALISIERUNG ---
                m = folium.Map(tiles='cartodbdark_matter' if ist_dunkel else 'cartodbpositron')
                alle_geoms = []
                
                for item in items:
                    folium.GeoJson(
                        item["gdf"],
                        style_function=lambda x: {'color':'#ff0055','weight':8},
                        tooltip=folium.GeoJsonTooltip(fields=['name'], aliases=['Straße:'])
                    ).add_to(m)
                    
                    alle_geoms.append(item["gdf"])
                    
                    if any(c.isdigit() for c in item["name"]):
                        p_gdf = ox.geocode_to_gdf(item["query"])
                        if not p_gdf.empty:
                            loc = p_gdf.iloc[0].geometry.centroid
                            folium.Marker([loc.y, loc.x], icon=folium.Icon(color='blue', icon='flag')).add_to(m)
                
                # --- ZOOM: VERBESSERTE LOGIK ---
                if alle_geoms:
                    combined_gdf = pd.concat(alle_geoms)
                    # bounds in [miny, minx, maxy, maxx] konvertieren
                    bounds = combined_gdf.total_bounds
                    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], padding=(0.05, 0.05))
                
                html_map = m._repr_html_()
                
                st.markdown(erzeuge_link(html_map, ortsteil), unsafe_allow_html=True)
                st.components.v1.html(html_map, height=500)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        if fehler:
            st.error(f"Nicht gefunden: {', '.join(fehler)}")
