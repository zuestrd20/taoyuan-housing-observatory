#!/usr/bin/env python3
"""Reproduce district-year aggregates from MOI public sale archives.

Raw data is cached outside this project and is never written to public/data.
Uses only the Python standard library. Run --download to fetch missing archives.
Publication fails closed until every required season is present and valid.
"""
import argparse
import collections
import concurrent.futures
import csv
import datetime as dt
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import hashlib
import io
import json
import math
import re
import statistics
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path('/tmp/taoyuan-moi-raw')
YEARS = list(range(2016, 2026))
DISTRICTS = ['桃園區','中壢區','大溪區','楊梅區','蘆竹區','大園區','龜山區','八德區','龍潭區','平鎮區','新屋區','觀音區','復興區']
SEASONS = [f'{y}S{q}' for y in range(105, 116) for q in range(1, 5) if y < 115 or q <= 3]
TYPE_MAP = {'公寓': 'apartment', '華廈': 'midrise', '住宅大樓': 'highrise', '透天厝': 'townhouse'}
TYPES = [
    {'id':'all','label':'集合住宅','unit':'萬元／坪','metricLabel':'成交單價中位數','valueKey':'medianPrice','includes':['apartment','midrise','highrise']},
    {'id':'apartment','label':'公寓','unit':'萬元／坪','metricLabel':'成交單價中位數','valueKey':'medianPrice'},
    {'id':'midrise','label':'華廈','unit':'萬元／坪','metricLabel':'成交單價中位數','valueKey':'medianPrice'},
    {'id':'highrise','label':'住宅大樓','unit':'萬元／坪','metricLabel':'成交單價中位數','valueKey':'medianPrice'},
    {'id':'townhouse','label':'透天厝（總價）','unit':'萬元／件','metricLabel':'成交總價中位數','valueKey':'medianPrice'},
]
# Explicit case-sensitive literal matches, reviewed and published for auditability.
SPECIAL_TERMS = ['親友','員工','共有人','特殊關係','急買','急賣','債權','債務','抵償','地上權','毛胚','合建','部分持分','持分交易']
VALID_TARGETS = {'房地(土地+建物)', '房地(土地+建物)+車位'}
REQUIRED_FIELDS = ['鄉鎮市區','交易標的','交易年月日','建物型態','主要用途','總價元','建物移轉總面積平方公尺',
    '單價元平方公尺','車位移轉總面積平方公尺','車位移轉總面積(平方公尺)','車位總價元','備註','編號']

def url(season, name='h_lvr_land_a.csv'):
    return f'https://plvr.land.moi.gov.tw/DownloadSeason?season={season}&fileName={name}'

def rows_from_bytes(data):
    rows = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
    assert rows and {'鄉鎮市區','交易年月日','編號','單價元平方公尺'}.issubset(rows[0]), 'Invalid MOI CSV schema'
    return [r for r in rows if r['鄉鎮市區'] != 'The villages and towns urban district']

def fetch(season):
    CACHE.mkdir(parents=True, exist_ok=True)
    result = {'season':season}
    for name, suffix in [('h_lvr_land_a.csv','.csv'),('build_time.xml','-build_time.xml')]:
        path = CACHE / (season + suffix)
        if path.exists():
            if name.endswith('.csv'):
                rows_from_bytes(path.read_bytes())
                continue
            try:
                if ET.fromstring(path.read_bytes()).findtext('lvr_time'):
                    continue
            except ET.ParseError:
                pass
            # A normal missing-file HTML response must never be represented as XML.
            if (CACHE/(season+'-period-unavailable.json')).exists():
                continue
        request = urllib.request.Request(url(season,name), headers={'User-Agent':'TaoyuanHousingObservatory/1.0 (public aggregate research)'})
        with urllib.request.urlopen(request, timeout=90) as response:
            data = response.read()
        if name.endswith('.csv'):
            rows_from_bytes(data)
        else:
            try:
                tree=ET.fromstring(data)
                if not tree.findtext('lvr_time'):
                    raise ValueError('No period statement')
            except (ET.ParseError,ValueError):
                (CACHE/(season+'-period-unavailable.json')).write_text(json.dumps({'period':None,'url':url(season,name),'note':'Official period endpoint returned no usable period metadata; no period inferred.'}))
                continue
        path.write_bytes(data)
    result['bytes'] = (CACHE / (season + '.csv')).stat().st_size
    return result

