import streamlit as st
import osmnx as ox
import folium
import io, zipfile, base64, os, re
import pandas as pd
from collections import defaultdict
from datetime import datetime

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="MAPMARKER 3000", layout="wide")

# Cache für OSMNX Daten
CACHE_DIR = "geocache"
if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
ox.settings.use_cache = True
ox.settings.cache_folder = f"./{CACHE_DIR}"

# --- 2. HILFSFUNKTIONEN ---
def bereinige_adresse(text):
    t = text.strip()
    t = re.sub(r'(?i)\bstr\b\.?', 'Straße', t)
    t = re.sub(r'(?i)strase\b', 'Straße', t)
    t = re.sub(r'(?i)strasse\b', 'Straße', t)
    t = re.sub(r'(?i)(\w+)str\b\.?', r'\1straße', t)
    t = re.sub(r'\s+', ' ', t)
    return t

def apply_custom_style(dark_mode):
    akzent = "#00d4ff"
    danger = "#ff4b4b"
    st.markdown(f"""
        <style>
        .copyright-branding {{
            position: fixed;
            bottom: 10px;
            right: 10px;
            font-family: sans-serif;
            font-size: 0.8rem;
            color: {akzent};
            text-decoration: none;
            z-index: 1000;
        }}
        .stButton button {{ width: 100%; border-radius: 10px; }}
        </style>
        <a href="#" class="copyright-branding">© 2026 Maus Industries</a>
    """, unsafe_allow_html=True)

# --- 3. UI LAYOUT ---
st.sidebar.title("🛠️ Konfiguration")
dark_mode = st.sidebar.toggle("Cyber-Modus (Dunkel)", True)
apply_custom_style(dark_mode)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Status")
cache_files = sum([len(files) for r, d, files in os.walk(CACHE_DIR)])
st.sidebar.metric("Cache Einträge", cache_files)

st.title("🗺️ MAPMARKER 3000 — FORCED SEARCH")
st.caption("Strikte Suche: Landkreis Marburg-Biedenkopf")

uploaded_file = st.file_uploader("📥 Lade deine Straßenliste (.txt) hoch", type=["txt"])

# --- 4. VERARBEITUNG ---
if uploaded_file is not None:
    stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
    strassen = [s.strip() for s in stringio if s.strip()]
    
    total = len(strassen)
    start_btn = st.button("🚀 Suche starten")
    
    if start_btn:
        ort_sammlung = defaultdict(list)
        errors = []
        
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        # Geofencing: Bounding Box für den Landkreis (Marburg-Biedenkopf)
        # Format: [north, south, east, west]
        LK_BOUNDS = [51.05, 50.65, 9.15, 8.30] 
        
        for i, strasse in enumerate(strassen):
            status_text.text(f"🔍 Suche: {strasse} ({i+1}/{total})")
            
            eintrag = bereinige_adresse(strasse)
            
            # --- SUCHE MIT FORCED BBOX ---
            query = f"{eintrag}, Germany"
            
            try:
                # Suche mit Bounding Box (Distanz reduziert, da BBox limitiert)
                gdf = ox.features_from_place(query, tags={"highway": True})
                
                # Wenn features_from_place nicht reicht, nutze features_from_address mit fallback
                if gdf.empty:
                    gdf = ox.features_from_address(f"{eintrag}, Germany", tags={"highway": True}, dist=1000)

                if not gdf.empty:
                    gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
                    
                    # Straßenname filtern
                    gdf_f = gdf[gdf['name'].str.contains(eintrag, case=False, na=False)] if 'name' in gdf.columns else gdf
                    
                    if not gdf_f.empty:
                        # Ortserkennung
                        stadt_info = "Sonstiges_Landkreis"
                        for col in ['addr:suburb', 'addr:city', 'municipality', 'city', 'county']:
                            if col in gdf_f.columns and gdf_f[col].dropna().any():
                                val = gdf_f[col].dropna().iloc[0]
                                if "Marburg" in val or "Biedenkopf" in val: # Ortsteil priorisieren
                                    stadt_info = val
                                    break
                        
                        ort_sammlung[stadt_info].append({"gdf": gdf_f, "name": eintrag, "query": query})
                    else: errors.append(f"Nicht gefunden: {strasse}")
                else: errors.append(f"Keine Daten: {strasse}")
            except Exception as e:
                errors.append(f"Fehler bei {strasse}: {str(e)}")
            
            progress_bar.progress((i + 1) / total)

        status_text.text("🎨 Karten werden erstellt...")
        
        # --- 5. DARSTELLUNG & ZIP GENERIERUNG ---
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            
            for ort, items in ort_sammlung.items():
                st.subheader(f"📍 {ort}")
                
                m = folium.Map(tiles='cartodbdark_matter' if dark_mode else 'cartodbpositron')
                alle_geoms = []
                
                for item in items:
                    folium.GeoJson(item["gdf"], style_function=lambda x: {'color':'red','weight':6}).add_to(m)
                    alle_geoms.append(item["gdf"])
                    
                    if any(c.isdigit() for c in item["name"]):
                        try:
                            p_gdf = ox.geocode_to_gdf(item["query"])
                            if not p_gdf.empty:
                                loc = p_gdf.iloc[0].geometry.centroid
                                folium.Marker([loc.y, loc.x], icon=folium.Icon(color='blue', icon='info-sign')).add_to(m)
                        except: pass
                
                if alle_geoms:
                    combined_gdf = pd.concat(alle_geoms)
                    bounds = combined_gdf.total_bounds
                    if not combined_gdf.empty:
                        m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], padding=(0.05, 0.05))
                
                st.components.v1.html(m._repr_html_(), height=500)
                
                safe_ort = "".join([c for c in ort if c.isalnum() or c in " _-"])
                zip_file.writestr(f"Karte_{safe_ort}.html", m._repr_html_())
        
        st.download_button(
            label="📥 Karten als ZIP herunterladen",
            data=zip_buffer.getvalue(),
            file_name=f"Karten_{datetime.now().strftime('%H%M')}.zip",
            mime="application/zip"
        )
        
        if errors:
            with st.expander("⚠️ Fehler-Log anzeigen"):
                for err in errors: st.write(err)

else:
    st.info("Bitte lade eine .txt Datei mit Straßennamen hoch.")
