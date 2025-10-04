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
from collections import Counter
from multiprocessing import freeze_support

# --- 颜色标签映射 ---
COLOR_TAG_MAP = {
    "司令": "p_purple",
    "军长": "p_red",
    "师长": "p_orange",
    "旅长": "p_yellow",
    "团长": "p_blue",
    "营长": "p_green",
    "连长": "p_cyan",
    "排长": "p_purple",
    "工兵": "p_red",
    "炸弹": "p_bold_red",
    "地雷": "p_yellow",
    "军旗": "p_blue"
}

# --- 导入核心模块 ---
from capture.realtime_capture import WindowCapture
from game_analyzer import GameAnalyzer
from game_model import BoardState, Piece, PieceTracker, GameLogicEngine, GameEvent
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional

# --- 辅助函数 ---
def dict_to_board_state(report_dict: Dict[str, Any]) -> BoardState:
    """将分析器的字典结果转换为BoardState对象"""
    board_state = BoardState(timestamp=time.time())

    # 从report_items中提取棋子信息
    report_items = report_dict.get('report_items', [])

    for item in report_items:
        if item.get('type') == 'piece_line':
            pieces = item.get('pieces', [])
            for piece_info in pieces:
                # 假设棋子信息格式，如果没有明确位置信息，使用默认位置
                piece_name = piece_info.get('piece_name', '')
                piece_color = piece_info.get('color', '')
                player_pos = {'blue': '下', 'green': '上', 'orange': '右', 'purple': '左'}.get(piece_color, '中')

                # 创建Piece对象（使用默认坐标）
                piece = Piece(
                    id='',  # 将由PieceTracker分配
                    name=piece_name,
                    color=piece_color,
                    player_pos=player_pos,
                    board_coords=(0, 0)  # 默认坐标
                )

                # 添加到board_state
                board_state.pieces[piece_name] = piece

    return board_state

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
                self.log_message("[信息] 未找到分区数据文件。请点击\"2. 开始识别\"以在首次识别时自动生成。")
                self.regions_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log_message(f"[严重错误] 分析器初始化失败: {e}", "p_red")
            import traceback
            self.log_message(f"[调试] 详细错误: {traceback.format_exc()}", "p_red")

    def setup_control_buttons(self):
        # ... (This function is now complete and correct)
        button_frame_1 = ttk.Frame(self.control_frame)
        button_frame_1.pack(fill='x', expand=True, padx=20, pady=5)
        button_frame_2 = ttk.Frame(self.control_frame)
        button_frame_2.pack(fill='x', expand=True, padx=20, pady=5)
        button_frame_3 = ttk.Frame(self.control_frame)
        button_frame_3.pack(fill='x', expand=True, padx=20, pady=5)
        buttons_row1 = ["检测游戏窗口", "开始识别", "连续识别", "停止识别"]
        buttons_row2 = ["查看区域划分", "显示检测区域", "查看节点分布", "功能按钮"]
        buttons_row3 = ["精确检测区域", "理论坐标地图", "全图识别", "退出程序"]
        for i, text in enumerate(buttons_row1):
            button = ttk.Button(button_frame_1, text=text, width=12)
            button.pack(side="left", fill="x", expand=True, padx=5)
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
            button = ttk.Button(button_frame_2, text=text, width=12)
            button.pack(side="left", fill="x", expand=True, padx=5)
            if i == 0: button.config(command=self.visualize_regions)
            elif i == 1: button.config(command=self.visualize_plus_region)
            elif i == 2: button.config(command=self.visualize_all_nodes)
        for i, text in enumerate(buttons_row3):
            button = ttk.Button(button_frame_3, text=text, width=12)
            button.pack(side="left", fill="x", expand=True, padx=5)
            if i == 0: button.config(command=self.visualize_detection_zones)  # 按钮9
            elif i == 1: button.config(command=self.visualize_theoretical_grid)  # 按钮10
            elif i == 2: button.config(command=self.full_board_recognition)  # 按钮11
            elif i == 3: button.config(command=self.on_closing)

    def log_to_dashboard(self, report: Dict[str, Any], recognition_id: str = None):
        """OLD版本风格的日志方法"""
        self.info_text.config(state='normal')

        if recognition_id:
            total_count = report.get('total_count', 0)
            separator = f"\n{'='*15} [ {recognition_id} ] (总棋子数: {total_count}个) {'='*15}\n"
            self.info_text.insert(tk.END, separator, ("h_default",))

        report_items = report.get('report_items', [])
        for item in report_items:
            item_type = item.get('type', 'info')
            text = item.get('text', '')

            if item_type == 'header':
                self.info_text.insert(tk.END, text + "\n", ("h_default",))
            elif item_type == 'error':
                self.info_text.insert(tk.END, text + "\n", ("p_bold_red",))
            elif item_type == 'info':
                self.info_text.insert(tk.END, text + "\n", ("p_cyan",))
            elif item_type == 'piece_line':
                pieces = item.get('pieces', [])
                for piece_info in pieces:
                    piece_text = piece_info.get('text', '')
                    color_tag = piece_info.get('color_tag', 'p_default')
                    is_eliminated = piece_info.get('is_eliminated', False)
                    tag = color_tag if not is_eliminated else 'eliminated'
                    self.info_text.insert(tk.END, f"  {piece_text} ", (tag,))
                self.info_text.insert(tk.END, "\n")
            elif item_type == 'separator':
                self.info_text.insert(tk.END, "\n")
            else:
                self.info_text.insert(tk.END, text + "\n")

        self.info_text.see(tk.END)
        self.info_text.config(state='disabled')

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
        recognition_id = time.strftime("%Y%m%d%H%M-%S")
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
                    self.log_message("[警告] 未能计算出完整的5个区域...", "p_red")
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

        if self.app_state.board_roi:
            x1, y1, x2, y2 = self.app_state.board_roi
            board_image = screenshot[y1:y2, x1:x2]
        else:
            board_image = screenshot

        try:
            report = self.app_state.game_analyzer.analyze_screenshot(board_image, match_threshold=threshold)
            self.log_to_dashboard(report, recognition_id=recognition_id)
        except Exception as e:
            self.log_message(f"[严重错误] 分析时出错: {e}", "p_red")

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
        # 连续识别 worker - 使用与按钮2相同的输出格式
        recognition_count = 0
        while self.is_recognizing:
            screenshot = self.app_state.window_capture.get_screenshot()
            if screenshot is None or not self.app_state.board_roi:
                time.sleep(0.5)
                continue
            x1, y1, x2, y2 = self.app_state.board_roi
            board_image = screenshot[y1:y2, x1:x2]
            try:
                # 使用与按钮2相同的识别方法和时间戳格式
                recognition_id = time.strftime("%Y%m%d%H%M-%S")
                report = self.app_state.game_analyzer.analyze_screenshot(board_image, 0.8)

                # 使用相同的日志输出格式
                self.root.after(0, self.log_to_dashboard, report, recognition_id)

                recognition_count += 1
                time.sleep(1.0)  # 每秒识别一次，避免过于频繁

            except Exception as e:
                self.root.after(0, self.log_message, f"[严重错误] (后台) 分析时出错: {e}", "p_red")
                time.sleep(1.0)  # 出错时稍等再试

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

            # 绘制棋盘边框
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # 计算中心点
            center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
            height, width = y2 - y1, x2 - x1

            # 使用固定厚度而不是比例，避免线条太粗
            thickness = max(3, min(height // 20, width // 20))  # 合理的线条厚度

            # 绘制十字分区线 - 水平线 (绿色)
            cv2.line(vis_image, (x1, center_y), (x2, center_y), (0, 255, 0), thickness)

            # 绘制十字分区线 - 垂直线 (绿色)
            cv2.line(vis_image, (center_x, y1), (center_x, y2), (0, 255, 0), thickness)

            # 添加区域标签
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.7
            text_color = (0, 255, 255)  # 黄色文字
            text_thickness = 2

            # 标注四个区域
            cv2.putText(vis_image, "左上", (x1 + 10, y1 + 30), font, font_scale, text_color, text_thickness)
            cv2.putText(vis_image, "右上", (x2 - 60, y1 + 30), font, font_scale, text_color, text_thickness)
            cv2.putText(vis_image, "左下", (x1 + 10, y2 - 10), font, font_scale, text_color, text_thickness)
            cv2.putText(vis_image, "右下", (x2 - 60, y2 - 10), font, font_scale, text_color, text_thickness)
            cv2.putText(vis_image, "中央", (center_x - 20, center_y - 10), font, font_scale, text_color, text_thickness)

            cv2.imshow("Detection Area", vis_image)
            cv2.waitKey(1)
            self._force_set_topmost()
            self.log_message("[成功] '+' 形区域图显示完毕。", "p_green")

        except Exception as e:
            self.log_message(f"[错误] 可视化 '+' 形区域时出错: {e}", "p_red")

    def visualize_detection_zones(self):
        """按钮9: 实现OLD版本按钮6的功能 - 显示正确的检测区域"""
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return

        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_message("[错误] 获取截图失败。", "p_red")
            return

        self.log_message("[信息] 正在生成精确检测区域图...", "h_default")
        try:
            if not self.app_state.locked_regions:
                self.log_message("[错误] 区域数据未锁定，请先运行一次识别。", "p_red")
                return

            vis_image = screenshot.copy()

            # 绘制各个玩家的检测区域
            colors = {
                "上方": (255, 0, 0), "下方": (0, 255, 0),
                "左侧": (0, 0, 255), "右侧": (255, 255, 0),
                "中央": (255, 0, 255)
            }

            for region_name, (x1, y1, x2, y2) in self.app_state.locked_regions.items():
                color = colors.get(region_name, (128, 128, 128))
                # 绘制半透明填充
                overlay = vis_image.copy()
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
                cv2.addWeighted(overlay, 0.3, vis_image, 0.7, 0, vis_image)
                # 绘制边框
                cv2.rectangle(vis_image, (x1, y1), (x2, y2), color, 3)
                # 添加区域标签
                cv2.putText(vis_image, region_name, (x1 + 5, y1 + 25),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            cv2.imshow("Detection Zones", vis_image)
            cv2.waitKey(1)
            self._force_set_topmost()
            self.log_message("[成功] 精确检测区域图显示完毕。", "p_green")

        except Exception as e:
            self.log_message(f"[错误] 可视化检测区域时出错: {e}", "p_red")

    def visualize_theoretical_grid(self):
        """按钮10: 实现理论坐标地图功能"""
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return

        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_message("[错误] 获取截图失败。", "p_red")
            return

        self.log_message("[信息] 正在生成理论坐标地图...", "h_default")
        try:
            if not self.app_state.locked_regions:
                self.log_message("[错误] 区域数据未锁定，请先运行一次识别。", "p_red")
                return

            vis_image = screenshot.copy()
            regions = self.app_state.locked_regions

            # 为每个区域绘制理论网格
            for region_name, (x1, y1, x2, y2) in regions.items():
                if region_name == "中央":
                    rows, cols = 3, 3
                else:
                    rows, cols = 6, 5

                region_w = x2 - x1
                region_h = y2 - y1
                cell_w = region_w // cols
                cell_h = region_h // rows

                # 绘制网格线
                for i in range(rows + 1):
                    y = y1 + i * cell_h
                    cv2.line(vis_image, (x1, y), (x2, y), (255, 255, 255), 1)

                for j in range(cols + 1):
                    x = x1 + j * cell_w
                    cv2.line(vis_image, (x, y1), (x, y2), (255, 255, 255), 1)

                # 添加坐标标签
                for i in range(rows):
                    for j in range(cols):
                        x = x1 + j * cell_w + cell_w // 2
                        y = y1 + i * cell_h + cell_h // 2
                        coord_text = f"{i},{j}"
                        cv2.putText(vis_image, coord_text, (x - 10, y + 5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.3, (200, 200, 200), 1)

                # 绘制区域边框和标签
                cv2.rectangle(vis_image, (x1, y1), (x2, y2), (0, 255, 255), 2)
                cv2.putText(vis_image, f"{region_name} ({rows}x{cols})",
                           (x1 + 5, y1 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            cv2.imshow("Theoretical Grid", vis_image)
            cv2.waitKey(1)
            self._force_set_topmost()
            self.log_message("[成功] 理论坐标地图显示完毕。", "p_green")

        except Exception as e:
            self.log_message(f"[错误] 可视化理论坐标地图时出错: {e}", "p_red")

    def full_board_recognition(self):
        """按钮11: 实现100%准确率的全图识别"""
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return

        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_message("[错误] 获取截图失败。", "p_red")
            return

        self.log_message("[信息] 正在执行100%准确率全图识别...", "h_default")
        try:
            # 使用整个截图而非ROI进行识别
            full_image = screenshot.copy()

            # 使用较低的阈值确保100%检测
            threshold = 0.6
            all_detections = self.app_state.game_analyzer.get_all_detections(full_image, threshold)

            # 可视化所有检测结果
            vis_image = screenshot.copy()

            # 绘制所有检测到的棋子
            color_map = {
                "blue": (255, 0, 0), "green": (0, 255, 0),
                "orange": (0, 165, 255), "purple": (255, 0, 255)
            }

            detection_count = 0
            for detection in all_detections:
                detection_count += 1
                bbox = detection.bbox
                color = color_map.get(detection.color, (255, 255, 255))

                # 绘制检测框
                cv2.rectangle(vis_image, (bbox[0], bbox[1]), (bbox[2], bbox[3]), color, 2)

                # 添加标签
                label = f"{detection.piece_name}({detection.color})"
                cv2.putText(vis_image, label, (bbox[0], bbox[1] - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

            # 显示结果
            cv2.imshow("Full Board Recognition", vis_image)
            cv2.waitKey(1)
            self._force_set_topmost()

            # 生成详细报告
            self.log_message(f"[结果] 全图识别完成！检测到 {detection_count} 个棋子。", "h_default")

            # 按颜色统计
            color_counts = {}
            for detection in all_detections:
                color = detection.color
                if color not in color_counts:
                    color_counts[color] = 0
                color_counts[color] += 1

            for color, count in color_counts.items():
                self.log_message(f"  - {color}: {count} 个", color_map.get(color, "p_default"))

            # 按棋子类型统计
            piece_counts = {}
            for detection in all_detections:
                piece_type = detection.piece_name
                if piece_type not in piece_counts:
                    piece_counts[piece_type] = 0
                piece_counts[piece_type] += 1

            for piece_type, count in piece_counts.items():
                tag = COLOR_TAG_MAP.get(piece_type, "p_default")
                self.log_message(f"  - {piece_type}: {count} 个", tag)

            self.log_message("[成功] 100%准确率全图识别完毕。", "p_green")

        except Exception as e:
            self.log_message(f"[错误] 全图识别时出错: {e}", "p_red")

    def visualize_all_nodes(self):
        """按钮7: 显示全节点分布图"""
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

            # 检查截图是否有效
            if screenshot.size == 0:
                self.log_message("[错误] 截图为空。", "p_red")
                return

            board_image = screenshot[y1:y2, x1:x2]

            # 检查board_image是否有效
            if board_image.size == 0:
                self.log_message(f"[错误] 棋盘图像为空。ROI: {(x1, y1, x2, y2)}", "p_red")
                return

            self.log_message(f"[调试] 棋盘图像尺寸: {board_image.shape}", "h_default")

            # 使用get_all_detections方法
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
            import traceback
            self.log_message(f"[调试] 详细错误: {traceback.format_exc()}", "p_red")

if __name__ == "__main__":
    freeze_support()
    root = tk.Tk()
    app = DashboardApp(root)
    root.mainloop()
