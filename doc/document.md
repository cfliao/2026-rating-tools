# 文件說明

## 環境設定 (Windows 11)

1. 建立一個專案目錄用來存放本工具，例如C:\rating-tools。
2. 解壓縮 (如`release-win.zip`)到此目錄，會得到類似下面的目錄結構。 (該檔案可在此下傳:  [release.md](../release/release.md))
```text
C:/rating-tools
├─ filter_ai_courses.exe --> AI關鍵字初篩工具
├─ rate_courses.exe      --> AI能力評分工具
├─ build_dashboard.exe   --> 互動網頁產生工具
├─ dashboard_template.html
├─ keyterms.txt
├─ prompt.txt

```

## AI關鍵字初篩 (filter_ai_courses)

1. 首先，我們要使用「AI關鍵字初篩工具 (filter_ai_courses)」從下傳的課程網資料(xlsx)中，初篩潛在具有AI內涵的課程。
2. 它的輸出入關係如下圖所示，系統在config/keyterms.txt中定義了預設的關鍵字，您可自行編修keyterms.txt的內容調整篩選結果。
3. 只要「課程名稱」或「課程描述」中的內容符合任一關鍵字，就視為通過初篩。
```text
課程網下載資料 (xlsx)        -------┐
                                   ├--> filter_ai_courses.exe --> 通過關鍵字初篩的課程資料 (csv)
config/keyterms.txt (關鍵字列表)----┘
```

4. filter_ai_courses指令說明如下:

```bash
usage: filter_ai_courses [-h] [--input INPUT] [--terms TERMS] [--output OUTPUT]

依關鍵詞篩選 Excel 課程清單並輸出 CSV

options:
  -h, --help       show this help message and exit
  --input INPUT    輸入課程 Excel 檔案 (.xls/.xlsx)
  --terms TERMS    關鍵詞清單檔案
  --output OUTPUT  輸出的 CSV 檔案
```
例如:
```bash
filter_ai_courses --input 114-0001.xlsx --terms keyterms.txt --output ai-courses.csv
```
若不帶參數，預設使用同目錄的 `input.xlsx`, `keyterms.txt`，並輸出到 `ai-courses.csv`。執行成功後可看到類似下面的結果:

```bash
c:\rating-tools>filter_ai_courses --input 114-0001.xlsx

讀取格式: Excel (.xls/.xlsx)
輸出編碼: utf-8
欄位逗號處理: 已將欄位內容中的 ',' 替換為 ';'
關鍵詞數量: 62
原始課程數: 5356
篩選出 AI 相關課程數: 416
已輸出至: ai-courses.csv
```
功能重點：
- 自動嘗試 UTF-8 與 Big5/CP950 編碼
- 針對純英數關鍵詞（如 AI, ML, LLM）做全字比對，降低誤判
- 可處理 CSV 內含多行文字欄位
- 輸出檔固定為CSV/UTF-8 編碼

## 用 LLM 產生課程評分 (rate_courses)

接下來要利用LLM為前面所產出的課程列表一門一門地評皆。首先要先決定要使用的LLM，目前本程式相容於Open AI API，可以使用Open AI API或落地模型(大部份model serving framework都可提供Open AI相容的API)。

1. 這裡以使用Open AI API為例，首先要到 https://openai.com/zh-Hant/api/ 申請帳戶，並付費購買點數，之後可透過網站內的操作介面新增並取得API Key (這個key只會顯示一次，必須妥善保存，不可公開)

2. 取得key之後首先要透過命令列介面設定好環境變數

```bash
c:\rating-tools>set OPENAI_API_KEY=...(您的API key)
```
3. 接下來就可以使用rate_courses進行評分，其指令格式如下:

```bash
usage: rate_courses [-h] [--input INPUT] [--prompt PROMPT] [--output OUTPUT]  [--model MODEL] [--base-url BASE_URL] [--api-key API_KEY] [--batch-size BATCH_SIZE] [--max-retries MAX_RETRIES] [--dry-run][--raw-log-dir RAW_LOG_DIR]

呼叫 LLM 依 prompt.txt 準則為課程評分，輸出 rating.csv

options:
  -h, --help            show this help message and exit
  --input INPUT         課程清單 CSV（需含課程名稱、課程大綱欄位）
  --prompt PROMPT       評分準則 prompt 檔案
  --output OUTPUT       輸出的評分結果 CSV
  --model MODEL         模型名稱;預設為openai的gpt-5.6-luna
  --base-url BASE_URL   API 位址; 預設 https://api.openai.com/v1
  --api-key API_KEY     API key；未提供時讀取環境變數 OPENAI_API_KEY
  --batch-size BATCH_SIZE 每次請求評分的課程數的建議值；能力較弱的模型建議調低，例如 1～2，避免長輸出中途規則漂移或格式跑掉，實務上不一定會是此值，因為系統必須保持同一個課程具有相同分數，所以同課程必須同一批次
  --max-retries MAX_RETRIES 單一批次失敗時的重試次數
  --dry-run             不呼叫任何API，只印出每一批送出的內容供檢查
  --raw-log-dir RAW_LOG_DIR 若指定目錄，會把每一批的原始請求與回應存成檔案，方便檢查模型輸出格式跑掉或評分邏輯跑掉的問題
```
4. 以下為一個參考執行範例，使用OPEN AI API

```bash
rate_courses --model gpt-5.6-luna --base-url https://api.openai.com/v1 --input ai-courses.csv --prompt prompt.txt --output rating.csv
```
補充說明:
- 若相鄰課程的「課程名稱」相同，程式會把它們保留在同一批，即使該批次因此超過 `--batch-size`。
- 程式會另外輸出 `failed.csv`；若有失敗批次，檔內會列出尚未成功評分的課程，若沒有失敗則檔案只包含表頭。
- 建議明確設定--raw-log-dir，以利錯誤時檢視原始資料除錯。

## 產生儀表板網頁
上步驟完成後會產生一個評分結果(預設為rating.csv)，它可供進一步資料處理。為了方便檢視結果，可以用build_dashboard 來基於評分結果的csv檔產生一個儀表板網頁，指令如下:
```bash
usage: build_dashboard [-h] [--input INPUT] [--outdir OUTDIR] [--template TEMPLATE]

依 rating.csv 產生互動網頁

options:
  -h, --help           show this help message and exit
  --input INPUT        rate_courses.py 產生的評分結果 CSV
  --outdir OUTDIR      輸出目錄
  --template TEMPLATE  HTML 樣板路徑（預設使用與dashboard_template.html）
```
例如:
```bash
build_dashboard.exe --input rating.csv --template dashboard_template.html --outdir out
```
它會在out目錄輸出 `dashboard.html`，它是一個自我包含的網頁，可直接用瀏覽器開啟。

## 完整流程回顧

```bash
filter_ai_courses --input input.xlsx --terms keyterms.txt --output ai-courses.csv
rate_courses --model gpt-5.6-luna --base-url https://api.openai.com/v1 --input ai-courses.csv --prompt prompt.txt --output rating.csv
build_dashboard --input rating.csv --outdir out
```



