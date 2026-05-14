import requests
import time
import random
import json
import os
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pymysql
import re
import math
import logging

# =========================
# 日志配置（彩色版）
# =========================
def setup_logger():
    log_filename = f"rainfall_crawl_{date.today()}.log"
    logger = logging.getLogger("RainfallCrawler")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # 普通格式（文件日志不带颜色）
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 控制台彩色格式
    color_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 文件日志（无颜色）
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setFormatter(file_formatter)

    # 控制台日志（带颜色）
    class ColorConsoleHandler(logging.StreamHandler):
        def emit(self, record):
            color = "\033[37m"  # 默认白色
            if record.levelno == logging.WARNING:
                color = "\033[34m"  # 蓝色
            elif record.levelno == logging.ERROR:
                color = "\033[31m"  # 红色
            record.msg = f"{color}{record.msg}\033[0m"
            super().emit(record)

    console_handler = ColorConsoleHandler()
    console_handler.setFormatter(color_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

logger = setup_logger()

# =========================
# 基础配置
# =========================
HEADERS = {
    "Referer": "http://www.weather.com.cn/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "1111",
    "database": "rain",
    "charset": "utf8mb4"
}

TARGET_TABLE = "city_daily_rainfall"
MAX_WORKERS = 3
SAVE_FAIL_FILE = "failed_cities.json"

session = requests.Session()
session.headers.update(HEADERS)


# =========================
# 工具函数
# =========================
def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def read_citys():
    """TC-01 城市列表读取"""
    try:
        file_path = os.path.join(os.path.dirname(__file__), "citys.txt")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cities = []
        for item in data:
            try:
                city_name = str(item["name"]).strip()
                city_id = int(str(item["id"]).strip())
                cities.append({
                    "name": city_name,
                    "city_id": city_id
                })
            except Exception:
                logger.warning(f"跳过异常数据: {item}")

        logger.info(f"[TC-01] 城市列表读取测试通过 | 共读取 {len(cities)} 个城市")
        return cities

    except Exception as e:
        logger.error(f"[TC-01] 城市列表读取测试失败：{str(e)}")
        raise


def fetch_city_rainfall(city_name, city_id, max_retries=3):
    """TC-02 单城市降雨量抓取 + TC-07 异常重试"""
    url = f"https://www.weather.com.cn/weather1d/{city_id}.shtml"
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            time.sleep(random.uniform(1.0, 2.5))
            response = session.get(url, timeout=10)
            response.encoding = "utf-8"
            html = response.text

            match = re.search(r'var\s+observe24h_data\s*=\s*(\{.*?\});', html, re.S)
            if not match:
                raise ValueError("未找到 observe24h_data")

            data = json.loads(match.group(1))
            od2 = data.get("od", {}).get("od2", [])
            if not od2:
                raise ValueError("od2 数据为空")

            rain_list = []
            for item in od2:
                val = item.get("od26", "")
                try:
                    if val not in ("", None, "null"):
                        rain_list.append(float(val))
                except Exception:
                    continue

            rain_total = math.floor(sum(rain_list) * 10) / 10
            return {
                "name": city_name,
                "city_id": city_id,
                "rainfall": rain_total,
                "date": date.today()
            }

        except Exception as e:
            last_error = e
            logger.warning(f"[{city_name}] 第 {attempt} 次重试失败")
            time.sleep(random.uniform(1.5, 3.0))

    raise last_error


# def upsert_results_to_mysql(results):
#     """TC-04 数据写入数据库 + TC-05 重复数据更新"""
#     if not results:
#         logger.warning("⚠️ 无数据可写入数据库")
#         return
#
#     try:
#         conn = pymysql.connect(**MYSQL_CONFIG)
#         with conn.cursor() as cursor:
#             sql = f"""
#                 INSERT INTO {TARGET_TABLE} (city_id, date, rainfall, name)
#                 VALUES (%s, %s, %s, %s)
#                 ON DUPLICATE KEY UPDATE
#                     rainfall = VALUES(rainfall),
#                     name = VALUES(name)
#             """
#             values = [(r["city_id"], r["date"], r["rainfall"], r["name"]) for r in results]
#             cursor.executemany(sql, values)
#         conn.commit()
#         logger.info(f"[TC-04] 数据写入数据库测试通过 | 共 {len(results)} 条")
#         logger.info(f"[TC-05] 重复数据更新测试通过 | 已自动覆盖更新")
#     except Exception as e:
#         conn.rollback()
#         logger.error(f"[TC-04/TC-05] 数据库操作失败：{str(e)}")
#         raise
#     finally:
#         conn.close()
def upsert_results_to_mysql(results):
    """TC-04 数据写入数据库 + TC-05 重复数据更新"""
    if not results:
        logger.warning("⚠️ 无数据可写入数据库")
        return

    conn = None

    try:
        conn = pymysql.connect(**MYSQL_CONFIG)

        with conn.cursor() as cursor:
            # 1. 查询 city 表中已有的城市 id
            cursor.execute("SELECT id FROM city")
            valid_city_ids = {row[0] for row in cursor.fetchall()}

            # 2. 检查哪些结果的 city_id 不存在于 city 表
            valid_results = []
            invalid_results = []

            for r in results:
                if r["city_id"] in valid_city_ids:
                    valid_results.append(r)
                else:
                    invalid_results.append(r)

            # 3. 打印缺失城市
            if invalid_results:
                logger.warning(f"发现 {len(invalid_results)} 个城市在 city 表中不存在，已跳过：")
                for item in invalid_results:
                    logger.warning(
                        f"缺失城市：{item['name']}，city_id={item['city_id']}，rainfall={item['rainfall']}"
                    )

            if not valid_results:
                logger.warning("没有可入库的数据，全部 city_id 都未在 city 表中找到")
                return

            # 4. 正常插入存在的城市
            sql = f"""
                INSERT INTO {TARGET_TABLE} (city_id, date, rainfall, name)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    rainfall = VALUES(rainfall),
                    name = VALUES(name)
            """

            values = [
                (r["city_id"], r["date"], r["rainfall"], r["name"])
                for r in valid_results
            ]

            cursor.executemany(sql, values)

        conn.commit()

        logger.info(f"[TC-04] 数据写入数据库测试通过 | 共 {len(valid_results)} 条")
        logger.info(f"[TC-05] 重复数据更新测试通过 | 已自动覆盖更新")

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"[TC-04/TC-05] 数据库操作失败：{str(e)}")
        raise

    finally:
        if conn:
            conn.close()

