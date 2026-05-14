# services/predict_region.py

import os
import json
import pickle
from typing import Dict, List, Any

import numpy as np
import pandas as pd
import pymysql
from tensorflow.keras.models import load_model


MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "1111",
    "database": "rain",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor
}

MODEL_ROOT = "models"

ASSET_CACHE: Dict[str, Dict[str, Any]] = {}

PROVINCE_SPECIAL_NAMES = {
    "北京市", "天津市", "上海市", "重庆市",
    "内蒙古自治区", "广西壮族自治区", "西藏自治区",
    "宁夏回族自治区", "新疆维吾尔自治区",
    "香港特别行政区", "澳门特别行政区"
}

DEFAULT_LEVEL_NAMES = {
    0: "弱雨",
    1: "中雨",
    2: "强雨",
    3: "暴雨"
}


class PredictionError(Exception):
    pass


class InvalidParamError(PredictionError):
    pass


class ModelAssetError(PredictionError):
    pass


class HistoryDataError(PredictionError):
    pass


def get_connection():
    return pymysql.connect(**MYSQL_CONFIG)


def normalize_target_type(target_type: str) -> str:
    if not target_type:
        raise InvalidParamError("target_type 不能为空")

    target_type = target_type.strip().lower()
    if target_type not in {"city", "province"}:
        raise InvalidParamError("target_type 只能是 city 或 province")

    return target_type


def normalize_target_name(target_type: str, target_name: str) -> str:
    if not target_name:
        raise InvalidParamError("target_name 不能为空")

    name = target_name.strip()

    if target_type == "city":
        if name.endswith(("市", "区", "县", "自治州", "地区", "盟")):
            return name
        return f"{name}市"

    if name in PROVINCE_SPECIAL_NAMES:
        return name

    if name.endswith(("省", "自治区", "特别行政区", "市")):
        return name

    return f"{name}省"


def get_model_dir(target_type: str, target_name: str) -> str:
    return os.path.join(MODEL_ROOT, target_type, target_name)


def load_predict_assets(target_type: str, target_name: str, force_reload: bool = False) -> Dict[str, Any]:
    cache_key = f"{target_type}:{target_name}"

    if (not force_reload) and cache_key in ASSET_CACHE:
        return ASSET_CACHE[cache_key]

    model_dir = get_model_dir(target_type, target_name)

    rf_model_path = os.path.join(model_dir, "rf_classifier.pkl")
    level_model_path = os.path.join(model_dir, "rain_level_best.keras")
    feature_scaler_path = os.path.join(model_dir, "feature_scaler.pkl")
    meta_path = os.path.join(model_dir, "meta.json")

    required_files = [rf_model_path, level_model_path, feature_scaler_path, meta_path]
    missing_files = [p for p in required_files if not os.path.exists(p)]
    if missing_files:
        raise ModelAssetError(f"模型资产缺失: {missing_files}")

    with open(rf_model_path, "rb") as f:
        rf_model = pickle.load(f)

    level_model = load_model(level_model_path, compile=False)

    with open(feature_scaler_path, "rb") as f:
        feature_scaler = pickle.load(f)

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    if "level_map" in meta and isinstance(meta["level_map"], dict):
        meta["level_map"] = {int(k): float(v) for k, v in meta["level_map"].items()}

    if "names" in meta and isinstance(meta["names"], dict):
        meta["names"] = {int(k): v for k, v in meta["names"].items()}

    assets = {
        "rf_model": rf_model,
        "level_model": level_model,
        "feature_scaler": feature_scaler,
        "meta": meta,
        "model_dir": model_dir
    }

    ASSET_CACHE[cache_key] = assets
    return assets


def query_city_history_for_predict(city_name: str) -> List[Dict[str, Any]]:
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql = """
            SELECT
                date,
                rainfall
            FROM city_daily_rainfall
            WHERE name = %s
            ORDER BY date ASC
        """
        cursor.execute(sql, (city_name,))
        return cursor.fetchall()
    finally:
        if conn:
            conn.close()


