import cv2
import numpy as np
from typing import List, Dict, Tuple, Any
from collections import Counter
from sklearn.cluster import KMeans
from dataclasses import dataclass
from multiprocessing import Pool, cpu_count
import time

# --- 导入核心模块 ---
from vision.templates_manager import TemplatesManager, Template
from game_model import BoardState, Piece, map_pixel_to_grid

# --- Top-level function for multiprocessing ---
def parallel_find_matches_static(args: Tuple) -> List[Dict]:
    """
    A static, top-level function for parallel processing to avoid pickling issues.
    It takes a tuple of arguments and returns a list of dictionaries with detection info.
    """
    image, templates, threshold, color = args
    results = []
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    for template in templates:
        gray_template = cv2.cvtColor(template.image, cv2.COLOR_BGR2GRAY)
        if gray_template.shape[0] > gray_image.shape[0] or gray_template.shape[1] > gray_image.shape[1]:
            continue
        
        match_result = cv2.matchTemplate(gray_image, gray_template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(match_result >= threshold)
        
        for pt in zip(*locations[::-1]):
            confidence = match_result[pt[1], pt[0]]
            # Create a serializable dictionary instead of a custom object
            result_info = {
                'piece_type': template.piece_type,
                'color': template.color,
                'orientation': template.orientation,
                'image_shape': template.image.shape,
                'location': pt,
                'confidence': confidence
            }
            results.append(result_info)
    return results

@dataclass
class DetectionResult:
    """A dataclass to hold detection results after processing."""
    template_info: Dict[str, Any]
    location: Tuple[int, int]
    confidence: float

    @property
    def piece_name(self) -> str:
        return self.template_info['piece_type']
    
    @property
    def color(self) -> str:
        return self.template_info['color']

    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        x1, y1 = self.location
        h, w, _ = self.template_info['image_shape']
        x2 = x1 + w
        y2 = y1 + h
        return (x1, y1, x2, y2)

class GameAnalyzer:
    def __init__(self, templates_path: str):
        self.tm = TemplatesManager(templates_path)
        self.tm.load_templates()
        # Initialize the pool only once
        self.pool = Pool(processes=cpu_count())

    def get_all_detections(self, board_image: np.ndarray, match_threshold: float = 0.8) -> List[DetectionResult]:
        """
        Performs template matching in parallel and returns all raw detection results.
        """
        tasks = []
        templates_by_color = self.tm.get_templates_by_color()
        for color, templates in templates_by_color.items():
            task = (board_image, templates, match_threshold, color)
            tasks.append(task)

        # Use the static function for mapping
        results_from_pool = self.pool.map(parallel_find_matches_static, tasks)

        all_matches_info = [item for sublist in results_from_pool for item in sublist]

        # Convert the dictionaries back into DetectionResult objects
        all_matches = [
            DetectionResult(
                template_info=info,
                location=info['location'],
                confidence=info['confidence']
            ) for info in all_matches_info
        ]

        detections = standard_non_max_suppression(all_matches, iou_threshold=0.3)
        return detections

    def analyze_screenshot(self, screenshot: np.ndarray, locked_regions: Dict, match_threshold: float = 0.8) -> BoardState:
        detections = self.get_all_detections(screenshot, match_threshold)
        
        timestamp = time.time()
        preliminary_state = BoardState(timestamp=timestamp)

        temp_id_counter = 0
        for det in detections:
            center_x = det.bbox[0] + (det.bbox[2] - det.bbox[0]) / 2
            center_y = det.bbox[1] + (det.bbox[3] - det.bbox[1]) / 2
            
            grid_info = map_pixel_to_grid(center_x, center_y, locked_regions)
            if not grid_info:
                continue

            player_pos, board_coords = grid_info
            
            temp_id = f"temp_{temp_id_counter}"
            temp_id_counter += 1

            piece = Piece(
                id=temp_id,
                name=det.piece_name,
                color=det.color,
                player_pos=player_pos,
                board_coords=board_coords
            )
            preliminary_state.pieces[temp_id] = piece
            preliminary_state.grid[board_coords] = temp_id
            
        return preliminary_state

    def get_player_regions(self, screenshot: np.ndarray, match_threshold: float = 0.7) -> Dict[str, Tuple[int, int, int, int]]:
        all_detections = self.get_all_detections(screenshot, match_threshold)
        if len(all_detections) < 4:
            return {}

        points = np.array([
            (det.bbox[0] + (det.bbox[2] - det.bbox[0]) / 2, det.bbox[1] + (det.bbox[3] - det.bbox[1]) / 2)
            for det in all_detections
        ])

        kmeans = KMeans(n_clusters=4, random_state=0, n_init=10).fit(points)
        
        centers = kmeans.cluster_centers_
        img_center_x, img_center_y = screenshot.shape[1] / 2, screenshot.shape[0] / 2
        
        labels = {}
        for i, (cx, cy) in enumerate(centers):
            if abs(cx - img_center_x) > abs(cy - img_center_y):
                labels[i] = "左侧" if cx < img_center_x else "右侧"
            else:
                labels[i] = "上方" if cy < img_center_y else "下方"

        regions = {}
        for i in range(4):
            cluster_points = points[kmeans.labels_ == i]
            if len(cluster_points) > 0:
                min_x, min_y = np.min(cluster_points, axis=0)
                max_x, max_y = np.max(cluster_points, axis=0)
                regions[labels[i]] = (int(min_x), int(min_y), int(max_x), int(max_y))

        if len(regions) == 4:
            center_min_x = max(regions["左侧"][2], regions["上方"][0], regions["下方"][0])
            center_max_x = min(regions["右侧"][0], regions["上方"][2], regions["下方"][2])
            center_min_y = max(regions["上方"][3], regions["左侧"][1], regions["右侧"][1])
            center_max_y = min(regions["下方"][1], regions["左侧"][3], regions["右侧"][3])
            regions["中央"] = (int(center_min_x), int(center_min_y), int(center_max_x), int(center_max_y))
            
        return regions

    def visualize_regions_on_image(self, image: np.ndarray, regions: Dict) -> np.ndarray:
        vis_image = image.copy()
        colors = {
            "上方": (255, 0, 0), "下方": (0, 255, 0),
            "左侧": (0, 0, 255), "右侧": (255, 255, 0),
            "中央": (255, 0, 255)
        }
        for name, (x1, y1, x2, y2) in regions.items():
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), colors.get(name, (255,255,255)), 2)
            cv2.putText(vis_image, name, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, colors.get(name, (255,255,255)), 2)
        return vis_image

    def __del__(self):
        # Ensure the pool is closed when the object is destroyed
        self.pool.close()
        self.pool.join()

def standard_non_max_suppression(detections: List[DetectionResult], iou_threshold: float) -> List[DetectionResult]:
    if not detections: return []
    detections.sort(key=lambda x: x.confidence, reverse=True)
    final_detections = []
    while detections:
        best = detections.pop(0)
        final_detections.append(best)
        remaining = []
        for other in detections:
            x1=max(best.bbox[0],other.bbox[0]); y1=max(best.bbox[1],other.bbox[1])
            x2=min(best.bbox[2],other.bbox[2]); y2=min(best.bbox[3],other.bbox[3])
            intersection=max(0,x2-x1)*max(0,y2-y1)
            area_best=(best.bbox[2]-best.bbox[0])*(best.bbox[3]-best.bbox[1])
            area_other=(other.bbox[2]-other.bbox[0])*(other.bbox[3]-other.bbox[1])
            union=area_best+area_other-intersection
            iou=intersection/union if union>0 else 0
            if iou<iou_threshold: remaining.append(other)
        detections=remaining
    return final_detections