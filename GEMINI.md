# 四国军棋 (Four-Country Military Chess) AI Assistant

## Project Overview

This project is a Python-based AI assistant for the game "Four-Country Military Chess" (四国军棋). It uses computer vision to analyze the game board from a screen capture, identify the pieces and their positions, and determine the game state.

The core technologies used are:
- **Python**: The main programming language.
- **OpenCV (`cv2`)**: For computer vision tasks like template matching and image processing.
- **Typer**: For creating the command-line interface.
- **Scikit-learn (`sklearn`)**: Used for clustering algorithms (`KMeans`) to identify player regions on the board.
- **Numpy**: For numerical operations, especially with image data and coordinates.

The application works by:
1.  **Calibration**: Identifying the game window and the board area on the screen. This can be done automatically or manually.
2.  **Screen Capture**: Continuously grabbing images of the game board.
3.  **Piece Detection**: Using template matching with pre-defined images of the chess pieces to locate them on the board.
4.  **Game State Analysis**: Mapping detected pieces to the board's grid, identifying player regions, and logging the state of the game.

## Building and Running

This project does not have a standard `requirements.txt`. Based on the imports, you will need to install the following packages:

```bash
pip install opencv-python-headless typer scikit-learn numpy pynput rich
```

### Key Commands

**1. Calibrate the Board:**

Before running the main application, you need to calibrate the board to let the program know where the game is on your screen.

*   **Automatic Calibration:**
    ```bash
    python main.py calibrate
    ```
*   **Manual Calibration (if automatic fails):**
    ```bash
    python main.py calibrate --manual
    ```

**2. Run the AI Assistant:**

Once calibrated, you can run the main recognition loop.

```bash
python main.py run
```

The `run` command has different modes, but `suggest_only` appears to be the default.

## Development Conventions

*   **Configuration**: The application uses a `config.json` file to store settings, including the board region coordinates.
*   **Modularity**: The code is organized into modules with specific responsibilities:
    *   `capture/`: Screen capturing logic.
    *   `vision/`: Image processing, template matching, and OCR.
    *   `board/`: Game board state representation and coordinate mapping.
    *   `main.py`: Main application entry point and CLI.
    *   `game_analyzer.py`: High-level game state analysis.
*   **Templates**: Piece detection relies on a directory of template images (e.g., `vision/new_templates/`). Each piece for each color has its own image file.
*   **Coordinate Mapping**: A `new_coordinate_map.json` file in the `board/` directory maps the pixel locations to logical grid positions on the board.
