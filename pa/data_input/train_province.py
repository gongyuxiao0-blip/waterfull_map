import os
import json
import pickle
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pymysql
import tensorflow as tf
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import classification_report, mean_absolute_error, mean_squared_error
from sklearn.ensemble import RandomForestClassifier
from sklearn.utils.class_weight import compute_class_weight

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Input, LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
from tensorflow.keras.optimizers import Adam


tf.get_logger().setLevel("ERROR")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# =========================
# 1. 基础配置
# =========================
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "1111",   # 改成你的密码
    "database": "rain",
    "charset": "utf8mb4"
}

TARGET_TYPE = "province"
TARGET_NAME = "湖北省"     # 改成你要训练的省份

DATA_START_DATE = "2022-01-01"

TIME_STEP = 21
TRAIN_RATIO = 0.8
EPOCHS = 40
BATCH_SIZE = 256
CLS_THRESHOLD = 0.45

BASE_MODEL_DIR = "models"

# =========================
# 2. 等级定义
# =========================
RAIN_LEVEL_NAMES = {0: "小雨", 1: "中雨", 2: "大雨", 3: "暴雨"}
NUM_RAIN_LEVELS = 4



def get_model_paths(target_type: str, target_name: str):
    model_dir = os.path.join(BASE_MODEL_DIR, target_type, target_name)
    return {
        "model_dir": model_dir,
        "rf_model_path": os.path.join(model_dir, "rf_classifier.pkl"),
        "level_model_path": os.path.join(model_dir, "rain_level_best.keras"),
        "feature_scaler_path": os.path.join(model_dir, "feature_scaler.pkl"),
        "meta_path": os.path.join(model_dir, "meta.json"),
    }


@dataclass
class PreparedData:
    df: pd.DataFrame
    seq_feature_cols: list
    cls_feature_cols: list
    feature_scaler: MinMaxScaler

    X_train_seq: np.ndarray
    X_test_seq: np.ndarray
    X_train_cls: np.ndarray
    X_test_cls: np.ndarray

    y_train_cls: np.ndarray
    y_test_cls: np.ndarray
    y_train_level: np.ndarray
    y_test_level: np.ndarray
    y_train_mm: np.ndarray
    y_test_mm: np.ndarray

    train_dates: list
    test_dates: list
    train_level_to_mm: dict


# =========================
# 3. 数据读取
# =========================
def get_db_connection():
    return pymysql.connect(**MYSQL_CONFIG)


def load_province_avg_rainfall(province_name: str) -> pd.DataFrame:
    """
    省份日平均降雨量：
    = 该省当天所有城市降雨量之和 / 该省城市总数

    这里采用“固定城市总数”做分母。
    如果某天某些城市没有记录，相当于这些城市当天按 0 处理。
    """
    sql = """
    SELECT
        cdr.date AS date,
        SUM(COALESCE(cdr.rainfall, 0)) / pc.city_count AS rainfall
    FROM city_daily_rainfall cdr
    JOIN city c ON cdr.city_id = c.id
    JOIN province p ON c.province_id = p.id
    JOIN (
        SELECT province_id, COUNT(*) AS city_count
        FROM city
        GROUP BY province_id
    ) pc ON pc.province_id = p.id
    WHERE p.name = %s
    GROUP BY cdr.date, pc.city_count
    ORDER BY cdr.date ASC
    """

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, [province_name])
            result = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(result, columns=columns)
    finally:
        conn.close()

    if df.empty:
        raise ValueError(f"未找到省份 {province_name} 的平均降雨数据。")
    return df


