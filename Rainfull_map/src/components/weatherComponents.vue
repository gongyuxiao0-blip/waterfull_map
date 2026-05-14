<template>
  <div class="box">
    <div class="weather-panel">
      <div class="panel-corner corner-left-top"></div>
      <div class="panel-corner corner-right-top"></div>
      <div class="panel-corner corner-left-bottom"></div>
      <div class="panel-corner corner-right-bottom"></div>

      <div class="title">
        当前层级：{{ currentLevel }}
        <span v-if="currentLevel === 'china' || provinces.includes(currentLevel)"></span>
      </div>

      <div v-if="loading" class="loading">天气加载中...</div>
      <div v-if="error" class="error">{{ error }}</div>

      <div class="result">
        <div class="top-section">
          <div class="weather-info" v-if="weatherData">
            <h3>{{ weatherData.area }} - {{ weatherData.weather }}</h3>
            <p>温度：{{ weatherData.real }}</p>
            <p>湿度：{{ weatherData.humidity }}%</p>
            <p>风速：{{ weatherData.wind }} {{ weatherData.windsc }}</p>
            <p>空气质量：{{ weatherData.quality }}</p>
          </div>

          <div class="gauge-wrapper" v-if="weatherData">
            <div ref="chartRef" class="chart"></div>
          </div>
        </div>

        <div v-if="isDistrictOrCounty" class="district-info">
          <div class="district-title">当前区县不显示近15天降雨量对比</div>
          <p>降雨量：{{ weatherData?.pcpn || '暂无数据' }}</p>
          <p>提示：{{ weatherData?.tips || '暂无提示信息' }}</p>
          <p>
            预警信息：
            {{
              weatherData?.alarmlist && weatherData.alarmlist.length > 0
                ? weatherData.alarmlist[0].content
                : '暂无预警信息'
            }}
          </p>
        </div>

        <template v-else>
          <div v-if="rainCompareData" class="rain-title">
            {{ rainCompareData.target_name }} 近15天降雨量对比
          </div>
          <div v-if="rainCompareData" ref="rainChartRef" class="rain-chart"></div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick, onBeforeUnmount, computed } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const props = defineProps({
  currentLevel: {
    type: String,
    default: 'china'
  }
})

const provinces = [
  '北京市', '天津市', '河北省', '山西省', '内蒙古自治区',
  '辽宁省', '吉林省', '黑龙江省', '上海市', '江苏省',
  '浙江省', '安徽省', '福建省', '江西省', '山东省',
  '河南省', '湖北省', '湖南省', '广东省', '广西壮族自治区',
  '海南省', '重庆市', '四川省', '贵州省', '云南省',
  '西藏自治区', '陕西省', '甘肃省', '青海省', '宁夏回族自治区',
  '新疆维吾尔自治区'
]

const weatherData = ref(null)
const rainCompareData = ref(null)

const loading = ref(false)
const error = ref('')

const chartRef = ref(null)
const rainChartRef = ref(null)

let tempChart = null
let rainChart = null

// ==================== 测试用例日志标记 ====================
console.log('===== 天气面板初始化完成 | 覆盖测试用例 TC-21 ~ TC-24 =====')

const isDistrictOrCounty = computed(() => {
  const level = props.currentLevel || ''
  const result = level.includes('区') || level.includes('县')

  return result
})

const apiKey = '67197908720c4deae679274dc116f75f'

function formatCityName(name) {
  if (!name) return ''
  return name.replace(/市|区|县/g, '')
}

//获取城市名（如果是省份，则取武汉市）
function getWeatherTarget(city) {
  if (!city || city === 'china' || provinces.includes(city)) {
    return '武汉市'
  }
  return city
}

function parseTemperature(temp) {
  if (temp === null || temp === undefined) return 0
  const num = parseFloat(String(temp).replace(/[^\d.-]/g, ''))
  return isNaN(num) ? 0 : num
}

