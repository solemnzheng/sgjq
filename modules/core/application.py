"""
核心应用类
集成所有模块，提供统一的应用程序入口
"""

import tkinter as tk
from tkinter import ttk
from pathlib import Path
import json
from multiprocessing import freeze_support
from dataclasses import dataclass
from typing import Optional, Dict, Any

# 导入模块
from modules.ui.ui_manager import UIManager
from modules.core.logger import LogManager
from modules.core.threshold_manager import ThresholdManager
from modules.buttons.button_functions import ButtonFunctions
from modules.core.config import config

# 导入核心模块
from game_analyzer import GameAnalyzer
from game_model import BoardState

@dataclass
class AppState:
    """应用状态类"""
    def __init__(self):
        self.hwnd = 0
        self.window_capture = None
        self.game_analyzer = None
        self.locked_regions = None
        self.board_roi = None

class ModularDashboardApp:
    """模块化仪表板应用"""
    def __init__(self, root):
        self.root = root

        # 初始化应用状态
        self.app_state = AppState()

        # 初始化UI管理器
        self.ui_manager = UIManager(root)

        # 初始化日志管理器
        self.log_manager = LogManager(self.ui_manager.get_info_text())

        # 初始化阈值管理器
        self.threshold_manager = ThresholdManager(
            self.ui_manager.threshold_frame,
            self.log_manager.log_message,
            self.log_manager.log_message
        )

        # 初始化按钮功能
        self.button_functions = ButtonFunctions(
            self.app_state,
            self.ui_manager,
            self.log_manager,
            self.threshold_manager
        )

        # 设置清空信息回调
        self.threshold_manager.set_clear_info_callback(self.log_manager.clear_info_panel)

        # 设置控制按钮
        self.setup_control_buttons()

        # 初始化分析器
        self.initialize_analyzer()

        # 设置窗口关闭协议
        self.root.protocol("WM_DELETE_WINDOW", self.button_functions.on_closing)

    def setup_control_buttons(self):
        """设置控制按钮"""
        button_commands = {
            'row1_0': self.button_functions.detect_game_window,
            'row1_1': lambda: self.button_functions.start_recognition(self.threshold_manager.get_thresholds),
            'row1_2': self.button_functions.start_continuous_recognition,
            'row1_3': self.button_functions.stop_continuous_recognition,
            'row2_0': self.button_functions.visualize_regions,
            'row2_1': self.button_functions.visualize_plus_region,
            'row2_2': self.button_functions.visualize_all_nodes,
            'row2_3': lambda: None,  # 功能按钮，暂时为空
            'row3_0': self.button_functions.visualize_detection_zones,
            'row3_1': self.button_functions.visualize_theoretical_grid,
            'row3_2': self.button_functions.full_board_recognition,
            'row3_3': self.button_functions.on_closing
        }

        self.ui_manager.setup_control_buttons(button_commands)

        # 获取按钮引用
        # 这里需要获取连续识别和停止识别按钮的引用
        # 由于UI管理器的实现方式，我们需要稍后设置这些引用

    def initialize_analyzer(self):
        """初始化分析器"""
        try:
            self.app_state.game_analyzer = GameAnalyzer(config.templates_dir)
            self.log_manager.log_message("--- 战情室启动成功 ---")

            regions_file = config.regions_file
            if regions_file.exists():
                try:
                    with open(regions_file, 'r') as f:
                        self.app_state.locked_regions = json.load(f)
                    self.log_manager.log_message("[信息] 已成功从文件加载锁定的分区数据。")
                except Exception as e:
                    self.log_manager.log_message(f"[错误] 加载分区文件失败: {e}", "p_red")
            else:
                self.log_manager.log_message("[信息] 未找到分区数据文件。请点击\"2. 开始识别\"以在首次识别时自动生成。")
                regions_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log_manager.log_message(f"[严重错误] 分析器初始化失败: {e}", "p_red")
            import traceback
            self.log_manager.log_message(f"[调试] 详细错误: {traceback.format_exc()}", "p_red")

    def run(self):
        """运行应用"""
        self.root.mainloop()

def main():
    """主函数"""
    freeze_support()
    root = tk.Tk()
    app = ModularDashboardApp(root)
    app.run()

if __name__ == "__main__":
    main()