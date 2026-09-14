import json
import torch
from data_loader import get_edge_index_from_graph

def export_visualization_graph(num_nodes=5000):
    """
    Exports a 5,000 node subgraph for the web visualizer.
    """
    print(f"Extracting {num_nodes} nodes for the web visualizer...")
    
    # Just generate a small set of edges directly for the visualizer
    edge_index = get_edge_index_from_graph(None, num_nodes=5000, expected_edges=15000)
    
    nodes = []
    for n in range(num_nodes):
        if n == 0:
            color, group = "#ff3366", "Sensory"
        elif n >= num_nodes - 4:
            color, group = "#33ccff", "Motor"
        else:
            color, group = "#aaaaaa", "Interneuron"
        nodes.append({"id": str(n), "group": group, "color": color})
        
    links = []
    sources = edge_index[0].tolist()
    targets = edge_index[1].tolist()
    for s, t in zip(sources, targets):
        links.append({"source": str(s), "target": str(t), "value": 1})
        
    data = {"nodes": nodes, "links": links}
    
    import os
    os.makedirs("static", exist_ok=True)
    with open("static/graph_data.json", 'w') as f:
        json.dump(data, f)
    
    print(f"Exported {len(nodes)} nodes and {len(links)} edges for visualization.")

if __name__ == "__main__":
    export_visualization_graph()
