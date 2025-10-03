import cv2
import numpy as np
from sklearn.cluster import DBSCAN
from collections import Counter
# Import the class and the functions we need
from game_analyzer import GameAnalyzer, DetectionResult, find_all_matches_with_color_mask, standard_non_max_suppression
from typing import List, Dict

def analyze_rows_and_nodes_final(image_path: str):
    """
    Final, most accurate analysis of rows and nodes based on the perfected
    GameAnalyzer's full detection results.
    """
    try:
        image = cv2.imread(image_path)
        if image is None:
            print("Error: Could not read the image file.")
            return

        # 1. Initialize the analyzer to access its configuration
        analyzer = GameAnalyzer("vision/new_templates")
        
        # 2. Group templates by color
        templates_by_color: Dict[str, List] = {}
        for t in analyzer.templates_manager.get_all_templates():
            if t.color not in templates_by_color:
                templates_by_color[t.color] = []
            templates_by_color[t.color].append(t)

        # 3. Call the imported functions directly to get all detections
        matches = find_all_matches_with_color_mask(image, templates_by_color, analyzer.hsv_color_ranges, threshold=0.7)
        detections = standard_non_max_suppression(matches, iou_threshold=0.3)

        # 4. Filter for only the blue pieces
        blue_pieces: List[DetectionResult] = [d for d in detections if d.template.color == 'blue']

        if not blue_pieces:
            print("Error: No blue pieces were detected by the analyzer.")
            return

        # 5. Get center points of the blue pieces
        piece_centers = []
        for piece in blue_pieces:
            x1, y1, x2, y2 = piece.bbox
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            piece_centers.append({'x': cx, 'y': cy})

        # 6. Cluster Y-coordinates to identify rows
        y_coords = np.array([p['y'] for p in piece_centers]).reshape(-1, 1)
        clustering = DBSCAN(eps=15, min_samples=1).fit(y_coords)
        labels = clustering.labels_
        
        # 7. Assign each piece to a row
        pieces_by_row: Dict[int, List] = {label: [] for label in set(labels)}
        for i, label in enumerate(labels):
            pieces_by_row[label].append(piece_centers[i])

        # 8. Count nodes in each row and present results
        sorted_rows = sorted(pieces_by_row.items(), key=lambda item: np.mean([p['y'] for p in item[1]]))
        
        print(f"Final Analysis of the Bottom Player's Area ({len(blue_pieces)} pieces found):")
        print("-" * 30)
        
        row_node_counts = []
        for i, (label, pieces) in enumerate(sorted_rows):
            num_nodes = len(pieces)
            row_node_counts.append(num_nodes)
            print(f"Row {i+1} (Y≈{int(np.mean([p['y'] for p in pieces]))}): Contains {num_nodes} nodes.")
        
        print("-" * 30)
        print(f"Summary of nodes per row: {row_node_counts}")
        print(f"Total nodes/pieces counted: {sum(row_node_counts)}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    analyze_rows_and_nodes_final("1.png")
