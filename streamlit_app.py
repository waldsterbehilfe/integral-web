import st.dataframe as st_df # Für interne Referenz

# ... (restlicher Setup-Code bleibt gleich) ...

def sync_editor():
    """Überarbeitete Sync-Logik: Verhindert KeyError durch Prüfung der State-Struktur"""
    if "streets_editor" in st.session_state:
        # Wir holen uns die aktuellen Daten direkt aus dem State
        editor_state = st.session_state["streets_editor"]
        
        # Streamlit speichert im 'data' Key nur die initialen Daten plus Änderungen.
        # Wir müssen sicherstellen, dass wir nicht ins Leere greifen.
        if "data" in editor_state:
            # Wenn der Key da ist, ziehen wir die Liste
            try:
                new_data = editor_state["data"]["Adresse (Strasse | Nr)"].tolist()
                save_streets(new_data)
            except Exception:
                # Falls die Struktur intern während des Edits abweicht
                pass

# --- Im UI Bereich ---
if not st.session_state.ort_sammlung:
    # ...
    with s_col2:
        st.subheader(f"📝 Liste ({len(st.session_state.saved_manual_streets)})")
        
        # WICHTIG: Wir übergeben das DataFrame direkt aus dem State, 
        # damit Anzeige und Datei immer synchron bleiben.
        df_init = pd.DataFrame(st.session_state.saved_manual_streets, columns=["Adresse (Strasse | Nr)"])
        
        st.data_editor(
            df_init, 
            num_rows="dynamic", 
            use_container_width=True, 
            key="streets_editor", 
            on_change=sync_editor
        )
