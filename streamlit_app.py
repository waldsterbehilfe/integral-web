import streamlit as st
import osmnx as ox
import folium
import io, zipfile, os, re
import pandas as pd
from collections import defaultdict
from datetime import datetime

# --- 1. SETUP ---
st.set_page_config(page_title="INTEGRAL PRO", layout="wide", page_icon="🛡️")

# Cache für OSMNX (beschleunigt wiederholte Suchen enorm)
CACHE_DIR = "geocache"
if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
ox.settings.use_cache = True
ox.settings.cache_folder = f"./{CACHE_DIR}"

# --- 2. LOGIK ---
def verarbeite_strasse(strasse):
    # Automatische Korrektur von Abkürzungen
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    # Strikte Suche im Landkreis
    query = f"{s_clean}, Landkreis Marburg-Biedenkopf, Germany"
    
    try:
        # Suche nach Straßen-Features
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=800)
        
        if not gdf.empty:
            # Nur Linien akzeptieren (Straßenzüge)
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            
            # Namensabgleich zur Sicherheit
            if 'name' in gdf.columns:
                gdf_f = gdf[gdf['name'].str.contains(s_clean, case=False, na=False)]
            else:
                gdf_f = gdf
            
            if not gdf_f.empty:
                # Automatisierte Ortsteil-Erkennung
                stadt_info = "Unbekannt"
                for col in ['addr:suburb', 'addr:city', 'municipality', 'city', 'county']:
                    if col in gdf_f.columns and gdf_f[col].dropna().any():
                        val = gdf_f[col].dropna().iloc[0]
                        # Wenn der Landkreis-Name im Feld steht, weitersuchen für präziseren Ortsteil
                        if "Marburg-Biedenkopf" not in val:
                            stadt_info = val
                            break
                        else:
                            stadt_info = val
                return {"gdf": gdf_f, "ort": stadt_info, "name": s_clean}
    except:
        pass
    return None

# --- 3. UI ---
st.title("🛡️ INTEGRAL PRO")
st.markdown("Automatisierte Straßensortierung nach Ortsteilen im **Landkreis Marburg-Biedenkopf**.")

uploaded_file = st.file_uploader("Datei wählen (.txt)", type=["txt"])

if uploaded_file:
    if st.button("Verarbeitung starten"):
        # Einlesen
        content = uploaded_file.getvalue().decode("utf-8")
        strassen_liste = [s.strip() for s in content.splitlines() if s.strip()]
        
        ort_sammlung = defaultdict(list)
        fehler_liste = []
        
        prog = st.progress(0)
        status = st.empty()
        
        for i, s in enumerate(strassen_liste):
            status.text(f"🔍 Suche: {s} ({i+1}/{len(strassen_liste)})")
            res = verarbeite_strasse(s)
            if res:
                ort_sammlung[res["ort"]].append(res)
            else:
                fehler_liste.append(s)
            prog.progress((i + 1) / len(strassen_liste))
            
        status.text("✅ Suche abgeschlossen. Erstelle Karten...")

        # --- DOWNLOADS & KARTEN ---
        if ort_sammlung:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                
                for ort, items in ort_sammlung.items():
                    st.subheader(f"📍 {ort}")
                    
                    # Karte initialisieren
                    m = folium.Map()
                    all_geoms = []
                    
                    for item in items:
                        # Rote Linien zeichnen
                        folium.GeoJson(item["gdf"], 
                                       style_function=lambda x: {'color':'red', 'weight':6, 'opacity':0.8},
                                       tooltip=item["name"]).add_to(m)
                        all_geoms.append(item["gdf"])
                    
                    # Automatischer Zoom auf alle gefundenen Straßen eines Ortes
                    if all_geoms:
                        combined = pd.concat(all_geoms)
                        bounds = combined.total_bounds # [minx, miny, maxx, maxy]
                        m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], padding=(0.05, 0.05))
                    
                    # Karte anzeigen
                    st.components.v1.html(m._repr_html_(), height=450)
                    
                    # HTML für ZIP-Export generieren
                    safe_ort = "".join([c for c in ort if c.isalnum() or c in " _-"])
                    zip_file.writestr(f"Karte_{safe_ort}.html", m._repr_html_())
            
            st.divider()
            
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("📥 ZIP: Alle Karten", 
                                   zip_buffer.getvalue(), 
                                   f"INTEGRAL_Export_{datetime.now().strftime('%H%M')}.zip", 
                                   "application/zip")
            
            if fehler_liste:
                with c2:
                    fehler_text = "\n".join(fehler_liste)
                    st.download_button("⚠️ Fehlerliste (.txt)", 
                                       fehler_text, 
                                       "nicht_gefunden.txt", 
                                       "text/plain")
        else:
            st.error("Keine der Straßen wurde im Landkreis gefunden.")
