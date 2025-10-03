import cv2
import numpy as np
from sklearn.cluster import DBSCAN

def count_board_positions(image_path: str):
    """
    Analyzes a board screenshot to count the number of valid positions.
    """
    try:
        # 1. Load and preprocess the image
        image = cv2.imread(image_path)
        if image is None:
            print("Error: Could not read the image file.")
            return

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Use a binary threshold to isolate the board lines and positions
        # This helps in getting cleaner features
        _, binary = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)

        # 2. Detect features using Shi-Tomasi Corner Detector
        # This is excellent for finding corners of the grid squares
        corners = cv2.goodFeaturesToTrack(
            binary,
            maxCorners=500,       # High number to ensure we get everything
            qualityLevel=0.02,    # Low quality level to be sensitive
            minDistance=5         # Small min distance to detect close points
        )

        if corners is None or len(corners) < 1:
            print("Error: No corners were detected.")
            return

        points = np.intp(corners).reshape(-1, 2)

        # 3. Cluster the detected points
        # A single position might have multiple corners detected around it.
        # We use DBSCAN to group these into single clusters.
        # The `eps` parameter is crucial: it's the max distance between two samples 
        # for one to be considered as in the neighborhood of the other. 
        # This should be roughly the radius of a single piece position.
        # Let's estimate a piece position to be around 30x30 pixels, so a radius of 15-20.
        clustering = DBSCAN(eps=20, min_samples=2).fit(points)
        
        # The number of clusters is the number of unique labels, excluding the noise label (-1)
        labels = clustering.labels_
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

        print(f"Detected {len(points)} raw feature points.")
        print(f"After clustering, found {n_clusters} distinct positions on the board.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    count_board_positions("1.png")