# =========================
# 4. 数据清洗
# =========================
def clean_and_fill_dates(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data["date"] = pd.to_datetime(data["date"])
    data["rainfall"] = pd.to_numeric(data["rainfall"], errors="coerce")
    data = data.drop_duplicates(subset=["date"], keep="last")

    full_dates = pd.date_range(data["date"].min(), data["date"].max(), freq="D")
    full_df = pd.DataFrame({"date": full_dates})
    data = pd.merge(full_df, data, on="date", how="left")
    data["rainfall"] = data["rainfall"].fillna(0.0)
    return data


# =========================
# 5. 标签定义
# =========================
def rainfall_to_rain_level(x: float) -> int:
    if x <= 0:
        raise ValueError("只应用于雨天样本")
    if x < 10:
        return 0
    if x < 25:
        return 1
    if x < 50:
        return 2
    return 3


# =========================
# 6. 特征工程（无泄漏版）
# =========================
def add_features(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data["month"] = data["date"].dt.month
    data["day_of_year"] = data["date"].dt.dayofyear

    data["month_sin"] = np.sin(2 * np.pi * data["month"] / 12)
    data["month_cos"] = np.cos(2 * np.pi * data["month"] / 12)
    data["doy_sin"] = np.sin(2 * np.pi * data["day_of_year"] / 366)
    data["doy_cos"] = np.cos(2 * np.pi * data["day_of_year"] / 366)

    rainy = (data["rainfall"] > 0).astype(int)
    raw_streak = rainy.groupby((rainy == 0).cumsum()).cumsum()

    data["lag_1"] = data["rainfall"].shift(1)
    data["lag_3"] = data["rainfall"].shift(3)
    data["lag_7"] = data["rainfall"].shift(7)

    data["rolling_mean_7"] = data["rainfall"].shift(1).rolling(7).mean()
    data["rolling_max_7"] = data["rainfall"].shift(1).rolling(7).max()
    data["rolling_sum_7"] = data["rainfall"].shift(1).rolling(7).sum()
    data["rolling_std_7"] = data["rainfall"].shift(1).rolling(7).std()

    data["prev_is_rainy"] = rainy.shift(1)
    data["prev_rain_streak"] = raw_streak.shift(1).fillna(0)
    data["recent_rain_days_7"] = rainy.shift(1).rolling(7).sum()

    # 标签
    data["target_cls"] = (data["rainfall"] > 0).astype(int)
    data["target_level"] = -1
    rain_mask = data["rainfall"] > 0
    data.loc[rain_mask, "target_level"] = data.loc[rain_mask, "rainfall"].apply(rainfall_to_rain_level)

    data = data.dropna().reset_index(drop=True)
    data["target_cls"] = data["target_cls"].astype(int)
    data["target_level"] = data["target_level"].astype(int)
    return data


# =========================
# 7. 构造样本序列
# =========================
def create_sequences(seq_features, cls_features, y_cls, y_level, y_mm, dates, time_step):
    X_seq, X_cls, cls_y, level_y, mm_y, out_dates = [], [], [], [], [], []

    for i in range(len(seq_features) - time_step):
        target_idx = i + time_step
        X_seq.append(seq_features[i:target_idx])
        X_cls.append(cls_features[target_idx])
        cls_y.append(y_cls[target_idx])
        level_y.append(y_level[target_idx])
        mm_y.append(y_mm[target_idx])
        out_dates.append(dates[target_idx])

    return (
        np.asarray(X_seq, dtype=np.float32),
        np.asarray(X_cls, dtype=np.float32),
        np.asarray(cls_y, dtype=np.int32),
        np.asarray(level_y, dtype=np.int32),
        np.asarray(mm_y, dtype=np.float32),
        out_dates,
    )


# =========================
# 8. 等级转毫米
# =========================
def build_train_level_to_mm(df_train: pd.DataFrame) -> dict:
    mapping = {}
    fallback = {0: 5.0, 1: 17.5, 2: 37.5, 3: 75.0}
    for lv in range(NUM_RAIN_LEVELS):
        vals = df_train.loc[
            (df_train["target_level"] == lv) & (df_train["rainfall"] > 0),
            "rainfall"
        ]
        mapping[lv] = float(vals.median()) if len(vals) > 0 else fallback[lv]
    return mapping


def levels_to_mm(levels: np.ndarray, level_to_mm: dict) -> np.ndarray:
    return np.array([level_to_mm[int(x)] for x in levels], dtype=np.float32)


# =========================
# 9. 数据准备
# =========================
def prepare_data(target_name: str, time_step: int, train_ratio: float) -> PreparedData:
    df = load_province_avg_rainfall(target_name)
    df = clean_and_fill_dates(df)
    df = df[df["date"] >= pd.to_datetime(DATA_START_DATE)].copy().reset_index(drop=True)
    if df.empty:
        raise ValueError("无有效数据")

    df = add_features(df)

    seq_feature_cols = [
        "rainfall",
        "lag_1", "lag_3", "lag_7",
        "rolling_mean_7", "rolling_max_7", "rolling_sum_7", "rolling_std_7",
        "prev_is_rainy", "prev_rain_streak", "recent_rain_days_7",
        "month_sin", "month_cos", "doy_sin", "doy_cos",
    ]
    cls_feature_cols = [
        "lag_1", "lag_3", "lag_7",
        "rolling_mean_7", "rolling_max_7", "rolling_sum_7", "rolling_std_7",
        "prev_is_rainy", "prev_rain_streak", "recent_rain_days_7",
        "month_sin", "month_cos", "doy_sin", "doy_cos",
    ]

    seq_values_raw = df[seq_feature_cols].values.astype(np.float32)
    cls_values_raw = df[cls_feature_cols].values.astype(np.float32)
    y_cls_raw = df["target_cls"].values.astype(np.int32)
    y_level_raw = df["target_level"].values.astype(np.int32)
    y_mm_raw = df["rainfall"].values.astype(np.float32)
    all_dates = df["date"].tolist()

    split_index = int(len(df) * train_ratio)
    if split_index <= time_step:
        raise ValueError("训练集太短，至少要大于 TIME_STEP")

    feature_scaler = MinMaxScaler()
    feature_scaler.fit(seq_values_raw[:split_index])
    full_seq_scaled = feature_scaler.transform(seq_values_raw)

    X_train_seq, X_train_cls, y_train_cls, y_train_level, y_train_mm, train_dates = create_sequences(
        full_seq_scaled[:split_index],
        cls_values_raw[:split_index],
        y_cls_raw[:split_index],
        y_level_raw[:split_index],
        y_mm_raw[:split_index],
        all_dates[:split_index],
        time_step,
    )

    X_test_seq, X_test_cls, y_test_cls, y_test_level, y_test_mm, test_dates = create_sequences(
        full_seq_scaled[split_index - time_step:],
        cls_values_raw[split_index - time_step:],
        y_cls_raw[split_index - time_step:],
        y_level_raw[split_index - time_step:],
        y_mm_raw[split_index - time_step:],
        all_dates[split_index - time_step:],
        time_step,
    )

    df_train = df.iloc[:split_index].copy()
    train_level_to_mm = build_train_level_to_mm(df_train)

    return PreparedData(
        df=df,
        seq_feature_cols=seq_feature_cols,
        cls_feature_cols=cls_feature_cols,
        feature_scaler=feature_scaler,
        X_train_seq=X_train_seq,
        X_test_seq=X_test_seq,
        X_train_cls=X_train_cls,
        X_test_cls=X_test_cls,
        y_train_cls=y_train_cls,
        y_test_cls=y_test_cls,
        y_train_level=y_train_level,
        y_test_level=y_test_level,
        y_train_mm=y_train_mm,
        y_test_mm=y_test_mm,
        train_dates=train_dates,
        test_dates=test_dates,
        train_level_to_mm=train_level_to_mm,
    )


# =========================
# 10. LSTM 模型
# =========================
def build_rain_level_model(time_step: int, feature_dim: int, num_classes: int):
    model = Sequential([
        Input(shape=(time_step, feature_dim)),
        LSTM(64, return_sequences=True),
        Dropout(0.20),
        LSTM(32),
        Dropout(0.20),
        Dense(16, activation="relu"),
        Dense(num_classes, activation="softmax"),
    ])
    model.compile(
        optimizer=Adam(learning_rate=0.001),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def oversample_rain_level_data(X, y):
    rng = np.random.default_rng(42)
    class_indices = {cls: np.where(y == cls)[0] for cls in range(NUM_RAIN_LEVELS)}
    class_counts = {cls: len(idx) for cls, idx in class_indices.items() if len(idx) > 0}
    if not class_counts:
        raise ValueError("训练集中没有雨天样本，无法训练 LSTM 雨强模型")

    max_count = max(class_counts.values())
    target_count = max(1, int(max_count * 0.6))

    X_list, y_list = [], []
    for cls in range(NUM_RAIN_LEVELS):
        idx = class_indices.get(cls, np.array([], dtype=int))
        if len(idx) == 0:
            continue
        if len(idx) < target_count:
            extra = rng.choice(idx, target_count - len(idx), replace=True)
            idx = np.concatenate([idx, extra])
        X_list.append(X[idx])
        y_list.append(y[idx])

    Xb = np.concatenate(X_list, axis=0)
    yb = np.concatenate(y_list, axis=0)
    shf = rng.permutation(len(yb))
    return Xb[shf], yb[shf]


def build_rain_level_class_weight(y_level: np.ndarray) -> dict:
    classes = np.unique(y_level)
    weights = compute_class_weight(class_weight="balanced", classes=classes, y=y_level)
    w = {int(c): float(v) for c, v in zip(classes, weights)}
    return {
        0: w.get(0, 1.0),
        1: w.get(1, 1.5),
        2: w.get(2, 2.0),
        3: w.get(3, 3.0),
    }


@tf.function(jit_compile=False)
def fast_predict_level(model, x):
    return model(x)


# =========================
# 11. 构造“明天”的输入
# =========================
def _count_prev_rain_streak(rainfall_series: pd.Series) -> int:
    streak = 0
    for x in rainfall_series.iloc[::-1]:
        if float(x) > 0:
            streak += 1
        else:
            break
    return streak


def build_next_day_inputs(prepared: PreparedData, time_step: int):
    hist = prepared.df.copy()
    if len(hist) < time_step:
        raise ValueError("历史长度不足，无法构造明日输入")

    next_date = hist["date"].iloc[-1] + pd.Timedelta(days=1)

    next_seq_raw = hist[prepared.seq_feature_cols].tail(time_step).values.astype(np.float32)
    next_seq_scaled = prepared.feature_scaler.transform(next_seq_raw).reshape(1, time_step, -1)

    rainfall_hist = hist["rainfall"].astype(float)
    last7 = rainfall_hist.tail(7)

    next_cls_dict = {
        "lag_1": float(rainfall_hist.iloc[-1]),
        "lag_3": float(rainfall_hist.iloc[-3]),
        "lag_7": float(rainfall_hist.iloc[-7]),
        "rolling_mean_7": float(last7.mean()),
        "rolling_max_7": float(last7.max()),
        "rolling_sum_7": float(last7.sum()),
        "rolling_std_7": float(last7.std(ddof=1)) if len(last7) > 1 else 0.0,
        "prev_is_rainy": float(rainfall_hist.iloc[-1] > 0),
        "prev_rain_streak": float(_count_prev_rain_streak(rainfall_hist)),
        "recent_rain_days_7": float((last7 > 0).sum()),
        "month_sin": float(np.sin(2 * np.pi * next_date.month / 12)),
        "month_cos": float(np.cos(2 * np.pi * next_date.month / 12)),
        "doy_sin": float(np.sin(2 * np.pi * next_date.dayofyear / 366)),
        "doy_cos": float(np.cos(2 * np.pi * next_date.dayofyear / 366)),
    }

    next_cls_raw = np.array([[next_cls_dict[c] for c in prepared.cls_feature_cols]], dtype=np.float32)
    return next_seq_scaled, next_cls_raw, next_date


# =========================
# 12. 保存
# =========================
def save_outputs(prepared: PreparedData, rf_model, next_date, target_type: str, target_name: str):
    paths = get_model_paths(target_type, target_name)
    os.makedirs(paths["model_dir"], exist_ok=True)

    with open(paths["rf_model_path"], "wb") as f:
        pickle.dump(rf_model, f)

    with open(paths["feature_scaler_path"], "wb") as f:
        pickle.dump(prepared.feature_scaler, f)

    meta = {
        "target_type": target_type,
        "target_name": target_name,
        "time_step": TIME_STEP,
        "seq_cols": prepared.seq_feature_cols,
        "cls_cols": prepared.cls_feature_cols,
        "next_date": str(next_date),
        "threshold": CLS_THRESHOLD,
        "level_map": prepared.train_level_to_mm,
        "names": RAIN_LEVEL_NAMES,
    }

    with open(paths["meta_path"], "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


# =========================
# 13. 主流程
# =========================
def train_and_predict(target_name: str):
    paths = get_model_paths(TARGET_TYPE, target_name)
    prepared = prepare_data(target_name, TIME_STEP, TRAIN_RATIO)
    feature_dim = prepared.X_train_seq.shape[2]

    os.makedirs(paths["model_dir"], exist_ok=True)

    print(f"\n开始训练: {TARGET_TYPE} / {target_name}")

    # 1) 是否下雨分类器
    print("\n训练 RF 分类器（无泄漏版）...")
    train_y = prepared.y_train_cls.astype(int)
    classes_arr = np.array([0, 1])
    weights = compute_class_weight(class_weight="balanced", classes=classes_arr, y=train_y)
    class_weight_dict = {0: float(weights[0]), 1: float(weights[1])}

    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_split=4,
        min_samples_leaf=2,
        class_weight=class_weight_dict,
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(prepared.X_train_cls, train_y)
    yp_prob = rf.predict_proba(prepared.X_test_cls)[:, 1]
    yp_cls = (yp_prob >= CLS_THRESHOLD).astype(int)

    # 2) 雨强等级 LSTM
    print("\n训练 LSTM 雨强分类器（无泄漏版）...")
    train_mask = prepared.y_train_cls == 1
    Xl = prepared.X_train_seq[train_mask]
    yl = prepared.y_train_level[train_mask]

    if len(Xl) == 0:
        raise ValueError("训练集中没有雨天样本，无法继续训练 LSTM。")

    Xlb, ylb = oversample_rain_level_data(Xl, yl)
    lw = build_rain_level_class_weight(ylb)
    model = build_rain_level_model(TIME_STEP, feature_dim, NUM_RAIN_LEVELS)

    callbacks = [
        EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True),
        ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-5),
        ModelCheckpoint(paths["level_model_path"], save_best_only=True),
    ]

    history = model.fit(
        Xlb,
        ylb,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        validation_split=0.1,
        callbacks=callbacks,
        class_weight=lw,
        shuffle=True,
        verbose=1,
    )

    # 训练损失图
    plt.figure(figsize=(10, 4))
    plt.plot(history.history["loss"], label="train_loss")
    plt.plot(history.history["val_loss"], label="val_loss")
    plt.title("LSTM训练损失曲线（省份平均降雨量）")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # 3) 测试集推理
    print("\n测试集推理中...")
    X_test_seq_tensor = tf.convert_to_tensor(prepared.X_test_seq, dtype=tf.float32)
    yp_level_prob = fast_predict_level(model, X_test_seq_tensor).numpy()

    # 这个保留，后面分类评估还要用
    yp_level = np.argmax(yp_level_prob, axis=1)

    # ===== 新增：概率加权毫米值，而不是 argmax 后映射固定值 =====
    level_centers = np.array(
        [prepared.train_level_to_mm[i] for i in range(NUM_RAIN_LEVELS)],
        dtype=np.float32
    )

    # 每一行 softmax 概率 × 各档代表值
    yp_mm_soft = yp_level_prob @ level_centers

    # 如果 RF 判定不下雨，则强制为 0
    y_final = np.where(yp_cls == 1, yp_mm_soft, 0.0)

    print("\n===== 下雨分类评估 =====")
    print(classification_report(prepared.y_test_cls, yp_cls, zero_division=0))

    test_rain_mask = prepared.y_test_cls == 1
    if test_rain_mask.sum() > 0:
        print("\n===== 雨强分类评估（仅真实雨天） =====")
        print(
            classification_report(
                prepared.y_test_level[test_rain_mask],
                yp_level[test_rain_mask],
                labels=list(range(NUM_RAIN_LEVELS)),
                target_names=[RAIN_LEVEL_NAMES[i] for i in range(NUM_RAIN_LEVELS)],
                zero_division=0,
            )
        )

    mae = mean_absolute_error(prepared.y_test_mm, y_final)
    rmse = np.sqrt(mean_squared_error(prepared.y_test_mm, y_final))
    print(f"\nMAE  = {mae:.4f}")
    print(f"RMSE = {rmse:.4f}")

    # 4) 真正的“明天预测”
    next_seq_scaled, next_cls_raw, next_date = build_next_day_inputs(prepared, TIME_STEP)
    next_seq_tensor = tf.convert_to_tensor(next_seq_scaled, dtype=tf.float32)

    prob = rf.predict_proba(next_cls_raw)[:, 1][0]
    rain_pred = 1 if prob >= CLS_THRESHOLD else 0

    level_pred_prob = fast_predict_level(model, next_seq_tensor).numpy()[0]
    level_pred = int(np.argmax(level_pred_prob))  # 这个保留，用来显示“哪一档概率最大”

    # ===== 新增：概率加权毫米值 =====
    level_centers = np.array(
        [prepared.train_level_to_mm[i] for i in range(NUM_RAIN_LEVELS)],
        dtype=np.float32
    )

    mm_pred = float(level_pred_prob @ level_centers) if rain_pred else 0.0

    print(
        f"\n预测 {next_date.date()}："
        f"{'下雨' if rain_pred else '无雨'}，"
        f"{RAIN_LEVEL_NAMES.get(level_pred, '无雨')}，"
        f"{mm_pred:.1f} mm"
    )
    print(f"下雨概率：{prob:.4f}")
    print(f"雨强概率：{level_pred_prob}")

    # 结果对比图
    plt.rcParams["font.sans-serif"] = ["SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

    plt.figure(figsize=(14, 5))
    plt.plot(prepared.test_dates, prepared.y_test_mm, label="真实平均降雨量(mm)", alpha=0.7)
    plt.plot(prepared.test_dates, y_final, label="预测平均降雨量(mm)", alpha=0.7)
    plt.title(f"{target_name} 平均降雨量预测对比")
    plt.xlabel("日期")
    plt.ylabel("平均降雨量(mm)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

    save_outputs(prepared, rf, next_date.date(), TARGET_TYPE, target_name)


if __name__ == "__main__":
    train_and_predict(TARGET_NAME)