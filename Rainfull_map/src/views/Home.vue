<template>
  <div class="home-container">
    <!-- 背景装饰层 -->
    <div class="bg-grid"></div>
    <div class="bg-glow bg-glow-1"></div>
    <div class="bg-glow bg-glow-2"></div>

    <!-- 顶部标题 -->
    <div class="screen-header">
      <div class="header-line left"></div>
      <div class="header-title">
        基于 ECharts 的中国降雨量时空分布可视化系统
      </div>
      <div class="header-line right"></div>
    </div>

    <!-- 主体内容 -->
    <div class="content-area">
      <!-- 左侧 -->
      <div class="left-panel">
        <div class="left-card">
          <!-- 顶部菜单栏 -->
          <div class="tab-menu">
            <div
              class="tab-item"
              :class="{ active: activeTab === 'weather' }"
              @click="activeTab = 'weather'"
            >
              天气信息
            </div>
            <div
              class="tab-item"
              :class="{ active: activeTab === 'predict' }"
              @click="activeTab = 'predict'"
            >
              预测信息
            </div>
            <div
              class="tab-item"
              :class="{ active: activeTab === 'agent' }"
              @click="activeTab = 'agent'"
            >
              预测信息
            </div>
          </div>

          <!-- 内容区域 -->
          <div class="tab-content">
            <WeatherComponents
              v-if="activeTab === 'weather'"
              :currentLevel="currentLevel"
            />

            <PredicterComponents
              v-if="activeTab === 'predict'"
              :currentLevel="currentLevel"
            />

            <AgentChatComponents
              v-if="activeTab === 'agent'"
              :currentLevel="currentLevel"
            />
          </div>
        </div>
      </div>

      <!-- 右侧 -->
      <div class="right-panel">
        <MapComponents
          :currentLevel="currentLevel"
          @update:currentLevel="handleCurrentLevelChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import WeatherComponents from "@/components/weatherComponents.vue";
import PredicterComponents from "@/components/predicterComponents.vue";
import MapComponents from "@/components/mapComponents.vue";
import AgentChatComponents from "@/components/AgentChatComponents.vue";
const currentLevel = ref("china");
const activeTab = ref("weather");

function handleCurrentLevelChange(newLevel) {
  currentLevel.value = newLevel;
}
</script>

<style scoped>
.home-container {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  background:
    radial-gradient(
      circle at 50% 35%,
      rgba(0, 180, 255, 0.18),
      transparent 30%
    ),
    linear-gradient(180deg, #031225 0%, #061a35 45%, #020b18 100%);
  padding: 18px;
  box-sizing: border-box;
  color: #d9f6ff;
}

/* 科技网格背景 */
.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(71, 163, 255, 0.12) 1px, transparent 1px),
    linear-gradient(90deg, rgba(71, 163, 255, 0.12) 1px, transparent 1px),
    radial-gradient(rgba(91, 220, 255, 0.25) 1px, transparent 1px);
  background-size:
    40px 40px,
    40px 40px,
    24px 24px;
  background-position: center center;
  opacity: 0.22;
  pointer-events: none;
}

.bg-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  pointer-events: none;
}

.bg-glow-1 {
  width: 420px;
  height: 420px;
  left: -80px;
  top: 120px;
  background: rgba(0, 183, 255, 0.18);
}

.bg-glow-2 {
  width: 380px;
  height: 380px;
  right: -60px;
  bottom: 40px;
  background: rgba(0, 140, 255, 0.15);
}

