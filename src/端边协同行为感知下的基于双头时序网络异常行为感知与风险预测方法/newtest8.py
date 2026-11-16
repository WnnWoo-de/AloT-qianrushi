import os
import logging
import random
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix
import pandas as pd
from matplotlib import rcParams


# Windows 
plt.rcParams['font.sans-serif'] = ['SimHei']  # 黑体



plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# ==========================================
# 核心配置
# ==========================================
TARGET_NAMES = [
    '正常',
    '跌倒前兆',
    '跌倒',
    '背痛',
    '擤鼻涕',
    '头痛',
    '恶心/呕吐',
    '颈部疼痛',
    '打喷嚏/咳嗽',
    '步态不稳'
]

NUM_CLASSES = len(TARGET_NAMES)  # 10类
EXCLUDE_LABEL = 5


def remap_label(label):

    label = int(label)

    if label == EXCLUDE_LABEL:
        return -1

    if label > EXCLUDE_LABEL:
        return label - 1

    return label


# ==========================================
# 工具函数
# ==========================================
def get_next_version_path(base_path):

    if not os.path.exists(base_path):
        os.makedirs(base_path)

    version = 1

    while True:
        version_path = os.path.join(base_path, f"exp{version}")

        if not os.path.exists(version_path):
            os.makedirs(version_path)
            return version_path

        version += 1


def setup_logger(log_file_path):

    logger = logging.getLogger("TrainLogger")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    file_handler = logging.FileHandler(
        log_file_path,
        mode='w',
        encoding='utf-8'
    )

    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


# ==========================================
# 中文混淆矩阵
# ==========================================
def plot_confusion_matrix(y_true,
                          y_pred,
                          labels,
                          title,
                          save_path):

    cm = confusion_matrix(
        y_true,
        y_pred,
        labels=range(len(labels)),
        normalize='true'
    )

    plt.figure(figsize=(10, 8))

    sns.heatmap(
        cm,
        annot=True,
        fmt='.2f',
        cmap='Blues',
        xticklabels=labels,
        yticklabels=labels,
        linewidths=.5,
        cbar_kws={"shrink": .75}
    )

    plt.title(title, fontsize=16, fontweight='bold', pad=20)
    plt.ylabel('真实标签', fontsize=12, fontweight='bold')
    plt.xlabel('预测标签', fontsize=12, fontweight='bold')

    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)

    plt.tight_layout()

    plt.savefig(
        save_path,
        dpi=300,
        bbox_inches='tight'
    )

    plt.close()


# ==========================================
# 中文 Top5 准确率柱状图
# ==========================================
def plot_top5_accuracy(report_dict,
                       target_names,
                       save_path):

    accuracies = []

    for name in target_names:
        accuracies.append(report_dict[name]['recall'])

    # 排序取前5
    top5_idx = np.argsort(accuracies)[-5:][::-1]

    top5_names = [target_names[i] for i in top5_idx]
    top5_values = [accuracies[i] for i in top5_idx]

    plt.figure(figsize=(10, 6))

    colors = sns.color_palette("viridis", 5)

    bars = plt.bar(
        top5_names,
        top5_values,
        color=colors
    )

    plt.ylim(0, 1.1)

    plt.title(
        '准确率最高的前五类别',
        fontsize=14,
        fontweight='bold'
    )

    plt.ylabel(
        '准确率',
        fontsize=12
    )

    for bar in bars:

        height = bar.get_height()

        plt.text(
            bar.get_x() + bar.get_width() / 2.,
            height + 0.02,
            f'{height:.2f}',
            ha='center',
            va='bottom',
            fontweight='bold'
        )

    plt.tight_layout()

    plt.savefig(
        save_path,
        dpi=300
    )

    plt.close()


