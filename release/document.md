# 文件說明

## 概述

本文件提供發佈包的安裝與使用說明。

## 套件內容

- 壓縮檔：`260715.zip`
- 用途：課程篩選、LLM 評分與儀表板產出。

## 快速開始

1. 建立一個專案目錄用來存放本工具，例如C:\rating-tools。
2. 解壓縮 `260715.zip`到此目錄，會得到類似下面的目錄結構。
```text
C:/rating-tools
├─ filter_ai_courses.exe --> AI關鍵字初篩工具
├─ rate_courses.exe      --> AI能力評分工具
├─ build_dashboard.exe   --> 互動網頁產生工具
├─ config/
│  ├─ dashboard_template.html
│  ├─ keyterms.txt
│  └─ prompt.txt

```
3. 上面三個工具的輸出、入關係如下
```text
課程網下載資料 (xlsx) -------┐
                            ├--> filter_ai_courses.exe --> 通過關鍵字初篩的課程資料 (csv)
keyterms.txt (關鍵字列表)----┘
```



