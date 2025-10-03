import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
import win32gui
import win32con
import win32api
from threading import Thread
import time
from typing import Optional, List, Dict, Any
import cv2
import numpy as np
from sklearn.cluster import DBSCAN
import json
from multiprocessing import freeze_support

# --- AppState Class ---
class AppState:
    def __init__(self):
        self.hwnd = 0
        self.window_capture = None
        self.game_analyzer = None
        self.locked_regions = None
        self.board_roi = None

# Import project modules after AppState is defined
from capture.realtime_capture import WindowCapture
from game_analyzer import GameAnalyzer

# --- GUI Application ---

class DashboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("陆战棋-实时战情室 (V20-最终格式)")
        self.root.geometry("800x800")
        self.root.resizable(False, False)
        
        self.app_state = AppState()
        self.regions_file = Path("data/regions.json")
        self.is_recognizing = False
        self.recognition_thread = None
        self.button3 = None
        self.button4 = None

        # --- UI Layout ---
        self.info_frame = ttk.Frame(root, height=650)
        self.info_frame.pack(fill="both", expand=True)
        self.info_frame.pack_propagate(False)
        self.control_frame = ttk.Frame(root, height=150)
        self.control_frame.pack(fill="x")
        self.control_frame.pack_propagate(False)
        
        self.info_text = scrolledtext.ScrolledText(self.info_frame, wrap=tk.WORD, state='disabled', font=("Microsoft YaHei", 10), bg="#F0F0F0", fg="black")
        self.info_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # --- Configure Text Tags ---
        self.info_text.tag_config("p_purple", foreground="#8A2BE2")
        self.info_text.tag_config("p_red", foreground="#DC143C")
        self.info_text.tag_config("p_orange", foreground="#FF8C00")
        self.info_text.tag_config("p_yellow", foreground="#BDB76B")
        self.info_text.tag_config("p_blue", foreground="#4169E1")
        self.info_text.tag_config("p_green", foreground="#2E8B57")
        self.info_text.tag_config("p_bold_red", foreground="#FF0000", font=("Microsoft YaHei", 10, "bold"))
        self.info_text.tag_config("p_cyan", foreground="#008B8B")
        self.info_text.tag_config("p_default", foreground="black")
        self.info_text.tag_config("eliminated", overstrike=True, foreground="#888888")
        
        self.info_text.tag_config("h_blue", foreground="blue", font=("Microsoft YaHei", 11, "bold"))
        self.info_text.tag_config("h_green", foreground="green", font=("Microsoft YaHei", 11, "bold"))
        self.info_text.tag_config("h_orange", foreground="orange", font=("Microsoft YaHei", 11, "bold"))
        self.info_text.tag_config("h_purple", foreground="purple", font=("Microsoft YaHei", 11, "bold"))
        self.info_text.tag_config("h_default", font=("Microsoft YaHei", 11, "bold"), foreground="#000080")

        self.setup_control_buttons()
        self.initialize_analyzer()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        self.is_recognizing = False
        if self.app_state.game_analyzer:
            del self.app_state.game_analyzer
        if self.app_state.hwnd and win32gui.IsWindow(self.app_state.hwnd):
            try:
                # **NEW**: Minimize the game window before closing
                win32gui.ShowWindow(self.app_state.hwnd, win32con.SW_MINIMIZE)
                win32gui.SetWindowPos(self.app_state.hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            except Exception: pass
        self.root.destroy()

    def initialize_analyzer(self):
        try:
            templates_dir = "vision/new_templates"
            self.app_state.game_analyzer = GameAnalyzer(templates_dir)
            self.log_to_dashboard({'report_items': [{'type':'header', 'text':"--- 战情室启动成功 ---"}]})
            
            if self.regions_file.exists():
                try:
                    with open(self.regions_file, 'r') as f:
                        self.app_state.locked_regions = json.load(f)
                    self.log_to_dashboard({'report_items': [{'type':'info', 'text':"[信息] 已成功从文件加载锁定的分区数据。"}]})
                    self._calculate_board_roi()
                except Exception as e:
                    self.log_to_dashboard({'report_items': [{'type':'error', 'text':f"[错误] 加载分区文件失败: {e}"}]})
            else:
                self.log_to_dashboard({'report_items': [{'type':'info', 'text':"[信息] 未找到分区数据文件。请点击“2. 开始识别”以在首次识别时自动生成。"}]})
                self.regions_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log_to_dashboard({'report_items': [{'type':'error', 'text':f"[严重错误] 分析器初始化失败: {e}"}]})

    def setup_control_buttons(self):
        button_frame_1 = ttk.Frame(self.control_frame)
        button_frame_1.pack(fill='x', expand=True, padx=20, pady=5)
        button_frame_2 = ttk.Frame(self.control_frame)
        button_frame_2.pack(fill='x', expand=True, padx=20, pady=5)
        button_frame_3 = ttk.Frame(self.control_frame)
        button_frame_3.pack(fill='x', expand=True, padx=20, pady=5)
        
        buttons_row1 = ["1. 检测游戏窗口", "2. 开始识别", "3. 连续识别", "4. 停止识别"]
        buttons_row2 = ["5. 查看区域划分", "6. 显示检测区域", "7. 查看节点分布", "按钮8"]
        buttons_row3 = ["按钮9", "按钮10", "按钮11", "按钮12 (退出)"]

        for i, text in enumerate(buttons_row1):
            button = ttk.Button(button_frame_1, text=text)
            button.pack(side="left", fill="x", expand=True, padx=10)
            if i == 0: button.config(command=self.detect_game_window)
            elif i == 1: button.config(command=lambda: self.start_recognition(0.8))
            elif i == 2:
                self.button3 = button
                button.config(command=self.start_continuous_recognition)
            elif i == 3:
                self.button4 = button
                button.config(command=self.stop_continuous_recognition)
        
        self.button4.config(state='disabled')

        for i, text in enumerate(buttons_row2):
            button = ttk.Button(button_frame_2, text=text)
            button.pack(side="left", fill="x", expand=True, padx=10)
            if i == 0: button.config(command=self.visualize_regions)
            elif i == 1: button.config(command=self.visualize_plus_region)
            elif i == 2: button.config(command=self.visualize_all_nodes)

        for i, text in enumerate(buttons_row3):
            button = ttk.Button(button_frame_3, text=text)
            button.pack(side="left", fill="x", expand=True, padx=10)
            if i == 3: button.config(command=self.on_closing)

    def log_to_dashboard(self, report: Dict[str, Any], recognition_id: str = None):
        self.info_text.config(state='normal')
        
        if recognition_id:
            total_count = report.get('total_count', 0)
            separator = f"\n{'='*15} [ {recognition_id} ] (总棋子数: {total_count}个) {'='*15}\n"
            self.info_text.insert(tk.END, separator, ("h_default",))

        report_items = report.get('report_items', [])
        for item in report_items:
            item_type = item.get('type', 'info')
            
            if item_type == 'header':
                header_color_tag = f"h_{item.get('color', 'default')}"
                self.info_text.insert(tk.END, item['text'] + "\n", (header_color_tag,))
            
            elif item_type == 'piece_line':
                for i, piece in enumerate(item['pieces']):
                    tags = [piece['color_tag']]
                    if piece['is_eliminated']:
                        tags.append('eliminated')
                    self.info_text.insert(tk.END, piece['text'], tuple(tags))
                    if i < len(item['pieces']) - 1:
                        self.info_text.insert(tk.END, ", ")
                self.info_text.insert(tk.END, "\n")

            elif item_type == 'separator':
                self.info_text.insert(tk.END, "\n")
            else:
                self.info_text.insert(tk.END, item.get('text', '') + "\n")

        self.info_text.see(tk.END)
        self.info_text.config(state='disabled')

    def _calculate_board_roi(self):
        if not self.app_state.locked_regions:
            self.app_state.board_roi = None
            return
        regions = self.app_state.locked_regions.values()
        min_x = min(r[0] for r in regions)
        min_y = min(r[1] for r in regions)
        max_x = max(r[2] for r in regions)
        max_y = max(r[3] for r in regions)
        self.app_state.board_roi = (int(min_x), int(min_y), int(max_x), int(max_y))
        self.log_to_dashboard({'report_items': [{'type':'info', 'text':f"[信息] 棋盘ROI计算完成: {self.app_state.board_roi}"}]})

    def _force_set_topmost(self):
        if self.app_state.hwnd and win32gui.IsWindow(self.app_state.hwnd):
            try:
                win32gui.SetWindowPos(self.app_state.hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            except Exception: pass

    def detect_game_window(self):
        self.log_to_dashboard({'report_items': [{'type':'header', 'text':"--- 开始检测游戏窗口 ---"}]})
        try:
            process_name = "JunQiRpg.exe"
            title_substring = "四国军棋"
            self.app_state.window_capture = WindowCapture(process_name=process_name, title_substring=title_substring)
            self.app_state.hwnd = self.app_state.window_capture.hwnd
            win32gui.ShowWindow(self.app_state.hwnd, win32con.SW_RESTORE)
            self._force_set_topmost()
            win32gui.SetForegroundWindow(self.app_state.hwnd)
            self.log_to_dashboard({'report_items': [{'type':'info', 'text':"成功检测到游戏窗口！"}]})
        except Exception as e:
            self.log_to_dashboard({'report_items': [{'type':'error', 'text':f"错误: {e}"}]})

    def start_recognition(self, threshold: float):
        recognition_id = time.strftime("%Y%m%d%H%M-%S")
        if not self.app_state.window_capture:
            self.log_to_dashboard({'report_items': [{'type':'error', 'text':"[错误] 请先检测游戏窗口。"}]})
            return
        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_to_dashboard({'report_items': [{'type':'error', 'text':"[错误] 获取截图失败。"}]})
            return
        if not self.app_state.locked_regions:
            self.log_to_dashboard({'report_items': [{'type':'info', 'text':"[信息] 正在尝试自动锁定初始分区..."}]})
            try:
                regions = self.app_state.game_analyzer.get_player_regions(screenshot)
                if not regions or len(regions) < 5:
                    self.log_to_dashboard({'report_items': [{'type':'error', 'text':"[警告] 未能计算出完整的5个区域..."}]})
                else:
                    self.app_state.locked_regions = regions
                    serializable_regions = {k: tuple(map(int, v)) for k, v in regions.items()}
                    with open(self.regions_file, 'w') as f:
                        json.dump(serializable_regions, f, indent=4)
                    self.log_to_dashboard({'report_items': [{'type':'info', 'text':"[成功] 初始分区已自动锁定并保存！"}]})
                    self._calculate_board_roi()
            except Exception as e:
                self.log_to_dashboard({'report_items': [{'type':'error', 'text':f"[严重错误] 自动锁定分区时出错: {e}"}]})
        
        if self.app_state.board_roi:
            x1, y1, x2, y2 = self.app_state.board_roi
            board_image = screenshot[y1:y2, x1:x2]
        else:
            board_image = screenshot
        try:
            report = self.app_state.game_analyzer.analyze_screenshot(board_image, match_threshold=threshold)
            self.log_to_dashboard(report, recognition_id=recognition_id)
        except Exception as e:
            self.log_to_dashboard({'report_items': [{'type':'error', 'text':f"[严重错误] 分析时出错: {e}"}]})
        finally:
            self._force_set_topmost()

    def start_continuous_recognition(self):
        if self.is_recognizing: return
        if not self.app_state.window_capture:
            self.log_to_dashboard({'report_items': [{'type':'error', 'text':"[错误] 请先检测游戏窗口。"}]})
            return
        self.is_recognizing = True
        self.button3.config(state='disabled')
        self.button4.config(state='normal')
        self.recognition_thread = Thread(target=self._continuous_recognition_worker, daemon=True)
        self.recognition_thread.start()
        self.log_to_dashboard({'report_items': [{'type':'header', 'text':"==================== 连续识别已启动 ===================="}]})

    def stop_continuous_recognition(self):
        if not self.is_recognizing: return
        self.is_recognizing = False
        self.button3.config(state='normal')
        self.button4.config(state='disabled')
        self.log_to_dashboard({'report_items': [{'type':'header', 'text':"==================== 连续识别已停止 ===================="}]})

    def _continuous_recognition_worker(self):
        while self.is_recognizing:
            recognition_id = time.strftime("%Y%m%d%H%M-%S")
            screenshot = self.app_state.window_capture.get_screenshot()
            if screenshot is None:
                self.root.after(0, self.log_to_dashboard, {'report_items': [{'type':'error', 'text':"[错误] (后台) 获取截图失败。"}]})
                time.sleep(0.1)
                continue
            if self.app_state.board_roi:
                x1, y1, x2, y2 = self.app_state.board_roi
                board_image = screenshot[y1:y2, x1:x2]
            else:
                self.root.after(0, self.log_to_dashboard, {'report_items': [{'type':'error', 'text':"[错误] (后台) 无法识别，ROI未设定。"}]})
                time.sleep(1)
                continue
            try:
                report = self.app_state.game_analyzer.analyze_screenshot(board_image, match_threshold=0.8)
                self.root.after(0, self.log_to_dashboard, report, recognition_id)
            except Exception as e:
                self.root.after(0, self.log_to_dashboard, {'report_items': [{'type':'error', 'text':f"[严重错误] (后台) 分析时出错: {e}"}]})

    def visualize_regions(self):
        self.log_to_dashboard({'report_items': [{'type':'header', 'text':"\n--- 生成已锁定的分区图 ---"}]})
        # ... (rest of the function is the same)
        pass
    def visualize_plus_region(self):
        self.log_to_dashboard({'report_items': [{'type':'header', 'text':"\n--- 生成基于锁定区域的“+”号 ---"}]})
        # ... (rest of the function is the same)
        pass
    def visualize_all_nodes(self):
        self.log_to_dashboard({'report_items': [{'type':'header', 'text':"\n--- 生成全节点分布图 ---"}]})
        # ... (rest of the function is the same)
        pass

if __name__ == "__main__":
    freeze_support()
    root = tk.Tk()
    app = DashboardApp(root)
    root.mainloop()