def query_province_avg_history_for_predict(province_name: str) -> List[Dict[str, Any]]:
    """
    省份预测：按省内城市平均降雨量构造历史序列
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql = """
            SELECT
                cdr.date,
                AVG(COALESCE(cdr.rainfall, 0)) AS rainfall
            FROM city_daily_rainfall cdr
            JOIN city c ON cdr.city_id = c.id
            JOIN province p ON c.province_id = p.id
            WHERE p.name = %s
            GROUP BY cdr.date
            ORDER BY cdr.date ASC
        """
        cursor.execute(sql, (province_name,))
        return cursor.fetchall()
    finally:
        if conn:
            conn.close()


def query_history_for_predict(target_type: str, target_name: str) -> List[Dict[str, Any]]:
    if target_type == "city":
        return query_city_history_for_predict(target_name)
    return query_province_avg_history_for_predict(target_name)


def build_next_day_features(history_rows: List[Dict[str, Any]], meta: Dict[str, Any], feature_scaler) -> Dict[str, Any]:
    if not history_rows:
        raise HistoryDataError("历史降雨数据为空，无法构造预测特征")

    df = pd.DataFrame(history_rows)
    if df.empty:
        raise HistoryDataError("历史降雨数据为空，无法构造预测特征")

    df["date"] = pd.to_datetime(df["date"])
    df["rainfall"] = pd.to_numeric(df["rainfall"], errors="coerce").fillna(0.0)
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

    full_dates = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    df = (
        df.set_index("date")
          .reindex(full_dates)
          .rename_axis("date")
          .reset_index()
    )
    df["rainfall"] = df["rainfall"].fillna(0.0)

    df["lag_1"] = df["rainfall"].shift(1)
    df["lag_2"] = df["rainfall"].shift(2)
    df["lag_3"] = df["rainfall"].shift(3)
    df["lag_7"] = df["rainfall"].shift(7)

    df["rolling_mean_7"] = df["rainfall"].shift(1).rolling(7).mean()
    df["rolling_max_7"] = df["rainfall"].shift(1).rolling(7).max()
    df["rolling_sum_7"] = df["rainfall"].shift(1).rolling(7).sum()
    df["rolling_std_7"] = df["rainfall"].shift(1).rolling(7).std()

    rainy_hist = (df["rainfall"] > 0).astype(int)
    df["recent_rain_days_7"] = rainy_hist.shift(1).rolling(7).sum()
    df["prev_is_rainy"] = rainy_hist.shift(1)

    streaks = []
    streak = 0
    for val in df["rainfall"].tolist():
        if float(val) > 0:
            streak += 1
        else:
            streak = 0
        streaks.append(streak)

    df["hist_rain_streak"] = streaks
    df["prev_rain_streak"] = df["hist_rain_streak"].shift(1)

    df["month"] = df["date"].dt.month
    df["doy"] = df["date"].dt.dayofyear
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12.0)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12.0)
    df["doy_sin"] = np.sin(2 * np.pi * df["doy"] / 365.0)
    df["doy_cos"] = np.cos(2 * np.pi * df["doy"] / 365.0)

    # 兼容旧字段
    df["is_rainy"] = rainy_hist
    df["rain_streak"] = df["hist_rain_streak"]

    df = df.reset_index(drop=True)

    last_date = df["date"].iloc[-1]
    next_date = last_date + pd.Timedelta(days=1)

    hist_rain = df["rainfall"].tolist()
    if len(hist_rain) < 7:
        raise HistoryDataError("历史数据不足 7 天，无法预测")

    next_row = {
        "date": next_date,
        "rainfall": 0.0,
        "lag_1": float(hist_rain[-1]),
        "lag_2": float(hist_rain[-2]) if len(hist_rain) >= 2 else 0.0,
        "lag_3": float(hist_rain[-3]) if len(hist_rain) >= 3 else 0.0,
        "lag_7": float(hist_rain[-7]),
        "rolling_mean_7": float(np.mean(hist_rain[-7:])),
        "rolling_max_7": float(np.max(hist_rain[-7:])),
        "rolling_sum_7": float(np.sum(hist_rain[-7:])),
        "rolling_std_7": float(np.std(hist_rain[-7:], ddof=1)) if len(hist_rain[-7:]) > 1 else 0.0,
        "recent_rain_days_7": float(np.sum(np.array(hist_rain[-7:]) > 0)),
        "prev_is_rainy": 1.0 if hist_rain[-1] > 0 else 0.0,
        "prev_rain_streak": float(df["hist_rain_streak"].iloc[-1]),
        "is_rainy": 1.0 if hist_rain[-1] > 0 else 0.0,
        "rain_streak": float(df["hist_rain_streak"].iloc[-1]),
        "month": next_date.month,
        "doy": next_date.dayofyear,
    }

    next_row["month_sin"] = float(np.sin(2 * np.pi * next_row["month"] / 12.0))
    next_row["month_cos"] = float(np.cos(2 * np.pi * next_row["month"] / 12.0))
    next_row["doy_sin"] = float(np.sin(2 * np.pi * next_row["doy"] / 365.0))
    next_row["doy_cos"] = float(np.cos(2 * np.pi * next_row["doy"] / 365.0))

    seq_cols = meta["seq_cols"]
    cls_cols = meta["cls_cols"]
    time_step = int(meta["time_step"])

    df_future = pd.concat([df, pd.DataFrame([next_row])], ignore_index=True)

    for col in set(seq_cols + cls_cols):
        if col not in df_future.columns:
            df_future[col] = 0.0

    seq_raw = df_future[seq_cols].astype(np.float32).values
    seq_scaled = feature_scaler.transform(seq_raw)

    if len(seq_scaled) < time_step:
        raise HistoryDataError(f"历史数据不足 {time_step} 天，无法构造 LSTM 输入")

    x_seq = seq_scaled[-time_step:].reshape(1, time_step, len(seq_cols)).astype(np.float32)
    x_cls = df_future.iloc[-1:][cls_cols].astype(np.float32).values

    return {
        "next_date": next_date.date(),
        "x_seq": x_seq,
        "x_cls": x_cls
    }


def get_level_names(meta: Dict[str, Any], class_count: int) -> Dict[int, str]:
    names = meta.get("names")
    if isinstance(names, dict) and names:
        return {int(k): str(v) for k, v in names.items()}

    result = {}
    for i in range(class_count):
        result[i] = DEFAULT_LEVEL_NAMES.get(i, f"等级{i}")
    return result


def predict_next_days(history_rows: List[Dict[str, Any]], assets: Dict[str, Any], days: int = 1) -> Dict[str, Any]:
    if days <= 0:
        raise InvalidParamError("days 必须大于 0")

    rf_model = assets["rf_model"]
    level_model = assets["level_model"]
    feature_scaler = assets["feature_scaler"]
    meta = assets["meta"]

    threshold = float(meta.get("threshold", 0.5))
    level_map = meta.get("level_map", {0: 5.0, 1: 17.5, 2: 37.5, 3: 75.0})
    level_keys = sorted(level_map.keys())
    level_values = np.array([float(level_map[k]) for k in level_keys], dtype=np.float32)
    level_names = get_level_names(meta, len(level_keys))

    rolling_rows = []
    for row in history_rows:
        rolling_rows.append({
            "date": row["date"],
            "rainfall": float(row["rainfall"]) if row["rainfall"] is not None else 0.0
        })

    daily_results = []

    for _ in range(days):
        built = build_next_day_features(rolling_rows, meta, feature_scaler)
        next_date = built["next_date"]
        x_seq = built["x_seq"]
        x_cls = built["x_cls"]

        rain_prob = float(rf_model.predict_proba(x_cls)[0, 1])
        rain_prob = float(np.clip(rain_prob, 0.0, 1.0))
        will_rain = rain_prob >= threshold

        level_prob = level_model.predict(x_seq, verbose=0)[0].astype(np.float32)
        prob_sum = float(level_prob.sum())
        if prob_sum <= 0:
            level_prob = np.ones_like(level_prob) / len(level_prob)
        else:
            level_prob = level_prob / prob_sum

        weighted_rainfall = float(np.dot(level_prob[:len(level_values)], level_values))

        if will_rain:
            rainfall_mm = round(max(0.1, weighted_rainfall), 2)
            level_code = int(np.argmax(level_prob))
            level_name = level_names.get(level_code, f"等级{level_code}")
        else:
            rainfall_mm = 0.0
            level_code = -1
            level_name = "无雨"

        level_prob_dict = {
            level_names.get(i, f"等级{i}"): round(float(level_prob[i]), 4)
            for i in range(min(len(level_prob), len(level_keys)))
        }

        day_result = {
            "date": next_date.strftime("%Y-%m-%d"),
            "predicted_rainfall_mm": rainfall_mm,
            "rain_probability": round(rain_prob, 4),
            "will_rain": bool(will_rain),
            "rain_level_code": level_code,
            "rain_level_name": level_name,
            "rain_level_probabilities_if_rain": level_prob_dict
        }
        daily_results.append(day_result)

        rolling_rows.append({
            "date": next_date,
            "rainfall": rainfall_mm
        })

    return {
        "tomorrow": daily_results[0] if daily_results else None,
        "daily": daily_results
    }


def predict_region(target_type: str, target_name: str, days: int = 1) -> Dict[str, Any]:
    target_type = normalize_target_type(target_type)
    target_name = normalize_target_name(target_type, target_name)

    assets = load_predict_assets(target_type, target_name)
    history_rows = query_history_for_predict(target_type, target_name)

    if not history_rows:
        raise HistoryDataError(f"未找到 {target_name} 的历史降雨数据")

    meta = assets["meta"]
    result = predict_next_days(history_rows, assets, days=days)
    last_observed_date = pd.to_datetime(history_rows[-1]["date"]).strftime("%Y-%m-%d")

    return {
        "target_type": target_type,
        "target_name": target_name,
        "predict_days": days,
        "last_observed_date": last_observed_date,
        "model_info": {
            "model_dir": assets["model_dir"],
            "time_step": int(meta.get("time_step", 0)),
            "threshold": float(meta.get("threshold", 0.5)),
            "seq_cols": meta.get("seq_cols", []),
            "cls_cols": meta.get("cls_cols", [])
        },
        "tomorrow": result["tomorrow"],
        "daily": result["daily"]
    }