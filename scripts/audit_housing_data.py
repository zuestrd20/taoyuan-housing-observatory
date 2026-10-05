"""Independent reverse-cohort, decimal-arithmetic audit. No pipeline imports.

Run after building/enriching the data, using a private raw-data cache:
  python scripts/audit_housing_data.py --raw-dir /path/to/raw-cache

Writes only a compact aggregate audit summary. No raw rows or IDs are published.
"""
import argparse, csv, json, hashlib, collections, datetime, math, decimal, xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--raw-dir',type=Path,required=True,help='Private cache containing 105S1.csv through 115S3.csv and latest period XML')
parser.add_argument('--data',type=Path,default=ROOT/'data/housing.json')
parser.add_argument('--report',type=Path,default=ROOT/'data/audit-summary.json')
args=parser.parse_args()
CACHE=args.raw_dir
document=json.loads(args.data.read_text())
districts=['桃園區','中壢區','大溪區','楊梅區','蘆竹區','大園區','龜山區','八德區','龍潭區','平鎮區','新屋區','觀音區','復興區']
seasons=[f'{y}S{q}' for y in range(105,116) for q in range(1,5) if (y,q)<=(115,3)]
terms=['親友','員工','共有人','特殊關係','急買','急賣','債權','債務','抵償','地上權','毛胚','合建','部分持分','持分交易']
types={'公寓':'apartment','華廈':'midrise','住宅大樓':'highrise','透天厝':'townhouse'}
seen={}; values=collections.defaultdict(list); parked=collections.defaultdict(collections.Counter)
stats=collections.Counter();excluded=collections.Counter();monthly=collections.defaultdict(collections.Counter)
manifest=[]; errors=[];classifications=collections.defaultdict(collections.Counter)
eligible_presale=collections.Counter();eligible_year_counts=collections.Counter()
raw_hashes={s['season']:s for s in document['sources']}

def number(row,key):
    try:
        v=decimal.Decimal(row.get(key,'') or '0')
        return v if v.is_finite() else decimal.Decimal(0)
    except decimal.InvalidOperation:return decimal.Decimal(0)

for season in reversed(seasons):
    path=CACHE/(season+'.csv');blob=path.read_bytes()
    sha=hashlib.sha256(blob).hexdigest();catalog=raw_hashes.get(season,{})
    if sha!=catalog.get('sha256') or len(blob)!=catalog.get('bytes'):errors.append({'season':season,'error':'source bytes/hash mismatch'})
    raw_rows=0;dates=[]
    with path.open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        schema=reader.fieldnames
        for row in reader:
            if row.get('交易年月日')=='transaction year month and day' or row.get('鄉鎮市區')=='The villages and towns urban district':continue
            raw_rows+=1;stats['source_rows']+=1
            identifier=row.get('編號','').strip()
            if not identifier:stats['missing_identifier']+=1;continue
            digest=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if identifier in seen:
                stats['exact_duplicates' if seen[identifier]==digest else 'updated_duplicates']+=1
                continue
            seen[identifier]=digest
            text=row.get('交易年月日','')
            try:
                if not text.isdigit() or len(text) not in (6,7):raise ValueError()
                date=datetime.date(int(text[:-4])+1911,int(text[-4:-2]),int(text[-2:]))
            except ValueError:excluded['invalid_transaction_date']+=1;continue
            dates.append(date.isoformat())
            if not 2016<=date.year<=2025:excluded['outside_2016_2025']+=1;continue
            d=row['鄉鎮市區'].strip();kind=types.get(row['建物型態'].partition('(')[0])
            classifications[date.year][row['建物型態']]+=1
            reason=None
            if d not in districts:reason='outside_taoyuan_districts'
            elif row['交易標的'] not in ['房地(土地+建物)','房地(土地+建物)+車位']:reason='not_land_and_building_sale'
            elif kind is None:reason='building_type_outside_scope'
            elif row['主要用途'].strip()!='住家用':reason='not_explicit_residential_use'
            elif any(t in row.get('備註','') for t in terms):reason='special_transaction_remark'
            elif number(row,'總價元')<=0 or number(row,'建物移轉總面積平方公尺')<1:reason='invalid_total_price_or_building_area'
            elif kind!='townhouse' and number(row,'單價元平方公尺')<=0:reason='invalid_unit_price'
            if reason:excluded[reason]+=1;continue
            stats['eligible_records']+=1;eligible_year_counts[date.year]+=1
            if '預售屋' in row['備註']:eligible_presale[date.year]+=1
            raw=number(row,'總價元' if kind=='townhouse' else '單價元平方公尺')
            for category in [kind] if kind=='townhouse' else [kind,'all']:
                values[(d,date.year,category)].append(raw)
                values[('桃園市',date.year,category)].append(raw)
                monthly[(date.year,category)][date.month]+=1
                key=(d,date.year,category)
                if '+車位' not in row['交易標的']:parked[key]['noParkingCount']+=1
                elif number(row,'車位總價元')>0 and (number(row,'車位移轉總面積平方公尺')>0 or number(row,'車位移轉總面積(平方公尺)')>0):parked[key]['separatelyDeclaredParkingCount']+=1
                else:parked[key]['unseparatedParkingCount']+=1
    if raw_rows!=catalog.get('rows'):errors.append({'season':season,'error':'source row count mismatch','computed':raw_rows,'published':catalog.get('rows')})
    manifest.append({'season':season,'sha256':sha,'rows':raw_rows,'schema':schema,'earliestRetainedTransactionDate':min(dates) if dates else None,'latestRetainedTransactionDate':max(dates) if dates else None})

