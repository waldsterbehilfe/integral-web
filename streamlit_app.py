import streamlit as st
import osmnx as ox
import folium
import io, zipfile, base64, os, re
import pandas as pd
from collections import defaultdict
from datetime import datetime

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="MAPMARKER 3000", layout="wide")

# Cache für OSMNX Daten, um Anfragen zu minimieren
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
    # Einfaches CSS für Branding und Farben
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
# Sidebar
st.sidebar.title("🛠️ Konfiguration")
dark_mode = st.sidebar.toggle("Cyber-Modus (Dunkel)", True)
apply_custom_style(dark_mode)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Status")
cache_files = sum([len(files) for r, d, files in os.walk(CACHE_DIR)])
st.sidebar.metric("Cache Einträge", cache_files)

# Hauptbereich
st.title("🗺️ MAPMARKER 3000")
st.caption("Sortiere Straßen nach Ortsteilen im Landkreis Marburg-Biedenkopf")

uploaded_file = st.file_uploader("📥 Lade deine Straßenliste (.txt) hoch", type=["txt"])

# --- 4. VERARBEITUNG ---
if uploaded_file is not None:
    # Textdatei einlesen
    stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
    strassen = [s.strip() for s in stringio if s.strip()]
    
    total = len(strassen)
    start_btn = st.button("🚀 Suche starten")
    
    if start_btn:
        ort_sammlung = defaultdict(list)
        errors = []
        
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        for i, strasse in enumerate(strassen):
            status_text.text(f"🔍 Suche: {strasse} ({i+1}/{total})")
            
            try:
                # Suche
                query = f"{strasse}, Landkreis Marburg-Biedenkopf, Germany"
                gdf = ox.features_from_address(query, tags={"highway": True}, dist=800)
                
                if not gdf.empty:
                    gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
                    gdf_f = gdf[gdf['name'].str.contains(strasse, case=False, na=False)] if 'name' in gdf.columns else gdf
                    
                    if not gdf_f.empty:
                        # Ortserkennung
                        stadt_info = "Unbekannter_Ort"
                        for col in ['addr:suburb', 'addr:city', 'municipality', 'city']:
                            if col in gdf_f.columns and gdf_f[col].dropna().any():
                                stadt_info = gdf_f[col].dropna().iloc[0]
                                break
                        
                        ort_sammlung[stadt_info].append({"gdf": gdf_f, "name": strasse, "query": query})
                    else: errors.append(f"Nicht eindeutig: {strasse}")
                else: errors.append(f"Fehlt: {strasse}")
            except Exception as e:
                errors.append(f"Fehler bei {strasse}: {str(e)}")
            
            progress_bar.progress((i + 1) / total)

        status_text.text("🎨 Karten werden erstellt...")
        
        # --- 5. DARSTELLUNG & ZIP GENERIERUNG ---
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            
            for ort, items in ort_sammlung.items():
                st.subheader(f"📍 {ort}")
                
                # Karte erstellen
                m = folium.Map(tiles='cartodbdark_matter' if dark_mode else 'cartodbpositron')
                alle_geoms = []
                
                for item in items:
                    folium.GeoJson(item["gdf"], style_function=lambda x: {'color':'red','weight':6}).add_to(m)
                    alle_geoms.append(item["gdf"])
                    
                    # Fähnchen für Hausnummer
                    if any(c.isdigit() for c in item["name"]):
                        p_gdf = ox.geocode_to_gdf(item["query"])
                        if not p_gdf.empty:
                            loc = p_gdf.iloc[0].geometry.centroid
                            folium.Marker([loc.y, loc.x], icon=folium.Icon(color='blue', icon='info-sign')).add_to(m)
                
                # Zoom auf Objekte
                if alle_geoms:
                    combined_gdf = pd.concat(alle_geoms)
                    bounds = combined_gdf.total_bounds
                    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], padding=(0.05, 0.05))
                
                # Im Streamlit anzeigen
                st.components.v1.html(m._repr_html_(), height=500)
                
                # In ZIP für Download speichern
                safe_ort = "".join([c for c in ort if c.isalnum() or c in " _-"])
                zip_file.writestr(f"Karte_{safe_ort}.html", m._repr_html_())
        
        # Download Button
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
