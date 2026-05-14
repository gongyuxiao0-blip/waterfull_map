
import time
import random
from datetime import datetime
import pymysql
import requests_cache
from retry_requests import retry
import openmeteo_requests
import pandas as pd

# =========================
# 1. MySQL 配置
# =========================
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "1111",
    "database": "rain",
    "charset": "utf8mb4",
    "autocommit": False
}

# =========================
# 2. 历史时间范围
# =========================
START_DATE = "2022-01-01"
END_DATE = "2026-04-24"

# =========================
# 3. 请求参数
# =========================
TIMEZONE = "Asia/Shanghai"

# 每个城市请求后的随机休眠，降低请求密度
SLEEP_MIN = 0.4
SLEEP_MAX = 1.2

# 每处理多少个城市提交一次
COMMIT_EVERY = 20


def get_db_connection():
    return pymysql.connect(**MYSQL_CONFIG)


def get_openmeteo_client():
    """
    使用缓存 + 重试，降低重复请求和偶发失败影响
    """
    cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.3)
    return openmeteo_requests.Client(session=retry_session)


def fetch_cities(cursor):
    """
    读取所有有经纬度的城市
    """
    sql = """
    SELECT id, name, latitude, longitude
    FROM city
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
    ORDER BY id
    """
    cursor.execute(sql)
    return cursor.fetchall()


def fetch_daily_precipitation(openmeteo, latitude, longitude, start_date, end_date, timezone):
    """
    调用 Open-Meteo Historical Weather API，获取日降雨量
    返回 DataFrame: date, precipitation_sum
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "precipitation_sum",
        "start_date": start_date,
        "end_date": end_date,
        "timezone": timezone
    }

    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]

    daily = response.Daily()
    daily_precipitation_sum = daily.Variables(0).ValuesAsNumpy()

    daily_data = {
        "date": pd.date_range(
            start=pd.to_datetime(daily.Time(), unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left"
        ),
        "precipitation_sum": daily_precipitation_sum
    }

    df = pd.DataFrame(data=daily_data)

    # 转成中国项目里更合适的 date 字段
    # 这里只保留日期部分
    df["date"] = pd.to_datetime(df["date"]).dt.date

    return df


def upsert_rainfall(cursor, city_id, city_name, date_value, rainfall_value):
    """
    写入 city_daily_rainfall：
    - 不存在则插入
    - 已存在则更新 rainfall / name / created_at
    """
    sql = """
    INSERT INTO city_daily_rainfall (city_id, date, rainfall, created_at, name)
    VALUES (%s, %s, %s, NOW(), %s)
    ON DUPLICATE KEY UPDATE
        rainfall = VALUES(rainfall),
        name = VALUES(name),
        created_at = NOW()
    """
    cursor.execute(sql, (city_id, date_value, rainfall_value, city_name))


def normalize_rainfall(value):
    """
    清洗降雨量：
    - None -> 0.0
    - NaN -> 0.0
    - 保留 1 位小数，适配 decimal(5,1)
    """
    if pd.isna(value):
        return 0.0
    return round(float(value), 1)


def process_one_city(openmeteo, cursor, city_row):
    city_id, city_name, latitude, longitude = city_row
    print(f"\n[开始] 城市: {city_name} ({latitude}, {longitude})")

    try:
        df = fetch_daily_precipitation(
            openmeteo=openmeteo,
            latitude=float(latitude),
            longitude=float(longitude),
            start_date=START_DATE,
            end_date=END_DATE,
            timezone=TIMEZONE
        )

        inserted_or_updated = 0

        for _, row in df.iterrows():
            date_value = row["date"]
            rainfall_value = normalize_rainfall(row["precipitation_sum"])
            upsert_rainfall(cursor, city_id, city_name, date_value, rainfall_value)
            inserted_or_updated += 1

        print(f"[完成] {city_name} 写入/更新 {inserted_or_updated} 条")
        return True, inserted_or_updated

    except Exception as e:
        print(f"[失败] {city_name} 抓取异常: {e}")
        return False, 0


def main():
    start_time = datetime.now()
    print(f"任务开始时间: {start_time}")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cities = fetch_cities(cursor)
        total_cities = len(cities)

        if total_cities == 0:
            print("未找到有经纬度的城市，请先补齐 city.latitude / city.longitude。")
            return

        print(f"共读取到 {total_cities} 个有经纬度的城市。")

        openmeteo = get_openmeteo_client()

        success_count = 0
        fail_count = 0
        total_rows = 0

        for idx, city_row in enumerate(cities, start=1):
            print(f"\n========== 进度 {idx}/{total_cities} ==========")

            ok, rows = process_one_city(openmeteo, cursor, city_row)

            if ok:
                success_count += 1
                total_rows += rows
            else:
                fail_count += 1

            # 分批提交，降低长事务风险
            if idx % COMMIT_EVERY == 0:
                conn.commit()
                print(f"[提交] 已处理 {idx} 个城市，数据库已提交。")

            # 基础防抖：随机休眠
            sleep_seconds = random.uniform(SLEEP_MIN, SLEEP_MAX)
            time.sleep(sleep_seconds)

        conn.commit()

        end_time = datetime.now()
        print("\n==============================")
        print("全部任务完成")
        print(f"开始时间: {start_time}")
        print(f"结束时间: {end_time}")
        print(f"成功城市数: {success_count}")
        print(f"失败城市数: {fail_count}")
        print(f"总写入/更新记录数: {total_rows}")
        print("==============================")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[致命错误] 程序异常，已回滚。错误: {e}")

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()