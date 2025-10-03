import cv2
import numpy as np

def auto_crop_xingying_template(image_path: str, save_path: str):
    """
    Automatically finds and crops a 'Xingying' (camp) template from the board.
    """
    try:
        image = cv2.imread(image_path)
        if image is None:
            print("Error: Could not read the image file.")
            return

        # 1. Convert to HSV and define the orange-yellow color range for the camp
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        # This range is broad to catch shades of orange/yellow. Hue, Saturation, Value
        lower_orange_yellow = np.array([15, 100, 100])
        upper_orange_yellow = np.array([35, 255, 255])
        
        mask = cv2.inRange(hsv, lower_orange_yellow, upper_orange_yellow)

        # 2. Find contours on the mask
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_contour = None
        min_diff = float('inf')

        for cnt in contours:
            # 3. Filter contours by area and circularity to find the best circle
            area = cv2.contourArea(cnt)
            
            # Camps are small, filter out anything too large or too small
            if 100 < area < 1000:
                perimeter = cv2.arcLength(cnt, True)
                if perimeter == 0:
                    continue
                
                # Circularity formula: 4 * pi * area / (perimeter^2)
                # A perfect circle has a circularity of 1
                circularity = (4 * np.pi * area) / (perimeter ** 2)
                
                # We want the contour that is closest to a perfect circle
                diff = abs(1 - circularity)
                if diff < min_diff:
                    min_diff = diff
                    best_contour = cnt

        if best_contour is None:
            print("Error: Could not find a suitable circular contour for the camp template.")
            return

        # 4. Crop the template from the original image using the bounding box
        x, y, w, h = cv2.boundingRect(best_contour)
        # Add a small padding to ensure the whole circle is captured
        padding = 2
        cropped_template = image[y-padding:y+h+padding, x-padding:x+w+padding]

        # 5. Save the cropped template
        cv2.imwrite(save_path, cropped_template)
        print(f"Successfully cropped and saved the camp template to '{save_path}'")
        print(f"Template dimensions: {cropped_template.shape[1]}x{cropped_template.shape[0]}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    auto_crop_xingying_template("1.png", "template_xingying.png")
