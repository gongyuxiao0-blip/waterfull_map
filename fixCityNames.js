const fs = require("fs");
const path = require("path");

// =========================
// 路径配置
// =========================
const RAW_FILE = path.join(__dirname, "citys.txt");
const GEO_DIR = path.join(__dirname, "citys");
const OUTPUT_FILE = path.join(__dirname, "citys_fixed.json");
const UNMATCHED_FILE = path.join(__dirname, "unmatched.json");
const MULTI_MATCH_FILE = path.join(__dirname, "multi_matched.json");

// 你的 citys.txt 实际上是整个 JSON 数组
const IS_TXT_LINE_JSON = false;

// =========================
// 特殊映射（优先级最高）
// 这里只放那些“简称”和“GeoJSON全名”差距较大的
// =========================
const SPECIAL_MAP = {
  "襄樊": "襄阳市",
  "香格里拉": "迪庆藏族自治州",
  "景洪": "西双版纳傣族自治州",
  "大兴安岭": "大兴安岭地区",
  "神农架": "神农架林区"
};

// =========================
// 工具函数
// =========================
function loadRawCityData(filePath) {
  const content = fs.readFileSync(filePath, "utf-8").trim();

  // 如果文件以 [ 开头，按整个 JSON 数组解析
  if (content.startsWith("[")) {
    return JSON.parse(content);
  }

  // 否则按“每行一个 JSON”解析
  return content
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      try {
        return JSON.parse(line);
      } catch (err) {
        console.error(`第 ${index + 1} 行 JSON 解析失败:`, line);
        throw err;
      }
    });
}

function loadGeoNames(geoDir) {
  return fs.readdirSync(geoDir)
    .filter(file => file.endsWith(".json"))
    .map(file => file.replace(/\.json$/i, ""));
}

// 去掉行政后缀，做模糊比较用
function normalizeName(name) {
  return name
    .replace(/特别行政区$/g, "")
    .replace(/自治州$/g, "")
    .replace(/自治县$/g, "")
    .replace(/自治区$/g, "")
    .replace(/地区$/g, "")
    .replace(/盟$/g, "")
    .replace(/林区$/g, "")
    .replace(/新区$/g, "")
    .replace(/市$/g, "")
    .replace(/区$/g, "")
    .replace(/县$/g, "");
}

// 核心匹配函数
function matchGeoFullName(shortName, geoNames, unmatchedList, multiMatchList) {
  // 1. 特殊映射优先
  if (SPECIAL_MAP[shortName] && geoNames.includes(SPECIAL_MAP[shortName])) {
    return SPECIAL_MAP[shortName];
  }

  // 2. 完全相同
  if (geoNames.includes(shortName)) {
    return shortName;
  }

  // 3. 前缀匹配：宜昌 -> 宜昌市，恩施 -> 恩施土家族苗族自治州
  let matches = geoNames.filter(name => name.startsWith(shortName));
  if (matches.length === 1) {
    return matches[0];
  }
  if (matches.length > 1) {
    multiMatchList.push({
      rawName: shortName,
      matches
    });
    return shortName;
  }

  // 4. 归一化后比较：比如 去掉 市/区/县/自治州 后相同
  const normalizedShort = normalizeName(shortName);
  matches = geoNames.filter(name => normalizeName(name) === normalizedShort);

  if (matches.length === 1) {
    return matches[0];
  }
  if (matches.length > 1) {
    multiMatchList.push({
      rawName: shortName,
      matches
    });
    return shortName;
  }

  // 5. 包含关系再兜底
  matches = geoNames.filter(name =>
    name.includes(shortName) || shortName.includes(normalizeName(name))
  );

  if (matches.length === 1) {
    return matches[0];
  }
  if (matches.length > 1) {
    multiMatchList.push({
      rawName: shortName,
      matches
    });
    return shortName;
  }

  // 6. 仍然找不到
  unmatchedList.push(shortName);
  return shortName;
}

// =========================
// 主流程
// =========================
function main() {
  if (!fs.existsSync(RAW_FILE)) {
    console.error("原始城市文件不存在：", RAW_FILE);
    return;
  }

  if (!fs.existsSync(GEO_DIR)) {
    console.error("GeoJSON目录不存在：", GEO_DIR);
    return;
  }

  const rawCityData = loadRawCityData(RAW_FILE);
  const geoNames = loadGeoNames(GEO_DIR);

  const unmatchedList = [];
  const multiMatchList = [];

  const fixedData = rawCityData.map(item => {
    const fixedName = matchGeoFullName(
      item.name,
      geoNames,
      unmatchedList,
      multiMatchList
    );

    return {
      ...item,
      name: fixedName
    };
  });

  // 去重输出
  const uniqueUnmatched = [...new Set(unmatchedList)].sort((a, b) => a.localeCompare(b, "zh-CN"));

  const uniqueMultiMatched = [];
  const seen = new Set();
  for (const item of multiMatchList) {
    const key = `${item.rawName}__${item.matches.join("|")}`;
    if (!seen.has(key)) {
      seen.add(key);
      uniqueMultiMatched.push(item);
    }
  }

  // 写文件
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(fixedData, null, 2), "utf-8");
  fs.writeFileSync(UNMATCHED_FILE, JSON.stringify(uniqueUnmatched, null, 2), "utf-8");
  fs.writeFileSync(MULTI_MATCH_FILE, JSON.stringify(uniqueMultiMatched, null, 2), "utf-8");

  // 控制台输出统计
  console.log("====================================");
  console.log("处理完成");
  console.log("GeoJSON 城市文件数：", geoNames.length);
  console.log("原始城市数据数：", rawCityData.length);
  console.log("输出文件：", OUTPUT_FILE);
  console.log("未匹配文件：", UNMATCHED_FILE);
  console.log("多匹配文件：", MULTI_MATCH_FILE);
  console.log("未匹配数量：", uniqueUnmatched.length);
  console.log("多匹配数量：", uniqueMultiMatched.length);
  console.log("====================================");

  if (uniqueUnmatched.length > 0) {
    console.log("\n未匹配示例：");
    console.log(uniqueUnmatched.slice(0, 20));
  }

  if (uniqueMultiMatched.length > 0) {
    console.log("\n多匹配示例：");
    console.log(uniqueMultiMatched.slice(0, 10));
  }
}

main();