def numeric(row, key):
    try:
        value = float(row.get(key, '') or 0)
        return value if math.isfinite(value) else 0
    except (ValueError, TypeError):
        return 0

def decimal_numeric(row, key):
    """Preserve declared decimal prices without a binary-float round trip."""
    try:
        value = Decimal(row.get(key, '') or '0')
        return value if value.is_finite() else Decimal(0)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(0)

def date_value(value):
    # ROC date is YYYMMDD; older values may have two-digit ROC years.
    if not value.isdigit() or len(value) not in (6,7):
        return None
    try:
        return dt.date(int(value[:-4])+1911, int(value[-4:-2]), int(value[-2:]))
    except ValueError:
        return None

def quantile(values, p):
    ordered = sorted(values)
    pos = Decimal(len(ordered)-1)*Decimal(str(p))
    lo = int(pos)
    hi = min(lo+1,len(ordered)-1)
    return ordered[lo]+(ordered[hi]-ordered[lo])*(pos-lo)

def unit_price_wan_per_ping(ntd_per_sqm):
    return Decimal(str(ntd_per_sqm))*Decimal(400)/Decimal(121)/Decimal(10000)

def retain_latest(latest, row, season):
    identifier = row.get('編號','').strip()
    if not identifier:
        return 'missing'
    old = latest.get(identifier)
    status = 'new' if old is None else 'duplicate' if row == old[0] else 'updated'
    if old is None or season >= old[1]:
        latest[identifier] = (row,season)
    return status

