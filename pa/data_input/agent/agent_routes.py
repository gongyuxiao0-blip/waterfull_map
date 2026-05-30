from flask import Blueprint, request, jsonify
from langchain_core.messages import HumanMessage

from .rain_agent import rain_agent

agent_bp = Blueprint("agent_bp", __name__)


@agent_bp.route("/api/agent/chat", methods=["POST"])
def agent_chat():
    data = request.get_json()

    question = data.get("question", "")
    current_level = data.get("currentLevel", {})

    if not question:
        return jsonify({
            "code": 400,
            "msg": "question不能为空"
        })

    extra_context = f"""
当前地图选中的区域信息：
{current_level}

用户问题：
{question}
"""

    try:
        result = rain_agent.invoke({
            "messages": [
                HumanMessage(content=extra_context)
            ]
        })

        answer = result["messages"][-1].content

        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "answer": answer
            }
        })

    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": f"Agent调用失败：{str(e)}"
        })