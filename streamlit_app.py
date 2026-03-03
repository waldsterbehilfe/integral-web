# ... (Importe wie oben, plus networkx)
import networkx as nx

# --- NEUE ROUTEN-LOGIK ---
def berechne_tour_km(ort, items):
    try:
        # Lade das Straßennetz für den Ortsteil
        G = ox.graph_from_address(f"{ort}, Marburg-Biedenkopf", network_type='drive', dist=3000)
        G = ox.project_graph(G, to_crs='EPSG:32632')
        
        # Hol die Knoten für alle markierten Straßen
        points = [item["gdf"].to_crs(epsg=32632).geometry.unary_union.centroid for item in items]
        nodes = [ox.nearest_nodes(G, p.x, p.y) for p in points]
        
        # Einfache "Nächster-Nachbar" Tour
        total_dist = 0
        current_node = nodes[0]
        to_visit = nodes[1:]
        
        while to_visit:
            next_node = min(to_visit, key=lambda n: nx.shortest_path_length(G, current_node, n, weight='length'))
            total_dist += nx.shortest_path_length(G, current_node, next_node, weight='length')
            current_node = next_node
            to_visit.remove(next_node)
            
        # + Eigenlänge der Straßen
        own_len = sum(item["laenge"] for item in items)
        return (total_dist + own_len) / 1000
    except:
        return sum(item["laenge"] for item in items) / 1000 * 1.3 # Fallback: Luftlinie + 30%

# --- UI ANPASSUNG ---
if st.session_state.ort_sammlung:
    if st.button("🛣️ ROUTE & ECHTE KM BERECHNEN (Planungs-Modus)"):
        with st.spinner("Berechne optimale Fahrwege..."):
            for ort, items in st.session_state.ort_sammlung.items():
                echte_km = berechne_tour_km(ort, items)
                st.session_state.ort_results[ort] = echte_km # Speichern im State
        st.success("Berechnung abgeschlossen!")
