import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

def get_db_connection():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "1111"),
        database=os.getenv("MYSQL_DATABASE", "rain"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )
# if __name__ == "__main__":
#     try:
#         # 尝试获取连接
#         conn = get_db_connection()
#         print("✅ 数据库连接成功！")
#
#         # 进一步测试：执行一条简单查询
#         with conn.cursor() as cursor:
#             cursor.execute("SELECT VERSION()")
#             result = cursor.fetchone()
#             print("✅ MySQL 版本:", result)
#
#         conn.close()
#         print("✅ 测试完成，连接已关闭")
#
#     except Exception as e:
#         print("❌ 数据库连接失败：", e)