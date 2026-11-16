import os
import cv2
import pandas as pd
import numpy as np
from ultralytics import YOLO
from tqdm import tqdm

# 导入配置文件
from config import (
    POSE_MODEL_PATH, ELDERLY_WIDTH, ELDERLY_HEIGHT,
    MEDICAL_WIDTH, MEDICAL_HEIGHT, BASE_DIR,
    OUTPUT_FEATURE_DIR, MEDICAL_CLASS_MAP
)


def process_elderly_care(pose_model):
    print("\n[--- 处理旧数据集: ElderlyCareAI (CSV 跌倒标记) ---]")
    csv_path = os.path.join(BASE_DIR, "ElderlyCareAI", "data_tuple3.csv")
    dataset_dir = os.path.join(BASE_DIR, "ElderlyCareAI", "dataset")

    if not os.path.exists(csv_path):
        print("[-] 找不到 CSV，跳过 ElderlyCareAI 数据集。")
        return

    df = pd.read_csv(csv_path, skiprows=1, names=['chute', 'cam', 'start', 'end', 'label']).dropna()
    df['chute_str'] = df['chute'].astype(int).apply(lambda x: f"chute{x:02d}")
    df['cam_str'] = df['cam'].astype(int).apply(lambda x: f"cam{x}.avi")

    grouped = df.groupby(['chute_str', 'cam_str'])
    for (chute_dir, cam_file), group_data in tqdm(grouped, desc="提取 Elderly 特征"):
        video_path = os.path.join(dataset_dir, chute_dir, cam_file)
        if not os.path.exists(video_path): continue

        cap = cv2.VideoCapture(video_path)
        frame_idx = 1
        video_features = []

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break

            current_label = 0
            for _, row in group_data.iterrows():
                if row['start'] <= frame_idx <= row['end']:
                    current_label = int(row['label'])
                    break

            results = pose_model(frame, verbose=False)
            current_kpts = np.zeros(34)
            if results[0].keypoints is not None and len(results[0].keypoints.xy) > 0:
                kpts = results[0].keypoints.xy[0].cpu().numpy()
                kpts[:, 0] /= ELDERLY_WIDTH  # 使用 config 中的参数
                kpts[:, 1] /= ELDERLY_HEIGHT  # 使用 config 中的参数
                current_kpts = kpts.flatten()

            video_features.append(np.append(current_kpts, current_label))
            frame_idx += 1

        cap.release()
        if len(video_features) > 0:
            np.save(os.path.join(OUTPUT_FEATURE_DIR, f"Elderly_{chute_dir}_{cam_file.split('.')[0]}.npy"),
                    np.array(video_features))


def process_medical_action(pose_model):
    print("\n[--- 处理新数据集: MEDICALActionRecognition (多类异常) ---]")
    dataset_dir = os.path.join(BASE_DIR, "MEDICALActionRecognition")

    for class_name, label_id in MEDICAL_CLASS_MAP.items():
        class_dir = os.path.join(dataset_dir, class_name)
        if not os.path.exists(class_dir): continue

        video_files = [f for f in os.listdir(class_dir) if f.endswith('.avi')]
        for video_file in tqdm(video_files, desc=f"提取 MEDICAL [{class_name}]"):
            video_path = os.path.join(class_dir, video_file)
            cap = cv2.VideoCapture(video_path)
            video_features = []

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret: break

                results = pose_model(frame, verbose=False)
                current_kpts = np.zeros(34)
                if results[0].keypoints is not None and len(results[0].keypoints.xy) > 0:
                    kpts = results[0].keypoints.xy[0].cpu().numpy()
                    kpts[:, 0] /= MEDICAL_WIDTH  # 使用 config 中的参数
                    kpts[:, 1] /= MEDICAL_HEIGHT  # 使用 config 中的参数
                    current_kpts = kpts.flatten()

                video_features.append(np.append(current_kpts, label_id))

            cap.release()
            if len(video_features) > 0:
                np.save(os.path.join(OUTPUT_FEATURE_DIR, f"Medical_{class_name}_{video_file.split('.')[0]}.npy"),
                        np.array(video_features))


def main():
    os.makedirs(OUTPUT_FEATURE_DIR, exist_ok=True)

    print(f"[+] 正在加载配置指定的 YOLO 姿态模型: {POSE_MODEL_PATH} ...")
    pose_model = YOLO(POSE_MODEL_PATH)

    process_elderly_care(pose_model)
    process_medical_action(pose_model)
    print(f"\n[+] 特征提取完毕！保存在: {OUTPUT_FEATURE_DIR}")


if __name__ == "__main__":
    main()