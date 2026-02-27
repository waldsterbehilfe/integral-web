import streamlit as st
import osmnx as ox
import folium
import io, base64, os, re, time
import pandas as pd
from collections import defaultdict
from folium.plugins import Fullscreen

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
def apply_titan_style(dark, bg_active):
    akzent = "#00d4ff"
    danger = "#ff4b4b"
    panel_bg = "rgba(10, 10, 15, 0.85)" if dark else "rgba(240, 242, 246, 0.9)"
    text_col = "#ffffff" if dark else "#2c3e50"

    # --- KONFIGURATION FÜR MAIL ---
    EMAIL_ADRESSE = "deine.email@beispiel.de" # <-- HIER ANPASSEN
    MAIL_LINK = f"mailto:{EMAIL_ADRESSE}?subject=Feedback%20zu%20Titan%20Mapmarker"

    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@500;700&display=swap');
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
        
        .stButton button {{ width: 100%; height: 3.5rem; border-radius: 15px; background: linear-gradient(90deg, #0055ff, #00d4ff) !important; font-family: 'Orbitron'; font-size: 1rem; border: none; }}
        div.stButton > button[kind="primary"] {{ background: linear-gradient(90deg, #550000, {danger}) !important; }}
        </style>
        <a href="{MAIL_LINK}" class="copyright-branding"><b>[DEIN NAME/FIRMA]</b> © 2026</a>
    """, unsafe_allow_html=True)

# --- APP LAYOUT ---
st.set_page_config(page_title="TITAN V17.0", layout="wide")
ist_dunkel = st.sidebar.toggle("Cyber-Modus (Dunkel)", True)
apply_titan_style(ist_dunkel, True)

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

st.title("MAPMARKER 3000 — TITAN")
st.caption("Version 17.0 // HTML Report Edition")

input_text = st.text_area("ZIEL-EINGABE:", height=150, placeholder="Bahnhofstr. 5\nAm Markt...")

col1, col2 = st.columns([4, 1])
with col1:
    start_btn = st.button("🚀 HTML-REPORT GENERIEREN")
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
            
            status_box.markdown(f"ANALYSE: {aktuelle_nr} / {gesamt} — <b>{eintrag}</b>", unsafe_allow_html=True)
            prog_bar.progress(aktuelle_nr / gesamt)
            
            try:
                q = f"{eintrag}, Landkreis Marburg-Biedenkopf, Germany"
                gdf = ox.features_from_address(q, tags={"highway": True}, dist=2000)
                
                if not gdf.empty:
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

        # --- HTML GENERIERUNG ---
        if results_by_district:
            # HTML Header & CSS
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Titan Map Report</title>
                <style>
                    body { font-family: 'Rajdhani', sans-serif; background-color: #0a0a0f; color: white; padding: 20px; }
                    .container { max-width: 1200px; margin: 0 auto; }
                    .district-box { background-color: #1a1a2e; border: 1px solid #00d4ff; border-radius: 20px; padding: 20px; margin-bottom: 30px; }
                    h1 { color: #00d4ff; font-family: 'Orbitron', sans-serif; }
                    .map-wrapper { width: 100%; height: 500px; margin-top: 10px; }
                </style>
            </head>
            <body>
            <div class="container">
                <h1>TITAN MAP REPORT</h1>
            """
            
            for ortsteil, items in results_by_district.items():
                html_content += f'<div class="district-box"><h2>📍 {ortsteil}</h2>'
                
                m = folium.Map(tiles='openstreetmap')
                alle_geoms = []
                
                for item in items:
                    tooltip_fields = ['name'] if 'name' in item["gdf"].columns else []
                    folium.GeoJson(
                        item["gdf"],
                        style_function=lambda x: {'color':'#ff0055','weight':8},
                        tooltip=folium.GeoJsonTooltip(fields=tooltip_fields, aliases=['Straße:']) if tooltip_fields else None
                    ).add_to(m)
                    
                    alle_geoms.append(item["gdf"])
                    
                    if any(c.isdigit() for c in item["name"]):
                        p_gdf = ox.geocode_to_gdf(item["query"])
                        if not p_gdf.empty:
                            loc = p_gdf.iloc[0].geometry.centroid
                            folium.Marker([loc.y, loc.x], icon=folium.Icon(color='blue', icon='info-sign')).add_to(m)
                
                if alle_geoms:
                    combined_gdf = pd.concat(alle_geoms)
                    bounds = combined_gdf.total_bounds
                    if not combined_gdf.empty:
                        m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], padding=(0.05, 0.05))
                
                # Karte in HTML einbetten
                m.get_root().width = "100%"
                m.get_root().height = "500px"
                map_html = m._repr_html_()
                html_content += f'<div class="map-wrapper">{map_html}</div>'
                html_content += '</div>'
            
            html_content += '</body></html>'
            
            # Download Button
            st.download_button(
                label="📥 HTML-REPORT HERUNTERLADEN",
                data=html_content,
                file_name=f"Titan_Map_Report_{time.strftime('%Y%m%d_%H%M')}.html",
                mime="text/html"
            )
            
        if fehler:
            st.error(f"Nicht gefunden: {', '.join(fehler)}")
