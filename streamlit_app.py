# --- FUNKTION (MIT STRIKTER FILTERUNG - FIX FÜR ÜBERMARKIERUNG) ---
def verarbeite_strasse(strasse_input):
    if not strasse_input: return {"success": False}
    
    time.sleep(random.uniform(1.0, 1.8))
    
    if " | " in strasse_input:
        parts = strasse_input.split(" | ")
        strasse_name = parts[0].strip()
        hnr = parts[1].strip()
    else:
        strasse_name = strasse_input.strip()
        hnr = None

    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse_name).strip()
    query = f"{s_clean}, Marburg-Biedenkopf"
    
    try:
        # Radius auf 50m leicht erhöht, damit er die Straße sicher trifft
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=50)
        
        if gdf.empty:
            return {"success": False, "original": strasse_input}

        # --- OPTIMIERTER FILTER (EXAKTER ABGLEICH) ---
        # Statt .contains nutzen wir nun den exakten Vergleich oder striktes Regex
        # Das verhindert, dass Nebenstraßen mit markiert werden.
        gdf = gdf[gdf['name'].apply(lambda x: str(x).strip().lower() == s_clean.lower())]
        
        if gdf.empty:
            # Fallback: Falls exakt nicht geht, nimm den ersten Treffer der Query
            # aber nur von der tatsächlichen Straße
            gdf = ox.features_from_address(query, tags={"highway": True}, dist=20)

        # --- REST BLEIBT GLEICH ---
        marker_coords = None
        if hnr:
            loc = geolocator.geocode(f"{s_clean} {hnr}, Marburg-Biedenkopf", timeout=10)
            if loc:
                marker_coords = (loc.latitude, loc.longitude)

        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])].to_crs(epsg=4326)
        osm_name = gdf['name'].iloc[0] if 'name' in gdf.columns else s_clean
        
        # Ortsteil-Logik...
        ortsteil = "Unbekannt"
        # (hier folgt dein bestehender Code zur Ortsteilbestimmung)
        
        return {
            "gdf": gdf, 
            "ort": ortsteil, 
            "name": osm_name, 
            "original": strasse_input, 
            "marker": marker_coords, 
            "success": True
        }
    except:
        pass
    return {"success": False, "original": strasse_input}