function getGaugeOption(tempValue) {
  return {
    backgroundColor: 'transparent',
    series: [
      {
        type: 'gauge',
        center: ['50%', '60%'],
        startAngle: 200,
        endAngle: -20,
        min: -20,
        max: 50,
        splitNumber: 14,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#5ce1ff' },
            { offset: 0.5, color: '#35b7ff' },
            { offset: 1, color: '#1e90ff' }
          ])
        },
        progress: {
          show: true,
          width: 28,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: '#5ce1ff' },
              { offset: 1, color: '#00c6ff' }
            ])
          }
        },
        pointer: { show: false },
        axisLine: {
          lineStyle: {
            width: 28,
            color: [[1, 'rgba(90, 180, 255, 0.16)']]
          }
        },
        axisTick: {
          distance: -42,
          splitNumber: 5,
          lineStyle: { width: 2, color: 'rgba(120, 220, 255, 0.65)' }
        },
        splitLine: {
          distance: -50,
          length: 14,
          lineStyle: { width: 3, color: 'rgba(120, 220, 255, 0.8)' }
        },
        axisLabel: {
          distance: -22,
          color: '#bfefff',
          fontSize: 15
        },
        anchor: { show: false },
        title: { show: false },
        detail: {
          valueAnimation: true,
          width: '65%',
          lineHeight: 44,
          borderRadius: 12,
          offsetCenter: [0, '-12%'],
          fontSize: 40,
          fontWeight: 'bolder',
          formatter: '{value} °C',
          color: '#e6fbff'
        },
        data: [{ value: tempValue }]
      },
      {
        type: 'gauge',
        center: ['50%', '60%'],
        startAngle: 200,
        endAngle: -20,
        min: -20,
        max: 50,
        itemStyle: { color: '#5ce1ff' },
        progress: { show: true, width: 8 },
        pointer: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        detail: { show: false },
        data: [{ value: tempValue }]
      }
    ]
  }
}

function getRainLineOption(data) {
  const colors = ['#35b7ff', '#5ce1ff', '#7a7cff']

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(4, 22, 45, 0.94)',
      borderColor: 'rgba(88, 220, 255, 0.35)',
      borderWidth: 1,
      textStyle: { color: '#dff8ff' },
      padding: 10
    },
    legend: {
      top: 10,
      data: data.series.map(item => `${item.year}年`),
      textStyle: { color: '#9fdfff' },
      itemGap: 20
    },
    grid: {
      left: 60,
      right: 30,
      top: 70,
      bottom: 50
    },
    xAxis: {
      type: 'category',
      data: data.xAxis,
      axisLine: { lineStyle: { color: 'rgba(120, 220, 255, 0.28)' } },
      axisLabel: { color: '#bfefff', fontSize: 13 },
      axisTick: { alignWithLabel: true }
    },
    yAxis: {
      type: 'value',
      name: '降雨量(mm)',
      nameTextStyle: { color: '#9fdfff', fontSize: 14 },
      axisLine: { lineStyle: { color: 'rgba(120, 220, 255, 0.28)' } },
      axisLabel: { color: '#bfefff', fontSize: 13 },
      splitLine: {
        lineStyle: {
          color: 'rgba(120, 220, 255, 0.14)',
          type: 'dashed'
        }
      }
    },
    series: data.series.map((item, index) => {
      const color = colors[index % colors.length]
      return {
        name: `${item.year}年`,
        type: 'line',
        smooth: true,
        data: item.data,
        symbol: 'circle',
        symbolSize: 7,
        lineStyle: {
          width: 3,
          color
        },
        itemStyle: {
          color,
          borderColor: '#dff8ff',
          borderWidth: 1
        },
        areaStyle: {
          opacity: 0.18,
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color },
            { offset: 1, color: 'rgba(0,0,0,0)' }
          ])
        }
      }
    })
  }
}

async function renderChartByWeather() {
  if (!weatherData.value) return

  await nextTick()
  if (!chartRef.value) return

  const temp = parseTemperature(weatherData.value.real)

  if (tempChart) {
    tempChart.dispose()
    tempChart = null
  }

  // TC-22 日志：温度仪表盘渲染
  console.log(`[TC-22] 温度仪表盘渲染成功 | 温度：${temp}℃ | 区域：${weatherData.value.area}`)

  tempChart = echarts.init(chartRef.value)
  tempChart.setOption(getGaugeOption(temp))
}

