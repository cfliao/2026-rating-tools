# -*- coding: utf-8 -*-
"""
filter_ai_courses2.py
----------------------
依據 keyterms.txt 中定義的關鍵詞，從 Excel 檔案（.xls/.xlsx）篩選出
「課程名稱」或「課程大綱」包含任一關鍵詞的課程，並輸出為 UTF-8 CSV。

另外，輸出 CSV 前會將每個欄位內容中的逗號 "," 一律替換為分號 ";"，
避免欄位內容中的逗號造成後續處理混淆。

使用方式:
    python filter_ai_courses.py --input data/114-0001.xlsx --terms keyterms.txt --output data/114-0001-output.csv
"""

import argparse
import csv
import os
import re
import sys


_ASCII_ALNUM_RE = re.compile(r"^[A-Za-z0-9\-]+$")
TARGET_SHEET_NAME = "課程資料"


def detect_and_read(path):
    """讀取文字檔並自動判斷編碼，回傳 (文字內容, 使用的編碼名稱)。"""
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

    print(
        f"[警告] 無法完全以標準編碼解析 {path}，將以 cp950 並容忍少量無法辨識的字元。",
        file=sys.stderr,
    )
    return raw.decode("cp950", errors="replace"), "cp950"


def load_keyterms(path):
    """讀取關鍵詞清單 (以換行分隔)，回傳去除空白與重複的關鍵詞清單。"""
    text, _ = detect_and_read(path)
    terms = []
    seen = set()
    for line in text.splitlines():
        term = line.strip()
        if not term:
            continue
        key = term.lower()
        if key not in seen:
            seen.add(key)
            terms.append(term)
    return terms


def build_matcher(terms):
    """回傳一個函式 match(text) -> bool，判斷 text 是否包含任一關鍵詞。"""
    word_patterns = []
    substr_terms = []

    for t in terms:
        if _ASCII_ALNUM_RE.match(t):
            pattern = re.compile(
                r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])",
                re.IGNORECASE,
            )
            word_patterns.append(pattern)
        else:
            substr_terms.append(t.lower())

    def match(text):
        if not text:
            return False
        low = text.lower()
        if any(term in low for term in substr_terms):
            return True
        return any(p.search(text) for p in word_patterns)

    return match


def resolve_input_path(path):
    """若輸入 .xls 不存在但同名 .xlsx 存在，則自動回退使用 .xlsx。"""
    if os.path.exists(path):
        return path

    root, ext = os.path.splitext(path)
    if ext.lower() == ".xls":
        alt = root + ".xlsx"
        if os.path.exists(alt):
            print(f"[提示] 找不到 {path}，改用 {alt}", file=sys.stderr)
            return alt

    return path


def read_excel_rows(input_path):
    """讀取 Excel，回傳 (header, data_rows)。"""
    try:
        import pandas as pd
    except ImportError:
        print("[錯誤] 缺少 pandas，請先安裝：uv add pandas openpyxl xlrd", file=sys.stderr)
        sys.exit(1)

    try:
        df = pd.read_excel(input_path, sheet_name=TARGET_SHEET_NAME, dtype=str)
    except ValueError:
        print(
            f"[警告] 找不到工作表「{TARGET_SHEET_NAME}」，改讀取第一張工作表。",
            file=sys.stderr,
        )
        df = pd.read_excel(input_path, dtype=str)
    except ImportError as e:
        print(
            "[錯誤] 缺少 Excel 解析引擎，請安裝：uv add openpyxl xlrd",
            file=sys.stderr,
        )
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[錯誤] 讀取 Excel 失敗: {e}", file=sys.stderr)
        sys.exit(1)

    df = df.fillna("")
    header = [str(col) for col in df.columns]
    data_rows = [[str(v) for v in row] for row in df.values.tolist()]
    return header, data_rows


def replace_comma_with_semicolon(value):
    """將欄位值中的逗號替換為分號。"""
    return (value or "").replace(",", ";")


def main():
    ap = argparse.ArgumentParser(description="依關鍵詞篩選 Excel 課程清單並輸出 CSV")
    ap.add_argument("--input", default="input.xls", help="輸入課程 Excel 檔案 (.xls/.xlsx)")
    ap.add_argument("--terms", default="keyterms.txt", help="關鍵詞清單檔案")
    ap.add_argument("--output", default="ai-courses.csv", help="輸出的 CSV 檔案")
    args = ap.parse_args()

    input_path = resolve_input_path(args.input)
    keyterms_path = args.terms

    if not os.path.exists(input_path):
        print(f"[錯誤] 找不到輸入檔案: {input_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(keyterms_path):
        print(f"[錯誤] 找不到關鍵詞檔案: {keyterms_path}", file=sys.stderr)
        sys.exit(1)

    #default_output = re.sub(r"\.(xls|xlsx)$", "-ai-courses.csv", input_path, flags=re.IGNORECASE)
    #output_path = args.output or default_output
    output_path = args.output 

    terms = load_keyterms(keyterms_path)
    if not terms:
        print("[錯誤] 關鍵詞清單為空，請確認 keyterms.txt 內容。", file=sys.stderr)
        sys.exit(1)

    matcher = build_matcher(terms)
    header, data_rows = read_excel_rows(input_path)

    try:
        name_idx = header.index("課程名稱")
    except ValueError:
        name_idx = 0
    try:
        outline_idx = header.index("課程大綱")
    except ValueError:
        outline_idx = 1

    matched_rows = []
    for row in data_rows:
        name = row[name_idx] if name_idx < len(row) else ""
        outline = row[outline_idx] if outline_idx < len(row) else ""
        if matcher(name) or matcher(outline):
            matched_rows.append([replace_comma_with_semicolon(cell) for cell in row])

    safe_header = [replace_comma_with_semicolon(cell) for cell in header]

    with open(output_path, "w", encoding="utf-8", newline="", errors="replace") as f:
        writer = csv.writer(f)
        writer.writerow(safe_header)
        writer.writerows(matched_rows)

    print("讀取格式: Excel (.xls/.xlsx)")
    print("輸出編碼: utf-8")
    print("欄位逗號處理: 已將欄位內容中的 ',' 替換為 ';'")
    print(f"關鍵詞數量: {len(terms)}")
    print(f"原始課程數: {len(data_rows)}")
    print(f"篩選出 AI 相關課程數: {len(matched_rows)}")
    print(f"已輸出至: {output_path}")


if __name__ == "__main__":
    main()
