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
import json
from multiprocessing import freeze_support

# --- 导入核心模块 ---
from capture.realtime_capture import WindowCapture
from game_analyzer import GameAnalyzer
from game_model import BoardState, PieceTracker, GameLogicEngine, GameEvent

# --- AppState Class ---
class AppState:
    def __init__(self):
        self.hwnd = 0
        self.window_capture = None
        self.game_analyzer = None
        self.locked_regions = None
        self.board_roi = None

# --- GUI Application ---

class DashboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("陆战棋-智能战情室 (V23-功能对齐)")
        self.root.geometry("800x800")
        self.root.resizable(False, False)
        
        self.app_state = AppState()
        self.regions_file = Path("data/regions.json")
        self.is_recognizing = False
        self.recognition_thread = None
        self.button3 = None
        self.button4 = None

        self.piece_tracker = PieceTracker()
        self.logic_engine = GameLogicEngine()
        self.prev_state: Optional[BoardState] = None
        self.curr_state: Optional[BoardState] = None

        # ... (UI Layout and Tag Config remains the same)
        self.info_frame = ttk.Frame(root, height=650)
        self.info_frame.pack(fill="both", expand=True)
        self.info_frame.pack_propagate(False)
        self.control_frame = ttk.Frame(root, height=150)
        self.control_frame.pack(fill="x")
        self.control_frame.pack_propagate(False)
        self.info_text = scrolledtext.ScrolledText(self.info_frame, wrap=tk.WORD, state='disabled', font=("Microsoft YaHei", 10), bg="#F0F0F0", fg="black")
        self.info_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.info_text.tag_config("p_purple", foreground="#8A2BE2")
        self.info_text.tag_config("p_red", foreground="#DC143C")
        self.info_text.tag_config("p_orange", foreground="#FF8C00")
        self.info_text.tag_config("p_yellow", foreground="#BDB76B")
        self.info_text.tag_config("p_blue", foreground="#4169E1")
        self.info_text.tag_config("p_green", foreground="#2E8B57")
        self.info_text.tag_config("p_bold_red", foreground="#FF0000", font=("Microsoft YaHei", 10, "bold"))
        self.info_text.tag_config("p_cyan", foreground="#008B8B")
        self.info_text.tag_config("h_default", font=("Microsoft YaHei", 11, "bold"), foreground="#000080")
        self.info_text.tag_config("eliminated", overstrike=True, foreground="#888888")
        self.info_text.tag_config("h_blue", foreground="blue", font=("Microsoft YaHei", 11, "bold"))
        self.info_text.tag_config("h_green", foreground="green", font=("Microsoft YaHei", 11, "bold"))
        self.info_text.tag_config("h_orange", foreground="orange", font=("Microsoft YaHei", 11, "bold"))
        self.info_text.tag_config("h_purple", foreground="purple", font=("Microsoft YaHei", 11, "bold"))

        self.setup_control_buttons()
        self.initialize_analyzer()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        self.is_recognizing = False
        if self.app_state.game_analyzer:
            del self.app_state.game_analyzer
        if self.app_state.hwnd and win32gui.IsWindow(self.app_state.hwnd):
            try:
                win32gui.ShowWindow(self.app_state.hwnd, win32con.SW_MINIMIZE)
                win32gui.SetWindowPos(self.app_state.hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            except Exception: pass
        self.root.destroy()

    def initialize_analyzer(self):
        try:
            templates_dir = "vision/new_templates"
            self.app_state.game_analyzer = GameAnalyzer(templates_dir)
            self.log_message("--- 战情室启动成功 ---")
            if self.regions_file.exists():
                try:
                    with open(self.regions_file, 'r') as f:
                        self.app_state.locked_regions = json.load(f)
                    self.log_message("[信息] 已成功从文件加载锁定的分区数据。")
                    self._calculate_board_roi()
                except Exception as e:
                    self.log_message(f"[错误] 加载分区文件失败: {e}", "p_red")
            else:
                self.log_message("[信息] 未找到分区数据文件。请点击“2. 开始识别”以在首次识别时自动生成。")
                self.regions_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log_message(f"[严重错误] 分析器初始化失败: {e}", "p_red")

    def setup_control_buttons(self):
        # ... (This function is now complete and correct)
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

    def log_message(self, message: str, tag: str = None):
        self.info_text.config(state='normal')
        self.info_text.insert(tk.END, message + "\n", tag)
        self.info_text.see(tk.END)
        self.info_text.config(state='disabled')

    def log_game_events(self, events: List[GameEvent]):
        self.info_text.config(state='normal')
        timestamp_str = time.strftime("%H:%M:%S")
        separator = f"\n{'='*15} [ {timestamp_str} ] {'='*15}\n"
        self.info_text.insert(tk.END, separator, "h_default")
        if not events:
            self.info_text.insert(tk.END, "棋盘无变化。\n")
        else:
            for event in events:
                if event.event_type == "move":
                    msg = f"移动: {event.piece.player_pos} {event.piece.name} 从 {event.from_coords} -> {event.to_coords}。"
                    self.info_text.insert(tk.END, msg + "\n")
                elif event.event_type == "capture":
                    msg = f"交战: {event.attacker.player_pos} {event.attacker.name} 在 {event.coords} 吃掉 {event.defender.player_pos} {event.defender.name}！"
                    self.info_text.insert(tk.END, msg + "\n", "p_bold_red")
                elif event.event_type == "trade":
                    msg = f"互换: {event.piece1.player_pos} {event.piece1.name} 与 {event.piece2.player_pos} {event.piece2.name} 在 {event.coords} 同归于尽！"
                    self.info_text.insert(tk.END, msg + "\n", "p_orange")
                elif event.event_type == "bomb":
                    msg = f"爆炸: {event.bomb.player_pos} 炸弹 💥 在 {event.coords} 炸掉 {event.target.player_pos} {event.target.name}！"
                    self.info_text.insert(tk.END, msg + "\n", "p_bold_red")
                elif event.event_type == "landmine":
                    msg = f"阵亡: {event.victim.player_pos} {event.victim.name} 在 {event.coords} 撞上地雷！"
                    self.info_text.insert(tk.END, msg + "\n", "p_yellow")
        self.info_text.see(tk.END)
        self.info_text.config(state='disabled')

    def _calculate_board_roi(self):
        # ... (This function is correct)
        if not self.app_state.locked_regions:
            self.app_state.board_roi = None
            return
        regions = self.app_state.locked_regions.values()
        min_x = min(r[0] for r in regions)
        min_y = min(r[1] for r in regions)
        max_x = max(r[2] for r in regions)
        max_y = max(r[3] for r in regions)
        self.app_state.board_roi = (int(min_x), int(min_y), int(max_x), int(max_y))
        self.log_message(f"[信息] 棋盘ROI计算完成: {self.app_state.board_roi}")

    def _force_set_topmost(self):
        # ... (This function is correct)
        if self.app_state.hwnd and win32gui.IsWindow(self.app_state.hwnd):
            try:
                win32gui.SetWindowPos(self.app_state.hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            except Exception: pass

    def detect_game_window(self):
        self.log_message("--- 开始检测游戏窗口 ---", "h_default")
        try:
            process_name = "JunQiRpg.exe"
            title_substring = "四国军棋"
            
            self.app_state.window_capture = WindowCapture(process_name=process_name, title_substring=title_substring)
            self.app_state.hwnd = self.app_state.window_capture.hwnd
            
            # --- 恢复详细信息显示 ---
            if self.app_state.hwnd:
                win32gui.ShowWindow(self.app_state.hwnd, win32con.SW_RESTORE)
                self._force_set_topmost()
                win32gui.SetForegroundWindow(self.app_state.hwnd)
                
                title = win32gui.GetWindowText(self.app_state.hwnd)
                class_name = win32gui.GetClassName(self.app_state.hwnd)
                rect = win32gui.GetWindowRect(self.app_state.hwnd)
                
                self.log_message("成功检测到游戏窗口！")
                self.log_message(f"  - 句柄 (HWND): {self.app_state.hwnd}", "p_cyan")
                self.log_message(f"  - 标题: {title}", "p_cyan")
                self.log_message(f"  - 类名: {class_name}", "p_cyan")
                self.log_message(f"  - 尺寸: {rect[2]-rect[0]}x{rect[3]-rect[1]} @ ({rect[0]},{rect[1]})", "p_cyan")
            else:
                self.log_message("错误: 未找到匹配的游戏窗口。", "p_red")

        except Exception as e:
            self.log_message(f"检测窗口时发生未知错误: {e}", "p_red")

    def start_recognition(self, threshold: float):
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return
        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_message("[错误] 获取截图失败。", "p_red")
            return
        
        # --- Region Locking Logic ---
        if not self.app_state.locked_regions:
            self.log_message("[信息] 正在尝试自动锁定初始分区...")
            try:
                regions = self.app_state.game_analyzer.get_player_regions(screenshot)
                if not regions or len(regions) < 5:
                    self.log_message("[错误] 未能计算出完整的5个区域。", "p_red")
                    return
                else:
                    self.app_state.locked_regions = regions
                    serializable_regions = {k: tuple(map(int, v)) for k, v in regions.items()}
                    with open(self.regions_file, 'w') as f:
                        json.dump(serializable_regions, f, indent=4)
                    self.log_message("[成功] 初始分区已自动锁定并保存！")
                    self._calculate_board_roi()
            except Exception as e:
                self.log_message(f"[严重错误] 自动锁定分区时出错: {e}", "p_red")
                return

        # --- Analysis and Detailed Logging ---
        if self.app_state.board_roi:
            x1, y1, x2, y2 = self.app_state.board_roi
            board_image = screenshot[y1:y2, x1:x2]
            
            # Get raw detections for logging
            all_detections = self.app_state.game_analyzer.get_all_detections(board_image, threshold)
            
            # --- DETAILED LOGGING RESTORED ---
            self.log_message(f"--- 单次识别报告 (阈值: {threshold}) ---", "h_default")
            if not all_detections:
                self.log_message("在ROI内未检测到任何棋子。")
                return

            pieces_by_region = {name: [] for name in self.app_state.locked_regions.keys()}
            
            # Adjust regions to be relative to the board_image ROI
            roi_x_offset, roi_y_offset = x1, y1
            relative_regions = {
                name: (r[0] - roi_x_offset, r[1] - roi_y_offset, r[2] - roi_x_offset, r[3] - roi_y_offset)
                for name, r in self.app_state.locked_regions.items()
            }

            for det in all_detections:
                center_x = det.bbox[0] + (det.bbox[2] - det.bbox[0]) / 2
                center_y = det.bbox[1] + (det.bbox[3] - det.bbox[1]) / 2
                
                for name, (rx1, ry1, rx2, ry2) in relative_regions.items():
                    if rx1 <= center_x <= rx2 and ry1 <= center_y <= ry2:
                        pieces_by_region[name].append(det)
                        break
            
            color_map = {"blue": "h_blue", "green": "h_green", "orange": "h_orange", "purple": "h_purple"}
            
            for region_name, pieces in pieces_by_region.items():
                counts = Counter(p.template.color for p in pieces)
                self.log_message(f"\n[{region_name}] - 检测到 {len(pieces)} 枚棋子", "h_default")
                if counts:
                    count_str = ", ".join([f"{color}: {num}" for color, num in counts.items()])
                    self.log_message(f"  颜色统计: {count_str}")
                for p in pieces:
                    tag = color_map.get(p.color, "p_cyan")
                    self.log_message(f"  - {p.piece_name} ({p.color}) @ ({p.location[0]}, {p.location[1]})", tag)

            # --- State Comparison Logic (Unchanged) ---
            preliminary_state = self.app_state.game_analyzer.analyze_screenshot(board_image, self.app_state.locked_regions)
            self.curr_state = self.piece_tracker.update_state(self.prev_state, preliminary_state)
            
            if self.prev_state:
                events = self.logic_engine.compare_states(self.prev_state, self.curr_state)
                self.log_game_events(events)
            else:
                self.log_message("\n已记录初始棋盘状态，再次点击以分析变化。")

            self.prev_state = self.curr_state
        else:
            self.log_message("[错误] 无法分析，请先生成分区数据。", "p_red")

    def start_continuous_recognition(self):
        # ... (This function is correct)
        if self.is_recognizing: return
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return
        self.is_recognizing = True
        self.button3.config(state='disabled')
        self.button4.config(state='normal')
        self.recognition_thread = Thread(target=self._continuous_recognition_worker, daemon=True)
        self.recognition_thread.start()
        self.log_message("==================== 连续识别已启动 ====================", "h_default")

    def stop_continuous_recognition(self):
        # ... (This function is correct)
        if not self.is_recognizing: return
        self.is_recognizing = False
        self.button3.config(state='normal')
        self.button4.config(state='disabled')
        self.log_message("==================== 连续识别已停止 ====================", "h_default")

    def _continuous_recognition_worker(self):
        # ... (This function is correct)
        while self.is_recognizing:
            screenshot = self.app_state.window_capture.get_screenshot()
            if screenshot is None or not self.app_state.board_roi:
                time.sleep(0.5)
                continue
            x1, y1, x2, y2 = self.app_state.board_roi
            board_image = screenshot[y1:y2, x1:x2]
            try:
                preliminary_state = self.app_state.game_analyzer.analyze_screenshot(board_image, self.app_state.locked_regions)
                self.curr_state = self.piece_tracker.update_state(self.prev_state, preliminary_state)
                if self.prev_state:
                    events = self.logic_engine.compare_states(self.prev_state, self.curr_state)
                    self.root.after(0, self.log_game_events, events)
                self.prev_state = self.curr_state
            except Exception as e:
                self.root.after(0, self.log_message, f"[严重错误] (后台) 分析时出错: {e}", "p_red")

    def visualize_regions(self):
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return
        
        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_message("[错误] 获取截图失败。", "p_red")
            return

        self.log_message("[信息] 正在生成可视化分区图...", "h_default")
        try:
            regions = self.app_state.locked_regions
            if not regions:
                self.log_message("[信息] 未找到已锁定的分区，将重新计算。")
                regions = self.app_state.game_analyzer.get_player_regions(screenshot)
            
            if not regions:
                self.log_message("[错误] 无法获取分区信息。", "p_red")
                return

            vis_image = self.app_state.game_analyzer.visualize_regions_on_image(screenshot.copy(), regions)
            cv2.imshow("Player Regions", vis_image)
            cv2.waitKey(1) # Use waitKey(1) to allow GUI to update
            self._force_set_topmost()
            self.log_message("[成功] 分区图显示完毕。", "p_green")

        except Exception as e:
            self.log_message(f"[错误] 可视化分区时出错: {e}", "p_red")

    def visualize_plus_region(self):
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return
        
        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_message("[错误] 获取截图失败。", "p_red")
            return

        self.log_message("[信息] 正在生成 '+' 形检测区域图...", "h_default")
        try:
            if not self.app_state.board_roi:
                self.log_message("[错误] 棋盘ROI未计算，请先运行一次识别。", "p_red")
                return

            x1, y1, x2, y2 = self.app_state.board_roi
            vis_image = screenshot.copy()
            
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), (0, 0, 255), 2)
            
            center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
            height, width = y2 - y1, x2 - x1
            
            thickness_ratio = 0.1 
            h_thickness = int(height * thickness_ratio)
            v_thickness = int(width * thickness_ratio)

            cv2.rectangle(vis_image, (x1, center_y - h_thickness), (x2, center_y + h_thickness), (255, 0, 0), 2)
            cv2.rectangle(vis_image, (center_x - v_thickness, y1), (center_x + v_thickness, y2), (255, 0, 0), 2)

            cv2.imshow("Detection Area", vis_image)
            cv2.waitKey(1)
            self._force_set_topmost()
            self.log_message("[成功] '+' 形区域图显示完毕。", "p_green")

        except Exception as e:
            self.log_message(f"[错误] 可视化 '+' 形区域时出错: {e}", "p_red")

    def visualize_all_nodes(self):
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return
        
        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_message("[错误] 获取截图失败。", "p_red")
            return

        self.log_message("[信息] 正在全图搜索棋子节点...", "h_default")
        try:
            if not self.app_state.board_roi:
                self.log_message("[错误] 棋盘ROI未计算，请先运行一次识别。", "p_red")
                return

            x1, y1, x2, y2 = self.app_state.board_roi
            board_image = screenshot[y1:y2, x1:x2]
            
            all_results = self.app_state.game_analyzer.get_all_detections(board_image, 0.8)
            
            vis_image = screenshot.copy()
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), (0, 0, 255), 2)
            
            node_count = 0
            for result in all_results:
                node_count += 1
                bbox = result.bbox
                abs_x = bbox[0] + x1
                abs_y = bbox[1] + y1
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]

                cv2.rectangle(vis_image, (abs_x, abs_y), (abs_x + w, abs_y + h), (0, 255, 0), 2)
                label = f"{result.piece_name}"
                cv2.putText(vis_image, label, (abs_x, abs_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            self.log_message(f"共检测到 {node_count} 个棋子节点。")
            cv2.imshow("All Detected Nodes", vis_image)
            cv2.waitKey(1)
            self._force_set_topmost()
            self.log_message("[成功] 全节点分布图显示完毕。", "p_green")

        except Exception as e:
            self.log_message(f"[错误] 可视化节点时出错: {e}", "p_red")

if __name__ == "__main__":
    freeze_support()
    root = tk.Tk()
    app = DashboardApp(root)
    root.mainloop()
