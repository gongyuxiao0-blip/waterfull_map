const fs = require("fs");
const path = require("path");

const jsonPath = path.join(__dirname, "citys_fixed.json");
const outputSqlPath = path.join(__dirname, "insert_city.sql");
const duplicateReportPath = path.join(__dirname, "duplicate_city.json");

const data = JSON.parse(fs.readFileSync(jsonPath, "utf-8"));

function escapeSql(str) {
  return String(str).replace(/'/g, "''");
}

const seen = new Set();
const duplicates = [];
const values = [];

for (const item of data) {
  const id = Number(item.id);
  const name = String(item.name).trim();
  const province_id = Number(item.province_id);

  if (!id || !name || !province_id) {
    console.log("跳过无效数据:", item);
    continue;
  }

  // 按 name + province_id 去重
  const uniqueKey = `${name}_${province_id}`;

  if (seen.has(uniqueKey)) {
    duplicates.push(item);
    console.log(`发现重复，已跳过: ${uniqueKey}`);
    continue;
  }

  seen.add(uniqueKey);

  values.push(`(${id}, '${escapeSql(name)}', ${province_id})`);
}

// 生成 SQL
const sql = `
START TRANSACTION;

TRUNCATE TABLE city;

INSERT INTO city (id, name, province_id)
VALUES
${values.join(",\n")};

COMMIT;
`;

// 写入文件
fs.writeFileSync(outputSqlPath, sql.trim(), "utf-8");
fs.writeFileSync(duplicateReportPath, JSON.stringify(duplicates, null, 2), "utf-8");

console.log("生成完成:");
console.log("SQL文件:", outputSqlPath);
console.log("重复数据报告:", duplicateReportPath);
console.log("插入条数:", values.length);
console.log("重复跳过条数:", duplicates.length);