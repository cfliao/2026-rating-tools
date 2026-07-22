# -*- coding: utf-8 -*-
"""
rate_courses.py
----------------
讀取課程清單 CSV（預設 output.csv，需含「課程名稱」「課程大綱」欄位）與
評分準則 prompt.txt，將 prompt.txt 的內容作為 system prompt，呼叫使用者
指定的 LLM 後端（可指派任何 API Key／模型／服務端點），依課程分批評分，
並將結果彙整輸出為 rating.csv：

課程名稱,A分數,A判定理由,B分數,B判定理由,C分數,C判定理由,D分數,D判定理由,
整體判定,主要依據,證據不足處

使用方式範例：
    # 使用任何 OpenAI 相容後端（例如自架LLM服務）
    export OPENAI_API_KEY=sk-xxxxxxxx
    python rate_courses.py --model gpt-5.6-luna \\
        --base-url https://api.openai.com/v1 \\
        --input output.csv --prompt prompt.txt --output rating.csv
    
    # example to call local the model: python rate_courses.py --model gpt-oss-120b-mxfp-GUFF --base-url http://192.168.4.89:13305/v1
 
    # 不呼叫任何 API，只印出將送出的請求內容供檢查
    python rate_courses.py --dry-run
"""

import argparse
import csv
import io
import json
import os
import sys
import time
import urllib.request
import urllib.error

# LLM 依 prompt.txt 規則實際輸出的欄位（不含課程大綱，由程式事後附加）
LLM_OUTPUT_FIELDS = ["課程名稱", "A分數", "A判定理由", "B分數", "B判定理由",
                      "C分數", "C判定理由", "D分數", "D判定理由",
                      "整體判定", "主要依據", "證據不足處"]

# rating.csv 最終輸出欄位：加入系統序號，並在課程名稱後插入原始課程大綱供人工檢核
FIELDS = ["系統序號", "課程名稱", "課程大綱", "A分數", "A判定理由", "B分數", "B判定理由",
          "C分數", "C判定理由", "D分數", "D判定理由",
          "整體判定", "主要依據", "證據不足處"]


# --------------------------------------------------------------------------
# 讀檔工具（沿用與 filter_ai_courses.py 相同的自動編碼偵測邏輯）
# --------------------------------------------------------------------------

def detect_and_read(path):
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc), "utf-8"
        except UnicodeDecodeError:
            pass
    for enc in ("cp950", "big5"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    print(f"[警告] 無法完全以標準編碼解析 {path}，將以 cp950 並容忍少量無法辨識的字元。",
          file=sys.stderr)
    return raw.decode("cp950", errors="replace"), "cp950"


def load_system_prompt(path):
    """讀取 prompt.txt，若整段被 ```text ... ``` 圍住則去除圍欄。"""
    text, _ = detect_and_read(path)
    text = text.strip()
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def load_courses(path, id_col, name_col, outline_col):
    text, _ = detect_and_read(path)
    reader = csv.DictReader(text.splitlines())
    if name_col not in reader.fieldnames or outline_col not in reader.fieldnames:
        print(f"[錯誤] {path} 找不到欄位「{name_col}」或「{outline_col}」，"
              f"實際欄位為: {reader.fieldnames}", file=sys.stderr)
        sys.exit(1)
    has_id_col = id_col in (reader.fieldnames or [])
    if not has_id_col:
        print(f"[警告] {path} 找不到欄位「{id_col}」，輸出的「系統序號」將留空。",
              file=sys.stderr)
    courses = []
    for row in reader:
        system_id = ((row.get(id_col) or "").strip() if has_id_col else "")
        name = (row.get(name_col) or "").strip()
        outline = (row.get(outline_col) or "").strip()
        if system_id or name or outline:
            courses.append({"id": system_id, "name": name, "outline": outline})
    return courses

def call_openai(system_prompt, user_content, api_key, model, base_url):
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "seed": 42,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=360) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 400:
            body = e.read().decode("utf-8", errors="replace").strip()
            raise ValueError(f"HTTP 400 Bad Request 回應內容：{body or '(empty response body)'}") from e
        raise
    return data["choices"][0]["message"]["content"]


# --------------------------------------------------------------------------
# 回應解析：從 LLM 的自由文字輸出中擷取符合 12 欄的 CSV 資料列
# --------------------------------------------------------------------------

def extract_csv_rows(text, expected_cols=len(LLM_OUTPUT_FIELDS)):
    rows = []
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if len(row) != expected_cols:
            continue
        if row[0].strip() == LLM_OUTPUT_FIELDS[0]:  # 跳過重複出現的表頭
            continue
        rows.append(row)
    return rows


