"""
模板匹配与检测流程模块
实现棋子检测、模板匹配和OCR二次确认功能
"""
from typing import List, Dict, Any, Tuple, Optional
import cv2
import numpy as np
import os
from pathlib import Path

from src.vision.utils import (
    preprocess_image, enhance_contrast, remove_noise,
    adaptive_threshold, morphological_operations, non_max_suppression,
    extract_cell_image, resize_with_aspect_ratio
)
from src.vision.templates_manager import TemplatesManager
from src.vision.ocr import confirm_label_by_ocr, OCREngine
from src.board.coordinate_manager import CoordinateManager

Detection = Dict[str, Any]  # {"position_key":str,"type":str|"unknown","color":str|None,
                           #  "confidence":float,"bbox":[x,y,w,h]}


def detect_pieces(board_img: np.ndarray, config: dict,
                templates_manager: Optional[TemplatesManager] = None,
                ocr_engine: Optional[OCREngine] = None,
                coord_manager: Optional[CoordinateManager] = None) -> List[Detection]:
    """
    检测棋盘上的棋子

    Args:
        board_img: 棋盘区域图像 (BGR格式)
        config: 配置字典
        templates_manager: 模板管理器实例
        ocr_engine: OCR引擎实例
        coord_manager: 坐标管理器实例

    Returns:
        检测到的棋子列表
    """
    if templates_manager is None:
        templates_manager = TemplatesManager(config.get('template_dir', ''))
    
    if coord_manager is None:
        map_path = Path(__file__).parent.parent / "board" / "new_coordinate_map.json"
        coord_manager = CoordinateManager(map_path)

    # 获取配置参数
    match_threshold = config.get('match_threshold', 0.78)
    nms_iou = config.get('nms_iou', 0.35)
    detect_stride = config.get('detect_stride', 1)
    ocr_enabled = config.get('ocr', {}).get('enable', True)

    # 预处理图像
    gray_img = preprocess_image(board_img, method='grayscale', normalize=True)
    enhanced_img = enhance_contrast(gray_img, method='clahe')

    # 获取所有模板
    templates = templates_manager.get_all_templates()
    if not templates:
        return []

    # 模板匹配
    all_detections = []

    for template in templates:
        template_img = template.image
        color = template.color
        piece_type = template.piece

        # 调整模板大小（如果需要）
        if template_img.shape[0] > enhanced_img.shape[0] or \
           template_img.shape[1] > enhanced_img.shape[1]:
            continue

        # 执行模板匹配
        matches = _template_match(enhanced_img, template_img,
                               match_threshold, detect_stride)

        for match in matches:
            x, y, w, h, score = match
            detection = {
                'position_key': None,  # 待映射
                'type': piece_type,
                'color': color,
                'confidence': score,
                'bbox': [x, y, w, h],
                'template_piece': piece_type,
                'template_color': color
            }
            all_detections.append(detection)

    # 非极大值抑制
    if all_detections:
        boxes = [(d['bbox'][0], d['bbox'][1],
                 d['bbox'][0] + d['bbox'][2],
                 d['bbox'][1] + d['bbox'][3])
                for d in all_detections]
        scores = [d['confidence'] for d in all_detections]

        keep_indices = non_max_suppression(boxes, scores, nms_iou)
        filtered_detections = [all_detections[i] for i in keep_indices]
    else:
        filtered_detections = []

    # 映射到逻辑坐标
    mapped_detections = []
    
    for detection in filtered_detections:
        # 计算检测框中心点
        x, y, w, h = detection['bbox']
        center_x = x + w // 2
        center_y = y + h // 2

        # 映射到逻辑坐标
        position_key = coord_manager.find_nearest_position(center_x, center_y)

        # 检查是否在有效范围内
        if position_key:
            detection['position_key'] = position_key

            # OCR二次确认（如果需要）
            if ocr_enabled and ocr_engine:
                cell_img = extract_cell_image(board_img, detection['bbox'])
                final_type, final_confidence = confirm_label_by_ocr(
                    cell_img, detection['type'], ocr_engine)

                if final_type != detection['type']:
                    detection['type'] = final_type
                    detection['confidence'] = final_confidence
                    detection['ocr_confirmed'] = True
                else:
                    detection['ocr_confirmed'] = False

            mapped_detections.append(detection)

    return mapped_detections


def _template_match(img: np.ndarray, template: np.ndarray,
                  threshold: float, stride: int = 1) -> List[Tuple[int, int, int, int, float]]:
    """
    执行模板匹配

    Args:
        img: 输入图像（灰度）
        template: 模板图像（灰度）
        threshold: 匹配阈值
        stride: 滑动步长

    Returns:
        匹配结果列表 [(x, y, w, h, score), ...]
    """
    h, w = template.shape[:2]
    img_h, img_w = img.shape[:2]

    if h > img_h or w > img_w:
        return []

    # 执行模板匹配
    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)

    # 找到所有超过阈值的匹配
    locations = np.where(result >= threshold)
    matches = []

    for pt in zip(*locations[::-1]):  # 切换为 (x, y) 顺序
        score = result[pt[1], pt[0]]
        matches.append((pt[0], pt[1], w, h, float(score)))

    return matches


