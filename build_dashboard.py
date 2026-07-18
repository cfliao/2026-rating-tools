#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_dashboard.py
-------------------
讀取 rating.csv（由 rate_courses.py 產生的 LLM 評分結果），輸出：

1. 一個自我包含（single-file）的互動網頁 dashboard.html，涵蓋：
   - A–D 各能力達 3 分以上的課程數與課名
   - 課程總數、任一能力達標、四項皆達標、四項皆為 0 的統計
   - A–D 最低分數篩選 + AND/OR 複合條件查詢
   - 課程名稱、評分理由、主要依據與證據不足處全文搜尋
   - A–D 達標課程數長條圖 / 各能力 0–5 分分布圖
   - 能力組合分析 / 篩選結果自動摘要
   - 課程能力熱度圖 / 可排序的課程資料表
   - 單一課程雷達圖與完整評分明細
   - 最多五門課程的能力比較
   - 響應式版面（電腦、平板、手機）

2. 五個 CSV 檔案：
   - rating_all.csv        全部課程（原始評分結果）
   - rating_A_ge3.csv      能力 A 單項 ≥3 分的課程
   - rating_B_ge3.csv      能力 B 單項 ≥3 分的課程
   - rating_C_ge3.csv      能力 C 單項 ≥3 分的課程
   - rating_D_ge3.csv      能力 D 單項 ≥3 分的課程

使用方式：
    python3 build_dashboard.py --input data/114-0001-rating.csv --outdir out
"""

import argparse
import csv
import json
import os
import re
import sys

# rating.csv 的欄位順序（來自 rate_courses.py 的輸出格式；
# 「課程大綱」為程式事後附加的原始文字，供人工檢核比對）
FIELDS = ["系統序號", "課程名稱", "課程大綱", "A分數", "A判定理由", "B分數", "B判定理由",
          "C分數", "C判定理由", "D分數", "D判定理由",
          "整體判定", "主要依據", "證據不足處"]

TEMPLATE_FILENAME = "dashboard_template.html"
PLACEHOLDER = "__DATA_JSON_PLACEHOLDER__"


def read_rating_csv(path):
    """讀取 rating.csv，容錯處理編碼與欄位順序，回傳 list[dict]。"""
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
        print("[警告] rating.csv 無法以 UTF-8 完整解碼，已容錯處理。", file=sys.stderr)

    reader = csv.DictReader(text.splitlines())
    rows = []
    for row in reader:
        # 過濾掉完全空白的列
        if not any((v or "").strip() for v in row.values()):
            continue
        rows.append(row)
    return rows


def to_int_score(v):
    """把分數欄位轉成 0–5 的整數，異常時回傳 0 並警告。"""
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return 0
    return max(0, min(5, n))


def build_data_list(rows):
    """把 rating.csv 的每一列轉成前端 DATA 陣列所需的物件格式。"""
    data = []
    for i, row in enumerate(rows):
        system_id = (row.get("系統序號") or "").strip()
        course_name = (row.get("課程名稱") or "").strip()
        display_name = f"{course_name}（系統序號：{system_id}）" if system_id else course_name
        data.append({
            "id": i,
            "name": display_name,
            "orig_name": course_name,
            "system_id": system_id,
            "outline": (row.get("課程大綱") or "").strip(),
            "A": to_int_score(row.get("A分數")),
            "B": to_int_score(row.get("B分數")),
            "C": to_int_score(row.get("C分數")),
            "D": to_int_score(row.get("D分數")),
            "Ar": (row.get("A判定理由") or "").strip(),
            "Br": (row.get("B判定理由") or "").strip(),
            "Cr": (row.get("C判定理由") or "").strip(),
            "Dr": (row.get("D判定理由") or "").strip(),
            "overall": (row.get("整體判定") or "").strip(),
            "basis": (row.get("主要依據") or "").strip(),
            "lack": (row.get("證據不足處") or "").strip(),
        })
    return data


def write_filtered_csv(rows, path, ability_col=None, threshold=3):
    """寫出 CSV；若指定 ability_col，僅保留該能力分數 >= threshold 的列。"""
    if ability_col:
        rows = [r for r in rows if to_int_score(r.get(ability_col)) >= threshold]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in FIELDS})
    return len(rows)


def render_dashboard(data, template_path, output_path):
    with open(template_path, encoding="utf-8") as f:
        template = f.read()

    data_json = json.dumps(data, ensure_ascii=False)
    # 避免 JSON 字串中出現 "</script>" 導致 HTML 解析中斷
    data_json = data_json.replace("</", "<\\/")

    if PLACEHOLDER not in template:
        raise RuntimeError(f"樣板檔案中找不到佔位符 {PLACEHOLDER}，請確認 {template_path} 是否正確。")

    html = template.replace(PLACEHOLDER, data_json)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    ap = argparse.ArgumentParser(description="依 rating.csv 產生互動網頁與篩選後的 CSV 檔案")
    ap.add_argument("--input", default="rating.csv", help="rate_courses.py 產生的評分結果 CSV")
    ap.add_argument("--outdir", default=".", help="輸出目錄")
    ap.add_argument("--template", default=None,
                     help="HTML 樣板路徑（預設使用與dashboard_template.html）")
    args = ap.parse_args()

    template_path = args.template or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), TEMPLATE_FILENAME)

    if not os.path.exists(template_path):
        print(f"[錯誤] 找不到樣板檔案：{template_path}", file=sys.stderr)
        sys.exit(1)

    rows = read_rating_csv(args.input)
    if not rows:
        print("[錯誤] rating.csv 沒有任何資料。", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)

    # 五個 CSV 檔案
    n_all = write_filtered_csv(rows, os.path.join(args.outdir, "rating_all.csv"))
    n_a = write_filtered_csv(rows, os.path.join(args.outdir, "rating_A_ge3.csv"), "A分數")
    n_b = write_filtered_csv(rows, os.path.join(args.outdir, "rating_B_ge3.csv"), "B分數")
    n_c = write_filtered_csv(rows, os.path.join(args.outdir, "rating_C_ge3.csv"), "C分數")
    n_d = write_filtered_csv(rows, os.path.join(args.outdir, "rating_D_ge3.csv"), "D分數")

    # 互動網頁
    data = build_data_list(rows)
    dashboard_path = os.path.join(args.outdir, "dashboard.html")
    render_dashboard(data, template_path, dashboard_path)

    print(f"總課程數: {n_all}")
    print(f"A 能力 ≥3 分課程數: {n_a}")
    print(f"B 能力 ≥3 分課程數: {n_b}")
    print(f"C 能力 ≥3 分課程數: {n_c}")
    print(f"D 能力 ≥3 分課程數: {n_d}")
    print(f"已輸出網頁: {dashboard_path}")


if __name__ == "__main__":
    main()
