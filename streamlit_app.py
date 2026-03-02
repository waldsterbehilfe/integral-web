def verarbeite_strasse(strasse):
    s_clean = re.sub(r'(?i)\bstr\b\.?', 'Straße', strasse).strip()
    query = f"{s_clean}, Landkreis Marburg-Biedenkopf, Germany"
    
    try:
        # 1. Daten holen (Radius etwas kleiner für mehr Präzision)
        gdf = ox.features_from_address(query, tags={"highway": True}, dist=500)
        
        if not gdf.empty:
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            
            # --- NEUE, STRENGE FILTERUNG ---
            # Wir behalten nur Straßen, die EXAKT den gesuchten Namen enthalten
            if 'name' in gdf.columns:
                gdf_f = gdf[gdf['name'].str.lower() == s_clean.lower()]
            else:
                gdf_f = gdf

            if not gdf_f.empty:
                # ... (Rest der Ortsteil-Erkennung bleibt gleich)
                ortsteil = "Unbekannter_Ort"
                cols = ['addr:suburb', 'suburb', 'village', 'hamlet', 'addr:city', 'city']
                for col in cols:
                    if col in gdf_f.columns and gdf_f[col].dropna().any():
                        val = str(gdf_f[col].dropna().iloc[0])
                        if "Marburg-Biedenkopf" not in val:
                            ortsteil = val
                            break
                return {"gdf": gdf_f, "ort": ortsteil, "name": s_clean, "success": True, "corrected": s_clean != strasse}
    except: pass
    return {"success": False, "original": strasse}
