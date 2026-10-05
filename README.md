# 桃園房價觀察室

以官方實價登錄公開資料，觀察桃園市 13 區的住宅交易價格。繁體中文靜態網站，無追蹤器、無帳號、無外部地圖服務。

## 網站與範圍

- 公開網址：https://zuestrd20.github.io/taoyuan-housing-observatory/
- 2016–2025 交易年；採已登記房地買賣 A 檔，包含完工交屋案件。
- 集合住宅、公寓、華廈、住宅大樓：成交單價中位數（萬元／坪）。
- 透天厝：成交總價中位數（萬元／件），與每坪單價分開呈現。
- 真實 2025 行政區界可點選，另有行政區選單、年度趨勢、比較列表及 CSV 下載。
- URL query 保留年度／房型／行政區；支援鍵盤操作與瀏覽器 Back。

不是品質調整房價指數，不是個別估價或投資建議。原始資料後續補登與更正可能改變過去年份，詳見網站「資料與方法」。缺值不是零；少於 5 筆不顯示價格，5–29 筆標示小樣本。

## 資料與授權

見 [DATA_SOURCES.md](DATA_SOURCES.md)。價格原始來源為內政部地政司，行政區界來自內政部國土測繪中心 1140318 版及其公開轉製鏡像。政府原始資料採政府資料開放授權條款第 1 版；程式採 MIT 授權。

只公開彙總資料與批次來源，不公開地址、個案交易編號、買賣方資訊或原始交易 CSV。

## 本機與檢查

需要 Node.js 22+、Python 3。網站本身沒有執行時依賴。

```sh
npm ci --ignore-scripts
npm test
python3 -m unittest discover -s tests -p 'test_*.py' -v
npm run build
python3 -m http.server 8000 --directory dist
```

- `tests/ui.cjs`：僅在記憶體建立合成測試資料，驗證 13 區、重複選取、鍵盤、缺值、單位、年份、重設、錨點、Back、無效 URL 與載入失敗。測試資料不打包發布。
- `tests/actual-ui.cjs`：逐一檢查 650 個真實資料組合的價格、筆數、單位及選取狀態。
- `tests/data.cjs`：實際彙總格、資料型別、缺值、小樣本、區界與隱私欄位檢查。
- `tests/test_data_pipeline.py`：日期轉換、精確面積換算、數值檢查、中位數、最新批次去重與小樣本測試。

## 重建資料

```sh
python3 scripts/build_housing_data.py --download
python3 scripts/enrich_metadata.py
npm test
```

原始 CSV 暫存於系統暫存目錄，不在網站或 repository 內。重建程式要求觀察所需各批次檔案存在且格式正確；未完整取得時不寫出完整年度成果。網路或上游資料失敗時請先查原因，不以缺檔當作零交易。

彙總包含嚴格「住家用」篩選、明確特殊備註排除、官方編號去重及交易年月日分年。官方單價可能受未拆分車位影響；不得任意猜測車位價格。2020 型態分類、2021 實價登錄制度調整，以及新屋集中交屋，均可能改變成交樣本組成。

地圖重建先下載 DATA_SOURCES.md 指定 GeoJSON 原檔，再執行 `python3 scripts/prepare_map.py <原檔>`；程式校驗來源 SHA-256，擷取 13 區並驗證區內標籤點。

## 獨立統計複核

`data/audit-summary.json` 記錄 43 批來源雜湊、700 個中位數與 1,400 個四分位數的獨立重算結果，並綁定 housing.json 的 SHA-256。`scripts/audit_housing_data.py` 使用另一套 Decimal 計算流程重新讀取原始檔；其輸入仍需具備原始快取，不下載或公開個案資料。

## 部署

GitHub Pages 使用 main 分支根目錄的原生部署。發布前於本機執行統計、資料與互動測試；GitHub 的原生 Pages 建置不會重跑這些自訂測試。網站使用純靜態 HTML、CSS、JavaScript、行政區界與彙總資料，原始碼、重建程式與測試也公開在 repository。研究暫存、原始交易個案與 node_modules 不會發布。
