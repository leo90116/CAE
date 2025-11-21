import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix


# =========================
# 1. Dataset 定義
# =========================
class RouteLogDataset(Dataset):
    def __init__(self, df, feature_cols, label_col, seq_len=6):
        """
        df: 已依 timestamp 排序好的 DataFrame
        feature_cols: 特徵欄位
        label_col: 目標欄位 (這裡是 'label')
        seq_len: LSTM 每次看幾個時間步
        """
        self.seq_len = seq_len

        features = df[feature_cols].values.astype(np.float32)
        labels = df[label_col].values.astype(np.float32)

        X_list, y_list = [], []
        N = len(df)
        # sliding window：每 seq_len 筆做一個樣本
        for i in range(N - seq_len + 1):
            X_list.append(features[i : i + seq_len])      # (seq_len, num_features)
            y_list.append(labels[i + seq_len - 1])        # 用最後一筆當 label

        self.X = np.array(X_list)
        self.y = np.array(y_list)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


# =========================
# 2. LSTM 模型
# =========================
class LSTMTrafficModel(nn.Module):
    def __init__(self, input_dim, hidden_dim=32, num_layers=1, dropout=0.0):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout,
        )
        self.fc = nn.Linear(hidden_dim, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        # x: (batch, seq_len, input_dim)
        out, _ = self.lstm(x)          # out: (batch, seq_len, hidden_dim)
        last_hidden = out[:, -1, :]    # 取最後一個時間步
        logit = self.fc(last_hidden)   # (batch, 1)
        prob = self.sigmoid(logit)     # (batch, 1)
        return prob.view(-1)           # 攤平成 (batch,)


# =========================
# 3. 主程式：讀「工作表3」+ 前處理 + 訓練
# =========================
def main():
    # --- 3.1 讀取 route_log.xlsx 的「工作表3」 ---
    df = pd.read_excel("route_log.xlsx", sheet_name="工作表3")

    # 轉成時間格式並依時間排序（保險起見）
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    # --- 3.2 建立二元 label：是否壅塞 ---
    # 這裡定義：difference_percent > 0 視為壅塞 (1)，否則 0
    df["label"] = (df["difference_percent"] > 10).astype(float)

    # --- 3.3 指定特徵欄位 ---
    feature_cols = [
        "duration_with_traffic",
        "duration_no_traffic",
        "difference_seconds",
        "difference_percent",
        "distance",
        "velocity_with_traffic",
        "velocity_no_traffic",
        "Ef with traffic",
        "Ef without traffic",
    ]

    # --- 3.4 標準化特徵 ---
    scaler = StandardScaler()
    df[feature_cols] = scaler.fit_transform(df[feature_cols])

    # --- 3.5 依時間順序切 train / test ---
    train_df, test_df = train_test_split(df, test_size=0.3, shuffle=False)

    seq_len = 12  # 用前 6 筆資料預測第 6 筆是否壅塞

    train_dataset = RouteLogDataset(train_df, feature_cols, "label", seq_len=seq_len)
    test_dataset = RouteLogDataset(test_df, feature_cols, "label", seq_len=seq_len)

    train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=8, shuffle=False)

    # --- 3.6 建立模型 ---
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    input_dim = len(feature_cols)
    model = LSTMTrafficModel(input_dim=input_dim, hidden_dim=32, num_layers=1).to(device)

    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    # --- 3.7 訓練迴圈 ---
    num_epochs = 30
    for epoch in range(num_epochs):
        # 訓練
        model.train()
        total_loss = 0.0
        for X_batch, y_batch in train_loader:
            X_batch = X_batch.to(device)
            y_batch = y_batch.to(device)

            optimizer.zero_grad()
            y_pred = model(X_batch)
            loss = criterion(y_pred, y_batch)
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * X_batch.size(0)

        avg_loss = total_loss / len(train_dataset)

        # 驗證
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for X_batch, y_batch in test_loader:
                X_batch = X_batch.to(device)
                y_batch = y_batch.to(device)

                y_pred = model(X_batch)
                preds = (y_pred >= 0.5).float()
                correct += (preds == y_batch).sum().item()
                total += y_batch.size(0)

        val_acc = correct / total if total > 0 else 0.0
        print(f"Epoch {epoch+1}/{num_epochs} - loss={avg_loss:.4f}, val_acc={val_acc:.4f}")

    # 訓練完之後做一次詳細評估
    model.eval()
    all_y_true = []
    all_y_pred = []
    with torch.no_grad():
        for X_batch, y_batch in test_loader:
            X_batch = X_batch.to(device)
            y_batch = y_batch.to(device)

            y_prob = model(X_batch)
            preds = (y_prob >= 0.5).float()

            all_y_true.extend(y_batch.cpu().numpy().tolist())
            all_y_pred.extend(preds.cpu().numpy().tolist())

    print("\n=== Detailed evaluation on test set ===")
    print("Confusion matrix [ [TN, FP], [FN, TP] ]:")
    print(confusion_matrix(all_y_true, all_y_pred))
    print("\nClassification report:")
    print(classification_report(all_y_true, all_y_pred, digits=3))


if __name__ == "__main__":
    main()
