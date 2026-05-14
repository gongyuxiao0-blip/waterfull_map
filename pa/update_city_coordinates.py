import os
import json
import pymysql

# =========================
# 1. MySQL 配置
# =========================
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "1111",   # 改成你的密码
    "database": "rain",
    "charset": "utf8mb4"
}

# =========================
# 2. GeoJSON 文件夹路径
# =========================
PROVINCE_DIR = r"F:\test_work\pa\province"   # 改成你的实际路径


def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(**MYSQL_CONFIG)


def update_city_coordinate(cursor, city_name, longitude, latitude):
    """
    更新 city 表中的经纬度
    只更新已有城市，不插入新城市
    返回影响行数
    """
    sql = """
    UPDATE city
    SET longitude = %s,
        latitude = %s
    WHERE name = %s
    """
    affected_rows = cursor.execute(sql, (longitude, latitude, city_name))
    return affected_rows


def process_geojson_file(filepath, cursor):
    """
    处理单个 GeoJSON 文件
    返回: (updated_count, skipped_count)
    """
    updated_count = 0
    skipped_count = 0

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    if not isinstance(features, list):
        print(f"[警告] 文件结构异常，features 不是列表：{filepath}")
        return 0, 0

    for feature in features:
        properties = feature.get("properties", {})
        city_name = properties.get("name")
        center = properties.get("center")

        # 跳过无效数据
        if not city_name or not center or not isinstance(center, list) or len(center) < 2:
            print(f"[跳过] 无有效 center/name: {filepath}")
            skipped_count += 1
            continue

        # GeoJSON center: [longitude, latitude]
        longitude = center[0]
        latitude = center[1]

        try:
            affected_rows = update_city_coordinate(cursor, city_name, longitude, latitude)

            if affected_rows > 0:
                print(f"[更新成功] {city_name} -> 经度: {longitude}, 纬度: {latitude}")
                updated_count += 1
            else:
                print(f"[跳过] 数据库无此城市: {city_name}")
                skipped_count += 1

        except Exception as e:
            print(f"[错误] 更新城市失败: {city_name}, 错误: {e}")
            skipped_count += 1

    return updated_count, skipped_count


def main():
    if not os.path.exists(PROVINCE_DIR):
        print(f"[错误] 文件夹不存在: {PROVINCE_DIR}")
        return

    json_files = [f for f in os.listdir(PROVINCE_DIR) if f.endswith(".json")]

    if not json_files:
        print(f"[提示] 未找到任何 JSON 文件: {PROVINCE_DIR}")
        return

    print(f"共发现 {len(json_files)} 个省份 GeoJSON 文件，开始处理...\n")

    total_updated = 0
    total_skipped = 0

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for filename in json_files:
            filepath = os.path.join(PROVINCE_DIR, filename)
            print(f"\n===== 正在处理文件: {filename} =====")

            updated_count, skipped_count = process_geojson_file(filepath, cursor)

            total_updated += updated_count
            total_skipped += skipped_count

        conn.commit()

        print("\n==============================")
        print("批量更新完成")
        print(f"成功更新城市数: {total_updated}")
        print(f"跳过/失败数: {total_skipped}")
        print("==============================")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[致命错误] 批量更新失败，已回滚。错误: {e}")

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()