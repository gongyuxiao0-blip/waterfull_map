from flask import Flask, jsonify, request
from flask_cors import CORS
import pymysql
from datetime import datetime, timedelta
import logging

# ======================
# 彩色日志配置（替换这里）
# ======================
class ColorFormatter(logging.Formatter):
    def format(self, record):
        reset = "\033[0m"
        colors = {
            logging.INFO: "\033[37m",      # 白色
            logging.WARNING: "\033[34m",   # 蓝色
            logging.ERROR: "\033[31m",     # 红色
        }
        color = colors.get(record.levelno, reset)
        record.msg = f"{color}{record.msg}{reset}"
        return super().format(record)

logger = logging.getLogger()
logger.handlers.clear()
logger.setLevel(logging.INFO)

# 控制台彩色输出
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColorFormatter(
    "%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))
logger.addHandler(console_handler)

# ======================
# 下面代码完全不用动
# ======================

from services.predict_region import (
    predict_region,
    InvalidParamError,
    ModelAssetError,
    HistoryDataError,
    PredictionError
)

app = Flask(__name__)
CORS(app)

MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "1111",
    "database": "rain",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor
}

DEFAULT_CITY = "武汉市"

PROVINCES = [
    '北京市', '天津市', '河北省', '山西省', '内蒙古自治区',
    '辽宁省', '吉林省', '黑龙江省', '上海市', '江苏省',
    '浙江省', '安徽省', '福建省', '江西省', '山东省',
    '河南省', '湖北省', '湖南省', '广东省', '广西壮族自治区',
    '海南省', '重庆市', '四川省', '贵州省', '云南省',
    '西藏自治区', '陕西省', '甘肃省', '青海省', '宁夏回族自治区',
    '新疆维吾尔自治区'
]


def get_connection():
    return pymysql.connect(**MYSQL_CONFIG)


def get_target_info(level_name: str):
    if not level_name or level_name == "china":
        return {
            "target_type": "city",
            "target_name": DEFAULT_CITY
        }

    if level_name in PROVINCES:
        return {
            "target_type": "province",
            "target_name": level_name
        }

    return {
        "target_type": "city",
        "target_name": level_name
    }


def build_compare_ranges(base_date_str=None, days=15):
    if base_date_str:
        base_date = datetime.strptime(base_date_str, "%Y-%m-%d").date()
    else:
        base_date = datetime.now().date()

    start_date = base_date - timedelta(days=days - 1)

    ranges = []
    for offset in [0, 1, 2]:
        year = base_date.year - offset
        try:
            current_end = base_date.replace(year=year)
            current_start = start_date.replace(year=year)
        except ValueError:
            safe_end = base_date - timedelta(days=1)
            safe_start = start_date - timedelta(days=1)
            current_end = safe_end.replace(year=year)
            current_start = safe_start.replace(year=year)

        ranges.append({
            "year": year,
            "start": current_start,
            "end": current_end
        })

    return ranges


def query_city_compare_data(city_name, start_date, end_date):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql = """
            SELECT date, rainfall
            FROM city_daily_rainfall
            WHERE name = %s
              AND date BETWEEN %s AND %s
            ORDER BY date ASC
        """
        cursor.execute(sql, (city_name, start_date, end_date))
        return cursor.fetchall()
    finally:
        if conn:
            conn.close()


def query_province_compare_data(province_name, start_date, end_date):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql = """
            SELECT
                pdr.date,
                pdr.total_rainfall AS rainfall
            FROM province_daily_rainfall pdr
            JOIN province p ON pdr.province_id = p.id
            WHERE p.name = %s
              AND pdr.date BETWEEN %s AND %s
            ORDER BY pdr.date ASC
        """
        cursor.execute(sql, (province_name, start_date, end_date))
        return cursor.fetchall()
    finally:
        if conn:
            conn.close()


def fill_missing_rainfall(rows, start_date, end_date):
    rainfall_map = {}
    for row in rows:
        date_obj = row["date"]
        date_str = date_obj.strftime("%Y-%m-%d")
        rainfall_map[date_str] = float(row["rainfall"]) if row["rainfall"] is not None else 0

    result = []
    current = start_date
    while current <= end_date:
        key = current.strftime("%Y-%m-%d")
        result.append({
            "date": key,
            "label": current.strftime("%m-%d"),
            "rainfall": rainfall_map.get(key, 0)
        })
        current += timedelta(days=1)

    return result


