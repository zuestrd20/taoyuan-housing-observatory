# 資料來源與授權

查核日：2026-10-05（UTC）。本網站為獨立整理，不代表資料提供機關背書。

## 住宅交易

- 原提供機關：內政部地政司。
- [不動產成交案件實際資訊批次資料](https://plvr.land.moi.gov.tw/DownloadOpenData)
- [政府開放資料目錄](https://data.gov.tw/dataset/77051)
- [官方實價登錄問答](https://lvr.land.moi.gov.tw/R11/jsp/qa.jsp)
- 授權：[政府資料開放授權條款第 1 版](https://data.gov.tw/license)。本站另行篩選及統計，不是官方房價指數。
- 實際下載批次、原始檔 SHA-256、登記期間與連結：`data/source-manifest.json`。
- 僅公開行政區／年度／房型彙總，不公開交易地址、個案編號或交易人資訊。

## 行政區界

- 原提供機關：內政部國土測繪中心。
- [鄉鎮市區界線（TWD97 經緯度）](https://data.gov.tw/dataset/7441)，1140318（2025-03-18）版。
- 下載用[公開 GeoJSON 轉製鏡像](https://geo.maderaojen.me/)，鏡像版本 2026-07-04.1；不是官方代管站。
- [鏡像原始檔](https://geo.maderaojen.me/datasets/tw-townships/releases/v1/2026-07-04.1/data.geojson)
- 原始檔 SHA-256：`4ab5da8297a75c3e3fd2cb272642693a91f04299a739897dffc8d7ae029d5196`，取得後核對一致。
- 授權：[政府資料開放授權條款第 1 版](https://data.gov.tw/license)。
- 本站只擷取桃園市 13 區，保留來源幾何，另計算區內標籤點；顯示時依緯度修正經度比例。
- 圖資呈現 2025 年版本的行政區概況，並非歷年地籍界址。不得作為測量、法定界址或個別物件判定的依據。

## 程式

網站介面及處理程式採 MIT 授權；原始政府資料與轉製資料仍須依上列來源顯名。