def _parse_template_name(template_name: str) -> Tuple[Optional[str], str]:
    """
    解析模板名称，提取颜色和棋子类型

    Args:
        template_name: 模板文件名（如 "red_commander.png"）

    Returns:
        (color, piece_type)
    """
    # 移除扩展名
    name_without_ext = os.path.splitext(template_name)[0]

    # 按下划线分割
    parts = name_without_ext.split('_')

    if len(parts) >= 2:
        color = parts[0]
        piece_type = '_'.join(parts[1:])  # 处理可能包含下划线的棋子类型
    else:
        color = None
        piece_type = parts[0]

    return color, piece_type


def detect_board_grid(board_img: np.ndarray, config: dict) -> Optional[Tuple[int, int, int, int]]:
    """
    自动检测棋盘网格

    Args:
        board_img: 棋盘图像
        config: 配置字典

    Returns:
        棋盘区域 (x, y, w, h) 或 None
    """
    # 预处理
    gray = preprocess_image(board_img, method='grayscale', normalize=True)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # 霍夫变换检测直线
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100,
                           minLineLength=100, maxLineGap=10)

    if lines is None:
        return None

    # 提取水平和垂直直线
    horizontal_lines = []
    vertical_lines = []

    for line in lines:
        x1, y1, x2, y2 = line[0]
        if abs(y2 - y1) < abs(x2 - x1):  # 水平线
            horizontal_lines.append((x1, y1, x2, y2))
        else:  # 垂直线
            vertical_lines.append((x1, y1, x2, y2))

    # 计算棋盘边界
    if len(horizontal_lines) >= 2 and len(vertical_lines) >= 2:
        # 获取边界坐标
        x_coords = [line[0] for line in vertical_lines] + [line[2] for line in vertical_lines]
        y_coords = [line[1] for line in horizontal_lines] + [line[3] for line in horizontal_lines]

        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        return (x_min, y_min, x_max - x_min, y_max - y_min)

    return None


def validate_detection(detection: Detection, config: dict) -> bool:
    """
    验证检测结果的有效性

    Args:
        detection: 检测结果
        config: 配置字典

    Returns:
        是否有效
    """
    # 检查置信度
    min_confidence = config.get('match_threshold', 0.78)
    if detection['confidence'] < min_confidence:
        return False

    # 检查棋子类型
    valid_piece_types = [
        'commander', 'general', 'major', 'colonel', 'captain',
        'lieutenant', 'sergeant', 'miner', 'scout', 'bomb', 'flag', 'unknown'
    ]

    if detection['type'] not in valid_piece_types:
        return False

    # 检查颜色
    if detection['color'] not in ['red', 'blue', None]:
        return False

    # 检查坐标范围
    rows = config.get('rows', 12)
    cols = config.get('cols', 5)

    if not (0 <= detection['row'] < rows and 0 <= detection['col'] < cols):
        return False

    return True


def filter_detections_by_grid(detections: List[Detection],
                           rows: int, cols: int) -> List[Detection]:
    """
    按网格过滤检测结果（每个格子只保留最高置信度的检测结果）

    Args:
        detections: 检测结果列表
        rows: 行数
        cols: 列数

    Returns:
        过滤后的检测结果
    """
    # 创建网格字典
    grid_dict = {}

    for detection in detections:
        key = (detection['row'], detection['col'])

        if key not in grid_dict or \
           detection['confidence'] > grid_dict[key]['confidence']:
            grid_dict[key] = detection

    return list(grid_dict.values())


def draw_detections(img: np.ndarray, detections: List[Detection],
                   config: dict) -> np.ndarray:
    """
    在图像上绘制检测结果

    Args:
        img: 输入图像
        detections: 检测结果
        config: 配置字典

    Returns:
        绘制了检测结果的图像
    """
    result = img.copy()

    for detection in detections:
        x, y, w, h = detection['bbox']
        confidence = detection['confidence']
        piece_type = detection['type']
        color = detection['color']

        # 绘制边界框
        color_bgr = (0, 255, 0) if confidence > 0.8 else (0, 255, 255)
        cv2.rectangle(result, (x, y), (x + w, y + h), color_bgr, 2)

        # 绘制标签
        label = f"{color or 'unknown'}_{piece_type}_{confidence:.2f}"
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        cv2.rectangle(result, (x, y - label_size[1] - 10),
                    (x + label_size[0], y), color_bgr, -1)
        cv2.putText(result, label, (x, y - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

    return result