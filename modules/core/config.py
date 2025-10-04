"""
配置管理模块
处理系统配置和常量定义
"""

from pathlib import Path
from typing import Dict, Any

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

# --- 系统配置 ---
class SystemConfig:
    def __init__(self):
        self.window_title = "陆战棋-智能战情室 (V23-功能对齐)"
        self.window_size = "800x800"
        self.resizable = False
        self.regions_file = Path("data/regions.json")
        self.templates_dir = "vision/new_templates"

        # 默认阈值
        self.default_match_threshold = 0.8
        self.default_nms_threshold = 0.3

        # 框架高度配置
        self.threshold_frame_height = 40
        self.info_frame_height = 650
        self.control_frame_height = 110

        # 按钮框架配置
        self.button_frame_height = 25
        self.button_frame_pady = 1
        self.button_frame_padx = 20

# --- 初始化配置实例 ---
config = SystemConfig()