/* 顶部标题 */
.screen-header {
  position: relative;
  z-index: 2;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.header-title {
  position: relative;
  padding: 10px 36px;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #dff9ff;
  text-shadow: 0 0 10px rgba(85, 220, 255, 0.65);
  background: linear-gradient(
    90deg,
    rgba(0, 150, 255, 0.18),
    rgba(0, 220, 255, 0.28),
    rgba(0, 150, 255, 0.18)
  );
  border: 1px solid rgba(90, 220, 255, 0.45);
  clip-path: polygon(
    16px 0,
    calc(100% - 16px) 0,
    100% 50%,
    calc(100% - 16px) 100%,
    16px 100%,
    0 50%
  );
  box-shadow:
    0 0 20px rgba(0, 170, 255, 0.18),
    inset 0 0 20px rgba(80, 220, 255, 0.08);
}

.header-line {
  width: 140px;
  height: 2px;
  background: linear-gradient(90deg, transparent, #56dfff, transparent);
  opacity: 0.85;
}

.header-line.left {
  margin-right: 14px;
}

.header-line.right {
  margin-left: 14px;
}

/* 主体布局 */
.content-area {
  position: relative;
  z-index: 2;
  display: flex;
  height: calc(100vh - 98px);
  gap: 18px;
}

.left-panel {
  width: 41%;
  display: flex;
  min-width: 360px;
}

.right-panel {
  flex: 1;
  min-width: 0;
  padding: 12px;
  border-radius: 16px;
  background: rgba(4, 21, 45, 0.68);
  border: 1px solid rgba(84, 211, 255, 0.28);
  box-shadow:
    0 0 0 1px rgba(0, 183, 255, 0.08) inset,
    0 0 22px rgba(0, 140, 255, 0.12),
    inset 0 0 35px rgba(0, 170, 255, 0.05);
  backdrop-filter: blur(10px);
  position: relative;
  overflow: hidden;
}

.right-panel::before,
.left-card::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  background:
    linear-gradient(
      90deg,
      rgba(89, 230, 255, 0.22),
      transparent 18%,
      transparent 82%,
      rgba(89, 230, 255, 0.22)
    ),
    linear-gradient(
      180deg,
      rgba(89, 230, 255, 0.18),
      transparent 20%,
      transparent 80%,
      rgba(89, 230, 255, 0.18)
    );
  opacity: 0.45;
}

/* 左侧整体卡片 */
.left-card {
  position: relative;
  width: 100%;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: rgba(4, 21, 45, 0.68);
  border: 1px solid rgba(84, 211, 255, 0.28);
  box-shadow:
    0 0 0 1px rgba(0, 183, 255, 0.08) inset,
    0 0 22px rgba(0, 140, 255, 0.12),
    inset 0 0 35px rgba(0, 170, 255, 0.05);
  backdrop-filter: blur(10px);
}

/* 顶部菜单栏 */
.tab-menu {
  display: flex;
  background: linear-gradient(
    180deg,
    rgba(7, 34, 68, 0.95) 0%,
    rgba(5, 26, 52, 0.95) 100%
  );
  border-bottom: 1px solid rgba(84, 211, 255, 0.2);
}

.tab-item {
  flex: 1;
  text-align: center;
  padding: 16px 0;
  cursor: pointer;
  font-size: 16px;
  font-weight: 600;
  color: #9fc8dd;
  transition: all 0.3s ease;
  position: relative;
  user-select: none;
}

.tab-item:hover {
  color: #d9f6ff;
  background: rgba(40, 132, 255, 0.12);
}

.tab-item.active {
  color: #ffffff;
  background: linear-gradient(
    180deg,
    rgba(0, 186, 255, 0.22) 0%,
    rgba(0, 133, 255, 0.12) 100%
  );
  text-shadow: 0 0 8px rgba(91, 226, 255, 0.7);
}

.tab-item.active::after {
  content: "";
  position: absolute;
  left: 18%;
  right: 18%;
  bottom: 0;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, transparent, #5ce1ff, transparent);
  box-shadow: 0 0 10px rgba(92, 225, 255, 0.8);
}

/* 内容区域 */
.tab-content {
  flex: 1;
  padding: 12px;
  overflow: auto;
  background: rgba(2, 14, 30, 0.2);
}

/* 滚动条美化 */
.tab-content::-webkit-scrollbar {
  width: 8px;
}

.tab-content::-webkit-scrollbar-track {
  background: rgba(13, 38, 70, 0.35);
  border-radius: 999px;
}

.tab-content::-webkit-scrollbar-thumb {
  background: rgba(80, 200, 255, 0.45);
  border-radius: 999px;
}

.tab-content::-webkit-scrollbar-thumb:hover {
  background: rgba(80, 200, 255, 0.7);
}
</style>
