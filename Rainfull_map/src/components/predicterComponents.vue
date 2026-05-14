<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from "vue"
import * as echarts from "echarts"
import { provinces, province_citys } from "@/utils/dataTools.js"
import { getRainPredict } from "@/api/predict.js"

const props = defineProps({
  currentLevel: {
    type: String,
    default: "china"
  }
})

const predictLoading = ref(false)
const predictError = ref("")
const predictData = ref(null)

const pieChartRef = ref(null)
let pieChartInstance = null

// ==================== 测试用例日志初始化 ====================
console.log('===== 降雨预测面板初始化 | 覆盖 TC-26 ~ TC-30 =====')

function resolveTargetInfo(levelName) {
  const name = (levelName || "").trim()

  if (!name || name === "china") {
    return {
      supported: true,
      targetType: "city",
      targetName: "武汉市",
      parentProvince: "湖北省"
    }
  }

  if (provinces.includes(name)) {
    return {
      supported: true,
      targetType: "province",
      targetName: name,
      parentProvince: name
    }
  }

  for (const provinceName in province_citys) {
    const cityList = province_citys[provinceName] || []
    if (cityList.includes(name)) {
      return {
        supported: true,
        targetType: "city",
        targetName: name,
        parentProvince: provinceName
      }
    }
  }

  return {
    supported: false,
    targetType: "district",
    targetName: name,
    parentProvince: ""
  }
}

const currentTargetInfo = computed(() => {
  const res = resolveTargetInfo(props.currentLevel)
  if (!res.supported) {
  }
  return res
})

const rainPieData = computed(() => {
  const probs = predictData.value?.tomorrow?.rain_level_probabilities_if_rain
  if (!probs) return []

  return Object.entries(probs).map(([name, value]) => ({
    name,
    value: Number((value * 100).toFixed(2))
  }))
})

function getPieOption() {
  return {
    backgroundColor: "transparent",
    color: ["#35b7ff", "#5ce1ff", "#7a7cff", "#2dd4bf"],
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(4, 22, 45, 0.94)",
      borderColor: "rgba(88, 220, 255, 0.35)",
      borderWidth: 1,
      textStyle: {
        color: "#dff8ff"
      },
      formatter: ({ name, value, percent }) => {
        return `${name}<br/>概率：${value}%<br/>占比：${percent}%`
      }
    },
    legend: {
      top: "5%",
      left: "center",
      textStyle: {
        color: "#bfefff",
        fontSize: 13
      },
      itemWidth: 14,
      itemHeight: 10
    },
    series: [
      {
        name: "雨强概率",
        type: "pie",
        radius: ["42%", "68%"],
        center: ["50%", "58%"],
        avoidLabelOverlap: false,
        padAngle: 3,
        itemStyle: {
          borderRadius: 8,
          borderColor: "rgba(3, 18, 36, 0.95)",
          borderWidth: 2,
          shadowBlur: 12,
          shadowColor: "rgba(53, 183, 255, 0.22)"
        },
        label: {
          show: true,
          color: "#e6fbff",
          formatter: "{b}\n{d}%",
          fontSize: 13
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 18,
            fontWeight: "bold",
            color: "#ffffff"
          },
          itemStyle: {
            shadowBlur: 20,
            shadowColor: "rgba(92, 225, 255, 0.35)"
          }
        },
        labelLine: {
          show: true,
          lineStyle: {
            color: "rgba(150, 230, 255, 0.6)"
          }
        },
        data: rainPieData.value
      }
    ]
  }
}

function renderPieChart() {
  if (!pieChartRef.value || !rainPieData.value.length) return

  if (!pieChartInstance) {
    pieChartInstance = echarts.init(pieChartRef.value)
  }

  pieChartInstance.setOption(getPieOption())
  pieChartInstance.resize()
  
  console.log('[TC-28] 雨强概率饼图渲染成功，预测结果展示正常')
}

function destroyPieChart() {
  if (pieChartInstance) {
    pieChartInstance.dispose()
    pieChartInstance = null
  }
}

