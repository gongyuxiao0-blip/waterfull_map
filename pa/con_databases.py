import pymysql

MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "1111",
    "database": "rain",
    "charset": "utf8mb4"
}

try:
    conn = pymysql.connect(**MYSQL_CONFIG)
    print("数据库连接成功")
    conn.close()
except Exception as e:
    print("数据库连接失败：", e)