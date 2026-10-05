"""Extract Taoyuan from a verified, publicly licensed NLSC GeoJSON mirror."""
import json, hashlib, sys
from pathlib import Path
EXPECTED='4ab5da8297a75c3e3fd2cb272642693a91f04299a739897dffc8d7ae029d5196'
p=Path(sys.argv[1]); assert hashlib.sha256(p.read_bytes()).hexdigest()==EXPECTED, 'Unexpected source hash'
j=json.loads(p.read_text()); fs=[f for f in j['features'] if f['properties']['COUNTYNAME']=='桃園市']; assert len(fs)==13
assert {f['properties']['TOWNCODE'] for f in fs}=={f'68000{i:03d}' for i in range(10,131,10)}
def area(r):return sum(p[0]*q[1]-q[0]*p[1] for p,q in zip(r,r[1:]))/2
def inside(p,r):
 x,y=p;c=False
 for (a,b),(d,e) in zip(r,r[1:]):
  if (b>y)!=(e>y) and x<(d-a)*(y-b)/(e-b)+a:c=not c
 return c
def centroid(r):
 a=area(r); x=sum((p[0]+q[0])*(p[0]*q[1]-q[0]*p[1]) for p,q in zip(r,r[1:]))/(6*a); y=sum((p[1]+q[1])*(p[0]*q[1]-q[0]*p[1]) for p,q in zip(r,r[1:]))/(6*a);return [x,y]
for f in fs:
 g=f['geometry']; ps=[g['coordinates']] if g['type']=='Polygon' else g['coordinates']; poly=max(ps,key=lambda p:abs(area(p[0]))); r=poly[0]; c=centroid(r)
 valid=lambda p:inside(p,r) and not any(inside(p,h) for h in poly[1:])
 if not valid(c):
  xs=[p[0] for p in r];ys=[p[1] for p in r]
  candidates=([min(xs)+(max(xs)-min(xs))*i/40,min(ys)+(max(ys)-min(ys))*k/40] for i in range(1,40) for k in range(1,40))
  c=min((p for p in candidates if valid(p)),key=lambda p:(p[0]-c[0])**2+(p[1]-c[1])**2)
 assert valid(c)
 f['properties']['labelPoint']=[round(v,6) for v in c]
 for poly in ps:
  for ring in poly:
   assert ring[0]==ring[-1]
   assert all(120.9<x<121.6 and 24.5<y<25.3 for x,y,*_ in ring)
result={'type':'FeatureCollection','source':'內政部國土測繪中心 鄉鎮市區界線1140318','license':'政府資料開放授權條款第1版','features':fs}
Path('data/taoyuan-districts.geojson').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')))
print('13 districts; exact codes; closed rings; geographic bounds; interior label points verified.')