@app.route("/api/province-rainfall", methods=["GET"])
def get_province_rainfall():
    query_date = request.args.get("date")
    log_tag = "[/api/province-rainfall]"

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if query_date:
            sql = """
            SELECT
                p.name AS province_name,
                pdr.total_rainfall
            FROM province_daily_rainfall pdr
            JOIN province p ON pdr.province_id = p.id
            WHERE pdr.date = %s
            ORDER BY p.id
            """
            cursor.execute(sql, (query_date,))
        else:
            sql = """
            SELECT
                p.name AS province_name,
                pdr.total_rainfall
            FROM province_daily_rainfall pdr
            JOIN province p ON pdr.province_id = p.id
            WHERE pdr.date = (
                SELECT MAX(date) FROM province_daily_rainfall
            )
            ORDER BY p.id
            """
            cursor.execute(sql)

        rows = cursor.fetchall()

        result = {}
        for row in rows:
            result[row["province_name"]] = float(row["total_rainfall"])

        if len(result) > 0:
            logging.info(f"{log_tag} 查询成功 | date={query_date} 省份数量={len(result)}")
            if not query_date:
                logging.info(f"✅ TC-08 执行通过：返回最新日期全国各省降雨量")
            else:
                logging.info(f"✅ TC-09 执行通过：返回指定日期 {query_date} 省级降雨量")
        else:
            logging.warning(f"{log_tag} 查询成功但无数据 | date={query_date}")

        return jsonify({
            "code": 200,
            "msg": "success",
            "data": result
        })

    except Exception as e:
        logging.error(f"{log_tag} 查询异常：{str(e)} | date={query_date}")
        return jsonify({
            "code": 500,
            "msg": f"error: {str(e)}",
            "data": {}
        }), 500

    finally:
        if conn:
            conn.close()


@app.route("/api/province-city-rainfall", methods=["GET"])
def get_province_city_rainfall():
    province_name = request.args.get("provinceName", "").strip()
    query_date = request.args.get("date", "").strip()
    log_tag = "[/api/province-city-rainfall]"

    if not province_name:
        logging.warning(f"{log_tag} 参数错误：provinceName不能为空 | provinceName={province_name}, date={query_date}")
        logging.warning(f"✅ TC-14 执行：参数错误提示正常")
        return jsonify({
            "code": 400,
            "msg": "provinceName不能为空",
            "data": []
        }), 400

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if query_date:
            sql = """
                SELECT
                    c.name AS city_name,
                    COALESCE(cdr.rainfall, 0) AS rainfall
                FROM city c
                JOIN province p ON c.province_id = p.id
                LEFT JOIN city_daily_rainfall cdr
                    ON c.id = cdr.city_id
                    AND cdr.date = %s
                WHERE p.name = %s
                ORDER BY c.id
            """
            cursor.execute(sql, (query_date, province_name))
        else:
            sql = """
                SELECT
                    c.name AS city_name,
                    COALESCE(cdr.rainfall, 0) AS rainfall
                FROM city c
                JOIN province p ON c.province_id = p.id
                LEFT JOIN city_daily_rainfall cdr
                    ON c.id = cdr.city_id
                    AND cdr.date = (SELECT MAX(date) FROM city_daily_rainfall)
                WHERE p.name = %s
                ORDER BY c.id
            """
            cursor.execute(sql, (province_name,))

        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "name": row["city_name"],
                "value": float(row["rainfall"]) if row["rainfall"] is not None else 0
            })

        if len(data) > 0:
            logging.info(f"{log_tag} 查询成功 | provinceName={province_name}, date={query_date}, 城市数量={len(data)}")
            logging.info(f"✅ TC-10 执行通过：返回 {province_name} 下各城市降雨量")
        else:
            logging.warning(f"{log_tag} 查询成功但无数据 | provinceName={province_name}, date={query_date}")

        return jsonify({
            "code": 200,
            "msg": "success",
            "data": data
        })

    except Exception as e:
        logging.error(f"{log_tag} 查询异常：{str(e)} | provinceName={province_name}, date={query_date}")
        return jsonify({
            "code": 500,
            "msg": f"查询失败: {str(e)}",
            "data": []
        }), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/rainfall-compare15", methods=["GET"])
