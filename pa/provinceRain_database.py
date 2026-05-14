import pymysql
from datetime import date

# 数据库配置
MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "1111",
    "database": "rain",
    "charset": "utf8mb4"
}


def update_province_rainfall(only_today=False):
    """
    汇总 city_daily_rainfall -> province_daily_rainfall

    :param only_today: True 只更新今天数据，False 更新全部
    """

    # SQL主体
    base_sql = """
    INSERT INTO province_daily_rainfall (province_id, date, total_rainfall, created_at)
    SELECT
        c.province_id,
        cdr.date,
        SUM(cdr.rainfall) AS total_rainfall,
        NOW() AS created_at
    FROM city_daily_rainfall cdr
    JOIN city c ON cdr.city_id = c.id
    {where_clause}
    GROUP BY c.province_id, cdr.date
    ON DUPLICATE KEY UPDATE
        total_rainfall = VALUES(total_rainfall),
        created_at = VALUES(created_at);
    """

    where_clause = ""
    if only_today:
        where_clause = "WHERE cdr.date = CURDATE()"

    sql = base_sql.format(where_clause=where_clause)

    conn = None
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()

        print("开始汇总省级降雨量数据...")

        affected_rows = cursor.execute(sql)
        conn.commit()

        print(f"执行成功！影响行数: {affected_rows}")

    except Exception as e:
        if conn:
            conn.rollback()
        print("执行失败:", e)

    finally:
        if conn:
            conn.close()
        print("数据库连接已关闭")


if __name__ == "__main__":
    # 方式1：更新全部历史数据
    update_province_rainfall(only_today=False)

    # 方式2：只更新今天（推荐用于定时任务）
    # update_province_rainfall(only_today=True)