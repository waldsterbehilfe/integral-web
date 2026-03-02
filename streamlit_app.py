import streamlit as st
import osmnx as ox
import folium
import io, re, os, random
import pandas as pd
import geopandas as gpd
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from geopy.geocoders import Nominatim # NEU
from geopy.extra.rate_limiter import RateLimiter # NEU

# --- SETUP ---
st.set_page_config(page_title="INTEGRAL PRO", layout="wide", page_icon="📈")

# NEU: Geocoder Setup
geolocator = Nominatim(user_agent="integral_pro_app")
reverse = RateLimiter(geolocator.reverse, min_delay_seconds=1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "persistent_geocache")
os.makedirs(CACHE_DIR, exist_ok=True)
ox.settings.use_cache = True
ox.settings.cache_folder = CACHE_DIR

if 'run_processing' not in st.session_state: st.session_state.run_processing = False
if 'stop_requested' not in st.session_state: st.session_state.stop_requested = False

def get_random_color():
    return f"#{random.randint(0, 0xFFFFFF):06x}"

# --- 2. VERBESSERTE LOGIK ---
def verarbeite_strasse(strasse):
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    
    # Präziserer Query
    query = f"{s_clean}, Marburg-Biedenkopf"
    
    try:
        # 1. Daten holen
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=500)
        
        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            if 'name' in gdf.columns:
                gdf_f = gdf[gdf['name'].str.contains(s_clean, case=False, na=False)]
            else:
                gdf_f = gdf

            if not gdf_f.empty:
                # 2. Verbesserte Ortsteil-Erkennung (Rückwärts)
                ortsteil = "Unbekannter_Ort"
                
                # Nimm den Mittelpunkt der Straße für das Reverse Geocoding
                centroid = gdf_f.geometry.centroid.iloc[0]
                location = reverse((centroid.y, centroid.x), language='de')
                
                if location and 'address' in location.raw:
                    addr = location.raw['address']
                    # Suche nach präzisen Bezeichnungen
                    for key in ['village', 'hamlet', 'suburb', 'city_district', 'town']:
                        if key in addr:
                            ortsteil = addr[key]
                            break
                
                return {"gdf": gdf_f, "ort": ortsteil, "name": s_clean, "success": True}
    except Exception as e:
        return {"success": False, "original": strasse, "error": str(e)}
        
    return {"success": False, "original": strasse}

# --- 3. UI (Bleibt gleich) ---
# ... [UI Code aus V4.2 hier einfügen] ...
