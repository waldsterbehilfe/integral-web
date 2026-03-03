import networkx as nx

def berechne_grobe_route(gdf_liste, orts_graph):
    """
    Findet eine sinnvolle Reihenfolge der Straßen und berechnet die Gesamtfahrstrecke.
    """
    total_route_km = 0.0
    # Wir nehmen die Schwerpunkte (Centroids) jeder Straße als Stopps
    stopps = [gdf.geometry.unary_union.centroid for gdf in gdf_liste]
    
    if not stopps: return 0.0
    
    # Finde die nächsten Knoten im Straßennetz für unsere Stopps
    nodes = [ox.nearest_nodes(orts_graph, p.x, p.y) for p in stopps]
    
    current_node = nodes[0]
    besuchte_nodes = [current_node]
    verbleibende_nodes = nodes[1:]
    
    while verbleibende_nodes:
        # Finde den nächstgelegenen Knoten im Netzwerk
        next_node = min(verbleibende_nodes, 
                        key=lambda n: nx.shortest_path_length(orts_graph, current_node, n, weight='length'))
        
        # Addiere die echte Fahrtstrecke zum Gesamtergebnis
        dist = nx.shortest_path_length(orts_graph, current_node, next_node, weight='length')
        total_route_km += dist
        
        current_node = next_node
        besuchte_nodes.append(current_node)
        verbleibende_nodes.remove(current_node)
        
    # Am Ende noch die Eigenlänge der Zielstraßen dazu (grob geschätzt)
    eigene_laenge = sum(gdf.to_crs(epsg=32632).geometry.length.sum() for gdf in gdf_liste)
    
    return (total_route_km + eigene_laenge) / 1000  # Rückgabe in km