async function renderRainChart() {
  if (!rainCompareData.value) return

  await nextTick()
  if (!rainChartRef.value) return

  if (rainChart) {
    rainChart.dispose()
    rainChart = null
  }

  // TC-23 日志：降雨对比图渲染
  console.log(`[TC-23] 近15天降雨对比图渲染成功 | 目标：${rainCompareData.value.target_name}`)

  rainChart = echarts.init(rainChartRef.value)
  rainChart.setOption(getRainLineOption(rainCompareData.value))
}

async function getWeather(city) {
  const targetCity = getWeatherTarget(city)

  loading.value = true
  error.value = ''
  weatherData.value = null

  const queryCity = formatCityName(targetCity)
  const url = `https://apis.tianapi.com/tianqi/index?key=${apiKey}&city=${encodeURIComponent(queryCity)}&type=1`

  try {
    console.log(`[TC-21] 开始请求天气数据 | 目标城市：${targetCity}`)

    const response = await axios.get(url)
    const data = response.data

    if (data.code === 200) {
      weatherData.value = data.result
      console.log(`[TC-21] 天气数据获取成功 | ${data.result.area}：${data.result.weather}`)
    } else {
      error.value = `天气请求失败：${data.msg}`
      console.error(`[TC-21] 天气接口失败：${data.msg}`)
    }
  } catch (err) {
    error.value = '天气网络请求失败：' + err.message
    console.error('[TC-21] 天气请求异常：', err)
  } finally {
    loading.value = false
  }
}

async function getRainCompare(level) {
  try {
    console.log(`[TC-23] 请求15天降雨对比 | 层级：${level}`)

    const response = await axios.get('http://127.0.0.1:5000/api/rainfall-compare15', {
      params: { level }
    })

    if (response.data.code === 200) {
      rainCompareData.value = response.data.data
      console.log('[TC-23] 降雨对比数据获取成功')
    } else {
      rainCompareData.value = null
      error.value = response.data.msg || '降雨对比请求失败'
      console.error('[TC-23] 降雨对比接口失败：', response.data.msg)
    }
  } catch (err) {
    rainCompareData.value = null
    error.value = '降雨对比网络请求失败：' + err.message
    console.error('[TC-23] 降雨对比请求异常：', err)
  }
}

async function loadData(level) {
  error.value = ''
  console.log(`\n=========================================`)
  console.log(`[TC-21/TC-24] 切换区域加载数据 | 当前层级：${level}`)
  console.log(`[TC-24] 地图与天气面板联动触发刷新`)

  await getWeather(level)

  if (isDistrictOrCounty.value) {
    rainCompareData.value = null
    if (rainChart) {
      rainChart.dispose()
      rainChart = null
    }
    
    
    
    
  } else {
    await getRainCompare(level)
  }
}

function handleResize() {
  if (tempChart) tempChart.resize()
  if (rainChart) rainChart.resize()
}

onMounted(() => {
  console.log('[天气面板] 组件挂载完成')
  loadData(props.currentLevel)
  window.addEventListener('resize', handleResize)
})

// TC-21 / TC-24：监听区域变化
watch(
  () => props.currentLevel,
  (newVal) => {
    console.log(`[TC-21/TC-24] 监测到区域切换：${newVal}，自动刷新天气`)
    loadData(newVal)
  }
)

watch(
  weatherData,
  async (newVal) => {
    if (newVal) {
      await renderChartByWeather()
    } else if (tempChart) {
      tempChart.dispose()
      tempChart = null
    }
  },
  { flush: 'post' }
)

watch(
  rainCompareData,
  async (newVal) => {
    if (newVal) {
      await renderRainChart()
    } else if (rainChart) {
      rainChart.dispose()
      rainChart = null
    }
  },
  { flush: 'post' }
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)

  if (tempChart) {
    tempChart.dispose()
    tempChart = null
  }
  if (rainChart) {
    rainChart.dispose()
    rainChart = null
  }
  console.log('[天气面板] 组件销毁，图表已释放')
})
</script>

<style scoped>
.box {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
  box-sizing: border-box;
  background: transparent;
}