async function fetchPredict() {
  const info = currentTargetInfo.value

  predictError.value = ""
  predictData.value = null
  destroyPieChart()

  console.log(`\n=========================================`)
  console.log(`[TC-29] 地图区域联动刷新 | 当前层级：${props.currentLevel}`)

  if (!info.supported) {
    predictError.value = `当前层级“${info.targetName}”属于区县，暂不进行预测`
    return
  }

  if (info.targetType === 'city') {
    console.log(`[TC-26] 城市级降雨预测：${info.targetName}`)
  } else if (info.targetType === 'province') {
    console.log(`[TC-27] 省级降雨预测：${info.targetName}`)
  }

  try {
    predictLoading.value = true

    const res = await getRainPredict(info.targetType, info.targetName, 1)
    const result = res.data

    if (result.code === 200) {
      predictData.value = result.data
      console.log(`[TC-26/TC-27] 预测数据获取成功`)
    } else {
      predictError.value = result.msg || "预测失败"
      console.error(`[TC-30] 预测接口异常：${predictError.value}`)
    }
  } catch (err) {
    predictError.value = err?.response?.data?.msg || err?.message || "预测接口调用失败"
    console.error(`[TC-30] 预测请求异常：`, err)
  } finally {
    predictLoading.value = false
    await nextTick()

    if (!predictError.value && rainPieData.value.length) {
      renderPieChart()
    }
  }
}

watch(
  () => props.currentLevel,
  () => {
    fetchPredict()
  },
  { immediate: true }
)

watch(
  rainPieData,
  async (newVal) => {
    if (!predictLoading.value && newVal.length) {
      await nextTick()
      renderPieChart()
    } else if (!newVal.length) {
      destroyPieChart()
    }
  },
  {
    deep: true,
    flush: "post"
  }
)

function handleResize() {
  pieChartInstance?.resize()
}

window.addEventListener("resize", handleResize)

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize)
  destroyPieChart()
  console.log('[预测面板] 组件已销毁，图表资源释放')
})
</script>

<template>
  <div class="predict-box">
    <div class="panel-corner corner-left-top"></div>
    <div class="panel-corner corner-right-top"></div>
    <div class="panel-corner corner-left-bottom"></div>
    <div class="panel-corner corner-right-bottom"></div>

    <div class="header">
      <div class="level-text">
        当前层级：{{ currentLevel }}
      </div>
      <div class="sub-text">
        识别结果：
        <template v-if="currentTargetInfo.supported">
          {{ currentTargetInfo.targetType }} / {{ currentTargetInfo.targetName }}
        </template>
        <template v-else>
          区县层级，不进行预测
        </template>
      </div>
    </div>

    <div v-if="predictLoading" class="loading">
      正在获取预测结果...
    </div>

    <div v-else-if="predictError" class="error">
      {{ predictError }}
    </div>

    <div v-else-if="predictData && predictData.tomorrow" class="result">
      <div class="card">
        <div class="card-title">明日预测</div>

        <div class="item">
          <span class="label">地区：</span>
          <span>{{ predictData.target_name }}</span>
        </div>
        <div class="item">
          <span class="label">地区类型：</span>
          <span>{{ predictData.target_type }}</span>
        </div>
        <div class="item">
          <span class="label">预测日期：</span>
          <span>{{ predictData.tomorrow.date }}</span>
        </div>
        <div class="item">
          <span class="label">预测降雨量：</span>
          <span>{{ predictData.tomorrow.predicted_rainfall_mm }} mm</span>
        </div>
        <div class="item">
          <span class="label">下雨概率：</span>
          <span>{{ (predictData.tomorrow.rain_probability * 100).toFixed(2) }}%</span>
        </div>
        <div class="item">
          <span class="label">是否下雨：</span>
          <span>{{ predictData.tomorrow.will_rain ? "是" : "否" }}</span>
        </div>
        <div class="item">
          <span class="label">雨强等级：</span>
          <span>{{ predictData.tomorrow.rain_level_name }}</span>
        </div>
      </div>

      <div
        v-if="predictData.tomorrow.rain_level_probabilities_if_rain"
        class="card"
      >
        <div class="card-title">雨强概率可视化</div>

        <div ref="pieChartRef" class="pie-chart"></div>

        <div class="prob-list">
          <div
            v-for="item in rainPieData"
            :key="item.name"
            class="prob-item"
          >
            <span>{{ item.name }}</span>
            <span>{{ item.value.toFixed(2) }}%</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.predict-box {
  position: relative;
  width: 100%;
  min-height: 420px;
  padding: 18px;
  border-radius: 18px;
  background:
    radial-gradient(circle at center, rgba(0, 183, 255, 0.06), transparent 42%),
    linear-gradient(180deg, rgba(4, 20, 43, 0.88) 0%, rgba(2, 12, 28, 0.94) 100%);
  border: 1px solid rgba(84, 211, 255, 0.24);
  box-shadow:
    inset 0 0 28px rgba(0, 170, 255, 0.05),
    0 0 24px rgba(0, 132, 255, 0.12);
  box-sizing: border-box;
  overflow: hidden;
}