def build_user_message(batch, include_id=False, batch_size=None):
    parts = ["以下為需要評分的課程，請依照系統指示逐一評分，"
             "並「只」輸出 CSV（含一列表頭，之後每門課一列），不要有其他文字：\n"]
    if batch_size is not None and len(batch) > batch_size:
        parts.append(
            f"注意：本批原設定 batch size 為 {batch_size}，但為避免相同課程名稱被拆到不同批次，"
            f"本批實際包含 {len(batch)} 門課程。請仍逐一對每門課輸出一列 CSV。\n"
        )
    for i, c in enumerate(batch, 1):
        if include_id:
            parts.append(f"【課程 {i}】\n系統序號：{c['id']}\n課程名稱：{c['name']}\n課程大綱：{c['outline']}\n")
        else:
            parts.append(f"【課程 {i}】\n課程名稱：{c['name']}\n課程大綱：{c['outline']}\n")
    return "\n".join(parts)


def attach_outline(rows, batch):
    """把原始「系統序號」與「課程大綱」插回 LLM 回傳的每一列，
    供人工檢核比對評分依據。優先用批次內順序一一對應（最常見且最可靠），
    若回傳列數與送出課程數不符，才退而用課程名稱在批次內比對。"""
    if len(rows) == len(batch):
        return [[course["id"], row[0], course["outline"]] + row[1:]
                for row, course in zip(rows, batch)], True

    used = [False] * len(batch)
    final_rows = []
    for row in rows:
        name = row[0].strip()
        system_id = ""
        outline = ""
        for i, course in enumerate(batch):
            if not used[i] and course["name"].strip() == name:
                system_id = course["id"]
                outline = course["outline"]
                used[i] = True
                break
        final_rows.append([system_id, row[0], outline] + row[1:])
    return final_rows, False


def build_batches(courses, size):
    if size <= 0:
        raise ValueError("batch size 必須大於 0")

    batches = []
    current_batch = []

    grouped_courses = []
    current_group = []
    current_name = None
    for course in courses:
        course_name = course["name"].strip()
        if current_group and course_name != current_name:
            grouped_courses.append(current_group)
            current_group = []
        if not current_group:
            current_name = course_name
        current_group.append(course)

    if current_group:
        grouped_courses.append(current_group)

    for group in grouped_courses:
        if current_batch and len(current_batch) + len(group) > size:
            batches.append(current_batch)
            current_batch = []
        current_batch.extend(group)

    if current_batch:
        batches.append(current_batch)

    return batches


def write_failed_courses(path, courses, id_col, name_col, outline_col):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow([id_col, name_col, outline_col])
        for course in courses:
            writer.writerow([course["id"], course["name"], course["outline"]])