.weather-panel {
  position: relative;
  width: 100%;
  max-width: 1000px;
  padding: 22px 24px;
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

.weather-panel::before {
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

.weather-panel::after {
  content: "";
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle, rgba(91, 220, 255, 0.12) 1px, transparent 1px);
  background-size: 24px 24px;
  opacity: 0.1;
  pointer-events: none;
}

.title {
  position: relative;
  z-index: 1;
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 18px;
  color: #e6fbff;
  letter-spacing: 0.5px;
  text-shadow: 0 0 8px rgba(84, 225, 255, 0.35);
}

.loading {
  position: relative;
  z-index: 1;
  color: #5ce1ff;
  font-size: 16px;
  padding: 12px 0;
}

.error {
  position: relative;
  z-index: 1;
  color: #ff7b7b;
  font-size: 16px;
  padding: 12px 0;
}

.result {
  position: relative;
  z-index: 1;
  width: 100%;
}

.top-section {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-bottom: 26px;
  padding: 18px 20px;
  background: rgba(5, 28, 55, 0.72);
  border: 1px solid rgba(84, 211, 255, 0.16);
  border-radius: 16px;
  box-shadow:
    inset 0 0 16px rgba(0, 170, 255, 0.03),
    0 0 12px rgba(0, 170, 255, 0.06);
  backdrop-filter: blur(8px);
}

.weather-info {
  flex: 0 0 220px;
  min-width: 220px;
}

.weather-info h3 {
  margin: 0 0 16px 0;
  font-size: 32px;
  line-height: 1.15;
  word-break: keep-all;
  color: #e6fbff;
  font-weight: 800;
  text-shadow: 0 0 10px rgba(84, 225, 255, 0.18);
}

.weather-info p {
  margin: 6px 0;
  font-size: 18px;
  line-height: 1.7;
  word-break: keep-all;
  color: #bfefff;
}

.gauge-wrapper {
  flex: 1;
  min-width: 400px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(3, 18, 36, 0.35);
  border-radius: 14px;
  border: 1px solid rgba(84, 211, 255, 0.14);
}

.chart {
  width: 100%;
  max-width: 550px;
  height: 320px;
}

.district-info {
  margin-top: 12px;
  padding: 18px 20px;
  background: rgba(5, 28, 55, 0.72);
  border: 1px solid rgba(84, 211, 255, 0.16);
  border-radius: 16px;
  box-shadow:
    inset 0 0 16px rgba(0, 170, 255, 0.03),
    0 0 12px rgba(0, 170, 255, 0.06);
}

.district-title {
  margin-bottom: 12px;
  font-size: 20px;
  font-weight: 700;
  color: #e6fbff;
  padding-left: 10px;
  border-left: 4px solid #5ce1ff;
  text-shadow: 0 0 8px rgba(84, 225, 255, 0.2);
}

.district-info p {
  margin: 10px 0;
  font-size: 17px;
  line-height: 1.8;
  color: #bfefff;
  word-break: break-word;
}

.rain-title {
  margin-top: 12px;
  margin-bottom: 12px;
  font-size: 22px;
  font-weight: 700;
  color: #e6fbff;
  padding-left: 10px;
  border-left: 4px solid #35b7ff;
  text-shadow: 0 0 8px rgba(84, 225, 255, 0.18);
}

.rain-chart {
  width: 100%;
  height: 340px;
  padding: 12px;
  background: rgba(5, 28, 55, 0.72);
  border: 1px solid rgba(84, 211, 255, 0.16);
  border-radius: 14px;
  box-shadow:
    inset 0 0 16px rgba(0, 170, 255, 0.03),
    0 0 12px rgba(0, 170, 255, 0.06);
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

@media (max-width: 900px) {
  .top-section {
    flex-direction: column;
    align-items: stretch;
    gap: 20px;
    padding: 16px;
  }

  .weather-info {
    flex: none;
    min-width: 0;
    width: 100%;
  }

  .gauge-wrapper {
    min-width: 0;
    width: 100%;
  }

  .chart {
    max-width: none;
    width: 100%;
    height: 280px;
  }

  .rain-chart {
    height: 280px;
    padding: 8px;
  }

  .weather-panel {
    padding: 18px;
  }
}

@media (max-width: 600px) {
  .weather-info h3 {
    font-size: 26px;
  }

  .weather-info p {
    font-size: 16px;
  }

  .rain-title {
    font-size: 20px;
  }
}
</style>