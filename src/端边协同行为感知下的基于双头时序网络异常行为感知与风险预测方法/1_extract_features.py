import os
import cv2
import pandas as pd
import numpy as np
from ultralytics import YOLO
from tqdm import tqdm


def main():
    # 自动获取当前 Python 脚本所在的绝对物理路径 (ElderlyCareAI目录)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # 完美匹配你的文件夹结构
    csv_path = os.path.join(BASE_DIR, "data_tuple3.csv")
    dataset_dir = os.path.join(BASE_DIR, "dataset")
    output_dir = os.path.join(BASE_DIR, "processed_features")

    # 如果输出文件夹不存在，自动创建
    os.makedirs(output_dir, exist_ok=True)

    print(f"[*] 正在尝试读取的 CSV 绝对路径: {csv_path}")
    print(f"[*] 正在尝试读取的 视频根目录 绝对路径: {dataset_dir}")

    # 检查 CSV 是否真的存在，防止后续报错
    if not os.path.exists(csv_path):
        print(f"\n[-] 致命错误: 找不到 CSV 文件！请确保你把 data_tuple3.csv 放在了: {csv_path}")
        return

    print("[+] 正在加载 YOLOv8-Pose 模型...")
    pose_model = YOLO("yolov8n-pose.pt")

    print("[+] 正在读取标注文件 data_tuple3.csv ...")

    # 【修复处】：跳过第一行表头，并剔除由于Excel保存带来的末尾空行
    df = pd.read_csv(csv_path, skiprows=1, names=['chute', 'cam', 'start', 'end', 'label'])
    df = df.dropna()

    # 将 chute 转换为字符串，不足两位前面补0 (例如 1.0 -> '01')
    df['chute_str'] = df['chute'].astype(int).apply(lambda x: f"chute{x:02d}")
    df['cam_str'] = df['cam'].astype(int).apply(lambda x: f"cam{x}.avi")

    # 按视频(场景+摄像头)进行分组处理
    grouped = df.groupby(['chute_str', 'cam_str'])

    for (chute_dir, cam_file), group_data in tqdm(grouped, desc="处理视频序列"):
        video_path = os.path.join(dataset_dir, chute_dir, cam_file)

        if not os.path.exists(video_path):
            continue  # 如果视频不存在就静默跳过，继续找下一个

        cap = cv2.VideoCapture(video_path)
        frame_idx = 1
        video_features = []

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break

            # --- 1. 判断当前帧的标签 ---
            current_label = 0  # 默认为0 (正常)
            for _, row in group_data.iterrows():
                if row['start'] <= frame_idx <= row['end']:
                    current_label = int(row['label'])
                    break

            # --- 2. YOLOv8 提取骨架 ---
            results = pose_model(frame, verbose=False)
            current_kpts = np.zeros(34)  # 17个点(x,y)

            if results[0].keypoints is not None and len(results[0].keypoints.xy) > 0:
                kpts = results[0].keypoints.xy[0].cpu().numpy()
                kpts[:, 0] = kpts[:, 0] / 720.0
                kpts[:, 1] = kpts[:, 1] / 480.0
                current_kpts = kpts.flatten()

            # 将特征(34维)和标签(1维)拼接，存入列表: shape (35,)
            feature_with_label = np.append(current_kpts, current_label)
            video_features.append(feature_with_label)

            frame_idx += 1

        cap.release()

        # 只有当成功提取到特征时才保存
        if len(video_features) > 0:
            save_name = f"{chute_dir}_{cam_file.split('.')[0]}.npy"
            np.save(os.path.join(output_dir, save_name), np.array(video_features))

    print(f"\n[+] 特征提取完毕！所有数据已转化为矩阵保存在 {output_dir} 目录下。")


if __name__ == "__main__":
    main()