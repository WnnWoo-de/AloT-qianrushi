import os
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
import pandas as pd
from sklearn.model_selection import train_test_split


# ==========================================
# 版本目录
# ==========================================
def get_next_version_path(base_path):
    if not os.path.exists(base_path):
        os.makedirs(base_path)
    version = 1
    while True:
        version_path = os.path.join(base_path, f"v{version}")
        if not os.path.exists(version_path):
            os.makedirs(version_path)
            return version_path
        version += 1


# ==========================================
#  Dataset（按“文件级”组织，避免泄漏）
# ==========================================
class MultiClassFallDataset(Dataset):
    def __init__(self, file_list, data_dir, window_size=30):
        self.sequences = []
        self.labels_cls = []
        self.labels_pred = []

        print(f"[*] 加载数据文件数: {len(file_list)}")

        for file in file_list:
            data = np.load(os.path.join(data_dir, file))
            features, labels = data[:, :34], data[:, 34]

            for i in range(len(data) - window_size - 15):
                seq_x = features[i: i + window_size]

                velocity = np.diff(seq_x, axis=0)
                velocity = np.vstack([velocity, velocity[-1]])
                seq_x = np.concatenate([seq_x, velocity], axis=1)

                curr_csv_label = int(labels[i + window_size - 1])

                curr_label = 2 if (
                    curr_csv_label == 1 and
                    np.all(labels[i + window_size - 15:i + window_size] == 1)
                ) else curr_csv_label

                future_15 = labels[i + window_size: i + window_size + 15]
                pred_label = 3 if (curr_label == 0 and 1 in future_15) else curr_label

                self.sequences.append(seq_x)
                self.labels_cls.append(curr_label)
                self.labels_pred.append(pred_label)

        print(f"[+] 样本总数: {len(self.sequences)}")

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        return (
            torch.tensor(self.sequences[idx], dtype=torch.float32),
            torch.tensor(self.labels_cls[idx], dtype=torch.long),
            torch.tensor(self.labels_pred[idx], dtype=torch.long)
        )


# ==========================================
# Model（保持不变）
# ==========================================
class DualHeadActionModel(nn.Module):
    def __init__(self, input_dim=68, hidden_dim=128,
                 num_classes_cls=3, num_classes_pred=4):
        super().__init__()

        self.lstm = nn.LSTM(
            input_dim, hidden_dim,
            num_layers=2,
            batch_first=True,
            bidirectional=True
        )

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

        attn_weights = torch.softmax(self.attention_fc(lstm_out), dim=1)
        context = torch.sum(lstm_out * attn_weights, dim=1)

        return self.classifier_head(context), self.prediction_head(context)


# ==========================================
# 保存结果
# ==========================================
def save_results(history, save_path):
    df = pd.DataFrame(history)
    df.to_csv(os.path.join(save_path, "training_log.csv"), index=False)

    epochs = range(1, len(history['loss']) + 1)
    plt.figure(figsize=(14, 5))

    plt.subplot(1, 2, 1)
    plt.plot(epochs, history['loss'], 'o-')
    plt.title("Training Loss")

    plt.subplot(1, 2, 2)
    plt.plot(epochs, history['val_acc_cls'], label="CLS Acc")
    plt.plot(epochs, history['val_acc_pred'], label="PRED Acc")
    plt.legend()
    plt.title("Validation Accuracy")

    plt.tight_layout()
    plt.savefig(os.path.join(save_path, "result.png"), dpi=300)
    plt.close()


# ==========================================
# 主程序（关键修改在这里）
# ==========================================
def main():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(BASE_DIR, "processed_features")
    save_path = get_next_version_path(os.path.join(BASE_DIR, "runs"))

    print(f"save to: {save_path}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # ======================================
    #  关键修复：按文件划分 train / val
    # ======================================
    all_files = [f for f in os.listdir(data_dir) if f.endswith(".npy")]

    train_files, val_files = train_test_split(
        all_files,
        test_size=0.2,
        random_state=42
    )

    train_set = MultiClassFallDataset(train_files, data_dir)
    val_set = MultiClassFallDataset(val_files, data_dir)

    train_loader = DataLoader(train_set, batch_size=128, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=128)

    model = DualHeadActionModel().to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.CrossEntropyLoss()

    history = {
        "epoch": [],
        "loss": [],
        "val_acc_cls": [],
        "val_acc_pred": []
    }

    # ======================================
    # train
    # ======================================
    for epoch in range(20):
        model.train()
        total_loss = 0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}")

        for x, y_cls, y_pred in pbar:
            x, y_cls, y_pred = x.to(device), y_cls.to(device), y_pred.to(device)

            optimizer.zero_grad()

            out_cls, out_pred = model(x)

            loss = criterion(out_cls, y_cls) + criterion(out_pred, y_pred)

            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            pbar.set_postfix(loss=loss.item())

        # ======================================
        # eval
        # ======================================
        model.eval()
        acc_cls, acc_pred = 0, 0

        with torch.no_grad():
            for x, y_cls, y_pred in val_loader:
                x, y_cls, y_pred = x.to(device), y_cls.to(device), y_pred.to(device)

                out_cls, out_pred = model(x)

                acc_cls += (out_cls.argmax(1) == y_cls).sum().item()
                acc_pred += (out_pred.argmax(1) == y_pred).sum().item()

        epoch_loss = total_loss / len(train_loader)
        epoch_acc_cls = acc_cls / len(val_set)
        epoch_acc_pred = acc_pred / len(val_set)

        history["epoch"].append(epoch + 1)
        history["loss"].append(epoch_loss)
        history["val_acc_cls"].append(epoch_acc_cls)
        history["val_acc_pred"].append(epoch_acc_pred)

        print(f"""
Epoch {epoch+1}
Loss: {epoch_loss:.4f}
CLS Acc: {epoch_acc_cls:.4f}
PRED Acc: {epoch_acc_pred:.4f}
""")

    # ======================================
    # save
    # ======================================
    torch.save(model.state_dict(), os.path.join(save_path, "model.pth"))
    save_results(history, save_path)

    with open(os.path.join(save_path, "summary.txt"), "w") as f:
        f.write(f"Final CLS Acc: {history['val_acc_cls'][-1]:.4f}\n")
        f.write(f"Final PRED Acc: {history['val_acc_pred'][-1]:.4f}\n")
        f.write(f"Epochs: 20\n")

    print(f"\ndone: {save_path}")


if __name__ == "__main__":
    main()