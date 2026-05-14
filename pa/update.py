import json
import pymysql
from pymysql.err import OperationalError, ProgrammingError

# -------------------------- 请修改这里的数据库配置 --------------------------
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "1111",
    "db": "rain",
    "charset": "utf8mb4"
}
JSON_FILE_PATH = "citys_fixed.json"
# -----------------------------------------------------------------------------

def load_json_data(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"读取JSON失败：{e}")
        return []

def insert_to_db(data_list):
    conn = None
    cursor = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 1. 先获取 province 表中所有合法的 id
        cursor.execute("SELECT id FROM province")
        valid_province_ids = {str(row[0]) for row in cursor.fetchall()}
        print(f"✅ 已加载 {len(valid_province_ids)} 个有效省份ID")

        # 2. 过滤掉不存在省份的城市（解决外键报错）
        valid_cities = []
        for item in data_list:
            pid = str(item["province_id"])
            if pid in valid_province_ids:
                valid_cities.append((item["id"], item["name"], item["province_id"]))

        print(f"✅ 有效城市数据：{len(valid_cities)} 条")

        if not valid_cities:
            print("❌ 没有可导入的有效城市，请先导入省份数据")
            return

        # 3. 批量插入（存在则更新）
        sql = """
        INSERT INTO city (id, name, province_id)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
        name = VALUES(name),
        province_id = VALUES(province_id)
        """
        cursor.executemany(sql, valid_cities)
        conn.commit()
        print(f"✅ 导入成功！共导入 {len(valid_cities)} 条城市数据")

    except OperationalError:
        print("❌ 数据库连接失败")
    except ProgrammingError:
        print("❌ 表不存在，请先建表")
    except Exception as e:
        print(f"❌ 插入失败：{e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    city_data = load_json_data(JSON_FILE_PATH)
    if city_data:
        insert_to_db(city_data)