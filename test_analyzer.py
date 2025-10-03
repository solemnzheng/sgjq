import cv2
from game_analyzer import GameAnalyzer
import os

# --- 配置 ---
TEMPLATES_PATH = "vision/new_templates"
IMAGE_1_PATH = "1.png"
IMAGE_2_PATH = "2.png"

def run_test():
    """执行完整的分析测试并打印报告"""
    
    # 检查文件是否存在
    if not os.path.exists(IMAGE_1_PATH) or not os.path.exists(IMAGE_2_PATH):
        print(f"错误: 确保 {IMAGE_1_PATH} 和 {IMAGE_2_PATH} 文件存在于根目录下。")
        return

    print("="*30)
    print("--- 初始化分析器 ---")
    try:
        analyzer = GameAnalyzer(TEMPLATES_PATH)
        print(f"分析器初始化成功，加载了 {len(analyzer.templates_manager.get_all_templates())} 个模板。")
    except Exception as e:
        print(f"初始化失败: {e}")
        return
    
    print("="*30)
    print(f"--- 正在分析 {IMAGE_1_PATH} ---")
    image1 = cv2.imread(IMAGE_1_PATH)
    report1 = analyzer.analyze_screenshot(image1)
    print(report1)
    
    print("\n" + "="*30)
    print(f"--- 正在分析 {IMAGE_2_PATH} ---")
    image2 = cv2.imread(IMAGE_2_PATH)
    report2 = analyzer.analyze_screenshot(image2)
    print(report2)
    print("\n" + "="*30)

if __name__ == "__main__":
    run_test()