def expected(seq,kind,quantile=None):
    n=len(seq)
    if n<5:return None
    a=sorted(seq)
    if quantile is None:
        m=a[n//2] if n%2 else (a[n//2-1]+a[n//2])/2
    else:
        rank=decimal.Decimal(n-1)*decimal.Decimal(str(quantile))
        lower=int(rank);fraction=rank-lower
        m=a[lower]*(1-fraction)+a[min(lower+1,n-1)]*fraction
    # Algebraically simplified conversion, applied after the raw-price median.
    v=m/10000 if kind=='townhouse' else m*4/12100
    return float(v.quantize(decimal.Decimal('.0001'),rounding=decimal.ROUND_HALF_EVEN))

for rec in document['records']+document['cityRecords']:
    key=(rec['district'],rec['year'],rec['type']);seq=values[key];n=len(seq);median=expected(seq,rec['type'])
    status='no_data' if n==0 else 'suppressed' if n<5 else 'low_sample' if n<30 else 'ok'
    for field,want in [('count',n),('medianPrice',median),('q25',expected(seq,rec['type'],.25)),('q75',expected(seq,rec['type'],.75)),('status',status),('lowSample',0<n<30)]:
        if rec[field]!=want:errors.append({'key':key,'field':field,'expected':want,'published':rec[field]})
    if rec['district']!='桃園市':
        for field in ['noParkingCount','separatelyDeclaredParkingCount','unseparatedParkingCount']:
            if rec.get(field,0)!=parked[key][field]:errors.append({'key':key,'field':field,'expected':parked[key][field],'published':rec.get(field,0)})

meta=document['metadata']
for key,want in [('sourceRows',stats['source_rows']),('uniqueSourceRows',len(seen)),('duplicateRows',stats['exact_duplicates']),('updatedDuplicateRows',stats['updated_duplicates']),('eligibleRecords',stats['eligible_records'])]:
    if meta.get(key)!=want:errors.append({'field':key,'expected':want,'published':meta.get(key)})
if dict(excluded)!=meta.get('exclusions'):errors.append({'field':'exclusions','expected':dict(excluded),'published':meta.get('exclusions')})
period=ET.fromstring((CACHE/'115S3-build_time.xml').read_bytes()).findtext('lvr_time')
if period!=meta['latestSourcePeriod']:errors.append({'field':'latestSourcePeriod','error':'XML mismatch'})
matrix={(r['district'],r['year'],r['type']) for r in document['records']}
expected_matrix={(d,y,t) for d in districts for y in range(2016,2026) for t in ['all','apartment','midrise','highrise','townhouse']}
if matrix!=expected_matrix or len(document['records'])!=650:errors.append({'error':'District-year-type matrix mismatch'})
report={'passed':not errors,'algorithm':'Independent newest-to-oldest ID selection, streaming CSV, decimal medians before unit conversion; no import of production pipeline.',
    'checkedDistrictCells':len(document['records']),'checkedCityCells':len(document['cityRecords']),'checkedArchives':len(manifest),'counts':dict(stats),'uniqueRecords':len(seen),
    'latestOfficialPeriod':period,'errors':errors,'sourceAudit':manifest,'exclusions':dict(excluded),
    'eligibleByTransactionYear':dict(eligible_year_counts),'eligiblePresaleRemarkByTransactionYear':dict(eligible_presale),
    'buildingClassificationsByTransactionYear':dict(classifications),
    'limitations':['Same declared population and filtering rules as the product were audited; this does not validate the economic representativeness of that population.',
        'Sale-file contracts can precede completed-house registration by years. Recent transaction-year cohorts may gain later handovers and corrections.',
        'Building classification changes and unclear-use exclusions can change historical composition.',
        'Official unit prices can include unseparated parking. Townhouse values are totals and must never share a unit-price comparison scale.',
        'Special-remark keywords are a declared heuristic, not a guarantee that every remaining sale is ordinary.']}
summary={
    'passed':report['passed'],
    'auditedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
    'validatedDataSha256':hashlib.sha256(args.data.read_bytes()).hexdigest(),
    'algorithm':report['algorithm'],
    'checks':{'sourceArchives':len(manifest),'sourceHashesVerified':len(manifest)-sum(e.get('error')=='source bytes/hash mismatch' for e in errors),
        'districtYearTypeCells':len(document['records']),'cityYearTypeCells':len(document['cityRecords']),
        'medianComparisons':len(document['records'])+len(document['cityRecords']),
        'quartileComparisons':2*(len(document['records'])+len(document['cityRecords'])),
        'sampleCountsAndSuppression':True,'parkingCounts':True,'latestCohortXmlMatches':period==meta['latestSourcePeriod']},
    'sourceRows':stats['source_rows'],'uniqueSourceRows':len(seen),'updatedDuplicateRows':stats['updated_duplicates'],
    'eligibleRecords':stats['eligible_records'],'latestOfficialPeriod':period,
    'limitations':report['limitations'],'errors':errors,
}
args.report.parent.mkdir(parents=True,exist_ok=True)
args.report.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
raise SystemExit(0 if not errors else 1)
