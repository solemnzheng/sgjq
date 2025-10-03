import win32gui
import win32process
import win32ui
import win32con
import numpy as np
import time
import psutil
import ctypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

def find_window_ultimate(process_name: str, title_substring: str, pid: int = None) -> int:
    """
    终极窗口查找器：依次尝试PID(如果提供)、进程名和标题子字符串。
    """
    # 方法1: 按PID查找 (如果提供了PID)
    if pid:
        try:
            proc = psutil.Process(pid)
            if proc.name().lower() == process_name.lower():
                def callback(hwnd, hwnds):
                    if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
                        _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                        if found_pid == pid:
                            hwnds.append(hwnd)
                    return True
                hwnds = []
                win32gui.EnumWindows(callback, hwnds)
                if hwnds: return hwnds[0]
        except (psutil.NoSuchProcess, Exception):
            pass

    # 方法2: 按进程名查找
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'].lower() == process_name.lower():
            pid_from_name = proc.info['pid']
            def callback(hwnd, hwnds):
                if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
                    _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                    if found_pid == pid_from_name and title_substring in win32gui.GetWindowText(hwnd):
                        hwnds.append(hwnd)
                return True
            hwnds = []
            win32gui.EnumWindows(callback, hwnds)
            if hwnds: return hwnds[0]

    # 方法3: 按标题模糊查找
    def callback(hwnd, hwnds):
        if win32gui.IsWindowVisible(hwnd) and title_substring in win32gui.GetWindowText(hwnd):
            hwnds.append(hwnd)
        return True
    hwnds = []
    win32gui.EnumWindows(callback, hwnds)
    if hwnds: return hwnds[0]
        
    return 0

class WindowCapture:
    def __init__(self, process_name: str, title_substring: str, pid: int = None):
        self.pid = pid
        self.process_name = process_name
        self.title_substring = title_substring
        self.hwnd = 0
        self._find_window()

    def _find_window(self):
        self.hwnd = find_window_ultimate(self.process_name, self.title_substring, self.pid)
        if not self.hwnd:
            raise Exception("错误: 未能找到游戏窗口。")

    def get_screenshot(self) -> np.ndarray:
        if not win32gui.IsWindow(self.hwnd):
            self._find_window()
        
        try:
            left, top, right, bot = win32gui.GetClientRect(self.hwnd)
            w = right - left
            h = bot - top
            if w <= 0 or h <= 0: return np.array([])

            wDC = win32gui.GetWindowDC(self.hwnd)
            dcObj = win32ui.CreateDCFromHandle(wDC)
            cDC = dcObj.CreateCompatibleDC()
            dataBitMap = win32ui.CreateBitmap()
            dataBitMap.CreateCompatibleBitmap(dcObj, w, h)
            cDC.SelectObject(dataBitMap)
            cDC.BitBlt((0, 0), (w, h), dcObj, (0, 0), win32con.SRCCOPY)
            
            signedIntsArray = dataBitMap.GetBitmapBits(True)
            img = np.frombuffer(signedIntsArray, dtype='uint8').reshape(h, w, 4)

            dcObj.DeleteDC()
            cDC.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, wDC)
            win32gui.DeleteObject(dataBitMap.GetHandle())

            return img[...,:3]
        except Exception:
            return np.array([])