.predict-box::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(67, 163, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(67, 163, 255, 0.06) 1px, transparent 1px);
  background-size: 36px 36px;
  opacity: 0.28;
  pointer-events: none;
}

.predict-box::after {
  content: "";
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle, rgba(91, 220, 255, 0.12) 1px, transparent 1px);
  background-size: 24px 24px;
  opacity: 0.1;
  pointer-events: none;
}

.header {
  position: relative;
  z-index: 1;
  margin-bottom: 14px;
}

.level-text {
  font-size: 18px;
  font-weight: 700;
  color: #e6fbff;
  text-shadow: 0 0 8px rgba(84, 225, 255, 0.35);
}

.sub-text {
  margin-top: 6px;
  font-size: 14px;
  color: #9fdfff;
}

.loading {
  position: relative;
  z-index: 1;
  color: #5ce1ff;
  font-size: 15px;
}

.error {
  position: relative;
  z-index: 1;
  color: #ff7b7b;
  font-size: 15px;
}

.result {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.card {
  padding: 16px;
  border-radius: 14px;
  background: rgba(5, 28, 55, 0.72);
  border: 1px solid rgba(84, 211, 255, 0.16);
  box-shadow:
    inset 0 0 16px rgba(0, 170, 255, 0.03),
    0 0 12px rgba(0, 170, 255, 0.06);
  backdrop-filter: blur(8px);
}

.card-title {
  margin-bottom: 12px;
  font-size: 16px;
  font-weight: 700;
  color: #e6fbff;
  text-shadow: 0 0 8px rgba(84, 225, 255, 0.2);
}

.item {
  display: flex;
  align-items: center;
  margin-bottom: 9px;
  font-size: 14px;
  color: #dff8ff;
}

.label {
  width: 100px;
  color: #9fdfff;
}

.pie-chart {
  width: 100%;
  height: 360px;
}

.prob-list {
  margin-top: 10px;
  border-top: 1px solid rgba(120, 220, 255, 0.14);
  padding-top: 10px;
}

.prob-item {
  display: flex;
  justify-content: space-between;
  padding: 7px 0;
  font-size: 14px;
  color: #bfefff;
}

.panel-corner {
  position: absolute;
  width: 18px;
  height: 18px;
  z-index: 2;
  border-color: rgba(98, 229, 255, 0.75);
  pointer-events: none;
}

.corner-left-top {
  top: 8px;
  left: 8px;
  border-top: 2px solid;
  border-left: 2px solid;
}

.corner-right-top {
  top: 8px;
  right: 8px;
  border-top: 2px solid;
  border-right: 2px solid;
}

.corner-left-bottom {
  bottom: 8px;
  left: 8px;
  border-bottom: 2px solid;
  border-left: 2px solid;
}

.corner-right-bottom {
  bottom: 8px;
  right: 8px;
  border-bottom: 2px solid;
  border-right: 2px solid;
}
</style>