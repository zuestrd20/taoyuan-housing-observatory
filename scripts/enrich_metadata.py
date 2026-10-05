"""Add source-backed display metadata to independently generated aggregates."""
import json, re
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'data/housing.json'
j=json.loads(p.read_text());m=j['metadata']
parts=re.search(r'登記日期\s*(\d+)年(\d+)月(\d+)日至\s*(\d+)年(\d+)月(\d+)日',m['latestSourcePeriod'])
assert parts, 'Missing verified sale registration period'
a,b,c,d,e,f=map(int,parts.groups())
m['saleRegistrationPeriod']=f'{a+1911:04d}-{b:02d}-{c:02d} 至 {d+1911:04d}-{e:02d}-{f:02d}'
m.update({'checkedAt':m['retrievedAt'],'metricLabel':'集合住宅成交單價中位數','coverageLabel':'2016–2025 · 十年交易日期範圍',
 'coverageNote':f"依交易日期分年，納入 {m['archiveRange']} 已揭露批次（最後登記期間：{m['saleRegistrationPeriod']}）。含完工交屋；後續補登仍可能改變歷年結果。",
 'mapCredit':'區界：內政部國土測繪中心 1140318（2025）版；GeoJSON 公開鏡像轉製。政府資料開放授權條款第 1 版。非地籍或法定界址。'})
m['methodSections']=[
 {'title':'交易年度、資料截止與完整性','paragraphs':[
  '觀察 2016-01-01 至 2025-12-31 的十個完整曆年，以原始「交易年月日」分組，不以登記年或檔案名稱的季別分年。',
  f"已取得 {m['sourceArchiveCount']} 個官方揭露批次（{m['archiveRange']}）；最後一批的登記期間為 {m['saleRegistrationPeriod']}。下載查核日 {m['retrievedAt']}。批次季別不等於曆季。",
  '2026 批次只用來納入較晚登記或完工交屋、但交易日期屬於 2016–2025 的案件。不將 2026 部分年度與全年混比。已取得各觀察年度十二個交易月份的有效樣本，但這不保證所有交易都已揭露；晚登、補登、更正與撤案仍可能改變歷年結果。',
  m['deduplication']], 'links':[{'label':'官方批次資料下載','url':m['sourceUrl']},{'label':'政府資料集與更新資訊','url':m['catalogUrl']}]},
 {'title':'房型範圍與兩種價格單位','paragraphs':[
  m['scope'],
  '集合住宅合併公寓、華廈及住宅大樓的逐筆有效單價，再計算中位數；不是各房型中位數的平均。三個房型也可個別篩選。',
  '透天厝的土地比例差異大，另呈現每件成交總價中位數（萬元／件），不以每坪價格與集合住宅混排。總價涵蓋土地、建物，以及申報總價內的車位。',
  m['unitConversion'],m['sampleCountDefinition'],
  '本站不納入土地、車位單獨交易、店面、辦公室、工廠或用途不明案件；因此不是桃園所有不動產的全市場指標。']},
 {'title':'車位、特殊交易與篩選','paragraphs':[
  m['parking'],
  '有效樣本須為房地或房地加車位買賣，主要用途明確為「住家用」，總價為正且移轉建物面積至少 1 平方公尺；集合住宅另須官方單價為正。',
  '官方公開資料可能已排除部分異常案件；本站另外依備註字詞排除：'+ '、'.join(m['specialRemarkExclusions'])+'。關鍵字篩選無法辨識所有特殊交易，也可能排除部分一般案件。',
  '未申報獨立車位價格及面積的案件，其單價可能仍含車位影響；本版保留官方單價，不自行猜測車位價值。下載 JSON 提供各彙總格的車位分列／未分列筆數。'],
  'links':[{'label':'內政部實價登錄問答與單價說明','url':'https://lvr.land.moi.gov.tw/R11/jsp/qa.jsp'}]},
 {'title':'制度變動與跨年可比性','paragraphs':[
  '2020-07-01 實價登錄申報改由買賣雙方隨移轉登記共同申報；官方統計也記載建物型態分類在該時點調整。舊制獨立套房等分類未納入本版三種集合住宅類型，分類改變可能影響跨年樣本，本站未量化或修正這項影響。',
  '2021-07-01 實價登錄 2.0 擴大預售屋申報、揭露完整門牌。本站只用買賣 A 檔，未將預售 B 檔疊加，因此不能將介面房型篩選當成成屋與預售的完整市場比較。'],
  'links':[{'label':'內政部：實價登錄 2.0 自 2021-07-01 施行','url':'https://www.moi.gov.tw/News_Content.aspx?n=4&s=323736&sms=9009'},{'label':'官方統計分類變動註記（高雄地政局）','url':'https://landp-ws.kcg.gov.tw/Download.ashx?n=TVRFeU5ESXRNRFl0TVRBbE1qZ3hNVEF3TXlVeU9TNXdaR1k9LnBkZg%3D%3D&u=L0ZTMDEvRmlsZVBhdGgvMS9yZWxmaWxlLzk1MS8yMjU1Ny84OTU3OTc0MC1lYTM3LTQ0NjgtOTcyZC0xZjQ4ODFiYTYwNjYucGRm'}]},
 {'title':'小樣本、缺值與比較限制','paragraphs':[
  '零筆顯示缺值，不當成零元；1–4 筆不公開價格；5–29 筆標示小樣本。這是本站呈現規則，不是官方統計標準。折線不跨缺值連接。',
  '年變化使用未經顯示四捨五入的中位數計算；前年缺值時不顯示百分比。',
  *m['limitations'],
  '同區不同年度的屋齡、面積、樓層、區位及新屋交屋占比都可能不同。因此中位數變動不等於同一棟住宅的價格變化，也不表示投資報酬。']},
 {'title':'來源、授權與資料下載','paragraphs':[
  m['attribution'],
  '行政區界：內政部國土測繪中心「鄉鎮市區界線（TWD97 經緯度）」1140318 版。採公開轉製鏡像，下載 SHA-256 已核對；擷取桃園 13 區並計算區內標籤點，未手繪界線。地圖為 2025 年版區界概況，不代表歷年地籍界址。',
  '下載 CSV 提供所有行政區、年度及房型的彙總數據；公開原始碼另含 JSON、批次連結與雜湊清單、重建程式。沒有交易地址、個案編號或交易人資料。'],
  'links':[{'label':'政府資料開放授權條款第 1 版','url':'https://data.gov.tw/license'},{'label':'官方行政區界資料集','url':'https://data.gov.tw/dataset/7441'},{'label':'GeoJSON 轉製鏡像與版本','url':'https://geo.maderaojen.me/'},{'label':'原始碼、資料及重建方法','url':'https://github.com/zuestrd20/taoyuan-housing-observatory'}]}
]
p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
