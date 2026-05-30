import json
import requests
from pydantic import BaseModel, Field
from langchain_core.tools import tool
import sys
from pathlib import Path

# 当前文件：data_input/agent/agent_tools.py
# parent 是 agent 目录
# parent.parent 是 data_input 目录
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
from .db import get_db_connection


class RecentRainInput(BaseModel):
    target_type: str = Field(description="地区类型，只能是 city 或 province")
    target_name: str = Field(description="地区名称，例如 武汉市、湖北省")
    days: int = Field(default=15, description="查询最近多少天的数据，默认15天")


@tool(args_schema=RecentRainInput)
def query_recent_rainfall(target_type: str, target_name: str, days: int = 15) -> str:
    """
    查询某个城市或省份最近若干天的历史降雨量。
    适合回答：最近15天降雨趋势、历史降雨情况、过去几天雨量变化等问题。
    """
    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            if target_type == "city":
                sql = """
                SELECT date, rainfall
                FROM city_daily_rainfall
                WHERE name = %s
                ORDER BY date DESC
                LIMIT %s
                """
                cursor.execute(sql, (target_name, days))

            elif target_type == "province":
                sql = """
                SELECT pdr.date, pdr.total_rainfall AS rainfall
                FROM province_daily_rainfall pdr
                JOIN province p ON pdr.province_id = p.id
                WHERE p.name = %s
                ORDER BY pdr.date DESC
                LIMIT %s
                """
                cursor.execute(sql, (target_name, days))

            else:
                return json.dumps({
                    "code": 400,
                    "msg": "target_type 只能是 city 或 province"
                }, ensure_ascii=False)

            rows = cursor.fetchall()

        rows = list(reversed(rows))

        return json.dumps({
            "code": 200,
            "target_type": target_type,
            "target_name": target_name,
            "days": days,
            "data": rows
        }, ensure_ascii=False, default=str)

    finally:
        conn.close()


class PredictRainInput(BaseModel):
    target_type: str = Field(description="地区类型，只能是 city 或 province")
    target_name: str = Field(description="地区名称，例如 武汉市、湖北省")


@tool(args_schema=PredictRainInput)
def predict_future_rainfall(target_type: str, target_name: str) -> str:
    """
    调用降雨预测接口，查询某个城市或省份未来7天的降雨预测。
    适合回答：未来会不会下雨、未来7天雨量、降雨风险、雨强等级等问题。
    """
    url = "http://127.0.0.1:5000/api/predict/rain"

    params = {
        "target_type": target_type,
        "target_name": target_name
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        return json.dumps(response.json(), ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "code": 500,
            "msg": f"预测接口调用失败：{str(e)}"
        }, ensure_ascii=False)