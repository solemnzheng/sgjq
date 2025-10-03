import cv2
import numpy as np
from sklearn.cluster import DBSCAN
from game_analyzer import GameAnalyzer

def analyze_central_region(image_path: str):
    """
    Precisely crops the central region and counts the nodes within it
    using feature detection.
    """
    try:
        image = cv2.imread(image_path)
        if image is None:
            print("Error: Could not read the image file.")
            return

        # 1. Use GameAnalyzer to get the precise central region
        analyzer = GameAnalyzer("vision/new_templates")
        regions = analyzer.get_player_regions(image)
        
        if "中央" not in regions:
            print("Error: GameAnalyzer could not identify the '中央' (central) region.")
            return
            
        x1, y1, x2, y2 = regions["中央"]
        # Ensure coordinates are integers for cropping
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        central_image = image[y1:y2, x1:x2]

        if central_image.size == 0:
            print("Error: Central region is empty or invalid.")
            return

        # 2. Preprocess the cropped central image
        gray = cv2.cvtColor(central_image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)

        # 3. Detect features (corners) within the central region
        corners = cv2.goodFeaturesToTrack(
            binary,
            maxCorners=100,      # More than enough for the central area
            qualityLevel=0.02,
            minDistance=10
        )

        if corners is None or len(corners) < 1:
            print("Error: No feature points were detected in the central region.")
            return

        points = np.intp(corners).reshape(-1, 2)

        # 4. Cluster the points to find the exact number of nodes
        # Using min_samples=1 to ensure even isolated points are counted as nodes
        clustering = DBSCAN(eps=20, min_samples=1).fit(points)
        
        labels = clustering.labels_
        n_nodes = len(set(labels))

        print(f"Analysis of the Central Region:")
        print("-" * 30)
        print(f"Detected {len(points)} raw feature points.")
        print(f"After clustering, found {n_nodes} distinct nodes in the central region.")
        print("-" * 30)

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    analyze_central_region("1.png")
