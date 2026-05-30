<template>
  <div class="agent-panel">
    <div class="chat-box">
      <div
        v-for="(item, index) in messages"
        :key="index"
        :class="['message', item.role]"
      >
        {{ item.content }}
      </div>
    </div>

    <div class="input-area">
      <input
        v-model="question"
        placeholder="例如：分析湖北省未来7天降雨风险"
        @keyup.enter="sendQuestion"
      />
      <button @click="sendQuestion">发送</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import axios from "axios";

const props = defineProps({
  currentLevel: {
    type: Object,
    required: true,
  },
});

const question = ref("");

const messages = ref([
  {
    role: "assistant",
    content: "你好，我可以帮你分析历史降雨、未来预测和降雨风险。",
  },
]);

const sendQuestion = async () => {
  if (!question.value.trim()) return;

  const userQuestion = question.value;

  messages.value.push({
    role: "user",
    content: userQuestion,
  });

  question.value = "";

  try {
    const res = await axios.post("http://127.0.0.1:5000/api/agent/chat", {
      question: userQuestion,
      currentLevel: props.currentLevel,
    });
    console.log(
      "----------------------AI接口返回--------------------------：",
      res.data,
    );

    messages.value.push({
      role: "assistant",
      content: res.data.data.answer,
    });
  } catch (error) {
    console.error("AI分析接口调用失败：", error);

    let msg = "AI分析失败。";

    if (error.response) {
      msg += ` 状态码：${error.response.status}，后端返回：${JSON.stringify(error.response.data)}`;
    } else if (error.request) {
      msg +=
        " 请求已发出，但后端没有响应，请检查 Flask 是否启动或代理是否配置。";
    } else {
      msg += ` 错误信息：${error.message}`;
    }

    messages.value.push({
      role: "assistant",
      content: msg,
    });
  }
};
</script>

<style scoped>
.agent-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  color: #dff8ff;
}

.chat-box {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.message {
  margin-bottom: 10px;
  padding: 10px;
  border-radius: 8px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.message.user {
  background: rgba(0, 180, 255, 0.18);
  text-align: right;
}

.message.assistant {
  background: rgba(0, 255, 220, 0.12);
}

.input-area {
  display: flex;
  gap: 8px;
  padding: 10px;
}

.input-area input {
  flex: 1;
  padding: 8px;
  background: rgba(0, 20, 40, 0.8);
  color: #fff;
  border: 1px solid rgba(0, 200, 255, 0.4);
  outline: none;
}

.input-area button {
  padding: 8px 14px;
  background: rgba(0, 180, 255, 0.8);
  color: white;
  border: none;
  cursor: pointer;
}
</style>
