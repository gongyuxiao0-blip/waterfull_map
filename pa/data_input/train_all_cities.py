import os
import json
import traceback
from datetime import datetime

from train_city_single import query_all_city_names, train_and_predict

SUMMARY_PATH = "models/city/train_summary.json"


def ensure_parent_dir(path: str):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def main():
    city_list = query_all_city_names()
    total = len(city_list)

    success_list = []
    failed_list = []

    print(f"共检测到 {total} 个城市，开始批量训练...")

    for idx, city_name in enumerate(city_list, start=1):
        print(f"\n[{idx}/{total}] 正在训练：{city_name}")

        try:
            result = train_and_predict(
                target_type="city",
                target_name=city_name,
                show_plot=False,         # 关图，加速
                verbose_eval=False,      # 关详细评估打印，加速
                do_predict_preview=True  # 保留明日预测与雨强概率
            )

            success_list.append(result)
            print(
                f"[成功] {city_name} | "
                f"明日降雨概率={result['next_day_rain_prob']:.4f} | "
                f"明日雨强类别={result['next_day_level_pred']} | "
                f"明日预测降雨量={result['next_day_mm_pred']:.2f} mm"
            )

        except Exception as e:
            failed_list.append({
                "target_type": "city",
                "target_name": city_name,
                "error": str(e),
                "traceback": traceback.format_exc(limit=1)
            })
            print(f"[失败] {city_name} -> {e}")

    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_type": "city",
        "total": total,
        "success_count": len(success_list),
        "failed_count": len(failed_list),
        "success_list": success_list,
        "failed_list": failed_list
    }

    ensure_parent_dir(SUMMARY_PATH)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n===== 批量训练结束 =====")
    print(f"成功: {len(success_list)}")
    print(f"失败: {len(failed_list)}")
    print(f"汇总文件: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()