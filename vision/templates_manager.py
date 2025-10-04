"""
模板库管理模块 (v5 - 最终标准版)
仅处理规范的英文文件名: {color}_{piece}_{position}_{index}.png
"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Template:
    """最终版的模板数据类"""
    name: str
    piece_type: str
    color: str
    position: str
    index: int
    image: np.ndarray
    shape: Tuple[int, int]
    filename: str

class TemplatesManager:
    """
    最终版模板库管理器
    - 高效、稳定，只处理标准英文文件名
    """

    def __init__(self, template_dir: str):
        self.template_dir = Path(template_dir)
        self.templates: Dict[str, Template] = {}
        self.load_templates()

    def _parse_filename(self, filename: str) -> Optional[Dict]:
        """
        Parses standard and special filenames.
        - Standard: color_piece_position_index.png
        - Special: template_xingying.png
        """
        # Handle special case for the camp template
        if filename == "template_xingying.png":
            return {
                "color": "neutral",  # Assign a neutral color
                "piece_type": "xingying", # Camp
                "position": "none",
                "index": 0,
            }

        # Original parsing logic for standard piece templates
        try:
            parts = filename.replace(".png", "").split('_')
            if len(parts) != 4:
                return None # Skip non-standard files

            color, piece_type, position, index_str = parts
            index = int(index_str)
            
            return {
                "color": color,
                "piece_type": piece_type,
                "position": position,
                "index": index,
            }
        except (ValueError, IndexError):
            return None

    def load_templates(self) -> None:
        """加载所有标准模板文件"""
        self.templates.clear()
        if not self.template_dir.is_dir():
            return

        for file_path in self.template_dir.glob("*.png"):
            parsed_info = self._parse_filename(file_path.name)
            if not parsed_info:
                logger.warning(f"文件名格式不规范，已跳过: {file_path.name}")
                continue

            try:
                # 使用 cv2.imdecode 从内存读取，以正确处理路径编码
                with open(file_path, "rb") as f:
                    file_bytes = np.fromfile(f, dtype=np.uint8)
                image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

                if image is None:
                    logger.warning(f"无法读取图片文件: {file_path.name}")
                    continue

                h, w = image.shape[:2]
                name = file_path.stem

                template = Template(
                    name=name,
                    piece_type=parsed_info['piece_type'],
                    color=parsed_info['color'],
                    position=parsed_info['position'],
                    index=parsed_info['index'],
                    image=image,
                    shape=(w, h),
                    filename=file_path.name
                )
                self.templates[name] = template

            except Exception as e:
                logger.error(f"加载模板失败 {file_path.name}: {e}")

        logger.info(f"模板加载完成。共加载 {len(self.templates)} 个模板。")

    def get_all_templates(self) -> List[Template]:
        return list(self.templates.values())

    def get_templates_by_color(self) -> Dict[str, List[Template]]:
        """
        Returns templates organized by color for multiprocessing
        """
        color_templates = {}
        for template in self.templates.values():
            color = template.color
            if color not in color_templates:
                color_templates[color] = []
            color_templates[color].append(template)
        return color_templates