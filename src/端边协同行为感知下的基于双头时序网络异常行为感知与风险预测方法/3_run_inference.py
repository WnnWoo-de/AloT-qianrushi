import cv2
import torch
import torch.nn as nn
import numpy as np
from ultralytics import YOLO
import os



class DualHeadActionModel(nn.Module):

    def __init__(self, input_dim=68, hidden_dim=128, num_classes_cls=3, num_classes_pred=4):
        super(DualHeadActionModel, self).__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers=2, batch_first=True, bidirectional=True)

        self.attention_fc = nn.Linear(hidden_dim * 2, 1)

        self.classifier_head = nn.Sequential(
            nn.Linear(hidden_dim * 2, 32),
            nn.ReLU(),
            nn.Linear(32, num_classes_cls)
        )
        self.prediction_head = nn.Sequential(
            nn.Linear(hidden_dim * 2, 32),
            nn.ReLU(),
            nn.Linear(32, num_classes_pred)
        )

    def forward(self, x):
        lstm_out, _ = self.lstm(x)


        attn_weights = torch.tanh(self.attention_fc(lstm_out))
        attn_weights = torch.softmax(attn_weights, dim=1)

        context = torch.sum(attn_weights * lstm_out, dim=1)

        return self.classifier_head(context), self.prediction_head(context)


def main():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    run_version = "v6"
    model_path = os.path.join(BASE_DIR, "runs", run_version, "model.pth")

    if not os.path.exists(model_path):
        print(f"[-] 找不到模型权重 {model_path}！")
        return

    print("[+] 正在加载 YOLOv8 前端提取器 ...")
    pose_model = YOLO("yolov8n-pose.pt")

    print("[+] 正在加载 匹配权重的双头 LSTM (带 Attention) ...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    action_model = DualHeadActionModel(input_dim=68, hidden_dim=128).to(device)
    action_model.load_state_dict(torch.load(model_path, map_location=device))
    action_model.eval()

    video_source = os.path.join(BASE_DIR, "dataset", "chute01", "cam1.avi")
    if not os.path.exists(video_source):
        print(f"[-] 找不到视频 {video_source}")
        return

    cap = cv2.VideoCapture(video_source)
    CLS_DICT = {0: "Normal", 1: "FALL DOWN!", 2: "ABNORMAL LYING"}
    PRED_DICT = {0: "Stable", 1: "Fall Expected", 2: "Lying Expected", 3: "WARNING: Pre-fall Stage"}

    window_size = 30
    keypoint_buffer = []

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        results = pose_model(frame, verbose=False)
        annotated_frame = results[0].plot()
        frame_h, frame_w = frame.shape[:2]

        current_kpts = np.zeros(68)
        pelvis_y = 0

        if results[0].keypoints is not None and len(results[0].keypoints.data) > 0:
  
            kpts_data = results[0].keypoints.data[0].cpu().numpy()

            if len(kpts_data) >= 13:
                pelvis_y = (kpts_data[11][1] + kpts_data[12][1]) / 2.0 / frame_h
            current_kpts[:kpts_data.size] = kpts_data.flatten()[:68]

        keypoint_buffer.append(current_kpts)
        if len(keypoint_buffer) > window_size:
            keypoint_buffer.pop(0)

        if len(keypoint_buffer) == window_size:
            input_tensor = torch.tensor([keypoint_buffer], dtype=torch.float32).to(device)
            with torch.no_grad():
                out_cls, out_pred = action_model(input_tensor)
                cls_idx = torch.argmax(out_cls, dim=1).item()
                pred_idx = torch.argmax(out_pred, dim=1).item()

                if cls_idx == 1 and pelvis_y > 0.7:
                    cls_idx = 2

                cv2.rectangle(annotated_frame, (10, frame_h - 130), (550, frame_h - 10), (0, 0, 0), -1)
                cv2.putText(annotated_frame, f"Status: {CLS_DICT.get(cls_idx)}", (20, frame_h - 85),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0) if cls_idx == 0 else (0, 0, 255), 2)
                cv2.putText(annotated_frame, f"Predict: {PRED_DICT.get(pred_idx)}", (20, frame_h - 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        cv2.imshow("Elderly Care AI", annotated_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()