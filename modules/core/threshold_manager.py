"""
阈值管理模块
处理匹配阈值和NMS阈值的调节功能
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable

class ThresholdManager:
    def __init__(self, parent_frame, match_callback: Callable, nms_callback: Callable):
        self.parent_frame = parent_frame
        self.match_callback = match_callback
        self.nms_callback = nms_callback

        # 阈值变量
        self.match_threshold = 0.8
        self.nms_threshold = 0.3

        # 创建阈值调节框架
        self.threshold_frame = ttk.Frame(parent_frame, height=40)
        self.threshold_frame.pack(fill="x", padx=10, pady=5)
        self.threshold_frame.pack_propagate(False)

        self._setup_ui()

    def _setup_ui(self):
        """设置阈值调节UI"""
        # 匹配阈值调节组件
        match_frame = ttk.Frame(self.threshold_frame)
        match_frame.pack(side="left", padx=10)
        ttk.Label(match_frame, text="匹配阈值:").pack(side="left")
        self.match_threshold_var = tk.StringVar(value="0.8")
        self.match_threshold_entry = ttk.Entry(match_frame, textvariable=self.match_threshold_var, width=5, state="readonly")
        self.match_threshold_entry.pack(side="left", padx=5)

        match_btn_frame = ttk.Frame(match_frame)
        match_btn_frame.pack(side="left")
        ttk.Button(match_btn_frame, text="▲", width=2, command=self.increase_match_threshold).pack(side="left", pady=0, padx=0, ipady=2)
        ttk.Button(match_btn_frame, text="▼", width=2, command=self.decrease_match_threshold).pack(side="left", pady=0, padx=0, ipady=2)

        # NMS阈值调节组件
        nms_frame = ttk.Frame(self.threshold_frame)
        nms_frame.pack(side="left", padx=10)
        ttk.Label(nms_frame, text="NMS阈值:").pack(side="left")
        self.nms_threshold_var = tk.StringVar(value="0.3")
        self.nms_threshold_entry = ttk.Entry(nms_frame, textvariable=self.nms_threshold_var, width=5, state="readonly")
        self.nms_threshold_entry.pack(side="left", padx=5)

        nms_btn_frame = ttk.Frame(nms_frame)
        nms_btn_frame.pack(side="left")
        ttk.Button(nms_btn_frame, text="▲", width=2, command=self.increase_nms_threshold).pack(side="left", pady=0, padx=0, ipady=2)
        ttk.Button(nms_btn_frame, text="▼", width=2, command=self.decrease_nms_threshold).pack(side="left", pady=0, padx=0, ipady=2)

        # 清空信息按钮
        self.clear_info_button = ttk.Button(self.threshold_frame, text="清空信息")
        self.clear_info_button.pack(side="right", padx=10)

    def increase_match_threshold(self):
        """增加匹配阈值"""
        current = float(self.match_threshold_var.get())
        if current < 0.9:
            new_value = round(current + 0.1, 1)
            self.match_threshold_var.set(f"{new_value:.1f}")
            self.match_threshold = new_value
            self.match_callback(f"[信息] 匹配阈值已调整为: {new_value:.1f}", "h_default")

    def decrease_match_threshold(self):
        """减少匹配阈值"""
        current = float(self.match_threshold_var.get())
        if current > 0.5:
            new_value = round(current - 0.1, 1)
            self.match_threshold_var.set(f"{new_value:.1f}")
            self.match_threshold = new_value
            self.match_callback(f"[信息] 匹配阈值已调整为: {new_value:.1f}", "h_default")

    def increase_nms_threshold(self):
        """增加NMS阈值"""
        current = float(self.nms_threshold_var.get())
        if current < 0.9:
            new_value = round(current + 0.1, 1)
            self.nms_threshold_var.set(f"{new_value:.1f}")
            self.nms_threshold = new_value
            self.nms_callback(f"[信息] NMS阈值已调整为: {new_value:.1f}", "h_default")

    def decrease_nms_threshold(self):
        """减少NMS阈值"""
        current = float(self.nms_threshold_var.get())
        if current > 0.1:
            new_value = round(current - 0.1, 1)
            self.nms_threshold_var.set(f"{new_value:.1f}")
            self.nms_threshold = new_value
            self.nms_callback(f"[信息] NMS阈值已调整为: {new_value:.1f}", "h_default")

    def set_clear_info_callback(self, callback: Callable):
        """设置清空信息回调函数"""
        self.clear_info_callback = callback

    def get_thresholds(self):
        """获取当前阈值"""
        return self.match_threshold, self.nms_threshold