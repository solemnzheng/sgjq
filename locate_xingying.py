import cv2
import numpy as np
from sklearn.cluster import DBSCAN
from game_analyzer import GameAnalyzer

def locate_and_analyze_camps(board_image_path: str, template_path: str):
    """
    Finds all camps on the board, assigns them to player rows, and reports the counts.
    """
    try:
        board_image = cv2.imread(board_image_path)
        template_image = cv2.imread(template_path)
        if board_image is None or template_image is None:
            print("Error: Could not read image or template file.")
            return

        # 1. Perform template matching to find all camps
        result = cv2.matchTemplate(board_image, template_image, cv2.TM_CCOEFF_NORMED)
        
        # Use a relatively high threshold to avoid false positives
        threshold = 0.85
        locations = np.where(result >= threshold)
        
        # Use a simple form of non-maximum suppression
        rects = []
        for pt in zip(*locations[::-1]):
            rects.append([int(pt[0]), int(pt[1]), template_image.shape[1], template_image.shape[0]])

        # Group overlapping rectangles
        def non_max_suppression_fast(boxes, overlapThresh):
            if len(boxes) == 0: return []
            pick = []
            x1, y1, x2, y2 = boxes[:,0], boxes[:,1], boxes[:,0]+boxes[:,2], boxes[:,1]+boxes[:,3]
            area = (x2 - x1 + 1) * (y2 - y1 + 1)
            idxs = np.argsort(y2)
            while len(idxs) > 0:
                last = len(idxs) - 1
                i = idxs[last]
                pick.append(i)
                xx1 = np.maximum(x1[i], x1[idxs[:last]])
                yy1 = np.maximum(y1[i], y1[idxs[:last]])
                xx2 = np.minimum(x2[i], x2[idxs[:last]])
                yy2 = np.minimum(y2[i], y2[idxs[:last]])
                w, h = np.maximum(0, xx2 - xx1 + 1), np.maximum(0, yy2 - yy1 + 1)
                overlap = (w * h) / area[idxs[:last]]
                idxs = np.delete(idxs, np.concatenate(([last], np.where(overlap > overlapThresh)[0])))
            return boxes[pick].astype("int")

        camp_rects = non_max_suppression_fast(np.array(rects), 0.3)
        
        print(f"Found {len(camp_rects)} camps on the entire board.")
        
        # 2. Get player regions from GameAnalyzer
        analyzer = GameAnalyzer("vision/new_templates")
        regions = analyzer.get_player_regions(board_image)
        
        # 3. Assign each camp to a player region
        camps_in_regions = {name: [] for name in regions}
        for x, y, w, h in camp_rects:
            cx, cy = x + w // 2, y + h // 2
            for name, (x1, y1, x2, y2) in regions.items():
                if x1 <= cx < x2 and y1 <= cy < y2:
                    camps_in_regions[name].append({'x': cx, 'y': cy})
                    break
        
        # 4. For the '下方' player, determine which row each camp belongs to
        if "下方" in camps_in_regions:
            bottom_camps = camps_in_regions["下方"]
            
            # We need a reference for the rows. Let's get the piece locations.
            # This part is simplified from the previous script.
            blue_pieces = [d for d in analyzer.analyze_screenshot(board_image, return_detections=True) if d.template.color == 'blue']
            piece_centers = [{'x': (p.bbox[0]+p.bbox[2])/2, 'y': (p.bbox[1]+p.bbox[3])/2} for p in blue_pieces]
            
            y_coords = np.array([p['y'] for p in piece_centers]).reshape(-1, 1)
            clustering = DBSCAN(eps=15, min_samples=1).fit(y_coords)
            
            row_y_centers = {}
            for i, label in enumerate(clustering.labels_):
                if label not in row_y_centers: row_y_centers[label] = []
                row_y_centers[label].append(piece_centers[i]['y'])
            
            avg_row_y = {label: np.mean(ys) for label, ys in row_y_centers.items()}
            sorted_row_labels = sorted(avg_row_y.keys(), key=lambda k: avg_row_y[k])

            # Now, assign each camp to the nearest row
            camps_per_row = [0] * len(sorted_row_labels)
            for camp in bottom_camps:
                camp_y = camp['y']
                # Find the row with the minimum y-distance
                min_dist = float('inf')
                best_row_idx = -1
                for i, label in enumerate(sorted_row_labels):
                    dist = abs(camp_y - avg_row_y[label])
                    if dist < min_dist:
                        min_dist = dist
                        best_row_idx = i
                if best_row_idx != -1:
                    camps_per_row[best_row_idx] += 1
            
            print("\n--- Analysis of Camps in Bottom Player's Area ---")
            print(f"Camps found per row: {camps_per_row}")
            
            # 5. Final Calculation
            previous_nodes = [5, 3, 4, 3, 5, 5]
            final_nodes = [p + c for p, c in zip(previous_nodes, camps_per_row)]
            
            print("\n--- Final Node Count per Row (Pieces + Camps) ---")
            for i, (p, c, f) in enumerate(zip(previous_nodes, camps_per_row, final_nodes)):
                print(f"Row {i+1}: {p} (pieces) + {c} (camps) = {f} total nodes")
            print(f"\nFinal Summary: {final_nodes}")

    except Exception as e:
        print(f"An error occurred: {e}")

# A small patch is needed for analyze_screenshot to return detections
def patched_analyze_screenshot(self, screenshot: np.ndarray, match_threshold: float = 0.7, return_detections=False):
    # This is a simplified version of the original function
    templates_by_color = {c: [] for c in self.hsv_color_ranges.keys()}
    for t in self.templates_manager.get_all_templates():
        if t.color in templates_by_color:
            templates_by_color[t.color].append(t)
    
    matches = find_all_matches_with_color_mask(screenshot, templates_by_color, self.hsv_color_ranges, threshold=match_threshold)
    detections = standard_non_max_suppression(matches, iou_threshold=0.3)
    
    if return_detections:
        return detections
    # The original reporting logic would go here
    return "Report generation skipped"

if __name__ == "__main__":
    # Temporarily patch the GameAnalyzer to allow returning raw detections
    GameAnalyzer.original_analyze = GameAnalyzer.analyze_screenshot
    GameAnalyzer.analyze_screenshot = patched_analyze_screenshot
    
    # We also need to import the functions for the patch to work
    from game_analyzer import find_all_matches_with_color_mask, standard_non_max_suppression
    
    locate_and_analyze_camps("1.png", "template_xingying.png")
