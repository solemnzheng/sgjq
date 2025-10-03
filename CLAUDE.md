# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based AI assistant for the game "Four-Country Military Chess" (四国军棋). It uses computer vision to analyze the game board from a screen capture, identify the pieces and their positions, and determine the game state.

Key technologies used:
- Python as the main programming language
- OpenCV (cv2) for computer vision tasks like template matching and image processing
- Tkinter for the GUI dashboard
- Scikit-learn (sklearn) for clustering algorithms (KMeans, DBSCAN) to identify player regions on the board
- Numpy for numerical operations, especially with image data and coordinates
- Windows API (win32gui, win32process, etc.) for screen capture on Windows

## Code Architecture

The application is organized into several modules with specific responsibilities:

1. **Dashboard GUI** (`dashboard_main.py`): Main GUI application with Tkinter interface for controlling the analysis
2. **Game Analysis** (`game_analyzer.py`): Core game state analysis, piece detection, and reporting
3. **Screen Capture** (`capture/realtime_capture.py`): Handles capturing screenshots of the game window
4. **Template Management** (`vision/templates_manager.py`): Manages the template images used for piece detection
5. **Vision Utilities** (`vision/` directory): Additional computer vision utilities and algorithms

The application works by:
1. Calibrating to find the game window using Windows API
2. Capturing screenshots of the game board
3. Using template matching with pre-defined images to locate pieces
4. Analyzing detected pieces to determine player regions and game state
5. Displaying results in a GUI dashboard

## Development Commands

### Environment Setup

Install required packages:
```bash
pip install opencv-python-headless typer scikit-learn numpy pynput rich pywin32 psutil
```

### Running the Application

1. Start the GUI dashboard:
```bash
python dashboard_main.py
```

2. Within the GUI:
   - Click "1. 检测游戏窗口" to detect the game window
   - Click "2. 开始识别" to start recognition
   - Click "3. 锁定初始分区" to lock initial regions
   - Use other buttons for visualization features

### Testing

Run the analyzer test script:
```bash
python test_analyzer.py
```
(Note: Requires 1.png and 2.png test images in the root directory)

## Key Implementation Details

- Piece detection uses HSV color masking combined with template matching for robust recognition
- Player regions are identified using KMeans clustering of detected piece positions
- Central region is calculated based on the positions of the four player regions
- Non-maximum suppression is used to eliminate duplicate detections
- All coordinates are mapped to logical grid positions using coordinate mapping