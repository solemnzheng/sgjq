"""
UI管理模块
处理界面组件的创建和管理
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import List, Callable
from modules.core.config import config, COLOR_TAG_MAP

class UIManager:
    def __init__(self, root):
        self.root = root
        self.setup_main_window()
        self.setup_frames()
        self.setup_tags()

    def setup_main_window(self):
        """设置主窗口"""
        self.root.title(config.window_title)
        self.root.geometry(config.window_size)
        self.root.resizable(config.resizable, config.resizable)

    def setup_frames(self):
        """设置框架"""
        # 阈值调节框架
        self.threshold_frame = ttk.Frame(self.root, height=40)
        self.threshold_frame.pack(fill="x", padx=10, pady=5)
        self.threshold_frame.pack_propagate(False)

        # 信息显示框架
        self.info_frame = ttk.Frame(self.root, height=config.info_frame_height)
        self.info_frame.pack(fill="both", expand=True)
        self.info_frame.pack_propagate(False)

        # 控制按钮框架
        self.control_frame = ttk.Frame(self.root, height=config.control_frame_height)
        self.control_frame.pack(fill="x")
        self.control_frame.pack_propagate(False)

        # 信息文本框
        self.info_text = scrolledtext.ScrolledText(
            self.info_frame,
            wrap=tk.WORD,
            state='disabled',
            font=("Microsoft YaHei", 10),
            bg="#F0F0F0",
            fg="black"
        )
        self.info_text.pack(fill="both", expand=True, padx=5, pady=5)

    def setup_tags(self):
        """设置文本标签样式"""
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

    def setup_control_buttons(self, button_commands: dict):
        """设置控制按钮"""
        # 清空现有按钮框架
        for widget in self.control_frame.winfo_children():
            widget.destroy()

        # 创建按钮框架
        button_frame_1 = ttk.Frame(self.control_frame, height=config.button_frame_height)
        button_frame_1.pack(fill='x', expand=True, padx=config.button_frame_padx, pady=config.button_frame_pady)
        button_frame_1.pack_propagate(False)

        button_frame_2 = ttk.Frame(self.control_frame, height=config.button_frame_height)
        button_frame_2.pack(fill='x', expand=True, padx=config.button_frame_padx, pady=config.button_frame_pady)
        button_frame_2.pack_propagate(False)

        button_frame_3 = ttk.Frame(self.control_frame, height=config.button_frame_height)
        button_frame_3.pack(fill='x', expand=True, padx=config.button_frame_padx, pady=config.button_frame_pady)
        button_frame_3.pack_propagate(False)

        # 按钮文本
        buttons_row1 = ["检测游戏窗口", "开始识别", "连续识别", "停止识别"]
        buttons_row2 = ["查看区域划分", "显示检测区域", "查看节点分布", "功能按钮"]
        buttons_row3 = ["精确检测区域", "理论坐标地图", "全图识别", "退出程序"]

        # 创建按钮
        self._create_buttons(button_frame_1, buttons_row1, button_commands, 'row1')
        self._create_buttons(button_frame_2, buttons_row2, button_commands, 'row2')
        self._create_buttons(button_frame_3, buttons_row3, button_commands, 'row3')

    def _create_buttons(self, parent_frame, button_texts: List[str], button_commands: dict, row_key: str):
        """创建按钮"""
        for i, text in enumerate(button_texts):
            button = ttk.Button(parent_frame, text=text, width=12)
            button.pack(side="left", fill="x", expand=True, padx=5)

            # 根据按钮文本和行号设置命令
            command_key = f"{row_key}_{i}"
            if command_key in button_commands:
                button.config(command=button_commands[command_key])

    def get_info_text(self):
        """获取信息文本框"""
        return self.info_text

    def log_message(self, message: str, tag: str = None):
        """记录消息到信息面板"""
        self.info_text.config(state='normal')
        self.info_text.insert(tk.END, message + "\n", tag)
        self.info_text.see(tk.END)
        self.info_text.config(state='disabled')