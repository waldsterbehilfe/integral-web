import streamlit as st
import osmnx as ox
import folium
from streamlit_folium import st_folium
from collections import defaultdict
import io
import zipfile
import base64
import os
from datetime import datetime

# --- DESIGN & BG ---
def set_bg():
    if os.path.exists('hintergrund.png'):
        with open('hintergrund.png', 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        st.markdown(f"""
            <style>
            .stApp {{
                background-image: url("data:image/png;base64,{data}");
                background-size: cover;
                background-attachment: fixed;
            }}
            .block-container {{
                background: rgba(30, 30, 30, 0.9);
                padding: 2rem; border-radius: 15px; color: white;
                box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            }}
            .stButton>button {{
                background: linear-gradient(to right, #1976d2, #004a99);
                color: white; font-weight: bold; width: 100%; border-radius: 8px; height: 3em;
            }}
            .map-container {{
                margin-bottom: 40px;
                border: 2px solid #1976d2;
                border-radius: 10px;
                overflow: hidden;
            }}
            </style>
        """, unsafe_allow_html=True)

st.set_page_config(page_title="INTEGRAL Gold v4.5", layout="wide") # 'wide' für bessere Kartenansicht
set_bg()

st.title("🗺️ INTEGRAL Web Gold")
st.markdown("Präzisions-Modus mit **Direkt-Vorschau**")

# Eingabe
input_text = st.text_area("Straßenliste:", height=150, placeholder="Hauptstraße\nSchloßweg...")

if st.button("KARTEN GENERIEREN & ANZEIGEN"):
    strassen_liste = [s.strip() for s in input_text.split('\n') if s.strip()]
    
    if strassen_liste:
        with st.status("Verarbeite und filtere Daten...", expanded=True) as status:
            ort_sammlung = defaultdict(list)
            
            for s_name in strassen_liste:
                try:
                    q = f"{s_name}, Landkreis Marburg-Biedenkopf, Germany"
                    gdf = ox.features_from_address(q, tags={"highway": True}, dist=800)
                    
                    if not gdf.empty:
                        # Präzisions-Filter
                        if 'name' in gdf.columns:
                            target_gdf = gdf[gdf['name'].str.contains(s_name, case=False, na=False)]
                        else:
                            target_gdf = gdf

                        if not target_gdf.empty:
                            stadt = "Unbekannt"
                            for col in ['addr:suburb', 'addr:city', 'municipality', 'city']:
                                if col in target_gdf.columns and target_gdf[col].dropna().any():
                                    stadt = target_gdf[col].dropna().iloc[0]
                                    break
                            
                            geo = folium.GeoJson(target_gdf, style_function=lambda x: {'color':'red','weight':8, 'opacity': 0.9})
                            ort_sammlung[stadt].append(geo)
                except:
                    continue
            
            if ort_sammlung:
                status.update(label="✅ Karten bereit!", state="complete")
                
                # 1. ZIP-BUFFER für den Download-Button (bleibt bestehen)
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    st.write("### 👁️ Direkt-Vorschau der Ergebnisse:")
                    
                    for ort, elemente in ort_sammlung.items():
                        # Karte erstellen
                        m = folium.Map(location=[50.81, 8.77], zoom_start=14)
                        for e in elemente:
                            e.add_to(m)
                        
                        # In ZIP speichern
                        zf.writestr(f"Karte_{ort}.html", m._repr_html_())
                        
                        # LIVE IM BROWSER ANZEIGEN
                        st.write(f"**📍 Ortsteil/Stadt: {ort}**")
                        st_folium(m, width=700, height=400, key=f"map_{ort}")
                        st.divider()

                # 2. DOWNLOAD BUTTON (immer am Ende)
                st.download_button(
                    label="📥 ALLES ALS ZIP HERUNTERLADEN",
                    data=zip_buffer.getvalue(),
                    file_name=f"INTEGRAL_Export_{datetime.now().strftime('%H%M')}.zip",
                    mime="application/zip"
                )
            else:
                status.update(label="❌ Keine passenden Straßennamen gefunden.", state="error")