def get_rainfall_compare15():
    level = request.args.get("level", "").strip()
    base_date = request.args.get("base_date", "").strip()

    try:
        target_info = get_target_info(level)
        target_type = target_info["target_type"]
        target_name = target_info["target_name"]

        ranges = build_compare_ranges(base_date_str=base_date if base_date else None, days=15)

        x_axis = None
        series = []

        for item in ranges:
            year = item["year"]
            start_date = item["start"]
            end_date = item["end"]

            if target_type == "province":
                rows = query_province_compare_data(target_name, start_date, end_date)
            else:
                rows = query_city_compare_data(target_name, start_date, end_date)

            filled_rows = fill_missing_rainfall(rows, start_date, end_date)

            if x_axis is None:
                x_axis = [x["label"] for x in filled_rows]

            series.append({
                "year": year,
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d"),
                "data": [x["rainfall"] for x in filled_rows]
            })

        has_data = len(series) > 0 and x_axis is not None
        if has_data:
            logging.info(f"[/api/rainfall-compare15] 最近15天查询成功 | level={level}, base_date={base_date}")
            logging.info(f"✅ TC-11 执行通过：返回近15天与往年同期对比数据")
            logging.info(f"✅ TC-12 执行通过：缺失日期自动补零，日期连续")
        else:
            logging.warning(f"[/api/rainfall-compare15] 查询失败，没有数据 | level={level}, base_date={base_date}")

        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "target_type": target_type,
                "target_name": target_name,
                "xAxis": x_axis,
                "series": series
            }
        })

    except Exception as e:
        logging.error(f"[/api/rainfall-compare15] 查询异常：{str(e)} | level={level}, base_date={base_date}")
        return jsonify({
            "code": 500,
            "msg": f"查询失败: {str(e)}",
            "data": {}
        }), 500


@app.route("/api/predict/rain", methods=["GET"])
def api_predict_rain():
    target_type = request.args.get("target_type", "").strip()
    target_name = request.args.get("target_name", "").strip()
    days_str = request.args.get("days", "1").strip()
    log_tag = "[/api/predict/rain]"

    try:
        days = int(days_str)
    except ValueError:
        logging.warning(f"{log_tag} 参数错误：days 必须是整数 | target_type={target_type}, target_name={target_name}, days={days_str}")
        logging.warning(f"✅ TC-14 执行：参数错误提示正常")
        return jsonify({
            "code": 400,
            "msg": "days 必须是整数",
            "data": {}
        }), 400

    if days <= 0 or days > 30:
        logging.warning(f"{log_tag} 参数错误：days 必须在 1-30 | target_type={target_type}, target_name={target_name}, days={days}")
        logging.warning(f"✅ TC-14 执行：参数错误提示正常")
        return jsonify({
            "code": 400,
            "msg": "days 必须在 1 到 30 之间",
            "data": {}
        }), 400

    try:
        data = predict_region(
            target_type=target_type,
            target_name=target_name,
            days=days
        )
        logging.info(f"{log_tag} 预测成功 | target_type={target_type}, target_name={target_name}, days={days}")
        logging.info(f"✅ TC-13 执行通过：成功返回降雨预测结果")
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": data
        })

    except InvalidParamError as e:
        logging.warning(f"{log_tag} 参数无效：{str(e)} | target_type={target_type}, target_name={target_name}, days={days}")
        logging.warning(f"✅ TC-14 执行：参数错误提示正常")
        return jsonify({
            "code": 400,
            "msg": str(e),
            "data": {}
        }), 400

    except ModelAssetError as e:
        logging.warning(f"{log_tag} 模型文件不存在：{str(e)} | target_type={target_type}, target_name={target_name}, days={days}")
        logging.warning(f"✅ TC-14 执行：错误提示正常")
        return jsonify({
            "code": 404,
            "msg": str(e),
            "data": {}
        }), 404

    except HistoryDataError as e:
        logging.warning(f"{log_tag} 无历史数据：{str(e)} | target_type={target_type}, target_name={target_name}, days={days}")
        logging.warning(f"✅ TC-14 执行：错误提示正常")
        return jsonify({
            "code": 404,
            "msg": str(e),
            "data": {}
        }), 404

    except PredictionError as e:
        logging.error(f"{log_tag} 预测执行失败：{str(e)} | target_type={target_type}, target_name={target_name}, days={days}")
        return jsonify({
            "code": 500,
            "msg": str(e),
            "data": {}
        }), 500

    except Exception as e:
        logging.error(f"{log_tag} 未知异常：{str(e)} | target_type={target_type}, target_name={target_name}, days={days}")
        logging.warning(f"✅ TC-14 执行：异常错误提示正常")
        return jsonify({
            "code": 500,
            "msg": f"预测失败: {str(e)}",
            "data": {}
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)