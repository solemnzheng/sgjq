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

# --- AppState Class ---
class AppState:
    def __init__(self):
        self.hwnd = 0
        self.window_capture = None
        self.game_analyzer = None
        self.locked_regions = None

# Import project modules after AppState is defined
from capture.realtime_capture import WindowCapture
from game_analyzer import GameAnalyzer

# --- GUI Application ---

class DashboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("陆战棋-实时战情室 (V18-UI微调)")
        self.root.geometry("800x800")
        self.root.resizable(False, False)
        
        self.app_state = AppState()
        self.regions_file = Path("data/regions.json")
        self.is_recognizing = False
        self.recognition_thread = None
        self.button3 = None
        self.button4 = None

        # --- UI Layout ---
        # **FIXED**: Adjust frame heights for better layout
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
        if self.app_state.hwnd and win32gui.IsWindow(self.app_state.hwnd):
            try:
                win32gui.SetWindowPos(self.app_state.hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            except Exception: pass
        self.root.destroy()

    def initialize_analyzer(self):
        try:
            templates_dir = "vision/new_templates"
            self.app_state.game_analyzer = GameAnalyzer(templates_dir)
            self.log_to_dashboard([{'type':'header', 'text':"--- 战情室启动成功 ---"}])
            
            if self.regions_file.exists():
                try:
                    with open(self.regions_file, 'r') as f:
                        self.app_state.locked_regions = json.load(f)
                    self.log_to_dashboard([{'type':'info', 'text':"[信息] 已成功从文件加载锁定的分区数据。"}])
                except Exception as e:
                    self.log_to_dashboard([{'type':'error', 'text':f"[错误] 加载分区文件失败: {e}"}])
            else:
                self.log_to_dashboard([{'type':'info', 'text':"[信息] 未找到分区数据文件。请点击“2. 开始识别”以在首次识别时自动生成。"}])
                self.regions_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log_to_dashboard([{'type':'error', 'text':f"[严重错误] 分析器初始化失败: {e}"}])

    def setup_control_buttons(self):
        # **FIXED**: Reduce vertical padding for a more compact layout
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

    def log_to_dashboard(self, report_data: List[Dict[str, Any]], recognition_id: str = None):
        self.info_text.config(state='normal')
        
        if recognition_id:
            separator = f"\n{'='*20} [ {recognition_id} ] {'='*20}\n"
            self.info_text.insert(tk.END, separator, ("h_default",))

        for item in report_data:
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

    def _force_set_topmost(self):
        if self.app_state.hwnd and win32gui.IsWindow(self.app_state.hwnd):
            try:
                win32gui.SetWindowPos(self.app_state.hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            except Exception: pass

    def detect_game_window(self):
        self.log_to_dashboard([{'type':'header', 'text':"--- 开始检测游戏窗口 ---"}])
        try:
            process_name = "JunQiRpg.exe"
            title_substring = "四国军棋"
            self.app_state.window_capture = WindowCapture(process_name=process_name, title_substring=title_substring)
            self.app_state.hwnd = self.app_state.window_capture.hwnd
            win32gui.ShowWindow(self.app_state.hwnd, win32con.SW_RESTORE)
            self._force_set_topmost()
            win32gui.SetForegroundWindow(self.app_state.hwnd)
            self.log_to_dashboard([{'type':'info', 'text':"成功检测到游戏窗口！"}])
        except Exception as e:
            self.log_to_dashboard([{'type':'error', 'text':f"错误: {e}"}])

    def start_recognition(self, threshold: float):
        # **FIXED**: Adjust timestamp format
        recognition_id = time.strftime("%Y%m%d%H%M-%S")
        
        if not self.app_state.window_capture:
            self.log_to_dashboard([{'type':'error', 'text':"[错误] 请先检测游戏窗口。"}])
            return
            
        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_to_dashboard([{'type':'error', 'text':"[错误] 获取截图失败。"}])
            return

        if not self.app_state.locked_regions:
            self.log_to_dashboard([{'type':'info', 'text':"[信息] 正在尝试自动锁定初始分区..."}])
            try:
                regions = self.app_state.game_analyzer.get_player_regions(screenshot)
                if not regions or len(regions) < 5:
                    self.log_to_dashboard([{'type':'error', 'text':"[警告] 未能计算出完整的5个区域，将在下次识别时重试。"}])
                else:
                    self.app_state.locked_regions = regions
                    serializable_regions = {k: tuple(map(int, v)) for k, v in regions.items()}
                    with open(self.regions_file, 'w') as f:
                        json.dump(serializable_regions, f, indent=4)
                    self.log_to_dashboard([{'type':'info', 'text':"[成功] 初始分区已自动锁定并保存！"}])
            except Exception as e:
                self.log_to_dashboard([{'type':'error', 'text':f"[严重错误] 自动锁定分区时出错: {e}"}])

        try:
            report = self.app_state.game_analyzer.analyze_screenshot(screenshot, match_threshold=threshold)
            self.log_to_dashboard(report, recognition_id=recognition_id)
        except Exception as e:
            self.log_to_dashboard([{'type':'error', 'text':f"[严重错误] 分析时出错: {e}"}])
        finally:
            self._force_set_topmost()

    def start_continuous_recognition(self):
        if self.is_recognizing:
            self.log_to_dashboard([{'type':'error', 'text':"[警告] 连续识别已在运行中。"}])
            return
        if not self.app_state.window_capture:
            self.log_to_dashboard([{'type':'error', 'text':"[错误] 请先检测游戏窗口。"}])
            return
        
        self.is_recognizing = True
        self.button3.config(state='disabled')
        self.button4.config(state='normal')

        self.recognition_thread = Thread(target=self._continuous_recognition_worker, daemon=True)
        self.recognition_thread.start()
        self.log_to_dashboard([{'type':'header', 'text':"==================== 连续识别已启动 ===================="}])

    def stop_continuous_recognition(self):
        if not self.is_recognizing:
            self.log_to_dashboard([{'type':'info', 'text':"[信息] 连续识别尚未启动。"}])
            return
            
        self.is_recognizing = False
        self.button3.config(state='normal')
        self.button4.config(state='disabled')
        self.log_to_dashboard([{'type':'header', 'text':"==================== 连续识别已停止 ===================="}])

    def _continuous_recognition_worker(self):
        while self.is_recognizing:
            # **FIXED**: Adjust timestamp format
            recognition_id = time.strftime("%Y%m%d%H%M-%S")
            screenshot = self.app_state.window_capture.get_screenshot()
            if screenshot is None:
                self.root.after(0, self.log_to_dashboard, [{'type':'error', 'text':"[错误] (后台) 获取截图失败。"}])
                time.sleep(0.1)
                continue
            try:
                report = self.app_state.game_analyzer.analyze_screenshot(screenshot, match_threshold=0.8)
                self.root.after(0, self.log_to_dashboard, report, recognition_id)
            except Exception as e:
                self.root.after(0, self.log_to_dashboard, [{'type':'error', 'text':f"[严重错误] (后台) 分析时出错: {e}"}])
    
    def visualize_regions(self):
        self.log_to_dashboard([{'type':'header', 'text':"\n--- 生成已锁定的分区图 ---"}])
        if not self.app_state.locked_regions:
            self.log_to_dashboard([{'type':'error', 'text':"[错误] 未找到分区数据。请先点击“2. 开始识别”来自动生成。"}])
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
            self.log_to_dashboard([{'type':'error', 'text':f"[严重错误] 可视化时出错: {e}"}])
        finally:
            self._force_set_topmost()

    def visualize_plus_region(self):
        self.log_to_dashboard([{'type':'header', 'text':"\n--- 生成基于锁定区域的“+”号 ---"}])
        if not self.app_state.locked_regions:
            self.log_to_dashboard([{'type':'error', 'text':"[错误] 未找到分区数据。请先点击“2. 开始识别”来自动生成。"}])
            return
        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None: return
        try:
            regions = self.app_state.locked_regions
            if not all(k in regions for k in ["上方", "下方", "左侧", "右侧"]):
                self.log_to_dashboard([{'type':'error', 'text':"[错误] 锁定的区域信息不完整。"}])
                return
            overlay = screenshot.copy()
            color = (0, 255, 0)
            h_x1, h_y1, _, h_y2 = map(int, regions["左侧"])
            _, _, h_x2, _ = map(int, regions["右侧"])
            cv2.rectangle(overlay, (h_x1, h_y1), (h_x2, h_y2), color, 2)
            v_x1, v_y1, v_x2, _ = map(int, regions["上方"])
            _, _, _, v_y2 = map(int, regions["下方"])
            cv2.rectangle(overlay, (v_x1, v_y1), (v_x2, v_y2), color, 2)
            cv2.imshow("Locked Plus Shape Region", overlay)
        except Exception as e:
            self.log_to_dashboard([{'type':'error', 'text':f"[严重错误] 可视化“+”号时出错: {e}"}])
        finally:
            self._force_set_topmost()

    def visualize_all_nodes(self):
        self.log_to_dashboard([{'type':'header', 'text':"\n--- 生成全节点分布图 ---"}])
        if not self.app_state.locked_regions:
            self.log_to_dashboard([{'type':'error', 'text':"[错误] 未找到分区数据。请先点击“2. 开始识别”来自动生成。"}])
            return
        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None: return
        try:
            regions = self.app_state.locked_regions
            all_nodes = []
            player_region_specs = {"上方": (6, 5), "下方": (6, 5), "左侧": (6, 5), "右侧": (6, 5)}
            for key, (rows, cols) in player_region_specs.items():
                if key in regions:
                    x1, y1, x2, y2 = map(int, regions[key])
                    cell_w = (x2 - x1) / cols; cell_h = (y2 - y1) / rows
                    for row in range(rows):
                        for col in range(cols):
                            all_nodes.append((int(x1 + (col + 0.5) * cell_w), int(y1 + (row + 0.5) * cell_h)))
            if "中央" in regions:
                x1, y1, x2, y2 = map(int, regions["中央"])
                cell_w = (x2 - x1) / 3; cell_h = (y2 - y1) / 3
                for row in range(3):
                    for col in range(cols):
                        all_nodes.append((int(x1 + (col + 0.5) * cell_w), int(y1 + (row + 0.5) * cell_h)))
            self.log_to_dashboard([{'type':'info', 'text':f"成功生成了 {len(all_nodes)} 个棋盘节点。"}])
            overlay = screenshot.copy()
            for (cx, cy) in all_nodes:
                cv2.circle(overlay, (cx, cy), 5, (0, 255, 0), -1)
                cv2.circle(overlay, (cx, cy), 6, (0, 0, 0), 1)
            cv2.imshow("All Nodes Distribution", overlay)
        except Exception as e:
            self.log_to_dashboard([{'type':'error', 'text':f"[严重错误] 可视化节点时出错: {e}"}])
        finally:
            self._force_set_topmost()

if __name__ == "__main__":
    root = tk.Tk()
    app = DashboardApp(root)
    root.mainloop()