# ==========================================
# 损失函数
# ==========================================
class FocalLoss(nn.Module):

    def __init__(self,
                 weight=None,
                 gamma=2.0,
                 reduction='mean'):

        super(FocalLoss, self).__init__()

        self.weight = weight
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, inputs, targets):

        ce_loss = F.cross_entropy(
            inputs,
            targets,
            weight=self.weight,
            reduction='none'
        )

        pt = torch.exp(-ce_loss)

        focal_loss = ((1 - pt) ** self.gamma) * ce_loss

        if self.reduction == 'mean':
            return focal_loss.mean()

        elif self.reduction == 'sum':
            return focal_loss.sum()

        else:
            return focal_loss


# ==========================================
# Dataset
# ==========================================
class UnifiedDualHeadDataset(Dataset):

    def __init__(self,
                 file_paths,
                 window_size=30,
                 stride=15):

        self.sequences = []
        self.labels_cls = []
        self.labels_pred = []

        for file in file_paths:

            data = np.load(file)

            features = data[:, :34]
            labels = data[:, 34]

            for i in range(
                    0,
                    len(data) - window_size,
                    stride):

                seq_x = features[i: i + window_size]

                velocity = np.diff(seq_x, axis=0)

                velocity = np.vstack([
                    velocity,
                    velocity[-1]
                ])

                seq_x = np.concatenate(
                    [seq_x, velocity],
                    axis=1
                )

                window_labels = labels[i: i + window_size]

                anomalies = [
                    int(l)
                    for l in window_labels
                    if l > 0
                ]

                if len(anomalies) >= 5:
                    raw_label = max(
                        set(anomalies),
                        key=anomalies.count
                    )
                else:
                    raw_label = 0

                curr_label = remap_label(raw_label)

                if curr_label == -1:
                    continue

                pred_label = curr_label

                if raw_label == 0:

                    future_15 = labels[
                        i + window_size:
                        min(i + window_size + 15, len(labels))
                    ]

                    future_anomalies = [
                        int(L)
                        for L in future_15
                        if L >= 2
                    ]

                    if len(future_anomalies) > 0:

                        raw_target = future_anomalies[-1]

                        mapped_target = remap_label(raw_target)

                        if mapped_target == -1:
                            continue

                        pred_label = (
                            1 if raw_target == 2
                            else mapped_target
                        )

                self.sequences.append(seq_x)
                self.labels_cls.append(curr_label)
                self.labels_pred.append(pred_label)

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):

        return (
            torch.tensor(
                self.sequences[idx],
                dtype=torch.float32
            ),

            torch.tensor(
                self.labels_cls[idx],
                dtype=torch.long
            ),

            torch.tensor(
                self.labels_pred[idx],
                dtype=torch.long
            )
        )


# ==========================================
# 模型
# ==========================================
class DualHeadActionModel(nn.Module):

    def __init__(self,
                 input_dim=68,
                 hidden_dim=128,
                 num_classes=10):

        super(DualHeadActionModel, self).__init__()

        self.lstm = nn.LSTM(
            input_dim,
            hidden_dim,
            num_layers=2,
            batch_first=True,
            bidirectional=True
        )

        self.attention_fc = nn.Linear(
            hidden_dim * 2,
            1
        )

        self.classifier_head = nn.Sequential(
            nn.Linear(hidden_dim * 2, 64),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(64, num_classes)
        )

        self.prediction_head = nn.Sequential(
            nn.Linear(hidden_dim * 2, 64),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(64, num_classes)
        )

    def forward(self, x):

        lstm_out, _ = self.lstm(x)

        attn_scores = self.attention_fc(lstm_out)

        attn_weights = torch.softmax(
            attn_scores,
            dim=1
        )

        context = torch.sum(
            lstm_out * attn_weights,
            dim=1
        )

        return (
            self.classifier_head(context),
            self.prediction_head(context)
        )


def compute_accuracy(pred, label):

    _, predicted = torch.max(pred, 1)

    return (
        predicted == label
    ).sum().item() / label.size(0)


def get_class_weights(labels_list,
                      num_classes=10,
                      smooth_factor=0.2):

    counts = np.bincount(
        labels_list,
        minlength=num_classes
    )

    counts = np.where(
        counts == 0,
        1,
        counts
    )

    weights = 1.0 / (counts ** smooth_factor)

    weights = (
            weights / weights.sum()
            * num_classes
    )

    return torch.tensor(
        weights,
        dtype=torch.float32
    )


