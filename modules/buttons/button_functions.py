"""
按钮功能模块
处理各个按钮的具体功能实现
"""

import tkinter as tk
from tkinter import ttk, messagebox
import win32gui
import win32con
import time
import json
import cv2
import numpy as np
from pathlib import Path
from threading import Thread
from typing import Optional, List, Dict, Any

# 导入核心模块
from capture.realtime_capture import WindowCapture
from game_analyzer import GameAnalyzer
from game_model import BoardState, Piece, PieceTracker, GameLogicEngine, GameEvent

class ButtonFunctions:
    def __init__(self, app_state, ui_manager, log_manager, threshold_manager):
        self.app_state = app_state
        self.ui_manager = ui_manager
        self.log_manager = log_manager
        self.threshold_manager = threshold_manager
        self.is_recognizing = False
        self.recognition_thread = None
        self.button3 = None
        self.button4 = None
        self.piece_tracker = PieceTracker()
        self.logic_engine = GameLogicEngine()
        self.prev_state: Optional[BoardState] = None
        self.curr_state: Optional[BoardState] = None

    def detect_game_window(self):
        """检测游戏窗口"""
        self.log_manager.log_message("--- 开始检测游戏窗口 ---", "h_default")
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

                self.log_manager.log_message("成功检测到游戏窗口！")
                self.log_manager.log_message(f"  - 句柄 (HWND): {self.app_state.hwnd}", "p_cyan")
                self.log_manager.log_message(f"  - 标题: {title}", "p_cyan")
                self.log_manager.log_message(f"  - 类名: {class_name}", "p_cyan")
                self.log_manager.log_message(f"  - 尺寸: {rect[2]-rect[0]}x{rect[3]-rect[1]} @ ({rect[0]},{rect[1]})", "p_cyan")
            else:
                self.log_manager.log_message("错误: 未找到匹配的游戏窗口。", "p_red")

        except Exception as e:
            self.log_manager.log_message(f"检测窗口时发生未知错误: {e}", "p_red")

    def start_recognition(self, threshold_getter):
        """开始识别"""
        recognition_id = time.strftime("%Y%m%d%H%M-%S")
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_manager.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return
        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_manager.log_message("[错误] 获取截图失败。", "p_red")
            return

        # 获取当前阈值
        match_threshold, nms_threshold = threshold_getter()

        # --- Region Locking Logic ---
        if not self.app_state.locked_regions:
            self.log_manager.log_message("[信息] 正在尝试自动锁定初始分区...")
            try:
                regions = self.app_state.game_analyzer.get_player_regions(screenshot, nms_threshold=nms_threshold)
                if not regions or len(regions) < 5:
                    self.log_manager.log_message("[警告] 未能计算出完整的5个区域...", "p_red")
                else:
                    self.app_state.locked_regions = regions
                    serializable_regions = {k: tuple(map(int, v)) for k, v in regions.items()}
                    # 保存分区数据
                    regions_file = Path("data/regions.json")
                    regions_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(regions_file, 'w') as f:
                        json.dump(serializable_regions, f, indent=4)
                    self.log_manager.log_message("[成功] 初始分区已自动锁定并保存！")
                    self._calculate_board_roi()
            except Exception as e:
                self.log_manager.log_message(f"[严重错误] 自动锁定分区时出错: {e}", "p_red")
                return

        if self.app_state.board_roi:
            x1, y1, x2, y2 = self.app_state.board_roi
            board_image = screenshot[y1:y2, x1:x2]
        else:
            board_image = screenshot

        try:
            report = self.app_state.game_analyzer.analyze_screenshot(board_image, match_threshold=match_threshold, nms_threshold=nms_threshold)
            self.log_manager.log_to_dashboard(report, recognition_id=recognition_id)
        except Exception as e:
            self.log_manager.log_message(f"[严重错误] 分析时出错: {e}", "p_red")

    def start_continuous_recognition(self):
        """开始连续识别"""
        if self.is_recognizing: return
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_manager.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return
        self.is_recognizing = True
        if self.button3:
            self.button3.config(state='disabled')
        if self.button4:
            self.button4.config(state='normal')
        self.recognition_thread = Thread(target=self._continuous_recognition_worker, daemon=True)
        self.recognition_thread.start()
        self.log_manager.log_message("==================== 连续识别已启动 ====================", "h_default")

    def stop_continuous_recognition(self):
        """停止连续识别"""
        if not self.is_recognizing: return
        self.is_recognizing = False
        if self.button3:
            self.button3.config(state='normal')
        if self.button4:
            self.button4.config(state='disabled')
        self.log_manager.log_message("==================== 连续识别已停止 ====================", "h_default")

    def _continuous_recognition_worker(self):
        """连续识别工作线程"""
        recognition_count = 0
        while self.is_recognizing:
            screenshot = self.app_state.window_capture.get_screenshot()
            if screenshot is None or not self.app_state.board_roi:
                time.sleep(0.5)
                continue
            x1, y1, x2, y2 = self.app_state.board_roi
            board_image = screenshot[y1:y2, x1:x2]
            try:
                # 获取当前阈值
                match_threshold, nms_threshold = self.threshold_manager.get_thresholds()

                # 使用与按钮2相同的识别方法和时间戳格式
                recognition_id = time.strftime("%Y%m%d%H%M-%S")
                report = self.app_state.game_analyzer.analyze_screenshot(board_image, match_threshold, nms_threshold=nms_threshold)

                # 使用相同的日志输出格式
                self.ui_manager.root.after(0, self.log_manager.log_to_dashboard, report, recognition_id)

                recognition_count += 1
                time.sleep(1.0)  # 每秒识别一次，避免过于频繁

            except Exception as e:
                self.ui_manager.root.after(0, self.log_manager.log_message, f"[严重错误] (后台) 分析时出错: {e}", "p_red")
                time.sleep(1.0)  # 出错时稍等再试

    def _force_set_topmost(self):
        """强制设置窗口置顶"""
        if self.app_state.hwnd and win32gui.IsWindow(self.app_state.hwnd):
            try:
                win32gui.SetWindowPos(self.app_state.hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            except Exception: pass

    def _calculate_board_roi(self):
        """计算棋盘ROI"""
        if not self.app_state.locked_regions:
            self.app_state.board_roi = None
            return
        regions = self.app_state.locked_regions.values()
        min_x = min(r[0] for r in regions)
        min_y = min(r[1] for r in regions)
        max_x = max(r[2] for r in regions)
        max_y = max(r[3] for r in regions)
        self.app_state.board_roi = (int(min_x), int(min_y), int(max_x), int(max_y))
        self.log_manager.log_message(f"[信息] 棋盘ROI计算完成: {self.app_state.board_roi}")

    def visualize_regions(self):
        """查看区域划分"""
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_manager.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return

        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_manager.log_message("[错误] 获取截图失败。", "p_red")
            return

        self.log_manager.log_message("[信息] 正在生成可视化分区图...", "h_default")
        try:
            regions = self.app_state.locked_regions
            if not regions:
                self.log_manager.log_message("[信息] 未找到已锁定的分区，将重新计算。")
                # 获取当前阈值
                _, nms_threshold = self.threshold_manager.get_thresholds()
                regions = self.app_state.game_analyzer.get_player_regions(screenshot, nms_threshold=nms_threshold)

            if not regions:
                self.log_manager.log_message("[错误] 无法获取分区信息。", "p_red")
                return

            vis_image = self.app_state.game_analyzer.visualize_regions_on_image(screenshot.copy(), regions)
            cv2.imshow("Player Regions", vis_image)
            cv2.waitKey(1) # Use waitKey(1) to allow GUI to update
            self._force_set_topmost()
            self.log_manager.log_message("[成功] 分区图显示完毕。", "p_green")

        except Exception as e:
            self.log_manager.log_message(f"[错误] 可视化分区时出错: {e}", "p_red")

    def visualize_plus_region(self):
        """显示检测区域"""
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_manager.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return

        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_manager.log_message("[错误] 获取截图失败。", "p_red")
            return

        self.log_manager.log_message("[信息] 正在生成 '+' 形检测区域图...", "h_default")
        try:
            if not self.app_state.board_roi:
                self.log_manager.log_message("[错误] 棋盘ROI未计算，请先运行一次识别。", "p_red")
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
            self.log_manager.log_message("[成功] '+' 形区域图显示完毕。", "p_green")

        except Exception as e:
            self.log_manager.log_message(f"[错误] 可视化 '+' 形区域时出错: {e}", "p_red")

    def visualize_all_nodes(self):
        """查看节点分布"""
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_manager.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return

        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_manager.log_message("[错误] 获取截图失败。", "p_red")
            return

        self.log_manager.log_message("[信息] 正在全图搜索棋子节点...", "h_default")
        try:
            if not self.app_state.board_roi:
                self.log_manager.log_message("[错误] 棋盘ROI未计算，请先运行一次识别。", "p_red")
                return

            x1, y1, x2, y2 = self.app_state.board_roi

            # 检查截图是否有效
            if screenshot.size == 0:
                self.log_manager.log_message("[错误] 截图为空。", "p_red")
                return

            board_image = screenshot[y1:y2, x1:x2]

            # 检查board_image是否有效
            if board_image.size == 0:
                self.log_manager.log_message(f"[错误] 棋盘图像为空。ROI: {(x1, y1, x2, y2)}", "p_red")
                return

            self.log_manager.log_message(f"[调试] 棋盘图像尺寸: {board_image.shape}", "h_default")

            # 使用get_all_detections方法
            # 获取当前阈值
            match_threshold, nms_threshold = self.threshold_manager.get_thresholds()
            all_results = self.app_state.game_analyzer.get_all_detections(board_image, match_threshold)

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

            self.log_manager.log_message(f"共检测到 {node_count} 个棋子节点。")
            cv2.imshow("All Detected Nodes", vis_image)
            cv2.waitKey(1)
            self._force_set_topmost()
            self.log_manager.log_message("[成功] 全节点分布图显示完毕。", "p_green")

        except Exception as e:
            self.log_manager.log_message(f"[错误] 可视化节点时出错: {e}", "p_red")
            import traceback
            self.log_manager.log_message(f"[调试] 详细错误: {traceback.format_exc()}", "p_red")

    def visualize_detection_zones(self):
        """精确检测区域"""
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_manager.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return

        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_manager.log_message("[错误] 获取截图失败。", "p_red")
            return

        self.log_manager.log_message("[信息] 正在生成精确检测区域图...", "h_default")
        try:
            if not self.app_state.locked_regions:
                self.log_manager.log_message("[错误] 区域数据未锁定，请先运行一次识别。", "p_red")
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
            self.log_manager.log_message("[成功] 精确检测区域图显示完毕。", "p_green")

        except Exception as e:
            self.log_manager.log_message(f"[错误] 可视化检测区域时出错: {e}", "p_red")

    def visualize_theoretical_grid(self):
        """理论坐标地图"""
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_manager.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return

        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_manager.log_message("[错误] 获取截图失败。", "p_red")
            return

        self.log_manager.log_message("[信息] 正在生成理论坐标地图...", "h_default")
        try:
            if not self.app_state.locked_regions:
                self.log_manager.log_message("[错误] 区域数据未锁定，请先运行一次识别。", "p_red")
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
            self.log_manager.log_message("[成功] 理论坐标地图显示完毕。", "p_green")

        except Exception as e:
            self.log_manager.log_message(f"[错误] 可视化理论坐标地图时出错: {e}", "p_red")

    def full_board_recognition(self):
        """全图识别"""
        if not self.app_state.window_capture or not self.app_state.window_capture.hwnd:
            self.log_manager.log_message("[错误] 请先成功检测游戏窗口。", "p_red")
            return

        screenshot = self.app_state.window_capture.get_screenshot()
        if screenshot is None:
            self.log_manager.log_message("[错误] 获取截图失败。", "p_red")
            return

        self.log_manager.log_message("[信息] 正在执行100%准确率全图识别...", "h_default")
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
            self.log_manager.log_message(f"[结果] 全图识别完成！检测到 {detection_count} 个棋子。", "h_default")

            # 按颜色统计
            color_counts = {}
            for detection in all_detections:
                color = detection.color
                if color not in color_counts:
                    color_counts[color] = 0
                color_counts[color] += 1

            for color, count in color_counts.items():
                self.log_manager.log_message(f"  - {color}: {count} 个", color_map.get(color, "p_default"))

            # 按棋子类型统计
            from modules.core.config import COLOR_TAG_MAP
            piece_counts = {}
            for detection in all_detections:
                piece_type = detection.piece_name
                if piece_type not in piece_counts:
                    piece_counts[piece_type] = 0
                piece_counts[piece_type] += 1

            for piece_type, count in piece_counts.items():
                tag = COLOR_TAG_MAP.get(piece_type, "p_default")
                self.log_manager.log_message(f"  - {piece_type}: {count} 个", tag)

            self.log_manager.log_message("[成功] 100%准确率全图识别完毕。", "p_green")

        except Exception as e:
            self.log_manager.log_message(f"[错误] 全图识别时出错: {e}", "p_red")

    def on_closing(self):
        """退出程序"""
        self.is_recognizing = False
        if self.app_state.game_analyzer:
            del self.app_state.game_analyzer
        if self.app_state.hwnd and win32gui.IsWindow(self.app_state.hwnd):
            try:
                win32gui.ShowWindow(self.app_state.hwnd, win32con.SW_MINIMIZE)
                win32gui.SetWindowPos(self.app_state.hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            except Exception: pass
        self.ui_manager.root.destroy()

    def set_buttons(self, button3, button4):
        """设置按钮引用"""
        self.button3 = button3
        self.button4 = button4