def main():
    ap = argparse.ArgumentParser(description="呼叫 LLM 依 prompt.txt 準則為課程評分，輸出 rating.csv")
    ap.add_argument("--input", default="output.csv", help="課程清單 CSV（需含課程名稱、課程大綱欄位）")
    ap.add_argument("--prompt", default="prompt.txt", help="評分準則 prompt 檔案")
    ap.add_argument("--output", default="rating.csv", help="輸出的評分結果 CSV")
    ap.add_argument("--id-col", default="系統序號")
    ap.add_argument("--name-col", default="課程名稱")
    ap.add_argument("--outline-col", default="課程大綱")
    #ap.add_argument("--provider", choices=["anthropic", "openai"], default="openai", help="LLM 後端介面類型")
    ap.add_argument("--model", default="gpt-5.6-luna",
                     help="模型名稱;預設為openai的gpt-5.6-luna")
    ap.add_argument("--base-url", default=None,
                     help="API 位址; 預設 https://api.openai.com/v1")
    ap.add_argument("--api-key", default=None,
                     help="API key；未提供時讀取環境變數 OPENAI_API_KEY")
    ap.add_argument("--batch-size", type=int, default=6,
                     help="每次請求評分的課程數；能力較弱的模型"
                          "建議調低，例如 1～2，避免長輸出中途規則漂移或格式跑掉")
    #ap.add_argument("--max-tokens", type=int, default=4096, help="每次請求的回應長度上限")
    ap.add_argument("--max-retries", type=int, default=2, help="單一批次失敗時的重試次數")
    ap.add_argument("--sleep", type=float, default=1.0, help="每個批次之間的間隔秒數")
    ap.add_argument("--dry-run", action="store_true",
                     help="不呼叫任何 API，只印出每一批送出的內容供檢查")
    ap.add_argument("--raw-log-dir", default=None,
                     help="若指定目錄，會把每一批的原始請求與回應存成檔案，"
                          "方便檢查模型輸出格式跑掉或評分邏輯跑掉的問題")
    args = ap.parse_args()

    # 目前只提供open ai 相容API
    model = args.model
    if not model:
         print("[錯誤] 必須以 --model 指定模型名稱。", file=sys.stderr)
         sys.exit(1)
 
    base_url = args.base_url or "https://api.openai.com/v1"
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")

    system_prompt = load_system_prompt(args.prompt)
    courses = load_courses(args.input, args.id_col, args.name_col, args.outline_col)
    if not courses:
        print(f"[錯誤] {args.input} 沒有讀到任何課程資料。", file=sys.stderr)
        sys.exit(1)

    total_courses = len(courses)
    batches = build_batches(courses, args.batch_size)

    if args.dry_run:
        dry_run_completed_courses = 0
        print(f"input 總課數：{total_courses}")
        print(f"目前評分完成總課數：0")
        print(f"共 {total_courses} 門課程，將分成 {len(batches)} 批（目標每批 {args.batch_size} 門）。\n")
        print("=== system prompt（前 300 字）===")
        print(system_prompt[:300] + ("..." if len(system_prompt) > 300 else ""))
        print("\n=== 各批 user message ===")
        for bi, batch in enumerate(batches, 1):
            print(f"\n--- 批次 {bi}/{len(batches)}，共 {len(batch)} 門 ---")
            dry_run_completed_courses += len(batch)
            print(f"input 總課數：{total_courses}，分批完成總課數：{dry_run_completed_courses}")
            print(build_user_message(batch, include_id=True, batch_size=args.batch_size))
        return

    if not api_key:
        print("[錯誤] 未提供 API key，請用 --api-key 或設定對應的環境變數。", file=sys.stderr)
        sys.exit(1)

    all_rows = []
    completed_courses = 0
    failed_batches = []
    failed_courses = []

    if args.raw_log_dir:
        os.makedirs(args.raw_log_dir, exist_ok=True)

    #print(f"input 總課數：{total_courses}")
    #print(f"目前評分完成總課數：{completed_courses}")

    for bi, batch in enumerate(batches, 1):
        user_msg = build_user_message(batch, batch_size=args.batch_size)
        last_err = None
        for attempt in range(1, args.max_retries + 1):
            try:
                resp_text = call_openai(
                    system_prompt, user_msg, api_key, model, base_url,
                )
                if args.raw_log_dir:
                    log_path = os.path.join(args.raw_log_dir, f"batch_{bi:03d}_attempt_{attempt}.txt")
                    with open(log_path, "w", encoding="utf-8") as lf:
                        lf.write("=== USER MESSAGE ===\n" + user_msg +
                                 "\n\n=== RAW RESPONSE ===\n" + resp_text)
                rows = extract_csv_rows(resp_text)
                if not rows:
                    raise ValueError("回應中未解析出任何符合欄位數的 CSV 資料列")
                if len(rows) != len(batch):
                    print(f"[批次 {bi}/{len(batches)}] [警告] 送出 {len(batch)} 門課程，"
                          f"但只解析出 {len(rows)} 列——可能有課程的 CSV 格式跑掉被跳過，"
                          f"建議搭配 --raw-log-dir 檢查原始回應。", file=sys.stderr)
                rows, matched_positionally = attach_outline(rows, batch)
                if not matched_positionally:
                    unmatched = sum(1 for r in rows if not r[1])
                    if unmatched:
                        print(f"[批次 {bi}/{len(batches)}] [警告] 有 {unmatched} 列無法比對回"
                              f"原始課程大綱（LLM 回傳的課程名稱與送出的不一致），"
                              f"這幾列的「課程大綱」欄位會留空，請人工比對。", file=sys.stderr)
                all_rows.extend(rows)
                completed_courses += len(rows)
                print(f"[批次 {bi}/{len(batches)}] 成功，取得 {len(rows)} 列"
                      f"（送出 {len(batch)} 門課程）")
                #print(f"目前進度：input 總課數 {total_courses}，評分完成總課數 {completed_courses}")
                break
            except (urllib.error.URLError, ValueError, json.JSONDecodeError, KeyError) as e:
                last_err = e
                wait = 2 ** attempt
                print(f"[批次 {bi}/{len(batches)}] 第 {attempt} 次嘗試失敗："
                      f"{e}，{wait} 秒後重試...", file=sys.stderr)
                time.sleep(wait)
        else:
            print(f"[批次 {bi}/{len(batches)}] 重試 {args.max_retries} 次後仍失敗，"
                  f"跳過此批次。最後錯誤：{last_err}", file=sys.stderr)
            failed_batches.append(bi)
            failed_courses.extend(batch)

        time.sleep(args.sleep)

    with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(FIELDS)
        writer.writerows(all_rows)

    failed_output = os.path.join(os.path.dirname(os.path.abspath(args.output)), "failed.csv")
    write_failed_courses(
        failed_output,
        failed_courses,
        args.id_col,
        args.name_col,
        args.outline_col,
    )

    print(f"\ninput 總課數：{total_courses}")
    print(f"評分完成總課數：{completed_courses}")
    print(f"共 {total_courses} 門課程，成功取得 {len(all_rows)} 列評分結果。")
    if failed_batches:
        print(f"失敗批次：{failed_batches}（共 {sum(len(batches[i-1]) for i in failed_batches)} 門課程未評分），"
              f"請檢查後可單獨重跑這些課程。", file=sys.stderr)
        print(f"失敗課程已輸出至: {failed_output}", file=sys.stderr)
    print(f"已輸出至: {args.output}")


if __name__ == "__main__":
    main()
