"""
PaddleOCR 封装模块
"""
from typing import Optional, Tuple
import numpy as np
import cv2
from paddleocr import PaddleOCR


class OCREngine:
    def __init__(self, lang: str = "ch", use_gpu: bool = False,
                 det_limit_side_len: int = 960, rec_batch_size: int = 8):
        """
        初始化 PaddleOCR 引擎

        Args:
            lang: 语言设置，默认中文 'ch'
            use_gpu: 是否使用 GPU
            det_limit_side_len: 检测边长限制
            rec_batch_size: 识别批处理大小
        """
        self.lang = lang
        self.use_gpu = use_gpu
        self.det_limit_side_len = det_limit_side_len
        self.rec_batch_size = rec_batch_size

        # 初始化 PaddleOCR
        try:
            self.ocr = PaddleOCR(
                use_angle_cls=True,
                lang=lang,
                det=True,
                det_limit_side_len=det_limit_side_len,
                rec_batch_num=rec_batch_size
            )
        except Exception as e:
            print(f"⚠️ PaddleOCR 初始化失败: {e}")
            self.ocr = None

    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        图像预处理：放大、二值化、去噪

        Args:
            image: 输入图像

        Returns:
            预处理后的图像
        """
        # 放大图像以提高识别率
        if image.shape[0] < 100 or image.shape[1] < 100:
            scale = max(2, min(4, 100 // min(image.shape[:2])))
            image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        # 转换为灰度图像
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # 自适应阈值处理
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        # 形态学去噪
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        denoised = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        denoised = cv2.morphologyEx(denoised, cv2.MORPH_OPEN, kernel)

        return denoised

    def read_text(self, image: np.ndarray,
                  roi: Optional[Tuple[int, int, int, int]] = None) -> Tuple[str, float]:
        """
        从图像中识别文字

        Args:
            image: 输入图像
            roi: 感兴趣区域 (x, y, w, h)，可选

        Returns:
            (text, confidence) 识别结果和置信度，无法识别时返回 ("", 0.0)
        """
        if self.ocr is None:
            return "", 0.0

        try:
            # 提取 ROI
            if roi is not None:
                x, y, w, h = roi
                roi_image = image[y:y+h, x:x+w]
                if roi_image.size == 0:
                    return "", 0.0
            else:
                roi_image = image

            # 预处理
            processed = self._preprocess_image(roi_image)

            # 执行 OCR
            result = self.ocr.ocr(processed, cls=True)

            if not result or not result[0]:
                return "", 0.0

            # 提取最佳结果
            best_text = ""
            best_confidence = 0.0

            for line in result[0]:
                if line and len(line) > 1:
                    text = line[1][0].strip()
                    confidence = line[1][1]

                    if confidence > best_confidence and text:
                        best_text = text
                        best_confidence = confidence

            return best_text, best_confidence

        except Exception as e:
            print(f"⚠️ OCR 识别失败: {e}")
            return "", 0.0


def confirm_label_by_ocr(cell_img: np.ndarray, rough_label: str,
                         ocr: OCREngine) -> Tuple[str, float]:
    """
    结合模板初判与 OCR 文本，返回最终类别与置信度

    Args:
        cell_img: 棋子图像
        rough_label: 模板匹配初判结果
        ocr: OCR 引擎实例

    Returns:
        (final_label, confidence) 最终标签和置信度
    """
    # 执行 OCR 识别
    ocr_text, ocr_confidence = ocr.read_text(cell_img)

    if not ocr_text or ocr_confidence < 0.5:
        # OCR 失败，返回模板初判结果
        return rough_label, 0.3

    # 军棋棋子名称映射
    piece_mapping = {
        "司令": "commander",
        "军长": "army_commander",
        "师长": "division_commander",
        "旅长": "brigade_commander",
        "团长": "regiment_commander",
        "营长": "battalion_commander",
        "连长": "company_commander",
        "排长": "platoon_commander",
        "工兵": "engineer",
        "地雷": "mine",
        "炸弹": "bomb",
        "军旗": "flag"
    }

    # 检查 OCR 识别结果
    for chinese_name, piece_type in piece_mapping.items():
        if chinese_name in ocr_text:
            # OCR 确认成功，返回高置信度
            return piece_type, max(ocr_confidence, 0.7)

    # OCR 未识别到已知棋子，但识别到文字
    if len(ocr_text) >= 2:
        return rough_label, min(ocr_confidence, 0.6)

    # 完全无法确认
    return rough_label, 0.2