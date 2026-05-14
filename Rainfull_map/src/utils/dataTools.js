
import chinaJson from "@/assets/geo/China1.json";
import axios from "axios"


//获取省份列表
export const provinces = (chinaJson?.features || []).map(item => {
  // 兜底：如果 name 不存在，返回空字符串或其他默认值
  return item?.properties?.name || '';
}).filter(name => name); // 过滤掉空字符串

//获取省份-城市列表
export async function loadCityMap() {
  let CityMap = {}

  for (const province of provinces) {

    try {

      // 动态加载geojson
      const geo = await import(`@/assets/geo/province/${province}.json`)

      const features = geo.default.features

      // 提取城市名
      const cities = features.map(item => item.properties.name)

      CityMap[province] = cities

    } catch (err) {

      console.error(`${province} 加载失败`, err)

    }

  }

  return CityMap
}
export const province_citys = await loadCityMap()




