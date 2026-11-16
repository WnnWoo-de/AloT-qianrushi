import os

# ==========================================
# 1. 模型配置 
POSE_MODEL_PATH = "yolov8n-pose.pt"

# ==========================================
# 2. 数据集分辨率配置 (用于坐标归一化)
# ==========================================
# 旧数据集 ElderlyCareAI 的分辨率
ELDERLY_WIDTH = 720.0
ELDERLY_HEIGHT = 480.0

# 新数据集 MEDICALActionRecognition 的分辨率
MEDICAL_WIDTH = 1920.0
MEDICAL_HEIGHT = 1080.0

# ==========================================
# 3. 路径配置 (自动获取绝对路径)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FEATURE_DIR = os.path.join(BASE_DIR, "processed_features")

# ==========================================
# 4. 统一标签字典 
# ==========================================
MEDICAL_CLASS_MAP = {
    'falling_down': 2,
    'back_pain': 3,
    'blow_nose': 4,
    'chest_pain': 5,
    'headache': 6,
    'nausea_or_vomiting': 7,
    'neck_pain': 8,
    'sneeze_or_cough': 9,
    'staggering': 10
}