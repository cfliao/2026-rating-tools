# 文件說明

## 環境設定 (Windows 11)

1. 建立一個專案目錄用來存放本工具，例如C:\rating-tools。
2. 解壓縮 (如`release-win.zip`)到此目錄，會得到類似下面的目錄結構。 (該檔案可在此下傳:  [release.md](release.md))
```text
C:/rating-tools
├─ filter_ai_courses.exe --> AI關鍵字初篩工具
├─ rate_courses.exe      --> AI能力評分工具
├─ build_dashboard.exe   --> 互動網頁產生工具
├─ dashboard_template.html
├─ keyterms.txt
├─ prompt.txt

```

## AI關鍵字初篩

1. 首先，我們要使用「AI關鍵字初篩工具 (filter_ai_courses)」從下傳的課程網資料(xlsx)中，初篩潛在具有AI內涵的課程。
2. 它的輸出入關係如下圖所示，系統在config/keyterms.txt中定義了預設的關鍵字，您可自行編修keyterms.txt的內容調整篩選結果。
3. 只要「課程名稱」或「課程描述」中的內容符合任一關鍵字，就視為通過初篩。
```text
課程網下載資料 (xlsx)        -------┐
                                   ├--> filter_ai_courses.exe --> 通過關鍵字初篩的課程資料 (csv)
config/keyterms.txt (關鍵字列表)----┘
```

4. 執行的指令如下:

```bash
filter_ai_courses.exe --input [輸入xlsx檔名] --terms [關鍵字檔名] --output [輸出csv檔名]
```
例如:
```bash
filter_ai_courses.exe --input 114-0001.xlsx --terms keyterms.txt --output ai-courses.csv
```
若不帶參數，預設使用同目錄的 `input.xlsx`, `keyterms.txt`，並輸出到 `ai-courses.csv`。

5. 功能重點：
- 自動嘗試 UTF-8 與 Big5/CP950 編碼
- 針對純英數關鍵詞（如 AI, ML, LLM）做全字比對，降低誤判
- 可處理 CSV 內含多行文字欄位
- 輸出檔固定為 UTF-8 編碼

## 用 LLM 產生課程評分

```bash
rate_courses.exe --model gpt-5.6-luna --base-url https://api.openai.com/v1 --input ai-courses.csv --prompt prompt.txt --output rating.csv
```
### OpenAI 相容介面範例

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="your_key"
rate_courses.exe --model gpt-5.6-luna --base-url https://api.openai.com/v1 --input ai-courses.csv --prompt prompt.txt --output rating.csv

# Windows Cmd
> set OPENAI_API_KEY="your_key"
rate_courses.exe --model gpt-5.6-luna --base-url https://api.openai.com/v1 --input ai-courses.csv --prompt prompt.txt --output rating.csv

```

補充說明：

- 若相鄰課程的「課程名稱」相同，程式會把它們保留在同一批，即使該批次因此超過 `--batch-size`。
- 程式會另外輸出 `failed.csv`；若有失敗批次，檔內會列出尚未成功評分的課程，若沒有失敗則檔案只包含表頭。

## 產生儀表板

```bash
build_dashboard.exe --input rating.csv --outdir out
```

輸出內容：

- `out/dashboard.html`
- `out/rating_all.csv`
- `out/rating_A_ge3.csv`
- `out/rating_B_ge3.csv`
- `out/rating_C_ge3.csv`
- `out/rating_D_ge3.csv`

`dashboard.html` 為單檔自我包含頁面，可直接用瀏覽器開啟。

## 完整流程

```bash
filter_ai_courses.exe --input input.xlsx --terms keyterms.txt --output ai-courses.csv
rate_courses.exe --model gpt-5.6-luna --base-url https://api.openai.com/v1 --input ai-courses.csv --prompt prompt.txt --output rating.csv
build_dashboard.exe --input rating.csv --outdir out
```