def compact_row(row):
    # The raw-row digest detects corrections without retaining addresses or other
    # unused transaction fields in the aggregation's in-memory working set.
    digest=hashlib.sha256(json.dumps(row,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    compact={key:row.get(key,'') for key in REQUIRED_FIELDS}
    compact['_rawRowDigest']=digest
    for key in ['鄉鎮市區','交易標的','建物型態','主要用途']:
        compact[key]=sys.intern(compact[key])
    return compact

def aggregate_record(district, year, type_id, values, parking_info=None):
    values = [value if isinstance(value, Decimal) else Decimal(str(value)) for value in values]
    n=len(values)
    def rounded(value):
        return float(value.quantize(Decimal('0.0001'),rounding=ROUND_HALF_EVEN))
    return {'district':district,'year':year,'type':type_id,'medianPrice':rounded(statistics.median(values)) if n>=5 else None,
        'count':n,'q25':rounded(quantile(values,.25)) if n>=5 else None,'q75':rounded(quantile(values,.75)) if n>=5 else None,
        'lowSample':0<n<30,'status':'no_data' if n==0 else 'suppressed' if n<5 else 'low_sample' if n<30 else 'ok',
        **dict(parking_info or {})}

def aggregate():
    missing = [s for s in SEASONS if not (CACHE/(s+'.csv')).exists()]
    if missing:
        raise RuntimeError('Refusing complete-year publication; required archives missing: '+', '.join(missing))
    sources, latest, exclusions = [], {}, collections.Counter()
    conflicts = exact_duplicates = 0
    for season in SEASONS:
        path = CACHE/(season+'.csv')
        data = path.read_bytes()
        rows = rows_from_bytes(data)
        period = None
        period_path=CACHE/(season+'-build_time.xml')
        try:
            if period_path.exists(): period=ET.fromstring(period_path.read_bytes()).findtext('lvr_time')
        except ET.ParseError:
            pass
        sources.append({'season':season,'url':url(season),'periodUrl':url(season,'build_time.xml'),'period':period,
            'periodMetadataStatus':'available' if period else 'unavailable',
            'retrievedAt':dt.datetime.fromtimestamp(path.stat().st_mtime,dt.timezone.utc).isoformat(timespec='seconds'),
            'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'rows':len(rows)})
        for row in rows:
            status = retain_latest(latest,compact_row(row),season)
            if status == 'missing':
                exclusions['missing_identifier'] += 1
                continue
            if status == 'duplicate': exact_duplicates += 1
            if status == 'updated': conflicts += 1

    buckets = collections.defaultdict(list)
    city = collections.defaultdict(list)
    diagnostics = collections.Counter()
    parking = collections.defaultdict(collections.Counter)
    monthly = collections.defaultdict(collections.Counter)
    excluded_by_year = collections.defaultdict(collections.Counter)
    for row, season in latest.values():
        date = date_value(row.get('交易年月日',''))
        if not date:
            exclusions['invalid_transaction_date'] += 1
            continue
        if date.year not in YEARS:
            exclusions['outside_2016_2025'] += 1
            continue
        reason = None
        district = row['鄉鎮市區'].strip()
        source_type = row.get('建物型態','').split('(')[0]
        kind = TYPE_MAP.get(source_type)
        if district not in DISTRICTS:
            reason = 'outside_taoyuan_districts'
        elif row.get('交易標的') not in VALID_TARGETS:
            reason = 'not_land_and_building_sale'
        elif not kind:
            reason = 'building_type_outside_scope'
        elif row.get('主要用途','').strip() != '住家用':
            reason = 'not_explicit_residential_use'
        elif any(term in row.get('備註','') for term in SPECIAL_TERMS):
            reason = 'special_transaction_remark'
        elif numeric(row,'總價元') <= 0 or numeric(row,'建物移轉總面積平方公尺') < 1:
            reason = 'invalid_total_price_or_building_area'
        elif kind != 'townhouse' and numeric(row,'單價元平方公尺') <= 0:
            reason = 'invalid_unit_price'
        if reason:
            exclusions[reason] += 1
            excluded_by_year[date.year][reason] += 1
            continue
        value = decimal_numeric(row,'總價元')/Decimal(10000) if kind == 'townhouse' else unit_price_wan_per_ping(decimal_numeric(row,'單價元平方公尺'))
        for type_id in ([kind] if kind == 'townhouse' else ['all',kind]):
            key = (district,date.year,type_id)
            buckets[key].append(value)
            city[(date.year,type_id)].append(value)
            monthly[(date.year,type_id)][date.month] += 1
            if '+車位' in row['交易標的']:
                park_area = numeric(row,'車位移轉總面積平方公尺') or numeric(row,'車位移轉總面積(平方公尺)')
                separated = numeric(row,'車位總價元')>0 and park_area>0
                parking[key]['separatelyDeclaredParkingCount' if separated else 'unseparatedParkingCount'] += 1
            else:
                parking[key]['noParkingCount'] += 1
        diagnostics['eligible_sale_records'] += 1
        if '預售屋' in row.get('備註',''):
            diagnostics['eligible_completed_presale_or_split_registration_remark'] += 1

    records = [aggregate_record(d,y,t['id'],buckets[(d,y,t['id'])],parking[(d,y,t['id'])]) for d in DISTRICTS for y in YEARS for t in TYPES]
    city_records = [aggregate_record('桃園市',y,t['id'],city[(y,t['id'])]) for y in YEARS for t in TYPES]
    for year in YEARS:
        assert set(monthly[(year,'all')]) == set(range(1,13)), f'Eligible city records do not cover all 12 transaction months in {year}'

    assert sources[-1]['period'], 'Latest archive cutoff must be verified, not inferred'
    timestamp=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    metadata={
        'title':'桃園房價觀測站','generatedAt':timestamp,'retrievedAt':timestamp[:10],
        'periodStart':'2016-01-01','periodEnd':'2025-12-31','yearBasis':'交易年月日（民國年轉西元年）',
        'coverage':'2016–2025十個完整曆年交易期間；僅涵蓋已取得批次中已揭露的案件，仍可能後續補登或更正。',
        'archiveRange':'105S1–115S3','latestSourcePeriod':sources[-1]['period'],
        'sourceName':'內政部地政司・不動產成交案件實際資訊批次資料',
        'sourceUrl':'https://plvr.land.moi.gov.tw/DownloadOpenData',
        'catalogUrl':'https://data.gov.tw/dataset/77051','license':'政府資料開放授權條款－第1版','licenseUrl':'https://data.gov.tw/license',
        'metric':'符合篩選條件之逐筆成交單價中位數；透天厝另用成交總價中位數',
        'scope':'主要用途明確為住家用的已登記房地買賣；集合住宅含公寓、華廈、住宅大樓，透天厝分列總價；包括完工交屋案件，不混入預售屋B檔。',
        'parking':'集合住宅沿用官方申報單價。車位價格及面積分列時通常已扣除；未分列時可能含車位。透天總價包含申報總價中的土地、建物及車位。',
        'unitConversion':'單價元平方公尺 × (400 / 121) ÷ 10000 = 萬元／坪；總價元 ÷ 10000 = 萬元／件',
        'sampleCountDefinition':'篩選後的買賣案件筆數，不是土地筆數、建物棟數或車位數的加總。',
        'smallSamples':{'suppressBelow':5,'warnBelow':30,'note':'1–4筆不顯示價格；5–29筆標示小樣本；0筆為無資料。門檻為本站呈現規則，非官方標準。'},
        'specialRemarkExclusions':SPECIAL_TERMS,
        'deduplication':'按官方編號去重；跨批次重複時保留較晚批次內容。相同編號跨期不重複計數。',
        'limitations':['這是成交組成的描述統計，未調整屋齡、樓層、面積或區位，非品質調整房價指數。','主要用途不明（如見其他登記事項）或非住家用者不納入；歷年申報分類差異可能影響樣本組成。','買賣A檔包括完工交屋案件；契約交易年與登記、揭露年可能相隔多年，後續補登可能改變歷年統計。','官方已排除部分異常及特殊案件；本站關鍵字篩選仍無法保證辨識全部特殊交易。','不代表單一物件估價、整區全部住宅行情或投資建議；缺值不補值。'],
        'sourceArchiveCount':len(sources),'sourceRows':sum(s['rows'] for s in sources),'uniqueSourceRows':len(latest),
        'duplicateRows':exact_duplicates,'updatedDuplicateRows':conflicts,'eligibleRecords':diagnostics['eligible_sale_records'],
        'diagnostics':dict(diagnostics),'exclusions':dict(exclusions),
        'attribution':'內政部地政司，2016–2026 不動產成交案件實際資訊批次資料（105S1–115S3）。原始開放資料依政府資料開放授權條款第1版提供；本站自行篩選與統計，不代表官方分析、推薦或背書。',
    }
    payload={'metadata':metadata,'types':TYPES,'years':YEARS,'districts':DISTRICTS,'records':records,'cityRecords':city_records,'sources':sources}
    out=ROOT/'data'
    out.mkdir(parents=True,exist_ok=True)
    (out/'housing.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    with (out/'housing.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['district','year','type','unit','medianPrice','count','q25','q75','lowSample','status']
        writer=csv.DictWriter(f,fields,lineterminator="\n");writer.writeheader()
        units={t['id']:t['unit'] for t in TYPES}
        for r in records: writer.writerow({k:(units[r['type']] if k=='unit' else r.get(k)) for k in fields})
    (out/'source-manifest.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    qa={'generatedAt':timestamp,'records':len(records),'expectedRecords':len(DISTRICTS)*len(YEARS)*len(TYPES),'statusCounts':dict(collections.Counter(r['status'] for r in records)),
        'eligibleMonthlyCounts':{f'{y}-{t}':dict(sorted(counts.items())) for (y,t),counts in monthly.items()},'exclusionsByYear':dict(excluded_by_year),
        'latestYear':{r['district']:{'price':r['medianPrice'],'count':r['count']} for r in records if r['year']==2025 and r['type']=='all'}}
    (ROOT/'research'/'data-quality.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'metadata':metadata,'qa':qa},ensure_ascii=False,indent=2))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--download',action='store_true')
    parser.add_argument('--skip-season',action='append',default=[])
    parser.add_argument('--download-only',action='store_true')
    args=parser.parse_args()
    if args.download:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures={pool.submit(fetch,s):s for s in SEASONS if s not in args.skip_season}
            failed=[]
            for future in concurrent.futures.as_completed(futures):
                season=futures[future]
                try: print(json.dumps(future.result()),flush=True)
                except Exception as exc: failed.append(season);print(f'FAILED {season}: {exc}',file=sys.stderr,flush=True)
            if failed: print('Failed archives: '+','.join(failed),file=sys.stderr);return 1
    if not args.download_only: aggregate()
    return 0

if __name__=='__main__': sys.exit(main())
