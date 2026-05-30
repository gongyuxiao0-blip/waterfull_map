import os
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_deepseek import ChatDeepSeek

from .rain_tools import query_recent_rainfall, predict_future_rainfall

load_dotenv()

model = ChatDeepSeek(
    model="deepseek-chat",
    api_key="sk-ef0c900f0ce9434fb786828453dab4ac",
    base_url="https://api.deepseek.com",
    temperature=0
)

tools = [
    query_recent_rainfall,
    predict_future_rainfall
]

system_prompt = """
你是一个气象数据智能分析助手，服务于“基于 ECharts 的中国降雨量时空分布可视化系统”。

你不能凭空编造降雨数据。
当用户询问历史降雨时，必须调用 query_recent_rainfall 工具。
当用户询问未来降雨、预测、风险时，必须调用 predict_future_rainfall 工具。
当用户要求综合分析时，应先调用相关工具，再根据综合分析时，应先调用相关工具，再根据工具结果进行总结。

系统支持的地区类型：
- city：城市，例如 武汉市、北京市、上海市
- province：省份，例如 湖北省、广东省

回答要求：
1. 先给出简洁结论。
2. 再说明依据的数据。
3. 如果预测接口返回模型缺失或数据不足，要明确说明，不要编造。
4. 输出风格适合前端展示。
"""

rain_agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=system_prompt
)