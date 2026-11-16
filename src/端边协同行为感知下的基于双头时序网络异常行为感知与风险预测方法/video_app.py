# -*- coding: utf-8 -*-
import cv2
import torch
import torch.nn as nn
import numpy as np
from ultralytics import YOLO
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import threading
import os
import time


# ==========================================
# 1. 核心模型结构 (已移除语法错误)
# ==========================================
class DualHeadActionModel(nn.Module):
    def __init__(self, input_dim=68, hidden_dim=128, num_classes=11):
        super(DualHeadActionModel, self).__init__()
        # 双向LSTM [cite: 10, 12]
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers=2, batch_first=True, bidirectional=True)
        # 注意力层 [cite: 10, 12]
        self.attention_fc = nn.Linear(hidden_dim * 2, 1)

        # 分类头 [cite: 10, 11]
        self.classifier_head = nn.Sequential(
            nn.Linear(hidden_dim * 2, 64),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(64, num_classes)
        )
        # 预测头 [cite: 10, 11]
        self.prediction_head = nn.Sequential(
            nn.Linear(hidden_dim * 2, 64),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(64, num_classes)
        )

    def forward(self, x):
        # 修复点：已删除  错误标记
        lstm_out, _ = self.lstm(x)
        # 注意力权重计算
        attn_scores = self.attention_fc(lstm_out)
        attn_weights = torch.softmax(attn_scores, dim=1)
        context = torch.sum(lstm_out * attn_weights, dim=1)
        return self.classifier_head(context), self.prediction_head(context)


# ==========================================
# 2. 桌面应用程序
# ==========================================
class ActionSystemUI:
    def __init__(self, root):
        self.root = root
        self.root.title("动作识别与早期预警可视化系统 v2.0")
        self.root.geometry("1100x800")
        self.root.configure(bg="#1a1a1a")

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.pose_model = YOLO("yolov8n-pose.pt")
        self.action_model = None
        self.is_running = False

        # 类别映射 [cite: 26]
        self.target_names = ['Normal', 'Pre-fall', 'Fall', 'Back Pain', 'Blow Nose',
                             'Chest Pain', 'Headache', 'Nausea/Vomit', 'Neck Pain',
                             'Sneeze/Cough', 'Staggering']

        self.setup_gui()

    def setup_gui(self):
        self.display_label = tk.Label(self.root, bg="black")
        self.display_label.place(x=20, y=20, width=780, height=540)

        res_panel = tk.LabelFrame(self.root, text=" 实时监测 ", bg="#1a1a1a", fg="white", font=("微软雅黑", 12))
        res_panel.place(x=820, y=20, width=250, height=540)

        tk.Label(res_panel, text="当前动作状态:", bg="#1a1a1a", fg="#aaa").pack(pady=(50, 5))
        self.lbl_curr = tk.Label(res_panel, text="---", font=("Arial", 16, "bold"), bg="#1a1a1a", fg="#00FF00")
        self.lbl_curr.pack()

        tk.Label(res_panel, text="未来预警预测:", bg="#1a1a1a", fg="#aaa").pack(pady=(50, 5))
        self.lbl_pred = tk.Label(res_panel, text="---", font=("Arial", 16, "bold"), bg="#1a1a1a", fg="#FFC107")
        self.lbl_pred.pack()

        ctrl_box = tk.Frame(self.root, bg="#1a1a1a")
        ctrl_box.place(x=20, y=580, width=1050, height=180)

        tk.Button(ctrl_box, text="1. 加载模型权重 (.pth)", command=self.load_weights, bg="#333", fg="white",
                  width=25).grid(row=0, column=0, padx=10)
        tk.Button(ctrl_box, text="2. 选择视频启动分析", command=self.start_stream, bg="#0056b3", fg="white",
                  width=25).grid(row=0, column=1, padx=10)
        tk.Button(ctrl_box, text="停止", command=self.stop, bg="#8b0000", fg="white", width=25).grid(row=0, column=2,
                                                                                                     padx=10)

        self.txt_log = tk.Text(ctrl_box, height=5, bg="black", fg="#00FF00", font=("Consolas", 10))
        self.txt_log.grid(row=1, column=0, columnspan=3, pady=15, sticky="we")

    def load_weights(self):
        path = filedialog.askopenfilename(filetypes=[("Weights", "*.pth")])
        if path:
            try:
                # 重新初始化模型 [cite: 10]
                self.action_model = DualHeadActionModel(input_dim=68, hidden_dim=128, num_classes=11).to(self.device)
                self.action_model.load_state_dict(torch.load(path, map_location=self.device))
                self.action_model.eval()
                self.log(f"模型权重已载入: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("结构错误", f"无法匹配权重！请检查代码结构。\n{e}")

    def log(self, text):
        self.txt_log.insert(tk.END, f">> {text}\n")
        self.txt_log.see(tk.END)

    def start_stream(self):
        if not self.action_model:
            messagebox.showwarning("提示", "请先加载模型权重！")
            return
        video_path = filedialog.askopenfilename()
        if video_path:
            self.is_running = True
            threading.Thread(target=self.video_worker, args=(video_path,), daemon=True).start()

    def stop(self):
        self.is_running = False

    def video_worker(self, path):
        cap = cv2.VideoCapture(path)
        # 获取视频原始FPS，用于控制播放速度
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        if video_fps <= 0: video_fps = 30
        frame_time = 1.0 / video_fps

        window_size = 30
        buffer = []

        self.log(f"开始处理视频: {os.path.basename(path)}")

        while self.is_running:
            start_time = time.time()
            ret, frame = cap.read()
            if not ret: break

            # 1. YOLO 提取关键点
            results = self.pose_model(frame, verbose=False)
            canvas = results[0].plot()

            # 2. 构造 68 维特征向量 [cite: 5, 6]
            kpt_vector = np.zeros(68)
            if results[0].keypoints is not None and len(results[0].keypoints.data) > 0:
                kpts = results[0].keypoints.data[0].cpu().numpy()
                flat_coords = kpts[:, :2].flatten()  # 17*2=34
                kpt_vector[:34] = flat_coords
                kpt_vector[34:] = flat_coords  # 填充速度位

            buffer.append(kpt_vector)
            if len(buffer) > window_size:
                buffer.pop(0)

            # 3. 动作推理
            if len(buffer) == window_size:
                # 修复点：先转为 numpy 数组再转 tensor，解决速度慢的警告
                np_buffer = np.array([buffer], dtype=np.float32)
                input_x = torch.from_numpy(np_buffer).to(self.device)

                with torch.no_grad():
                    out_cls, out_pred = self.action_model(input_x)
                    c_idx = torch.argmax(out_cls, dim=1).item()
                    p_idx = torch.argmax(out_pred, dim=1).item()

                    # 更新UI标签
                    self.lbl_curr.config(text=self.target_names[c_idx])
                    self.lbl_pred.config(text=self.target_names[p_idx])

            # 4. 刷新 UI 画面
            img = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
            imgtk = ImageTk.PhotoImage(image=img.resize((780, 540)))
            self.display_label.imgtk = imgtk
            self.display_label.configure(image=imgtk)

            # 控制 FPS，防止视频跑得太快或假死
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_time - elapsed)
            time.sleep(sleep_time)

        cap.release()
        self.log("视频流已完成。")
        self.is_running = False


if __name__ == "__main__":
    root = tk.Tk()
    app = ActionSystemUI(root)
    root.mainloop()