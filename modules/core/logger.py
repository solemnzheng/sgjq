"""
日志管理模块
处理系统日志和信息显示功能
"""

import tkinter as tk
from tkinter import scrolledtext
from typing import Optional, List, Dict, Any

class LogManager:
    def __init__(self, info_text: scrolledtext.ScrolledText):
        self.info_text = info_text

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
        """记录单条消息"""
        self.info_text.config(state='normal')
        self.info_text.insert(tk.END, message + "\n", tag)
        self.info_text.see(tk.END)
        self.info_text.config(state='disabled')

    def log_game_events(self, events: List[Any]):
        """记录游戏事件"""
        self.info_text.config(state='normal')
        import time
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

    def clear_info_panel(self):
        """清空信息显示面板的全部信息"""
        self.info_text.config(state='normal')
        self.info_text.delete(1.0, tk.END)
        self.info_text.config(state='disabled')