# ==========================================
# 主训练流程
# ==========================================
def main():

    BASE_DIR = os.path.dirname(
        os.path.abspath(__file__)
    )

    data_dir = os.path.join(
        BASE_DIR,
        "processed_features"
    )

    runs_dir = os.path.join(
        BASE_DIR,
        "newruns"
    )

    save_path = get_next_version_path(runs_dir)

    os.makedirs(
        os.path.join(save_path, "weights"),
        exist_ok=True
    )

    logger = setup_logger(
        os.path.join(save_path, "train.log")
    )

    logger.info(
        f"[*] 剔除类别: Chest Pain (Index 5) | 剩余类别数: {NUM_CLASSES}"
    )

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    all_files = [
        os.path.join(data_dir, f)
        for f in os.listdir(data_dir)
        if f.endswith('.npy')
    ]

    random.seed(42)
    random.shuffle(all_files)

    split_idx = int(0.8 * len(all_files))

    train_files = all_files[:split_idx]
    val_files = all_files[split_idx:]

    train_set = UnifiedDualHeadDataset(
        train_files,
        window_size=30,
        stride=2
    )

    val_set = UnifiedDualHeadDataset(
        val_files,
        window_size=30,
        stride=30
    )

    train_loader = DataLoader(
        train_set,
        batch_size=128,
        shuffle=True
    )

    val_loader = DataLoader(
        val_set,
        batch_size=128,
        shuffle=False
    )

    cls_weights = get_class_weights(
        train_set.labels_cls,
        num_classes=NUM_CLASSES
    ).to(device)

    pred_weights = get_class_weights(
        train_set.labels_pred,
        num_classes=NUM_CLASSES
    ).to(device)

    model = DualHeadActionModel(
        num_classes=NUM_CLASSES
    ).to(device)

    criterion_cls = FocalLoss(
        weight=cls_weights,
        gamma=1.5
    )

    criterion_pred = FocalLoss(
        weight=pred_weights,
        gamma=1.5
    )

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=0.001
    )

    epochs = 30

    best_val_score = 0.0

    history = {
        'train_loss': [],
        'val_cls_acc': [],
        'val_pred_acc': []
    }

    best_cls_p = []
    best_cls_l = []

    best_pred_p = []
    best_pred_l = []

    for epoch in range(epochs):

        model.train()

        train_loss = 0

        for x, y_cls, y_pred in train_loader:

            x = x.to(device)
            y_cls = y_cls.to(device)
            y_pred = y_pred.to(device)

            optimizer.zero_grad()

            out_cls, out_pred = model(x)

            loss = (
                    criterion_cls(out_cls, y_cls)
                    + criterion_pred(out_pred, y_pred)
            )

            loss.backward()

            optimizer.step()

            train_loss += loss.item()

        model.eval()

        val_acc_cls = 0
        val_acc_pred = 0

        all_cls_preds = []
        all_cls_labels = []

        all_pred_preds = []
        all_pred_labels = []

        with torch.no_grad():

            for x, y_cls, y_pred in val_loader:

                x = x.to(device)
                y_cls = y_cls.to(device)
                y_pred = y_pred.to(device)

                out_cls, out_pred = model(x)

                val_acc_cls += compute_accuracy(
                    out_cls,
                    y_cls
                )

                val_acc_pred += compute_accuracy(
                    out_pred,
                    y_pred
                )

                _, p_cls = torch.max(out_cls, 1)
                _, p_pred = torch.max(out_pred, 1)

                all_cls_preds.extend(
                    p_cls.cpu().numpy()
                )

                all_cls_labels.extend(
                    y_cls.cpu().numpy()
                )

                all_pred_preds.extend(
                    p_pred.cpu().numpy()
                )

                all_pred_labels.extend(
                    y_pred.cpu().numpy()
                )

        val_acc_cls /= len(val_loader)
        val_acc_pred /= len(val_loader)

        history['train_loss'].append(
            train_loss / len(train_loader)
        )

        history['val_cls_acc'].append(val_acc_cls)
        history['val_pred_acc'].append(val_acc_pred)

        logger.info(
            f"Epoch {epoch + 1:02d} | "
            f"Loss: {history['train_loss'][-1]:.4f} | "
            f"CLS Acc: {val_acc_cls:.4f} | "
            f"PRED Acc: {val_acc_pred:.4f}"
        )

        if (val_acc_cls + val_acc_pred) > best_val_score:

            best_val_score = (
                    val_acc_cls + val_acc_pred
            )

            torch.save(
                model.state_dict(),
                os.path.join(
                    save_path,
                    "weights",
                    "best.pth"
                )
            )

            best_cls_p = all_cls_preds
            best_cls_l = all_cls_labels

            best_pred_p = all_pred_preds
            best_pred_l = all_pred_labels

    # ==========================================
    # 保存训练曲线（中文）
    # ==========================================
    plt.figure(figsize=(14, 5))

    plt.subplot(1, 2, 1)

    plt.plot(
        history['train_loss'],
        label='训练损失',
        color='#e74c3c',
        marker='o'
    )

    plt.title('训练损失曲线')
    plt.xlabel('训练轮次')
    plt.ylabel('损失值')
    plt.legend()

    plt.subplot(1, 2, 2)

    plt.plot(
        history['val_cls_acc'],
        label='当前动作识别准确率',
        color='#3498db',
        marker='s'
    )

    plt.plot(
        history['val_pred_acc'],
        label='未来动作预测准确率',
        color='#2ecc71',
        marker='^'
    )

    plt.title('验证集准确率')
    plt.xlabel('训练轮次')
    plt.ylabel('准确率')
    plt.legend()

    plt.tight_layout()

    plt.savefig(
        os.path.join(save_path, "training_curves.png"),
        dpi=300
    )

    plt.close()

    # ==========================================
    # 分类报告
    # ==========================================
    target_labels = list(range(NUM_CLASSES))

    cls_report = classification_report(
        best_cls_l,
        best_cls_p,
        labels=target_labels,
        target_names=TARGET_NAMES,
        zero_division=0,
        output_dict=True
    )

    pred_report = classification_report(
        best_pred_l,
        best_pred_p,
        labels=target_labels,
        target_names=TARGET_NAMES,
        zero_division=0,
        output_dict=True
    )

    pd.DataFrame(cls_report).transpose().to_csv(
        os.path.join(
            save_path,
            "metrics_classification.csv"
        ),
        encoding='utf-8-sig'
    )

    pd.DataFrame(pred_report).transpose().to_csv(
        os.path.join(
            save_path,
            "metrics_prediction.csv"
        ),
        encoding='utf-8-sig'
    )

    logger.info(
        "\n【当前动作识别报告】:\n"
        + pd.DataFrame(cls_report).transpose().to_string()
    )

    # ==========================================
    # 中文混淆矩阵
    # ==========================================
    plot_confusion_matrix(
        best_cls_l,
        best_cls_p,
        TARGET_NAMES,
        '当前动作识别混淆矩阵（10类）',
        os.path.join(
            save_path,
            "confusion_matrix_cls_10.png"
        )
    )

    plot_confusion_matrix(
        best_pred_l,
        best_pred_p,
        TARGET_NAMES,
        '未来动作预测混淆矩阵（10类）',
        os.path.join(
            save_path,
            "confusion_matrix_pred_10.png"
        )
    )

    # ==========================================
    # 中文 Top5 柱状图
    # ==========================================
    plot_top5_accuracy(
        cls_report,
        TARGET_NAMES,
        os.path.join(
            save_path,
            "top5_accuracy_bar.png"
        )
    )

    logger.info(
        f"[+] 训练及结果保存完成。"
        f"所有报告与图表已保存至: {save_path}"
    )


if __name__ == "__main__":
    main()