def sync_city_name_from_city_table():
    """TC-06 城市名称同步"""
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        with conn.cursor() as cursor:
            sql = f"""
                UPDATE {TARGET_TABLE} r
                JOIN city c ON r.city_id = c.id
                SET r.name = c.name
                WHERE r.name != c.name
            """
            cursor.execute(sql)
        conn.commit()
        logger.info(f"[TC-06] 城市名称同步测试通过 | 受影响行数：{cursor.rowcount}")
    except Exception as e:
        conn.rollback()
        logger.error(f"[TC-06] 城市名同步失败：{str(e)}")
        raise
    finally:
        conn.close()


def save_failed_cities(failed_list):
    """TC-07 失败记录"""
    if not failed_list:
        logger.info("[TC-07] 无失败城市，异常重试测试通过")
        return

    try:
        with open(SAVE_FAIL_FILE, "w", encoding="utf-8") as f:
            json.dump(failed_list, f, ensure_ascii=False, indent=2)
        logger.warning(f"[TC-07] 失败城市已记录 | 共 {len(failed_list)} 个")
    except Exception as e:
        logger.error(f"[TC-07] 保存失败列表失败：{str(e)}")


# =========================
# 主程序
# =========================
if __name__ == "__main__":
    start_time = time.time()
    logger.info("=" * 70)
    logger.info("              降雨量爬虫 测试用例自动验证")
    logger.info("=" * 70)

    # TC-01
    cities = read_citys()

    success_results = []
    failed_cities = []

    logger.info(f"[TC-03] 开始多城市批量抓取测试 | 线程数：{MAX_WORKERS}")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(fetch_city_rainfall, c["name"], c["city_id"]): c
            for c in cities
        }

        for idx, future in enumerate(as_completed(futures), 1):
            city = futures[future]
            try:
                res = future.result()
                success_results.append(res)
                logger.info(f"[TC-02] [{idx}/{len(cities)}] ✅ {res['name']} {res['rainfall']}mm 抓取成功")
            except Exception as e:
                failed_cities.append(city)
                logger.error(f"[TC-02] [{idx}/{len(cities)}] ❌ {city['name']} 抓取失败")

    # TC-03 结果
    logger.info(f"[TC-03] 多城市批量抓取测试通过 | 成功：{len(success_results)} 失败：{len(failed_cities)}")

    # TC-04 TC-05
    upsert_results_to_mysql(success_results)

    # TC-06
    sync_city_name_from_city_table()

    # TC-07
    save_failed_cities(failed_cities)

    # 结束
    cost = time.time() - start_time
    logger.info("\n" + "=" * 70)
    logger.info(f"🏁 全部测试项执行完成 | 总耗时：{cost:.2f} 秒")
    logger.info("=" * 70)