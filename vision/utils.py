"""
图像预处理与工具模块
提供图像增强、滤波、形态学操作等预处理功能
"""
import cv2
import numpy as np
from typing import Tuple, Optional, List


def preprocess_image(img: np.ndarray,
                   method: str = "grayscale",
                   normalize: bool = True,
                   equalize: bool = False) -> np.ndarray:
    """
    基础图像预处理

    Args:
        img: 输入图像 (BGR格式)
        method: 处理方法 ("grayscale", "hsv", "lab", "bgr")
        normalize: 是否归一化到0-255
        equalize: 是否直方图均衡化

    Returns:
        处理后的图像
    """
    processed = img.copy()

    # 转换颜色空间
    if method == "grayscale":
        processed = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
    elif method == "hsv":
        processed = cv2.cvtColor(processed, cv2.COLOR_BGR2HSV)
    elif method == "lab":
        processed = cv2.cvtColor(processed, cv2.COLOR_BGR2LAB)

    # 归一化
    if normalize:
        processed = cv2.normalize(processed, None, 0, 255, cv2.NORM_MINMAX)

    # 直方图均衡化（仅对灰度图像）
    if equalize and len(processed.shape) == 2:
        processed = cv2.equalizeHist(processed)

    return processed


def enhance_contrast(img: np.ndarray,
                   method: str = "clahe",
                   clip_limit: float = 2.0,
                   grid_size: Tuple[int, int] = (8, 8)) -> np.ndarray:
    """
    增强图像对比度

    Args:
        img: 输入图像（单通道）
        method: 增强方法 ("clahe", "gamma", "stretch")
        clip_limit: CLAHE的对比度限制
        grid_size: CLAHE的网格大小

    Returns:
        增强后的图像
    """
    if method == "clahe":
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=grid_size)
        return clahe.apply(img)
    elif method == "gamma":
        gamma = 1.2
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255
                        for i in np.arange(0, 256)]).astype("uint8")
        return cv2.LUT(img, table)
    elif method == "stretch":
        return cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)
    else:
        return img


def remove_noise(img: np.ndarray,
                method: str = "gaussian",
                kernel_size: int = 3) -> np.ndarray:
    """
    去除图像噪声

    Args:
        img: 输入图像
        method: 去噪方法 ("gaussian", "median", "bilateral", "morphology")
        kernel_size: 卷积核大小（奇数）

    Returns:
        去噪后的图像
    """
    if method == "gaussian":
        return cv2.GaussianBlur(img, (kernel_size, kernel_size), 0)
    elif method == "median":
        return cv2.medianBlur(img, kernel_size)
    elif method == "bilateral":
        return cv2.bilateralFilter(img, kernel_size, 75, 75)
    elif method == "morphology":
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                          (kernel_size, kernel_size))
        return cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)
    else:
        return img


def adaptive_threshold(img: np.ndarray,
                     method: str = "gaussian",
                     block_size: int = 11,
                     c: float = 2.0) -> np.ndarray:
    """
    自适应阈值处理

    Args:
        img: 输入图像（单通道）
        method: 阈值方法 ("gaussian", "mean")
        block_size: 邻域块大小（奇数）
        c: 常数，从计算的平均/加权均值中减去的值

    Returns:
        二值化图像
    """
    if method == "gaussian":
        return cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY, block_size, c)
    elif method == "mean":
        return cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                 cv2.THRESH_BINARY, block_size, c)
    else:
        return img


def morphological_operations(img: np.ndarray,
                          operation: str = "open",
                          kernel_shape: str = "ellipse",
                          kernel_size: int = 3,
                          iterations: int = 1) -> np.ndarray:
    """
    形态学操作

    Args:
        img: 输入图像（二值或灰度）
        operation: 操作类型 ("open", "close", "erode", "dilate")
        kernel_shape: 核形状 ("ellipse", "rect", "cross")
        kernel_size: 核大小
        iterations: 迭代次数

    Returns:
        处理后的图像
    """
    if kernel_shape == "ellipse":
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                          (kernel_size, kernel_size))
    elif kernel_shape == "rect":
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT,
                                          (kernel_size, kernel_size))
    elif kernel_shape == "cross":
        kernel = cv2.getStructuringElement(cv2.MORPH_CROSS,
                                          (kernel_size, kernel_size))
    else:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                          (kernel_size, kernel_size))

    if operation == "open":
        return cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel, iterations=iterations)
    elif operation == "close":
        return cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel, iterations=iterations)
    elif operation == "erode":
        return cv2.erode(img, kernel, iterations=iterations)
    elif operation == "dilate":
        return cv2.dilate(img, kernel, iterations=iterations)
    else:
        return img


def non_max_suppression(boxes: List[Tuple[int, int, int, int]],
                       scores: List[float],
                       iou_threshold: float = 0.3) -> List[int]:
    """
    非极大值抑制

    Args:
        boxes: 边界框列表 [(x1, y1, x2, y2), ...]
        scores: 置信度列表
        iou_threshold: IOU阈值

    Returns:
        保留的边界框索引列表
    """
    if len(boxes) == 0:
        return []

    boxes = np.array(boxes)
    scores = np.array(scores)

    # 转换为 (x, y, w, h) 格式
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)

        inter = w * h
        union = areas[i] + areas[order[1:]] - inter
        iou = inter / union

        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]

    return keep


def extract_cell_image(img: np.ndarray,
                     bbox: Tuple[int, int, int, int],
                     padding: int = 2) -> np.ndarray:
    """
    从棋盘图像中提取单个格子图像

    Args:
        img: 棋盘图像
        bbox: 边界框 (x, y, w, h)
        padding: 填充像素

    Returns:
        格子图像
    """
    x, y, w, h = bbox

    # 添加填充，但不超过图像边界
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(img.shape[1], x + w + padding)
    y2 = min(img.shape[0], y + h + padding)

    return img[y1:y2, x1:x2]


def resize_with_aspect_ratio(img: np.ndarray,
                          target_size: Tuple[int, int],
                          method: str = "letterbox") -> np.ndarray:
    """
    保持长宽比的图像缩放

    Args:
        img: 输入图像
        target_size: 目标尺寸 (width, height)
        method: 缩放方法 ("letterbox", "crop", "stretch")

    Returns:
        缩放后的图像
    """
    h, w = img.shape[:2]
    target_w, target_h = target_size

    if method == "letterbox":
        # 计算缩放比例
        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)

        # 缩放图像
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # 创建目标尺寸的画布并居中放置
        result = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        offset_x = (target_w - new_w) // 2
        offset_y = (target_h - new_h) // 2
        result[offset_y:offset_y + new_h, offset_x:offset_x + new_w] = resized

        return result
    elif method == "crop":
        # 计算缩放比例和裁剪区域
        scale = max(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)

        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # 居中裁剪
        start_x = (new_w - target_w) // 2
        start_y = (new_h - target_h) // 2

        return resized[start_y:start_y + target_h, start_x:start_x + target_w]
    else:  # stretch
        return cv2.resize(img, target_size, interpolation=cv2.INTER_AREA)