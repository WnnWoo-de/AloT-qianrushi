"""
机器人性能参数配置
============================
每台机器人的独立性能参数。数量须与 config/global_params.py 中的 NUM_ROBOTS 一致。

capabilities 字段说明（与任务类型 TASK_TYPES 对应）：
  "inspection" : 巡检任务（默认，所有机器人都应具备）
  "emergency"  : 紧急响应任务
  "service"    : 服务类任务（引导、通知）
  "delivery"   : 配送类任务
"""

ROBOT_PROFILES = [
    {
        "id":           0,
        "name":         "Robot-A",
        "battery":      100.0,
        "speed":        3,
        "detect_radius": 6,
        "max_load":     3,
        "capabilities": ["inspection", "emergency"],
        "start_pos":    [4, 4],
        "color":        "#E74C3C",
    },
    {
        "id":           1,
        "name":         "Robot-B",
        "battery":      100.0,
        "speed":        4,
        "detect_radius": 4,
        "max_load":     2,
        "capabilities": ["inspection", "delivery", "emergency"],
        "start_pos":    [4, 35],
        "color":        "#3498DB",
    },
    {
        "id":           2,
        "name":         "Robot-C",
        "battery":      100.0,
        "speed":        2,
        "detect_radius": 8,
        "max_load":     4,
        "capabilities": ["inspection", "service", "delivery"],
        "start_pos":    [35, 4],
        "color":        "#2ECC71",
    },
    {
        "id":           3,
        "name":         "Robot-D",
        "battery":      100.0,
        "speed":        3,
        "detect_radius": 5,
        "max_load":     3,
        "capabilities": ["inspection", "emergency", "service"],
        "start_pos":    [35, 35],
        "color":        "#F39C12",
    },
]
