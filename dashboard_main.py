
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
import win32gui
import win32con
import win32api
from threading import Thread
import time
from typing import Optional
import cv2
import numpy as np
from sklearn.cluster import DBSCAN

# --- AppState Class ---
class AppState:
    def __init__(self):
        self.hwnd = 0
        self.window_capture = None
        self.game_analyzer = None
        self.locked_regions = None # To store the initial, perfect regions

# Import project modules after AppState is defined
from capture.realtime_capture import WindowCapture
from game_analyzer import GameAnalyzer, DetectionResult, find_all_matches_with_color_mask, standard_non_max_suppression

# --- GUI Application ---

class DashboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("陆战棋-实时战情室 (固化分区版)")
        self.root.geometry("800x800")
        self.root.resizable(False, False)
        
        self.app_state = AppState()

        # --- UI Layout ---
        self.info_frame = ttk.Frame(root, height=600)
        self.info_frame.pack(fill="both", expand=True)
        self.info_frame.pack_propagate(False)
        self.control_frame = ttk.Frame(root, height=200)
        self.control_frame.pack(fill="x")
        self.control_frame.pack_propagate(False)
        self.info_text = scrolledtext.ScrolledText(self.info_frame, wrap=tk.WORD, state='disabled', font=("Microsoft YaHei", 10), bg="white", fg="black")
        self.info_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.info_text.tag_config("red", foreground="red")
        self.info_text.tag_config("green", foreground="green")
        self.info_text.tag_config("blue", foreground="blue")

        self.setup_control_buttons()
        self.initialize_analyzer()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        if self.app_state.hwnd and win32gui.IsWindow(self.app_state.hwnd):
            try:
                win32gui.SetWindowPos(self.app_state.hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            except Exception: pass
        self.root.destroy()

    def initialize_analyzer(self):
        try:
            templates_dir = "vision/new_templates"
            self.app_state.game_analyzer = GameAnalyzer(templates_dir)
            self.log_to_dashboard("--- 战情室启动成功 ---")
            self.log_to_dashboard(f"已成功加载 {len(self.app_state.game_analyzer.templates_manager.get_all_templates())} 个棋子模板。")
            self.log_to_dashboard("请先点击“1. 检测游戏窗口”。")
        except Exception as e:
            self.log_to_dashboard(f"[严重错误] 分析器初始化失败: {e}", "red")

    def setup_control_buttons(self):
        button_frame_1 = ttk.Frame(self.control_frame)
        button_frame_1.pack(fill='x', expand=True, padx=20, pady=15)
        button_frame_2 = ttk.Frame(self.control_frame)
        button_frame_2.pack(fill='x', expand=True, padx=20, pady=15)
        
        buttons_row1 = ["1. 检测游戏窗口", "2. 开始识别", "3. 锁定初始分区", "按钮4"]
        buttons_row2 = ["5. 查看区域划分", "6. 显示检测区域", "7. 查看节点分布", "退出"]

        for i, text in enumerate(buttons_row1):
            button = ttk.Button(button_frame_1, text=text)
            button.pack(side="left", fill="x", expand=True, padx=10)
            if i == 0: button.config(command=self.detect_game_window)
            elif i == 1: button.config(command=lambda: self.start_recognition(0.7))
            elif i == 2: button.config(command=self.lock_initial_regions)
            
        for i, text in enumerate(buttons_row2):
            button = ttk.Button(button_frame_2, text=text)
            button.pack(side="left", fill="x", expand=True, padx=10)
            if i == 0: button.config(command=self.visualize_regions)
            elif i == 1: button.config(command=self.visualize_plus_region)
            elif i == 2: button.config(command=self.visualize_all_nodes)
            elif i == 3: button.config(command=self.on_closing)

    def log_to_dashboard(self, message: str, tag: str = None):
        self.info_text.config(state='normal')
        self.info_text.insert(tk.END, message + "\n", tag)
        self.info_text.see(tk.END)
        self.info_text.config(state='disabled')

    def _force_set_topmost(self):
        if self.app_state.hwnd and win32gui.IsWindow(self.app_state.hwnd):
            try:
                win32gui.SetWindowPos(self.app_state.hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            except Exception: pass

    def detect_game_window(self):
        self.log_to_dashboard("--- 开始检测游戏窗口 ---")
        try:
            # Correctly pass the required arguments
            process_name = "JunQiRpg.exe"
            title_substring = "四国军棋"
            self.app_state.window_capture = WindowCapture(process_name=process_name, title_substring=title_substring)
            self.app_state.hwnd = self.app_state.window_capture.hwnd
            win32gui.ShowWindow(self.app_state.hwnd, win32con.SW_RESTORE)
            self._force_set_topmost()
            win32gui.SetForegroundWindow(self.app_state.hwnd)
            self.log_to_dashboard("成功检测到游戏窗口！", "green")
        except Exception as e:
            self.log_to_dashboard(f"错误: {e}", "red")

    def start_recognition(self, threshold: float):
        recognition_id = time.strftime("%Y%m%d%H%M%S")
        self.log_to_dashboard(f"\n--- 开始新一轮识别 [ID: {recognition_id}] ---")
        
        if not self.app_state.window_capture:
            self.log_to_dashboard("[错误] 请先检测游戏窗口。", "red")
            return
            
        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_to_dashboard("[错误] 获取截图失败。", "red")
            return

        # Create the directory if it doesn't exist
        save_dir = Path("pictures/temp")
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"screenshot_{recognition_id}.png"
        
        cv2.imwrite(str(save_path), screenshot)
        self.log_to_dashboard(f"截图成功，已保存至 {save_path}")
            
        try:
            report = self.app_state.game_analyzer.analyze_screenshot(screenshot, match_threshold=threshold)
            self.log_to_dashboard("分析完成！")
            self.log_to_dashboard(report)
        except Exception as e:
            self.log_to_dashboard(f"[严重错误] 分析时出错: {e}", "red")
        finally:
            self._force_set_topmost()

    def lock_initial_regions(self):
        self.log_to_dashboard("\n--- 开始锁定初始分区 ---")
        if not self.app_state.window_capture:
            self.log_to_dashboard("[错误] 请先检测窗口。", "red")
            return
        
        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_to_dashboard("[错误] 获取截图失败。", "red")
            return

        try:
            regions = self.app_state.game_analyzer.get_player_regions(screenshot)
            if not regions or len(regions) < 5:
                self.log_to_dashboard("[错误] 未能计算出完整的5个区域，请确保棋盘布局完整。", "red")
                self.app_state.locked_regions = None
                return
            
            self.app_state.locked_regions = regions
            self.log_to_dashboard("[成功] 初始分区已成功锁定！", "green")
        except Exception as e:
            self.log_to_dashboard(f"[严重错误] 锁定分区时出错: {e}", "red")
        finally:
            self._force_set_topmost()

    def visualize_regions(self):
        self.log_to_dashboard("\n--- 生成已锁定的分区图 ---")
        if not self.app_state.locked_regions:
            self.log_to_dashboard("[错误] 请先点击“3. 锁定初始分区”！", "red")
            return
        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None: return

        try:
            overlay = screenshot.copy()
            colors = {"上方": (255, 0, 0), "下方": (0, 255, 0), "左侧": (0, 0, 255), "右侧": (255, 255, 0), "中央": (255, 0, 255)}
            for name, bounds in self.app_state.locked_regions.items():
                x1, y1, x2, y2 = map(int, bounds)
                cv2.rectangle(overlay, (x1, y1), (x2, y2), colors.get(name, (255,255,255)), 2)
                cv2.putText(overlay, name, (x1 + 5, y1 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, colors.get(name, (255,255,255)), 2)
            cv2.imshow("Locked Region Visualization", overlay)
        except Exception as e:
            self.log_to_dashboard(f"[严重错误] 可视化时出错: {e}", "red")
        finally:
            self._force_set_topmost()

    def visualize_plus_region(self):
        self.log_to_dashboard("\n--- 生成基于锁定区域的“+”号 ---")
        if not self.app_state.locked_regions:
            self.log_to_dashboard("[错误] 请先点击“3. 锁定初始分区”！", "red")
            return
        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None: return

        try:
            regions = self.app_state.locked_regions
            if not all(k in regions for k in ["上方", "下方", "左侧", "右侧"]):
                self.log_to_dashboard("[错误] 锁定的区域信息不完整。", "red")
                return
            overlay = screenshot.copy()
            color = (0, 255, 0) # Green color for the rectangles

            # Define and draw the horizontal rectangle
            h_x1, h_y1, _, h_y2 = map(int, regions["左侧"])
            _, _, h_x2, _ = map(int, regions["右侧"])
            cv2.rectangle(overlay, (h_x1, h_y1), (h_x2, h_y2), color, 2)

            # Define and draw the vertical rectangle
            v_x1, v_y1, v_x2, _ = map(int, regions["上方"])
            _, _, _, v_y2 = map(int, regions["下方"])
            cv2.rectangle(overlay, (v_x1, v_y1), (v_x2, v_y2), color, 2)
            cv2.imshow("Locked Plus Shape Region", overlay)
        except Exception as e:
            self.log_to_dashboard(f"[严重错误] 可视化“+”号时出错: {e}", "red")
        finally:
            self._force_set_topmost()

    def visualize_all_nodes(self):
        self.log_to_dashboard("\n--- 生成全节点分布图 ---")
        if not self.app_state.locked_regions:
            self.log_to_dashboard("[错误] 请先点击“3. 锁定初始分区”！", "red")
            return
        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None: return

        try:
            regions = self.app_state.locked_regions
            all_nodes = []

            # Define player regions and their grid dimensions (rows, cols)
            # Each player area has 30 positions (6 rows, 5 columns)
            player_region_specs = {
                "上方": (6, 5), "下方": (6, 5),
                "左侧": (6, 5), "右侧": (6, 5)
            }

            for key, (rows, cols) in player_region_specs.items():
                if key in regions:
                    x1, y1, x2, y2 = map(int, regions[key])
                    region_w = x2 - x1
                    region_h = y2 - y1
                    
                    cell_w = region_w / cols
                    cell_h = region_h / rows

                    for row in range(rows):
                        for col in range(cols):
                            cx = int(x1 + (col + 0.5) * cell_w)
                            cy = int(y1 + (row + 0.5) * cell_h)
                            all_nodes.append((cx, cy))

            # Central region (9 nodes, interpreted as a 3x3 grid)
            if "中央" in regions:
                x1, y1, x2, y2 = map(int, regions["中央"])
                region_w = x2 - x1
                region_h = y2 - y1
                
                rows, cols = 3, 3
                cell_w = region_w / cols
                cell_h = region_h / rows
                
                for row in range(rows):
                    for col in range(cols):
                        cx = int(x1 + (col + 0.5) * cell_w)
                        cy = int(y1 + (row + 0.5) * cell_h)
                        all_nodes.append((cx, cy))

            self.log_to_dashboard(f"成功生成了 {len(all_nodes)} 个棋盘节点。")
            overlay = screenshot.copy()
            for (cx, cy) in all_nodes:
                cv2.circle(overlay, (cx, cy), 5, (0, 255, 0), -1)
                cv2.circle(overlay, (cx, cy), 6, (0, 0, 0), 1)
            cv2.imshow("All Nodes Distribution", overlay)
        except Exception as e:
            self.log_to_dashboard(f"[严重错误] 可视化节点时出错: {e}", "red")
        finally:
            self._force_set_topmost()

if __name__ == "__main__":
    root = tk.Tk()
    app = DashboardApp(root)
    root.mainloop()
