import os
import pymysql

# MySQL 配置（你提供的配置）
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "1111",
    "database": "rain",
    "charset": "utf8mb4"
}

# 要创建文件夹的根路径
BASE_DIR = r"F:\test_work\pa\data_input\model_output_rf_lstm_rainlevel4_fast\province"


def create_city_folders():
    count = 0
    # 1. 连接数据库
    connection = pymysql.connect(**MYSQL_CONFIG)
    try:
        with connection.cursor() as cursor:
            # 2. 查询所有省份名称
            sql = "SELECT name FROM province"
            cursor.execute(sql)

            # 获取所有省份名（返回元组列表，提取name）
            provinces = cursor.fetchall()

            # 3. 遍历城市名，创建文件夹
            for province in provinces:
                province_name = province[0]  # 取出城市名称
                # 拼接完整路径
                province_folder = os.path.join(BASE_DIR, province_name)

                # 如果文件夹不存在则创建
                if not os.path.exists(province_folder):
                    os.makedirs(province_folder)
                    print(f"✅ 创建成功：{province_folder}")
                    count += 1
                else:
                    print(f"ℹ️ 已存在：{province_folder}")

    finally:
        # 确保数据库连接关闭
        connection.close()
        print("\n🎉 所有province文件夹处理完成！")
        print(count)


if __name__ == "__main__":
    create_city_folders()