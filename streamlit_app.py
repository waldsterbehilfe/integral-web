import streamlit as st
import osmnx as ox
import folium
from collections import defaultdict
import io
import zipfile
import base64
import os
from datetime import datetime

# --- 1. KONFIGURATION & SPEICHER (Caching) ---
ox.settings.use_cache = True
ox.settings.cache_folder = "./geocache"

# --- 2. DESIGN-LOGIK (Hintergrund & Modi) ---
def get_base64(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    return None

def apply_design(dark_mode=True):
    bg_img = get_base64('hintergrund.png')
    bg_style = ""
    if bg_img:
        bg_style = f'background-image: url("data:image/png;base64,{bg_img}"); background-size: cover; background-attachment: fixed;'

    main_bg = "#1e1e1e" if dark_mode else "#f5f7f9"
    text_color = "#ffffff" if dark_mode else "#2c3e50"
    box_bg = "rgba(30, 30, 30, 0.85)" if dark_mode else "rgba(255, 255, 255, 0.9)"

    st.markdown(f"""
        <style>
        .stApp {{ {bg_style} }}
        .block-container {{
            background: {box_bg};
            padding: 2rem;
            border-radius: 15px;
            color: {text_color};
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            margin-top: 20px;
        }}
        .stButton>button {{
            background: linear-gradient(to right, #1976d2, #004a99);
            color: white; border: none; font-weight: bold; width: 100%; border-radius: 8px; height: 3.5em;
        }}
        footer {{visibility: hidden;}}
        .footer-text {{ text-align: right; font-size: 12px; color: gray; }}
        </style>
    """, unsafe_allow_html=True)

# --- 3. UI-STRUKTUR ---
st.set_page_config(page_title="INTEGRAL WEB v4.0", layout="centered")

# Sidebar für die "Ewig-Einstellungen"
st.sidebar.title("⚙️ Optionen")
mode = st.sidebar.radio("Design-Modus", ["Dark Mode", "Light Mode"])
apply_design(dark_mode=(mode == "Dark Mode"))

st.sidebar.divider()
st.sidebar.info("Modus: Landkreis Marburg-Biedenkopf")

# Speicher-Funktion: Letzte 5 Karten (Session State)
if 'history' not in st.session_state:
    st.session_state.history = []

st.title("🗺️ INTEGRAL Web")
st.subheader("Der Goldstandard als Web-App")

# Eingabefeld (Eins-zu-Eins wie Tkinter)
input_text = st.text_area("Straßenliste hier einfügen:", height=250, placeholder="Am Markt\nSchlossstraße...")

if st.button("KARTEN GENERIEREN"):
    strassen = [s.strip() for s in input_text.split('\n') if s.strip()]
    
    if strassen:
        with st.status("🚀 Prozess gestartet...", expanded=True) as status:
            ort_sammlung = defaultdict(list)
            bar = st.progress(0)
            
            for i, strasse in enumerate(strassen):
                try:
                    query = f"{strasse}, Landkreis Marburg-Biedenkopf, Germany"
                    gdf = ox.features_from_address(query, tags={"highway": True}, dist=800)
                    
                    if not gdf.empty:
                        # Ort finden
                        stadt = "Unbekannt"
                        for col in ['addr:suburb', 'addr:city', 'municipality', 'city']:
                            if col in gdf.columns and gdf[col].dropna().any():
                                stadt = gdf[col].dropna().iloc[0]
                                break
                        
                        geo_json = folium.GeoJson(gdf, style_function=lambda x: {'color':'red','weight':6})
                        ort_sammlung[stadt].append(geo_json)
                except: continue
                bar.progress((i + 1) / len(strassen))

            if ort_sammlung:
                # Speicher für Historie aktualisieren
                st.session_state.history.append(f"{datetime.now().strftime('%H:%M')} - {len(ort_sammlung)} Orte")
                if len(st.session_state.history) > 5: st.session_state.history.pop(0)

                status.update(label="✅ Karten fertig berechnet!", state="complete")
                st.balloons()
                
                # ZIP-Download
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for ort, elemente in ort_sammlung.items():
                        m = folium.Map(location=[50.81, 8.77], zoom_start=13)
                        for el in elemente: el.add_to(m)
                        zf.writestr(f"Karte_{ort}.html", m._repr_html_())
                
                st.download_button("📥 KARTEN-PAKET (ZIP) HERUNTERLADEN", zip_buffer.getvalue(), 
                                   file_name=f"INTEGRAL_{datetime.now().strftime('%H%M')}.zip")
            else:
                status.update(label="❌ Nichts gefunden.", state="error")

# Letzte 5 Karten im Menü anzeigen
st.sidebar.divider()
st.sidebar.write("📜 Letzte Durchläufe:")
for h in reversed(st.session_state.history):
    st.sidebar.caption(h)

st.markdown("<div class='footer-text'>© Maus | Gold Edition v4.0</div>", unsafe_allow_html=True)
